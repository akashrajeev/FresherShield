"""FresherShield web app: FastAPI backend + a single-page UI in app/static."""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .jobs import Job, search_jobs  # noqa: E402
from .resume import extract_skills, match, pdf_to_text  # noqa: E402
from .i18n import LANGS, norm_lang, share_text, translate_report  # noqa: E402
from .scam import assess, estimate_searches  # noqa: E402
from .serp import OfflineMiss, SerpClient, SerpError  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="FresherShield", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

client = SerpClient()
_jobs: dict[str, Job] = {}  # job_id -> Job from the latest searches (for scam checks)
_resume: dict[str, str] = {"text": ""}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {"serpapi_key": bool(client.api_key), "offline": client.offline, "stats": client.stats(), "account": client.account()}


@app.post("/api/resume")
async def upload_resume(file: UploadFile | None = File(None), text: str = Form("")) -> dict:
    body = text
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > 5_000_000:
            raise HTTPException(413, "Resume must be under 5 MB")
        if file.filename.lower().endswith(".pdf"):
            try:
                body = pdf_to_text(data)
            except Exception as exc:
                raise HTTPException(400, f"Could not read that PDF: {exc}")
        else:
            body = data.decode("utf-8", errors="ignore")
    if not body.strip():
        raise HTTPException(400, "Upload a PDF/TXT resume or paste its text")
    _resume["text"] = body  # kept in memory only; never written to disk
    return {"skills": sorted(extract_skills(body)), "chars": len(body)}


@app.get("/api/jobs")
def jobs(role: str, location: str = "India", pages: int = 1) -> dict:
    pages = max(1, min(pages, 3))
    try:
        res = search_jobs(client, role, location, pages)
    except OfflineMiss as e:
        raise HTTPException(409, str(e))
    except SerpError as e:
        raise HTTPException(502, str(e))
    out = []
    for j in res["jobs"]:
        _jobs[j.job_id] = j
        d = j.to_dict()
        d["match"] = match(_resume["text"], j.full_text()) if _resume["text"] else None
        d["quick_flags"] = _quick_flags(j)
        out.append(d)
    return {"query": res["query"], "location": res["location"], "filters": res["filters"], "jobs": out, "stats": client.stats()}


def _quick_flags(job: Job) -> list[str]:
    from .scam import posting_signals

    return [s.label for s in posting_signals(job) if s.weight >= 10]


class CheckReq(BaseModel):
    job_id: str | None = None
    company: str | None = None
    offer_text: str | None = None  # paste a WhatsApp/email offer to check it
    use_web: bool = True
    lang: str = "en"  # en | hi | ml: language of the verdict, headline and signal labels


def _localized(rep, lang: str) -> dict:
    d = translate_report(rep.to_dict(), lang)
    d["share_text"] = share_text(d)
    return d


@app.get("/api/langs")
def langs() -> dict:
    return {"langs": LANGS}


@app.post("/api/check")
def check(req: CheckReq) -> dict:
    job = _jobs.get(req.job_id or "")
    if job is None and req.offer_text:
        job = Job("pasted", "", req.company or "", "", "", req.offer_text)
    company = req.company or (job.company if job else "")
    if not company and not job:
        raise HTTPException(400, "Give a job_id from a search or a company name")
    rep = assess(client, job, company, use_web=req.use_web)
    return {"report": _localized(rep, norm_lang(req.lang)), "stats": client.stats()}


COMPANY_HINT = re.compile(
    r"\b([A-Z][A-Za-z0-9&.\-]*(?: [A-Z][A-Za-z0-9&.\-]*){0,5} (?:Private Limited|Pvt\.? Ltd\.?|Limited|Ltd\.?|LLP))(?![A-Za-z])")


def guess_company(text: str) -> str:
    """Best guess at the company an offer letter claims to be from: the most frequent 'X Pvt Ltd'-style name."""
    names = [m.group(1).strip() for m in COMPANY_HINT.finditer(text)]
    names = [n for n in names if not n.lower().startswith(("dear", "congratulations", "the ", "we ", "this "))]
    if not names:
        return ""
    return max(set(names), key=lambda n: (names.count(n), -len(n)))


@app.post("/api/check-file")
async def check_file(file: UploadFile = File(...), company: str = Form(""), lang: str = Form("en")) -> dict:
    """Check an offer letter PDF (or .txt): extract the text, guess the company if not given, run the same report."""
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "File must be under 5 MB")
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        try:
            text = pdf_to_text(data)
        except Exception as exc:
            raise HTTPException(400, f"Could not read that PDF: {exc}")
    else:
        text = data.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(400, "No text found in the file. If it is a scanned image, paste the text instead.")
    company = company.strip() or guess_company(text)
    job = Job("pasted", "", company, "", "", text)
    rep = assess(client, job, company, use_web=bool(company))
    return {"report": _localized(rep, norm_lang(lang)), "company_guess": company, "chars": len(text), "stats": client.stats()}


BATCH_MAX = 10


class BatchReq(BaseModel):
    job_ids: list[str]
    lang: str = "en"
    dry_run: bool = False  # only estimate the SerpApi searches the batch would spend


@app.post("/api/check-batch")
def check_batch(req: BatchReq) -> dict:
    """Check several listings at once. Companies are de-duplicated so each costs credits once."""
    jobs = [j for j in (_jobs.get(i) for i in req.job_ids[:BATCH_MAX]) if j]
    companies = sorted({j.company for j in jobs if j.company})
    if req.dry_run:
        est = estimate_searches(client, companies)
        acct = client.account() if not client.offline else None
        left = (acct or {}).get("total_searches_left")
        return {"jobs": len(jobs), **est, "credits_left": left, "offline": client.offline,
                "affordable": est["searches"] == 0 if client.offline else (left is None or left >= est["searches"])}
    # Warm the cache once per unique company so parallel checks never pay twice.
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda c: assess(client, None, c), companies))
    reports = [assess(client, j, j.company) for j in jobs]
    lang = norm_lang(req.lang)
    return {"reports": {j.job_id: _localized(r, lang) for j, r in zip(jobs, reports)}, "stats": client.stats()}


@app.exception_handler(SerpError)
def serp_error(_, exc: SerpError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=502)


def run() -> None:  # `python -m app.main`
    import uvicorn

    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    run()
