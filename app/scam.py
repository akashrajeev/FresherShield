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
# Hindi (Devanagari) and Hinglish (romanised Hindi) versions of the same patterns. Fake offers
# are forwarded on WhatsApp in these forms far more than in formal English.
HINDI_RULES = {
    "fee": r"(?:registration|joining|training|security|kit|form)\s*(?:fee|fees|charges?|amount|paise)\s*(?:jama|bharn[ai]|bharo|den[ai]|do|pay kar)|fees?\s*(?:jama|bharo|bharn[ai]|den[ai]\s*hog[ia])|paise\s*(?:jama|dene)|शुल्क|फ़?फीस|फ़ीस|पंजीकरण|रजिस्ट्रेशन\s*(?:फ़?ीस|चार्ज|अमाउंट)|जमा\s*(?:करें|करना|कराएं|करो)|सिक्योरिटी\s*(?:डिपॉ?जिट|मनी|राशि)|रिफंडेबल|वापस\s*मिल\s*जाएगा",
    "chat_contact": r"व्हाट्स\s*[एऐ]प|वॉट्सऐप|टेलीग्राम",
    "no_interview": r"bina\s+(?:kisi\s+)?interview|interview\s+(?:nahi|nahin)|बिना\s+(?:किसी\s+)?(?:इंटरव्यू|साक्षात्कार)|(?:सीधी|डायरेक्ट)\s+(?:जॉइनिंग|भर्ती)|100%\s*(?:नौकरी|जॉब)\s*(?:गारंटी|पक्की)|नौकरी\s+पक्की",
    "easy_money": r"ghar\s+baithe.{0,40}(?:kama|kamai|earn|income)|(?:roz|rozana|daily|per\s*day|prati\s*din).{0,20}(?:kama|kamai)|घर\s+बैठे.{0,40}(?:कमा|आय|इनकम|कमाई)|(?:रोज़?|रोजाना|रोज़ाना|प्रतिदिन|हर\s+दिन).{0,25}(?:कमा|कमाई|₹|रुपये)",
    "urgency": r"jaldi\s+(?:karo|kare|apply)|aaj\s+hi|सीमित\s+(?:सीट|पद)|जल्दी\s+(?:करें|करो)|आज\s+ही",
}
# "No registration fee", "कोई फीस नहीं", "fees nahi" are reassurances, not requests for money.
FEE_NEGATION_BEFORE = re.compile(r"(?:\bno|\bzero|\bnot|\bnever|\bwithout|\bfree of|कोई|बिना|निःशुल्क|मुफ्त|मुफ़्त)[\s:-]*(?:[^\s.!?।]+\s*){0,2}$", re.I)
FEE_NEGATION_AFTER = re.compile(r"^[^\S\n]{0,3}(?:[^\s.!?।]+\s*){0,2}(?:nahi|nahin|not required|is not|are not|नहीं|नही|न\s)", re.I)


def _fee_is_negated(text: str, m: re.Match) -> bool:
    return bool(FEE_NEGATION_BEFORE.search(text[max(0, m.start() - 25): m.start()]) or FEE_NEGATION_AFTER.search(text[m.end(): m.end() + 25]))


def _rule_match(rid: str, pat: str, text: str) -> re.Match | None:
    """First match of the English rule or its Hindi/Hinglish version; fee mentions that are negated don't count."""
    for p in (pat, HINDI_RULES.get(rid)):
        if not p:
            continue
        for m in re.finditer(p, text, re.I):
            if rid == "fee" and _fee_is_negated(text, m):
                continue
            return m
    return None


SALARY_NUM = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(k|l|lakh|lpa|lac)?", re.I)
# Bare "25k per month" / "4.5 LPA" with no currency sign, only right after a pay word.
SALARY_BARE = re.compile(r"(?:salary|stipend|ctc|package|pay|income)\W{0,12}(?:of\s|upto\s|up to\s)?([\d,]+(?:\.\d+)?)\s*(k|lpa|lakh|lac)\b", re.I)


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
            m = _rule_match(rid, pat, text)
        if m:
            out.append(Signal(rid, label, weight, detail=_snippet(text, m.start(), m.end())))

    if re.fullmatch(r"\s*(confidential|undisclosed|not disclosed|hidden|company)?\s*", job.company or "", re.I) and job.job_id != "pasted":
        out.append(Signal("hidden_company", "Company name is hidden (\"Confidential\")", 12,
                          detail="You can't verify an employer you can't name. Ask for the company name before sharing documents."))

    pay = pay_signal(job)
    if pay:
        out.append(pay)

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


# Typical fresher pay by role family, annual CTC in INR (low, high). A posting offering
# more than twice the high end for a low-barrier role is the classic "data entry,
# Rs 45,000/month, no experience" hook. Sources are shown to the user with the flag.
ROLE_BANDS = [
    ("data entry", r"data[- ]entry|typing|form[- ]filling|copy[- ]paste|captcha", (1.2e5, 2.4e5),
     "https://salaryctc.com/data-entry-operator-salary/"),
    ("customer support", r"customer (?:support|service|care)|bpo|call[- ]?cent(?:er|re)|tele[- ]?call|voice process|chat process",
     (1.7e5, 3.5e5), "https://hyring.com/jobseeker-toolkit/salary/customer-support-executive-salary-in-india"),
    ("digital marketing", r"digital marketing|social media (?:executive|marketing|manager)|seo (?:executive|analyst)",
     (3.0e5, 6.5e5), "https://growai.in/digital-marketing-fresher-salary-india-2026/"),
    ("software", r"software|developer|programmer|sde\b|full[- ]?stack|back[- ]?end|front[- ]?end|data (?:analyst|scientist)|engineer",
     (3.5e5, 15e5), "https://www.simpliaxis.com/resources/software-engineer-salary-in-india"),
]
GENERIC_PAY_CAP = 18e5  # unknown role: flag above ~18 LPA for a fresher
PER_DAY = re.compile(r"(?:₹|rs\.?)\s?\d[\d,]*\s*(?:per|/|a)\s*(?:day|week)|(?:daily|roz(?:ana)?|per day)\s*(?:₹|rs\.?)?\s?\d{3,5}\s*(?:rs|rupay|rupees|₹)?\s*(?:kamai|kamao|earn|income)", re.I)


def fmt_lpa(annual: float) -> str:
    v = annual / 1e5
    return f"₹{v:.1f} LPA".replace(".0 ", " ")


def stated_pay(text: str) -> tuple[float, str] | None:
    """Highest annual CTC (INR) the text states, with the matched words. Monthly figures are x12."""
    t = text.lower()
    best: tuple[float, str] | None = None
    for m in [*SALARY_NUM.finditer(t), *SALARY_BARE.finditer(t)]:
        try:
            num = float(m.group(1).replace(",", "") or 0)
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        window = t[m.end(): m.end() + 25]
        monthly = any(w in window for w in ("month", "/m", " pm", "p.m", "mahina", "mahine"))
        if unit in ("l", "lakh", "lpa", "lac"):
            annual = num * 1e5 * (12 if monthly and unit != "lpa" else 1)
        elif unit == "k":
            annual = num * 1e3 * (12 if monthly else 1)
        else:
            annual = num * (12 if monthly else 1)
        if annual < 5e4:  # fees, deposits and small sums are not salaries
            continue
        if not best or annual > best[0]:
            best = (annual, (m.group(0) + window[:15]).strip())
    return best


def role_family(title_and_text: str) -> tuple | None:
    for fam in ROLE_BANDS:
        if re.search(fam[1], title_and_text, re.I):
            return fam
    return None


def pay_signal(job: Job) -> Signal | None:
    text = job.full_text()
    per_day = PER_DAY.search(text)
    if per_day:
        return Signal("pay", "Pay looks unusually high for a no-experience role", 15, detail=per_day.group(0))
    found = stated_pay(job.salary + " " + text[:800])
    if not found:
        return None
    annual, words = found
    fam = role_family(job.title + " " + text[:400])
    if fam:
        name, _, (lo, hi), src = fam
        if annual > 2 * hi:
            rng = f"{fmt_lpa(lo)}-{fmt_lpa(hi)}".replace(" LPA-", "-")
            return Signal("pay_role", f"Pay ({fmt_lpa(annual)}) is far above the usual fresher range for {name} ({rng})", 20,
                          detail=f"Stated: \"{words}\". High pay for easy work is how most fake-job scams hook freshers.",
                          evidence=[{"title": f"Fresher pay for {name} roles", "link": src, "source": urlparse(src).netloc}],
                          params={"role": name, "stated": fmt_lpa(annual), "range": rng})
        return None
    if annual >= GENERIC_PAY_CAP:
        return Signal("pay", "Pay looks unusually high for a no-experience role", 15, detail=words)
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
    news = news_items(client, name, engines, errors)                             # 5) Google News: fraud reports

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
    signals.extend(news_signals(company, news))
    maps_sig = maps_signals(company, places) if places is not None else []
    for sig in maps_sig:
        if sig.id == "maps":
            legit += 1
    signals.extend(maps_sig)
    if engines and legit == 0:
        signals.append(Signal("no_footprint", "No Knowledge Graph, reviews, registry record, official website or Maps listing found", 18,
                              detail="Brand-new or non-existent companies are a common scam pattern. Not proof on its own."))
    return signals, engines, impersonation, errors


# ----------------------------------------------------------------- Google News layer
NEWS_FRAUD = re.compile(r"(fake|bogus|fraud(?:ulent)?|scam|racket|duped|cheat(?:ed|ing)?|arrest(?:ed|s)?|busted|police|FIR\b|conned|swindl|looted|extort|trap)", re.I)
NEWS_JOBS = re.compile(r"(job|jobs|recruit|hiring|offer letter|placement|employment|candidates|aspirants|freshers|work from home|task|interview)", re.I)


def news_items(client: SerpClient, name: str, engines: list[str], errors: list[str]) -> list[dict]:
    """Google News for the company name next to job-fraud words. Stories with sub-stories are flattened."""
    try:
        data = client.search("google_news", q=f'"{name}" fake job OR scam OR fraud OR arrested', gl="in", hl="en")
    except SerpError as e:
        errors.append(str(e))
        return []
    if "google_news" not in engines:
        engines.append("google_news")
    out = []
    for r in data.get("news_results") or []:
        out.append(r)
        out.extend(r.get("stories") or [])
    return out


def news_signals(company: str, items: list[dict]) -> list[Signal]:
    """News reports that tie this name to job fraud.

    A report about impostors ("fake offers in the name of X") is impersonation, not evidence
    against X. Only headlines that mention the company AND a fraud word AND a jobs word count.
    """
    fraud, imp = [], []
    for it in items:
        title = it.get("title", "")
        if not it.get("link") or not _mentions(company, title) or not NEWS_FRAUD.search(title) or not NEWS_JOBS.search(title):
            continue
        src = (it.get("source") or {}).get("name", "") if isinstance(it.get("source"), dict) else str(it.get("source") or "")
        item = {"title": title, "link": it["link"], "source": src or domain_of(it["link"]), "engine": "google_news",
                "snippet": str(it.get("date") or "")[:40]}
        (imp if IMPERSONATION.search(title) else fraud).append(item)
    out = []
    fraud, imp = _dedupe(fraud), _dedupe(imp)
    if fraud:
        out.append(Signal("news_fraud", f"{len(fraud)} news report(s) link this name to job fraud", min(30, 12 + 6 * len(fraud)),
                          detail="News coverage of arrests or complaints is stronger evidence than forum posts. Read the headlines: some may be about impostors.",
                          evidence=fraud[:4], params={"n": len(fraud)}))
    if imp:
        out.append(Signal("news_impersonation", "News reports warn of fake offers using this company's name", 6,
                          detail="The company itself is usually the victim here. Apply only through its official careers page.",
                          evidence=imp[:3]))
    return out


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


def _ptype(p: dict) -> str:
    """Place category. SerpApi usually gives a string, but some places return a list."""
    t = p.get("type") or ""
    return ", ".join(str(x) for x in t) if isinstance(t, list) else str(t)


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
                 "snippet": " · ".join(x for x in (_ptype(p), str(p.get("address") or "")) if x)[:220]} for p in hits[:3]]
    weight = -10 if total_reviews >= 20 else -4
    low = rating is not None and float(rating) < 3.0 and total_reviews >= 10
    out = [Signal("maps", label, 6 if low else weight, detail=("Low Maps rating. Read the reviews." if low else where), evidence=evidence,
                  params={"n": len(hits), "stats": _stats(rating, total_reviews or None)})]
    types = " ".join([_ptype(best)] + [str(t) for t in (best.get("types") or [])])
    if AGENCY_TYPES.search(types):
        out.append(Signal("maps_agency", f"Google Maps lists it as \"{_ptype(best) or 'placement agency'}\", not an employer", 6, params={"type": _ptype(best) or "placement agency"},
                          detail="Placement agencies sometimes charge job seekers. Real employers never do. Ask who the actual employer is.",
                          evidence=evidence[:1]))
    elif INSTITUTE_TYPES.search(types):
        out.append(Signal("maps_institute", f"Google Maps lists it as \"{_ptype(best) or 'training institute'}\"", 10, params={"type": _ptype(best) or "training institute"},
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


# ----------------------------------------------------------------- contact domains
EMAIL_RE = re.compile(r"([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)", re.I)
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+(?:com|in|co\.in|org|net|info|online|site|xyz|io|co|biz|top|live))(?![\w.])", re.I)
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "ymail.com", "live.com", "icloud.com", "proton.me"}


def _root(domain: str) -> str:
    d = domain.lower().removeprefix("www.")
    parts = d.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in ("co.in", "org.in", "net.in", "gov.in", "co.uk"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _edit1or2(a: str, b: str) -> bool:
    """True if a and b differ by 1-2 edits (typosquats like 'infosis' vs 'infosys')."""
    if a == b or abs(len(a) - len(b)) > 2 or min(len(a), len(b)) < 4:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 2


def contact_signals(text: str, company: str, official_domain: str) -> list[Signal]:
    """Compare email/link domains in an offer with the company's real domain.

    Scammers send offers from look-alike domains (infosys-careers.in, tcs-recruitment.com,
    wipr0.in) or put the brand in a free-mail address (tcs.hr.recruit@gmail.com).
    """
    out: list[Signal] = []
    official = _root(official_domain) if official_domain else ""
    toks = [t for t in re.findall(r"[a-z0-9]+", short_name(company).lower()) if len(t) > 2 and t not in STOP]
    seen: set[str] = set()
    emails = EMAIL_RE.findall(text)
    hosts = [d for _, d in emails] + [m.group(1) for m in URL_RE.finditer(text)]
    own, fakes = [], []
    for h in hosts:
        h = h.lower().rstrip(".")
        r = _root(h)
        if r in seen or r in FREE_MAIL or _is_job_listing(h):
            continue
        seen.add(r)
        if official and r == official:
            own.append(h)
            continue
        label = r.split(".")[0].replace("-", "")
        off_label = official.split(".")[0].replace("-", "") if official else ""
        brand_in = bool(toks) and all(t in label for t in toks[:1])
        typo = bool(off_label) and _edit1or2(label, off_label)
        if official and (brand_in or typo):
            fakes.append(h)
    if fakes:
        out.append(Signal("lookalike_domain", f"Contact uses a look-alike domain ({', '.join(fakes[:2])}), not the company's own ({official})", 25,
                          detail="Real recruiters write from the company's own domain. A domain that only resembles it is a classic impersonation trick.",
                          params={"domains": ", ".join(fakes[:2]), "official": official}))
    elif own:
        out.append(Signal("own_domain", f"Contact uses the company's own domain ({official})", -6, params={"official": official}))
    for local, dom in emails:
        if dom.lower() in FREE_MAIL and toks and toks[0] in local.lower():
            out.append(Signal("brand_free_mail", f"Company name used in a free email address ({local}@{dom})", 12,
                              detail="Companies don't recruit from gmail/yahoo accounts named after themselves.",
                              params={"email": f"{local}@{dom}"}))
            break
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
        if job:
            official = next((s.params.get("domain", "") for s in ws if s.id == "official_site"), "")
            signals.extend(contact_signals(job.full_text(), company, official))

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
