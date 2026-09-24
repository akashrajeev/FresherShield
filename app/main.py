"""FresherShield web app: FastAPI backend + a single-page UI in app/static."""
from __future__ import annotations

import os
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
from .scam import assess  # noqa: E402
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


@app.post("/api/check")
def check(req: CheckReq) -> dict:
    job = _jobs.get(req.job_id or "")
    if job is None and req.offer_text:
        job = Job("pasted", "Pasted offer", req.company or "", "", "", req.offer_text)
    company = req.company or (job.company if job else "")
    if not company and not job:
        raise HTTPException(400, "Give a job_id from a search or a company name")
    rep = assess(client, job, company, use_web=req.use_web)
    return {"report": rep.to_dict(), "stats": client.stats()}


class BatchReq(BaseModel):
    job_ids: list[str]


@app.post("/api/check-batch")
def check_batch(req: BatchReq) -> dict:
    """Check several listings at once. Companies are de-duplicated so each costs credits once."""
    jobs = [j for j in (_jobs.get(i) for i in req.job_ids[:10]) if j]
    # Warm the cache once per unique company so parallel checks never pay twice.
    companies = sorted({j.company for j in jobs if j.company})
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda c: assess(client, None, c), companies))
    reports = [assess(client, j, j.company) for j in jobs]
    return {"reports": {j.job_id: r.to_dict() for j, r in zip(jobs, reports)}, "stats": client.stats()}


@app.exception_handler(SerpError)
def serp_error(_, exc: SerpError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=502)


def run() -> None:  # `python -m app.main`
    import uvicorn

    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    run()
