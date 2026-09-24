"""Scam-posting risk check for a job + company.

Two layers:
1. Posting signals (free): red-flag language in the Google Jobs posting itself and
   where it can be applied to.
2. Web footprint (SerpApi): what Google and Bing return when you search the company
   name next to scam/fraud/complaint words, plus whether the company has a real
   legitimacy footprint (Knowledge Graph, employee reviews, an official website) and a
   Google Maps presence (real offices with reviews, and what kind of business it is).

The output is a risk level with every signal and its evidence link. It is a triage
aid, not a verdict. See docs/METHODOLOGY.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

from .jobs import Job, board_for, domain_of
from .serp import SerpClient, SerpError

SCAM_WORDS = re.compile(r"\b(scam|scammers?|fraud|fraudulent|fake|cheat(?:ed|ing)?|complaints?|beware|warning|money (?:not )?refund|not refundable|no refund|be aware before|looted|extort)", re.I)
IMPERSONATION = re.compile(r"(fraud[- ]alert|disclaimer|fake (?:offer|job|appointment) letters?|in the name of|impersonat|pretending to be|posing as|fraudulent (?:job )?offers?|recruitment fraud|beware of fake|fraud alert|fake recruit)", re.I)
COMPLAINT_SITES = {
    "consumercomplaints.in": "ConsumerComplaints.in", "voxya.com": "Voxya", "mouthshut.com": "MouthShut",
    "trustpilot.com": "Trustpilot", "reddit.com": "Reddit", "quora.com": "Quora", "complaintboard.in": "ComplaintBoard",
    "scamadviser.com": "ScamAdviser", "pissedconsumer.com": "PissedConsumer", "glassdoor.co.in": "Glassdoor",
    "ambitionbox.com": "AmbitionBox", "cybercrime.gov.in": "Cyber Crime Portal",
}
REVIEW_SITES = {"ambitionbox.com": "AmbitionBox", "glassdoor.co.in": "Glassdoor", "glassdoor.com": "Glassdoor", "indeed.com": "Indeed",
                "in.indeed.com": "Indeed", "justdial.com": "Justdial", "google.com/maps": "Google Maps"}
# "fraud" used as a job function or product, not an accusation
BUSINESS_FRAUD = re.compile(r"\b(?:anti[- ]?)?fraud\s+(?:analyst|analytics|management|risk|detection|prevention|investigat\w*|operations|strategy|team|specialist|solutions?|control|monitoring)|\bfraud alert\b(?=\W{0,3}(?:job seekers|register|login|sign))", re.I)
AGGREGATORS = ("jooble.org", "jobrapido.com", "simplyhired.co.in", "simplyhired.com", "bebee.com", "jobaaj.com", "unojobs.com",
               "talent.com", "careerjet.co.in", "adzuna.in", "whatjobs.com", "hiringgo.com", "jobsora.com")
REGISTRY_SITES = ("zaubacorp.com", "tofler.in", "thecompanycheck.com", "falconebiz.com", "instafinancials.com")
INSTITUTE = re.compile(r"\b(training (?:institute|center|centre)|institute|academy|coaching|classes|course fees?|placement guarantee)", re.I)
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
    params: dict = field(default_factory=dict)  # values in the label, so app/i18n.py can translate it


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
    headline_key: str = ""
    headline_params: dict = field(default_factory=dict)

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
        out.append(Signal("boards", f"Listed on established job boards: {', '.join(known)}", -5, params={"boards": ", ".join(known)},
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


def _is_job_listing(domain: str) -> bool:
    return bool(board_for(domain)) or any(domain == a or domain.endswith("." + a) for a in AGGREGATORS)


def _classify_results(company: str, results: list[dict], engine: str, official_domain: str = "") -> tuple[list[dict], list[dict]]:
    """Split organic results into (scam-related hits about this company, impersonation-warning hits).

    Ignored: job-board/aggregator pages (their menus say "Fraud Alert"), results that only use
    "fraud" as a job function ("Fraud Analyst"), and the company's own site unless it is a
    fraud-alert page (which is an impersonation signal, not a complaint).
    """
    scam_hits, imp_hits = [], []
    for r in results:
        title, snip, link = r.get("title", ""), r.get("snippet", "") or r.get("description", ""), r.get("link", "")
        d = domain_of(link)
        if _is_job_listing(d):
            continue
        blob = BUSINESS_FRAUD.sub(" ", f"{title} {snip}")
        if not _mentions(company, f"{title} {snip} {link.replace('-', ' ')}") or not SCAM_WORDS.search(blob):
            continue
        if d.endswith(("youtube.com", "instagram.com", "facebook.com")):
            blob = BUSINESS_FRAUD.sub(" ", title)  # sidebars/other videos pollute snippets
            if not SCAM_WORDS.search(blob):
                continue
        own = (bool(official_domain) and (d == official_domain or d.endswith("." + official_domain))) or _looks_official(company, d)
        item = {"title": title, "link": link, "source": COMPLAINT_SITES.get(_base(d), d), "engine": engine, "snippet": snip[:220]}
        # A scam page on the company's own domain is the company warning about impostors.
        (imp_hits if own or IMPERSONATION.search(f"{title} {snip} {link}") else scam_hits).append(item)
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


def short_name(company: str) -> str:
    """'Tradexa Technologies Private Limited' -> 'Tradexa Technologies'. Long legal names make search engines drop the quotes."""
    n = re.sub(r"\b(private|pvt\.?|limited|ltd\.?|llp|inc\.?|opc|\(opc\)|india)\b", " ", company, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" .,-")
    return n or company


def web_signals(client: SerpClient, company: str, apply_domains: list[str] | None = None) -> tuple[list[Signal], list[str], bool, list[str]]:
    signals: list[Signal] = []
    engines: list[str] = []
    errors: list[str] = []
    name = short_name(company)
    q_scam = f'"{name}" scam OR fraud OR fake OR complaint'
    pool: list[dict] = []  # every organic result, used for the legitimacy footprint

    def run(engine: str, **params) -> list[dict]:
        try:
            data = client.search(engine, **params)
        except SerpError as e:
            errors.append(str(e))
            return []
        if engine not in engines:
            engines.append(engine)
        if engine == "google" and data.get("knowledge_graph"):
            run.kg = run.kg or data["knowledge_graph"]
        rows = data.get("organic_results", [])
        pool.extend(rows)
        return rows
    run.kg = None

    g_rows = run("google", q=q_scam, gl="in", hl="en", num=10)                  # 1) Google complaint footprint
    b_rows = run("bing", q=f'"{name}" scam OR fraud OR complaints', cc="IN")    # 2) Bing, independent index
    run("google", q=f'"{name}" reviews', gl="in", hl="en", num=10)               # 3) Google legitimacy footprint
    kg = run.kg
    places = maps_places(client, name, engines, errors)                          # 4) Google Maps: real offices

    # ---- legitimacy footprint from everything we saw
    rating = reviews = review_src = official = registry = None
    institute_hits = []
    for r in pool:
        link, title, snip = r.get("link", ""), r.get("title", ""), r.get("snippet", "") or ""
        d = domain_of(link)
        base = _base(d)
        about_us = _mentions(company, f"{title} {link.replace('-', ' ')}")
        if base in REVIEW_SITES and rating is None and about_us:
            rating, reviews = _rating_from(r)
            if rating is not None or reviews:
                review_src = {"title": title, "link": link, "source": REVIEW_SITES[base]}
        if registry is None and any(d.endswith(x) for x in REGISTRY_SITES) and about_us:
            m = re.search(r"incorporated on (\d{1,2} \w+,? \d{4})", snip, re.I)
            registry = {"title": title, "link": link, "source": d, "incorporated": m.group(1) if m else ""}
        if official is None and _looks_official(company, d):
            official = {"title": title, "link": link, "source": d}
        if about_us and INSTITUTE.search(f"{title} {snip}") and not _is_job_listing(d):
            institute_hits.append({"title": title, "link": link, "source": d})
    if kg and kg.get("website") and not official:
        official = {"title": kg.get("title", company), "link": kg["website"], "source": domain_of(kg["website"])}
    if not official:
        for ad in apply_domains or []:
            if _looks_official(company, ad):
                official = {"title": "Apply link on the company's own site", "link": "https://" + ad, "source": ad}
                break
    official_domain = official["source"] if official else ""
    g_scam, g_imp = _classify_results(company, g_rows, "google", official_domain)
    b_scam, b_imp = _classify_results(company, b_rows, "bing", official_domain)

    # ---- turn raw findings into weighted signals
    both = _cross_engine_overlap(g_scam, b_scam)
    n_scam = len({_norm_link(h["link"]) for h in g_scam + b_scam})
    n_imp = len({_norm_link(h["link"]) for h in g_imp + b_imp})
    complaint_hits = [h for h in g_scam + b_scam if _base(domain_of(h["link"])) in COMPLAINT_SITES]

    if n_scam:
        weight = min(40, 10 + 6 * n_scam) + (10 if both else 0)
        eng = "Google and Bing" if (g_scam and b_scam) else ("Google" if g_scam else "Bing")
        signals.append(Signal("web_scam", f"{n_scam} search result(s) link this company name to scam/fraud complaints ({eng})", weight, params={"n": n_scam, "engines": eng.replace(" and ", " + ")},
                              detail=("Same complaint pages surfaced on both engines" if both else ""),
                              evidence=_dedupe(g_scam + b_scam)[:5]))
    if complaint_hits:
        sites = sorted({h["source"] for h in complaint_hits})
        signals.append(Signal("complaint_sites", f"Discussed on complaint/review forums: {', '.join(sites)}", 8, params={"sites": ", ".join(sites)}, evidence=_dedupe(complaint_hits)[:3]))
    impersonation = False
    if n_imp:
        impersonation = True
        signals.append(Signal("impersonation", "Scammers are known to use this company's name (fake offer letters / fraud alerts)", 10,
                              detail="This is usually a warning about impostors, not the company. Apply only through the official careers site.",
                              evidence=_dedupe(g_imp + b_imp)[:4]))
    if not n_scam and not n_imp and engines:
        clean_on = ' or '.join(e.title() for e in engines if e in ('google', 'bing'))
        signals.append(Signal("web_clean", f"No scam or fraud complaints tied to this name on {clean_on}", -10, params={"engines": clean_on.replace(" or ", " + ")}))

    legit = 0
    if kg:
        legit += 1
        signals.append(Signal("kg", "Google shows a Knowledge Graph entry for the company", -12,
                              detail=kg.get("type", "") or (kg.get("description") or "")[:120],
                              evidence=[{"title": kg.get("title", company), "link": kg.get("website", "") or "", "source": "Google Knowledge Graph"}]))
    if review_src:
        legit += 1
        low = rating is not None and rating < 3.0
        signals.append(Signal("reviews", f"Reviews found on {review_src['source']}" + (f": {rating}/5" if rating else "") + (f" from {reviews:,} reviews" if reviews else ""),
                              8 if low else (-12 if (reviews or 0) >= 50 else -6),
                              detail="Low rating" if low else "", evidence=[review_src],
                              params={"source": review_src["source"], "stats": _stats(rating, reviews)}))
    if registry:
        legit += 1
        age_note, w = "", -6
        if registry["incorporated"]:
            import datetime as _dt
            try:
                inc = _dt.datetime.strptime(registry["incorporated"].replace(",", ""), "%d %B %Y")
                years = (_dt.datetime.now() - inc).days / 365.25
                age_note = f"incorporated {registry['incorporated']} ({years:.1f} years ago)"
                if years < 1:
                    w = 10
                    age_note += " - very new company"
            except ValueError:
                age_note = f"incorporated {registry['incorporated']}"
        signals.append(Signal("registry", "Listed in the company registry (MCA data via " + registry["source"] + ")", w,
                              detail=age_note, evidence=[{k: registry[k] for k in ("title", "link", "source")}], params={"source": registry["source"]}))
    if official:
        legit += 1
        signals.append(Signal("official_site", f"Has its own website ({official['source']})", -6, evidence=[official], params={"domain": official["source"]}))
    if institute_hits:
        signals.append(Signal("institute", "Looks like a training institute or academy, not a direct employer", 12,
                              detail="'Job + training' offers from institutes often mean paying course fees. Ask whether any fee is involved before you join.",
                              evidence=_dedupe(institute_hits)[:3]))
    maps_sig = maps_signals(company, places) if places is not None else []
    for sig in maps_sig:
        if sig.id == "maps":
            legit += 1
    signals.extend(maps_sig)
    if engines and legit == 0:
        signals.append(Signal("no_footprint", "No Knowledge Graph, reviews, registry record, official website or Maps listing found", 18,
                              detail="Brand-new or non-existent companies are a common scam pattern. Not proof on its own."))
    return signals, engines, impersonation, errors


# ----------------------------------------------------------------- Google Maps layer
INDIA_LL = "@22.5,79.0,5z"  # whole-country view: company names aren't tied to one city
AGENCY_TYPES = re.compile(r"employment agency|placement|recruit|staffing|manpower|job (?:consultant|agency)|consultant", re.I)
INSTITUTE_TYPES = re.compile(r"training|institute|academy|coaching|education|computer (?:training|school)|tutor", re.I)


def maps_places(client: SerpClient, name: str, engines: list[str], errors: list[str]) -> list[dict] | None:
    """Google Maps search for the company name across India. None if the call failed."""
    try:
        data = client.search("google_maps", q=name, type="search", ll=INDIA_LL, hl="en")
    except SerpError as e:
        errors.append(str(e))
        return None
    if "google_maps" not in engines:
        engines.append("google_maps")
    if data.get("place_results"):
        return [data["place_results"]]
    return list(data.get("local_results") or [])


def maps_url(place: dict) -> str:
    if place.get("place_id"):
        from urllib.parse import quote_plus
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(place.get('title', ''))}&query_place_id={place['place_id']}"
    return place.get("link") or place.get("website") or ""


def maps_signals(company: str, places: list[dict]) -> list[Signal]:
    """Real employers usually have offices on Google Maps with reviews; fee-scam "companies" usually don't.

    Only places whose name matches the company count. Several branches add up; the category tells
    us if it's actually a placement agency or a training institute (both common fee-scam fronts).
    """
    hits = [p for p in places if _mentions(company, p.get("title", ""))]
    if not hits:
        return [Signal("maps_absent", "No Google Maps listing under this name", 4,
                       detail="Most employers with a real office have one. Remote-first startups may not, so this is weak on its own.")]
    total_reviews = sum(int(p.get("reviews") or 0) for p in hits)
    best = max(hits, key=lambda p: int(p.get("reviews") or 0))
    rating = best.get("rating")
    where = best.get("address", "")
    label = f"On Google Maps: {len(hits)} listing(s)" + (f", {total_reviews:,} reviews" if total_reviews else "") + (f", top rated {rating}/5" if rating else "")
    evidence = [{"title": p.get("title", ""), "link": maps_url(p), "source": "Google Maps", "engine": "google_maps",
                 "snippet": " · ".join(x for x in (p.get("type", ""), p.get("address", "")) if x)[:220]} for p in hits[:3]]
    weight = -10 if total_reviews >= 20 else -4
    low = rating is not None and float(rating) < 3.0 and total_reviews >= 10
    out = [Signal("maps", label, 6 if low else weight, detail=("Low Maps rating. Read the reviews." if low else where), evidence=evidence,
                  params={"n": len(hits), "stats": _stats(rating, total_reviews or None)})]
    types = " ".join([best.get("type", "")] + list(best.get("types") or []))
    if AGENCY_TYPES.search(types):
        out.append(Signal("maps_agency", f"Google Maps lists it as \"{best.get('type') or 'placement agency'}\", not an employer", 6, params={"type": best.get("type") or "placement agency"},
                          detail="Placement agencies sometimes charge job seekers. Real employers never do. Ask who the actual employer is.",
                          evidence=evidence[:1]))
    elif INSTITUTE_TYPES.search(types):
        out.append(Signal("maps_institute", f"Google Maps lists it as \"{best.get('type') or 'training institute'}\"", 10, params={"type": best.get("type") or "training institute"},
                          detail="'Job + training' offers from institutes often mean paying course fees.", evidence=evidence[:1]))
    return out


STOP = {"pvt", "ltd", "private", "limited", "india", "the", "and", "solutions", "services", "technologies", "technology",
        "llp", "inc", "company", "consultants", "consultancy", "group", "global", "infotech", "software", "systems"}


def _looks_official(company: str, domain: str) -> bool:
    toks = [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) > 1 and t not in STOP and t != "by"]
    host = domain.split(":")[0].replace("-", "")
    blocked = ("linkedin", "naukri", "indeed", "facebook", "instagram", "youtube", "wikipedia", "justdial", "zaubacorp",
               "tofler", "crunchbase", "glassdoor", "ambitionbox", "shine", "internshala", "mouthshut", "reddit", "quora")
    if not toks or any(b in host for b in blocked) or any(host.endswith(a) for a in AGGREGATORS):
        return False
    labels = [l for l in host.split(".")[:-1] if l not in ("www", "co", "com", "in", "careers", "jobs")] or host.split(".")[:1]
    return any(all(t in l for t in toks[:2]) for l in labels)


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
        ws, engines, impersonation, errors = web_signals(client, company, [a["domain"] for a in job.apply_options] if job else [])
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
    hkey, hparams = headline_key(level, signals, impersonation)
    headline = HEADLINES[hkey].format(**hparams)
    signals.sort(key=lambda s: -s.weight)
    return Report(company, score, level, headline, signals, engines, impersonation, errors, hkey, hparams)


HEADLINES = {
    "fee": "Asks for money up front. Real employers in India do not charge freshers to get hired.",
    "high": "Multiple scam signals. Verify independently before sharing documents or money.",
    "caution_real": "Real company, but its name is used by impostors. Apply only via the official careers page.",
    "caution": "Some warning signs. Check the company's official site and never pay to apply.",
    "low_watch": "Low overall risk, but check this: {label}.",
    "low_imp": "Looks legitimate. Its name is sometimes misused, so apply only via official channels.",
    "low_clean": "No scam signals found in the posting or on the web.",
    "unknown": "Not enough data to judge.",
}


def _stats(rating, reviews) -> str:
    """Language-neutral numbers for translated labels, e.g. '★ 4.1/5 · 8,535'."""
    bits = ([f"★ {rating}/5"] if rating else []) + ([f"{int(reviews):,}"] if reviews else [])
    return " · ".join(bits)


def headline_key(level: str, signals: list[Signal], impersonation: bool) -> tuple[str, dict]:
    ids = {s.id for s in signals}
    if "fee" in ids:
        return "fee", {}
    if level == "high":
        return "high", {}
    if level == "caution":
        return ("caution_real", {}) if impersonation and ids & {"kg", "reviews", "maps"} else ("caution", {})
    if level == "low":
        watch = [s for s in signals if s.weight >= 10]
        if watch:
            top = max(watch, key=lambda s: s.weight)
            return "low_watch", {"label": top.label.lower(), "signal": top.id}
        return ("low_imp", {}) if impersonation else ("low_clean", {})
    return "unknown", {}


def _headline(level: str, signals: list[Signal], impersonation: bool) -> str:
    key, params = headline_key(level, signals, impersonation)
    return HEADLINES[key].format(**params)
