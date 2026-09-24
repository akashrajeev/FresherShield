"""Scam-posting risk check for a job + company.

Two layers:
1. Posting signals (free): red-flag language in the Google Jobs posting itself and
   where it can be applied to.
2. Web footprint (SerpApi): what Google and Bing return when you search the company
   name next to scam/fraud/complaint words, plus whether the company has a real
   legitimacy footprint (Knowledge Graph, employee reviews, an official website).

The output is a risk level with every signal and its evidence link. It is a triage
aid, not a verdict. See docs/METHODOLOGY.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

from .jobs import Job, board_for, domain_of
from .serp import SerpClient, SerpError

SCAM_WORDS = re.compile(r"\b(scam|scammers?|fraud|fraudulent|fake|cheat(?:ed|ing)?|complaints?|beware|warning|money (?:not )?refund|looted|extort)", re.I)
IMPERSONATION = re.compile(r"(fake (?:offer|job|appointment) letters?|in the name of|impersonat|pretending to be|posing as|fraudulent (?:job )?offers?|recruitment fraud|beware of fake|fraud alert|fake recruit)", re.I)
COMPLAINT_SITES = {
    "consumercomplaints.in": "ConsumerComplaints.in", "voxya.com": "Voxya", "mouthshut.com": "MouthShut",
    "trustpilot.com": "Trustpilot", "reddit.com": "Reddit", "quora.com": "Quora", "complaintboard.in": "ComplaintBoard",
    "scamadviser.com": "ScamAdviser", "pissedconsumer.com": "PissedConsumer", "glassdoor.co.in": "Glassdoor",
    "ambitionbox.com": "AmbitionBox", "cybercrime.gov.in": "Cyber Crime Portal",
}
REVIEW_SITES = {"ambitionbox.com": "AmbitionBox", "glassdoor.co.in": "Glassdoor", "glassdoor.com": "Glassdoor", "indeed.com": "Indeed", "in.indeed.com": "Indeed"}
GENERIC_EMAIL = re.compile(r"[\w.+-]+@(gmail|yahoo|outlook|hotmail|rediffmail|ymail)\.(com|in|co\.in)", re.I)

POSTING_RULES = [
    # (id, label, regex, weight)
    ("fee", "Asks for money (fee / deposit / payment)", r"(registration|training|joining|security|processing|kit|document(?:ation)?|verification|laptop|uniform)\s*(fee|fees|charges?|deposit|amount)|refundable|pay\s*(?:rs\.?|₹|inr)\s*\d|deposit of", 35),
    ("chat_contact", "Recruiting over WhatsApp/Telegram instead of a company channel", r"whats\s?app|telegram", 15),
    ("phone_contact", "A personal mobile number is the contact", r"(?<![\w%/.=-])(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w%])", 6),
    ("generic_email", "Recruiter uses a free email address (gmail/yahoo)", None, 12),
    ("no_interview", "Promises a job without an interview", r"no interview|without (?:any )?interview|direct (?:joining|selection)|100% (?:job|placement) guarantee|guaranteed (?:job|placement)|spot offer", 20),
    ("easy_money", "Easy-money work pattern (typing, likes, data entry from phone)", r"(typing|data entry|copy[- ]paste|form filling|like (?:and|&) (?:earn|subscribe)|youtube likes|rating tasks?|review tasks?|captcha)\s*(?:work|job)?.{0,40}(earn|income|daily|per day|weekly|payout)|work from (?:home|mobile).{0,40}earn|earn (?:rs\.?|₹)\s?\d", 20),
    ("urgency", "High-pressure urgency", r"limited (?:seats|slots|vacancies)|hurry|apply (?:immediately|asap|today only)|last date today|immediate joining.{0,20}(?:fee|pay)", 8),
]
SALARY_NUM = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|l|lakh|lpa|lac)?", re.I)


@dataclass
class Signal:
    id: str
    label: str
    weight: int  # positive = more risk, negative = reassuring
    detail: str = ""
    evidence: list[dict] = field(default_factory=list)  # [{title, link, source}]


@dataclass
class Report:
    company: str
    risk_score: int
    level: str  # "low" | "caution" | "high" | "unknown"
    headline: str
    signals: list[Signal]
    engines_used: list[str]
    impersonation_risk: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signals"] = [asdict(s) for s in self.signals]
        return d


# ----------------------------------------------------------------- posting layer
def posting_signals(job: Job) -> list[Signal]:
    text = job.full_text()
    out: list[Signal] = []
    for rid, label, pat, weight in POSTING_RULES:
        if rid == "generic_email":
            m = GENERIC_EMAIL.search(text)
        else:
            m = re.search(pat, text, re.I)
        if m:
            out.append(Signal(rid, label, weight, detail=_snippet(text, m.start(), m.end())))

    if re.fullmatch(r"\s*(confidential|undisclosed|not disclosed|hidden|company)?\s*", job.company or "", re.I) and job.job_id != "pasted":
        out.append(Signal("hidden_company", "Company name is hidden (\"Confidential\")", 12,
                          detail="You can't verify an employer you can't name. Ask for the company name before sharing documents."))

    pay = _too_good_pay(job.salary + " " + text[:600])
    if pay:
        out.append(Signal("pay", "Pay looks unusually high for a no-experience role", 15, detail=pay))

    boards = [board_for(a["domain"]) for a in job.apply_options]
    known = sorted({b for b in boards if b})
    others = sorted({a["domain"] for a, b in zip(job.apply_options, boards) if not b and a["domain"]})
    if not job.apply_options and job.job_id != "pasted":
        out.append(Signal("no_apply", "No apply link listed anywhere", 10))
    elif known:
        out.append(Signal("boards", f"Listed on established job boards: {', '.join(known)}", -5,
                          evidence=[{"title": a["title"], "link": a["link"], "source": a["domain"]} for a in job.apply_options[:3]]))
    if others and not known:
        out.append(Signal("unknown_apply", "Only apply route is an unfamiliar website", 8, detail=", ".join(others[:3])))
    return out


def _too_good_pay(text: str) -> str | None:
    """Flag monthly pay above ~₹1.5L or annual above ~₹18 LPA for a fresher, or per-day/week income pitches."""
    t = text.lower()
    if re.search(r"(?:₹|rs\.?)\s?\d[\d,]*\s*(?:per|/)\s*(?:day|week)", t):
        return re.search(r"(?:₹|rs\.?)\s?\d[\d,]*\s*(?:per|/)\s*(?:day|week)", t).group(0)
    for m in SALARY_NUM.finditer(t):
        num = float(m.group(1).replace(",", "") or 0)
        unit = (m.group(2) or "").lower()
        window = t[m.end(): m.end() + 25]
        if unit in ("l", "lakh", "lpa", "lac"):
            annual = num * 1e5
        elif unit == "k":
            annual = num * 1e3 * (12 if "month" in window or "pm" in window else 1)
        else:
            annual = num * (12 if ("month" in window or "/m" in window or "pm" in window) else 1)
        if "month" in window and unit in ("l", "lakh", "lac"):
            annual = num * 1e5 * 12
        if annual >= 18e5:
            return m.group(0) + window[:15]
    return None


def _snippet(text: str, a: int, b: int, pad: int = 60) -> str:
    s = text[max(0, a - pad): b + pad].replace("\n", " ").strip()
    return ("…" if a > pad else "") + s + ("…" if b + pad < len(text) else "")


# ----------------------------------------------------------------- web layer
def _mentions(company: str, text: str) -> bool:
    toks = [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) > 2 and t not in {"pvt", "ltd", "private", "limited", "india", "the", "solutions", "services", "technologies", "technology", "llp", "inc"}]
    if not toks:
        toks = re.findall(r"[a-z0-9]+", company.lower())
    tl = text.lower()
    return all(t in tl for t in toks[:2])


def _classify_results(company: str, results: list[dict], engine: str) -> tuple[list[dict], list[dict]]:
    """Split organic results into (scam-related hits about this company, impersonation-warning hits)."""
    scam_hits, imp_hits = [], []
    for r in results:
        title, snip, link = r.get("title", ""), r.get("snippet", "") or r.get("description", ""), r.get("link", "")
        blob = f"{title} {snip}"
        if not _mentions(company, blob) or not SCAM_WORDS.search(blob):
            continue
        d = domain_of(link)
        item = {"title": title, "link": link, "source": COMPLAINT_SITES.get(_base(d), d), "engine": engine, "snippet": snip[:220]}
        (imp_hits if IMPERSONATION.search(blob) else scam_hits).append(item)
    return scam_hits, imp_hits


def _base(d: str) -> str:
    for k in list(COMPLAINT_SITES) + list(REVIEW_SITES):
        if d == k or d.endswith("." + k):
            return k
    return d


def _rating_from(r: dict) -> tuple[float | None, int | None]:
    rs = r.get("rich_snippet") or {}
    top = rs.get("top") or {}
    det = top.get("detected_extensions") or {}
    rating, reviews = det.get("rating"), det.get("reviews")
    if rating is None:
        m = re.search(r"(\d(?:\.\d)?)\s*(?:/\s*5|stars?|★)", " ".join(top.get("extensions", []) + [r.get("snippet", "")]))
        rating = float(m.group(1)) if m else None
    if reviews is None:
        m = re.search(r"([\d,.]+\s*[kK]?)\s*(?:reviews|ratings)", " ".join(top.get("extensions", []) + [r.get("snippet", "")]))
        if m:
            raw = m.group(1).replace(",", "").strip()
            reviews = int(float(raw[:-1]) * 1000) if raw.lower().endswith("k") else int(float(raw))
    return (float(rating) if rating is not None else None), reviews


def web_signals(client: SerpClient, company: str) -> tuple[list[Signal], list[str], bool, list[str]]:
    signals: list[Signal] = []
    engines: list[str] = []
    errors: list[str] = []
    q_scam = f'"{company}" scam OR fraud OR fake OR complaint'

    # 1) Google: complaint footprint
    g_scam, g_imp = [], []
    try:
        g = client.search("google", q=q_scam, gl="in", hl="en", num=10)
        engines.append("google")
        g_scam, g_imp = _classify_results(company, g.get("organic_results", []), "google")
    except SerpError as e:
        errors.append(str(e))

    # 2) Bing: independent second index for the same question
    b_scam, b_imp = [], []
    try:
        b = client.search("bing", q=q_scam, cc="IN")
        engines.append("bing")
        b_scam, b_imp = _classify_results(company, b.get("organic_results", []), "bing")
    except SerpError as e:
        errors.append(str(e))

    # 3) Google: legitimacy footprint
    kg, rating, reviews, review_src, official = None, None, None, None, None
    try:
        lg = client.search("google", q=f'"{company}" company reviews employees', gl="in", hl="en", num=10)
        if "google" not in engines:
            engines.append("google")
        kg = lg.get("knowledge_graph") or None
        for r in lg.get("organic_results", []):
            d = domain_of(r.get("link", ""))
            base = _base(d)
            if base in REVIEW_SITES and rating is None and _mentions(company, r.get("title", "")):
                rating, reviews = _rating_from(r)
                review_src = {"title": r.get("title", ""), "link": r.get("link", ""), "source": REVIEW_SITES[base]}
            elif official is None and base not in COMPLAINT_SITES and base not in REVIEW_SITES and _looks_official(company, d):
                official = {"title": r.get("title", ""), "link": r.get("link", ""), "source": d}
        if kg and kg.get("website") and not official:
            official = {"title": kg.get("title", company), "link": kg["website"], "source": domain_of(kg["website"])}
    except SerpError as e:
        errors.append(str(e))

    # ---- turn raw findings into weighted signals
    both = _cross_engine_overlap(g_scam, b_scam)
    n_scam = len({_norm_link(h["link"]) for h in g_scam + b_scam})
    n_imp = len({_norm_link(h["link"]) for h in g_imp + b_imp})
    complaint_hits = [h for h in g_scam + b_scam if _base(domain_of(h["link"])) in COMPLAINT_SITES]

    if n_scam:
        weight = min(40, 10 + 6 * n_scam) + (10 if both else 0)
        eng = "Google and Bing" if (g_scam and b_scam) else ("Google" if g_scam else "Bing")
        signals.append(Signal("web_scam", f"{n_scam} search result(s) link this company name to scam/fraud complaints ({eng})", weight,
                              detail=("Same complaint pages surfaced on both engines" if both else ""),
                              evidence=_dedupe(g_scam + b_scam)[:5]))
    if complaint_hits:
        sites = sorted({h["source"] for h in complaint_hits})
        signals.append(Signal("complaint_sites", f"Discussed on complaint/review forums: {', '.join(sites)}", 8, evidence=_dedupe(complaint_hits)[:3]))
    impersonation = False
    if n_imp:
        impersonation = True
        signals.append(Signal("impersonation", "Scammers are known to use this company's name (fake offer letters / fraud alerts)", 10,
                              detail="This is usually a warning about impostors, not the company. Apply only through the official careers site.",
                              evidence=_dedupe(g_imp + b_imp)[:4]))
    if not n_scam and not n_imp and engines:
        signals.append(Signal("web_clean", f"No scam or fraud complaints tied to this name on {' or '.join(e.title() for e in engines)}", -10))

    legit = 0
    if kg:
        legit += 1
        signals.append(Signal("kg", "Google shows a Knowledge Graph entry for the company", -12,
                              detail=kg.get("type", "") or kg.get("description", "")[:120],
                              evidence=[{"title": kg.get("title", company), "link": kg.get("website", "") or "", "source": "Google Knowledge Graph"}]))
    if rating is not None or reviews:
        legit += 1
        low = rating is not None and rating < 3.0
        signals.append(Signal("reviews", f"Employee reviews found on {review_src['source']}" + (f": {rating}/5" if rating else "") + (f" from {reviews:,} reviews" if reviews else ""),
                              8 if low else (-12 if (reviews or 0) >= 50 else -6),
                              detail="Low employee rating" if low else "", evidence=[review_src]))
    if official:
        legit += 1
        signals.append(Signal("official_site", f"Has its own website ({official['source']})", -6, evidence=[official]))
    if engines and legit == 0:
        signals.append(Signal("no_footprint", "No Knowledge Graph, employee reviews or official website found", 18,
                              detail="Brand-new or non-existent companies are a common scam pattern. Not proof on its own."))
    return signals, engines, impersonation, errors


def _looks_official(company: str, domain: str) -> bool:
    toks = [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) > 2 and t not in {"pvt", "ltd", "private", "limited", "india", "the", "and"}]
    host = domain.split(":")[0].replace("-", "")
    return bool(toks) and toks[0] in host and not any(s in host for s in ("linkedin", "naukri", "indeed", "facebook", "instagram", "youtube", "wikipedia", "justdial", "zaubacorp", "tofler", "crunchbase"))


def _norm_link(u: str) -> str:
    p = urlparse(u)
    return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/")).lower()


def _cross_engine_overlap(a: list[dict], b: list[dict]) -> bool:
    return bool({_norm_link(x["link"]) for x in a} & {_norm_link(x["link"]) for x in b})


def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for i in items:
        k = _norm_link(i["link"])
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


# ----------------------------------------------------------------- combine
def assess(client: SerpClient, job: Job | None, company: str, use_web: bool = True) -> Report:
    company = (company or (job.company if job else "")).strip()
    signals: list[Signal] = posting_signals(job) if job else []
    engines, errors, impersonation = [], [], False
    if company.lower() in ("confidential", "undisclosed", "not disclosed"):
        company = ""  # nothing meaningful to search for
    if use_web and company:
        ws, engines, impersonation, errors = web_signals(client, company)
        signals.extend(ws)

    raw = 20 + sum(s.weight for s in signals)
    score = max(0, min(100, raw))
    # A direct request for money is a hard red flag regardless of footprint.
    if any(s.id == "fee" for s in signals):
        score = max(score, 70)
    if not engines and not job:
        level = "unknown"
    elif score >= 60:
        level = "high"
    elif score >= 35:
        level = "caution"
    else:
        level = "low"
    headline = _headline(level, signals, impersonation)
    signals.sort(key=lambda s: -s.weight)
    return Report(company, score, level, headline, signals, engines, impersonation, errors)


def _headline(level: str, signals: list[Signal], impersonation: bool) -> str:
    ids = {s.id for s in signals}
    if "fee" in ids:
        return "Asks for money up front. Real employers in India do not charge freshers to get hired."
    if level == "high":
        return "Multiple scam signals. Verify independently before sharing documents or money."
    if level == "caution":
        if impersonation and ("kg" in ids or "reviews" in ids):
            return "Real company, but its name is used by impostors. Apply only via the official careers page."
        return "Some warning signs. Check the company's official site and never pay to apply."
    if level == "low":
        if impersonation:
            return "Looks legitimate. Its name is sometimes misused, so apply only via official channels."
        return "No scam signals found in the posting or on the web."
    return "Not enough data to judge."
