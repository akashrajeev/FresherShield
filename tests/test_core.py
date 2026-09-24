"""Unit tests with small hand-written SerpApi-shaped payloads (no network, no credits)."""
from app.jobs import Job, fresher_fit, normalize
from app.resume import extract_skills, match
from app.scam import assess, posting_signals, _classify_results
from app.serp import SerpClient, cache_key


class FakeClient(SerpClient):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.ledger = []
        self.offline = False
        self.api_key = "x"

    def search(self, engine, **params):
        self.calls.append((engine, params.get("q")))
        for (eng, needle), body in self.responses.items():
            if eng == engine and needle in params.get("q", ""):
                return body
        return {}


def test_cache_key_ignores_api_key_and_empty():
    assert cache_key("google", {"q": "a", "api_key": "s1"}) == cache_key("google", {"q": "a", "api_key": "s2", "hl": ""})


def test_fresher_fit_orders_sensibly():
    hi, _ = fresher_fit("Freshers welcome, 0-1 years experience, 2026 batch")
    lo, _ = fresher_fit("Senior Python developer, 5+ years of experience required")
    assert hi > 70 and lo < 30


def test_normalize_google_jobs_row():
    j = normalize({
        "title": "Python Developer Fresher", "company_name": "Acme Labs", "location": "Pune", "via": "LinkedIn",
        "description": "Freshers welcome", "detected_extensions": {"posted_at": "2 days ago", "schedule_type": "Full-time"},
        "apply_options": [{"title": "LinkedIn", "link": "https://in.linkedin.com/jobs/view/1"}], "job_id": "abc",
    })
    assert j.company == "Acme Labs" and j.apply_options[0]["domain"] == "in.linkedin.com" and j.posted_at == "2 days ago"


def test_skills_and_match():
    s = extract_skills("Skills: Python, JavaScript, React.js, MySQL, Git, DSA")
    assert {"Python", "JavaScript", "React", "SQL", "Git", "Data Structures & Algorithms"} <= s
    assert "Java" not in s
    m = match("Python SQL Git", "Need Python, Django, SQL")
    assert m["matched"] == ["Python", "SQL"] and m["missing"] == ["Django"] and m["score"] == 67


def test_match_without_skills_is_none():
    assert match("Python", "Great place to work")["score"] is None


def test_posting_red_flags():
    j = Job("1", "Work from home typing job", "QuickEarn", "", "",
            "Earn Rs 3000 per day typing work. Pay registration fee Rs 999 (refundable). WhatsApp 9876543210. No interview.")
    ids = {s.id for s in posting_signals(j)}
    assert {"fee", "chat_contact", "no_interview", "easy_money", "pay", "no_apply"} <= ids


def test_clean_posting_has_no_red_flags():
    j = Job("2", "Graduate Engineer Trainee", "Acme Labs", "Pune", "LinkedIn", "B.E./B.Tech 2026 graduates. Training provided.",
            apply_options=[{"title": "LinkedIn", "link": "https://www.linkedin.com/jobs/1", "domain": "linkedin.com"}])
    assert all(s.weight <= 0 for s in posting_signals(j))


def test_impersonation_vs_scam_classification():
    rows = [
        {"title": "Beware of fake offer letters in the name of Infosys", "snippet": "Infosys never charges fees", "link": "https://www.infosys.com/fraud-alert"},
        {"title": "Infosys scam complaint", "snippet": "I was cheated", "link": "https://www.consumercomplaints.in/infosys-scam"},
        {"title": "Infosys careers", "snippet": "Join us", "link": "https://www.infosys.com/careers"},
    ]
    scam, imp = _classify_results("Infosys", rows, "google")
    assert [h["link"] for h in imp] == ["https://www.infosys.com/fraud-alert"]
    assert [h["source"] for h in scam] == ["ConsumerComplaints.in"]


def test_assess_high_risk_unknown_company():
    scam_rows = {"organic_results": [
        {"title": "QuickEarn Solutions fraud - took my money", "snippet": "QuickEarn Solutions asked for fee", "link": "https://www.consumercomplaints.in/quickearn-solutions-c123"},
        {"title": "Is QuickEarn Solutions a scam?", "snippet": "QuickEarn Solutions scam reddit", "link": "https://www.reddit.com/r/developersIndia/comments/x"},
    ]}
    fc = FakeClient({("google", "scam"): scam_rows, ("bing", "scam"): scam_rows, ("google", "reviews"): {"organic_results": []}})
    j = Job("3", "Data entry", "QuickEarn Solutions", "", "", "Registration fee Rs 1500. Contact on WhatsApp.")
    r = assess(fc, j, j.company)
    assert r.level == "high" and r.engines_used == ["google", "bing"]
    ids = {s.id for s in r.signals}
    assert {"fee", "web_scam", "complaint_sites", "no_footprint"} <= ids
    assert len(fc.calls) == 3


def test_assess_big_company_impersonation_is_not_high():
    imp = {"organic_results": [{"title": "Fraud alert: fake job offers in the name of TCS", "snippet": "TCS does not charge", "link": "https://www.tcs.com/fraud-alert"}]}
    legit = {"knowledge_graph": {"title": "Tata Consultancy Services", "website": "https://www.tcs.com"},
             "organic_results": [{"title": "TCS Reviews by 90k employees | AmbitionBox", "link": "https://www.ambitionbox.com/reviews/tcs-reviews",
                                  "rich_snippet": {"top": {"detected_extensions": {"rating": 3.8, "reviews": 90000}}}}]}
    fc = FakeClient({("google", "scam"): imp, ("bing", "scam"): imp, ("google", "reviews"): legit})
    j = Job("4", "Graduate Trainee", "TCS", "", "", "Freshers 2026", apply_options=[{"title": "TCS", "link": "https://www.tcs.com/careers", "domain": "tcs.com"}])
    r = assess(fc, j, "TCS")
    assert r.impersonation_risk and r.level == "low"


def test_tracking_ids_are_not_phone_numbers():
    j = Job("5", "Walk-in", "Infosys BPM", "", "", "Register at https://x.com/?a=7C638561289526257677%7CUnknown")
    assert "phone_contact" not in {s.id for s in posting_signals(j)}


def test_hidden_company_flag():
    j = Job("6", "Python Developer", "Confidential", "", "", "contact 7019878842")
    ids = {s.id for s in posting_signals(j)}
    assert {"hidden_company", "phone_contact"} <= ids


def test_job_board_menus_and_fraud_job_titles_are_ignored():
    rows = [
        {"title": "Python Internship Job in Tradexa - Shine", "snippet": "Tradexa is a technology company ... Fraud Alert. Job Seekers", "link": "https://www.shine.com/jobs/x/tradexa-1"},
        {"title": "Tradexa Senior Fraud Analyst Reviews", "snippet": "Tradexa fraud analyst", "link": "https://www.example.org/tradexa-fraud-analyst"},
    ]
    assert _classify_results("Tradexa", rows, "google") == ([], [])


def test_company_fraud_alert_page_is_impersonation():
    rows = [{"title": "Disclaimer - Recruitment Fraud Alert", "snippet": "... fraud ... Infosys BPM", "link": "https://www.infosys.com/careers/apply/recruitment-fraud-alert.html"}]
    scam, imp = _classify_results("Infosys BPM", rows, "google")
    assert scam == [] and len(imp) == 1


def test_short_name_strips_legal_suffixes():
    from app.scam import short_name
    assert short_name("Tradexa Technologies Private Limited") == "Tradexa Technologies"
    assert short_name("Mahe Technologies Pvt. Ltd.") == "Mahe Technologies"


def test_scam_pages_on_brand_domains_are_impersonation():
    rows = [{"title": "Identifying a scam - Amazon Customer Service", "snippet": "Amazon scam", "link": "https://www.amazon.com/gp/help/scam"}]
    scam, imp = _classify_results("Amazon", rows, "google", "amazon.in")
    assert scam == [] and len(imp) == 1
