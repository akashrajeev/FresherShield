"""Fresher job discovery on top of SerpApi's Google Jobs API (engine=google_jobs)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

from .serp import SerpClient

# Phrases that signal a role is open to people with no work experience.
FRESHER_POSITIVE = [
    r"\bfreshers?\b", r"\b0\s*[-–to]+\s*[12]\s*(?:years?|yrs?)\b", r"\bno (?:prior )?experience\b",
    r"\bentry[- ]level\b", r"\bgraduate (?:engineer )?trainee\b", r"\b(?:20(?:25|26|27)) (?:pass[- ]?outs?|batch|graduates?)\b",
    r"\bcampus\b", r"\btrainee\b", r"\bintern(?:ship)?\b", r"\bjunior\b", r"\bexperience\s*:\s*0\b",
]
# Phrases that signal the role actually wants experienced people.
FRESHER_NEGATIVE = [
    r"\b([3-9]|1[0-9])\s*\+?\s*(?:[-–to]+\s*\d+\s*)?(?:years?|yrs?)\b(?:\s+of)?\s+(?:relevant |professional |industry |hands[- ]on )?experience",
    r"\bminimum (?:of )?([2-9])\s*(?:years?|yrs?)\b", r"\bsenior\b", r"\blead\b", r"\bmanager\b", r"\barchitect\b",
]

KNOWN_BOARDS = {
    "linkedin.com": "LinkedIn", "naukri.com": "Naukri", "indeed.com": "Indeed", "in.indeed.com": "Indeed",
    "foundit.in": "foundit", "internshala.com": "Internshala", "glassdoor.co.in": "Glassdoor", "glassdoor.com": "Glassdoor",
    "shine.com": "Shine", "timesjobs.com": "TimesJobs", "instahyre.com": "Instahyre", "wellfound.com": "Wellfound",
    "cutshort.io": "Cutshort", "apna.co": "apna", "workindia.in": "WorkIndia", "hirist.tech": "hirist",
    "unstop.com": "Unstop", "iimjobs.com": "iimjobs", "freshersworld.com": "Freshersworld", "ziprecruiter.com": "ZipRecruiter",
}


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    location: str
    via: str
    description: str
    posted_at: str = ""
    schedule_type: str = ""
    salary: str = ""
    work_from_home: bool = False
    highlights: list[dict] = field(default_factory=list)
    apply_options: list[dict] = field(default_factory=list)
    share_link: str = ""
    thumbnail: str = ""
    fresher_score: int = 0
    fresher_reasons: list[str] = field(default_factory=list)

    def full_text(self) -> str:
        parts = [self.title, self.description]
        for h in self.highlights:
            parts.append(h.get("title", ""))
            parts.extend(h.get("items", []))
        return "\n".join(p for p in parts if p)

    def to_dict(self) -> dict:
        return asdict(self)


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def board_for(domain: str) -> str | None:
    for d, name in KNOWN_BOARDS.items():
        if domain == d or domain.endswith("." + d):
            return name
    return None


def fresher_fit(text: str) -> tuple[int, list[str]]:
    """Score 0-100 for how open a posting is to freshers, with the phrases that drove it."""
    t = text.lower()
    score, reasons = 50, []
    for pat in FRESHER_POSITIVE:
        m = re.search(pat, t)
        if m:
            score += 12
            reasons.append(f"+ \"{m.group(0).strip()}\"")
    for pat in FRESHER_NEGATIVE:
        m = re.search(pat, t)
        if m:
            score -= 25
            reasons.append(f"- \"{m.group(0).strip()}\"")
    return max(0, min(100, score)), reasons[:6]


def normalize(raw: dict) -> Job:
    ext = raw.get("detected_extensions") or {}
    job = Job(
        job_id=raw.get("job_id", ""),
        title=raw.get("title", "").strip(),
        company=(raw.get("company_name") or "").strip(),
        location=raw.get("location", ""),
        via=(raw.get("via") or "").replace("via ", ""),
        description=raw.get("description", ""),
        posted_at=ext.get("posted_at", ""),
        schedule_type=ext.get("schedule_type", ""),
        salary=ext.get("salary", ""),
        work_from_home=bool(ext.get("work_from_home")),
        highlights=raw.get("job_highlights") or [],
        apply_options=[{"title": a.get("title", ""), "link": a.get("link", ""), "domain": domain_of(a.get("link", ""))}
                       for a in (raw.get("apply_options") or [])],
        share_link=raw.get("share_link", ""),
        thumbnail=raw.get("thumbnail", ""),
    )
    job.fresher_score, job.fresher_reasons = fresher_fit(job.full_text())
    return job


def search_jobs(client: SerpClient, role: str, location: str = "India", pages: int = 1) -> dict:
    """Search Google Jobs for fresher-friendly roles. One SerpApi credit per page (cached)."""
    query = role.strip()
    if not re.search(r"fresher|entry|intern|trainee|graduate|junior", query, re.I):
        query = f"{query} fresher"
    params = {"q": query, "location": location or "India", "gl": "in", "hl": "en"}
    jobs: list[Job] = []
    filters = []
    token = None
    for page in range(max(1, pages)):
        p = dict(params)
        if token:
            p["next_page_token"] = token
        data = client.search("google_jobs", **p)
        if page == 0:
            filters = [f.get("name") for f in data.get("filters", []) if f.get("name")]
        jobs.extend(normalize(r) for r in data.get("jobs_results", []))
        token = (data.get("serpapi_pagination") or {}).get("next_page_token")
        if not token:
            break
    seen, unique = set(), []
    for j in jobs:
        k = j.job_id or (j.title, j.company)
        if k not in seen:
            seen.add(k)
            unique.append(j)
    unique.sort(key=lambda j: -j.fresher_score)
    return {"query": query, "location": params["location"], "jobs": unique, "filters": filters}
