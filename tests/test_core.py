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
    assert r.level == "high" and r.engines_used == ["google", "bing", "google_maps", "google_news"]
    ids = {s.id for s in r.signals}
    assert {"fee", "web_scam", "complaint_sites", "no_footprint", "maps_absent"} <= ids
    assert len(fc.calls) == 5


def test_assess_big_company_impersonation_is_not_high():
    imp = {"organic_results": [{"title": "Fraud alert: fake job offers in the name of TCS", "snippet": "TCS does not charge", "link": "https://www.tcs.com/fraud-alert"}]}
    legit = {"knowledge_graph": {"title": "Tata Consultancy Services", "website": "https://www.tcs.com"},
             "organic_results": [{"title": "TCS Reviews by 90k employees | AmbitionBox", "link": "https://www.ambitionbox.com/reviews/tcs-reviews",
                                  "rich_snippet": {"top": {"detected_extensions": {"rating": 3.8, "reviews": 90000}}}}]}
    maps = {"local_results": [{"title": "TCS Sahyadri Park", "rating": 4.4, "reviews": 3100, "type": "Software company", "place_id": "ChIJx"}]}
    fc = FakeClient({("google", "scam"): imp, ("bing", "scam"): imp, ("google", "reviews"): legit, ("google_maps", ""): maps})
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


# ---------------------------------------------------------------- Google Maps signal
from app.scam import maps_signals, maps_url


def test_maps_presence_with_reviews_is_reassuring():
    places = [{"title": "Tradexa Technologies", "rating": 4.6, "reviews": 41, "type": "Software company", "address": "Baner, Pune", "place_id": "ChIJabc"},
              {"title": "Some Other Cafe", "reviews": 900}]
    sigs = maps_signals("Tradexa Technologies", places)
    assert [s.id for s in sigs] == ["maps"] and sigs[0].weight == -10
    assert "41 reviews" in sigs[0].label and "query_place_id=ChIJabc" in sigs[0].evidence[0]["link"]


def test_maps_absent_and_unrelated_places_do_not_count():
    sigs = maps_signals("QuickEarn Solutions", [{"title": "Quick Bites Restaurant", "reviews": 300}])
    assert [s.id for s in sigs] == ["maps_absent"] and sigs[0].weight > 0


def test_maps_category_flags_agencies_and_institutes():
    agency = maps_signals("Star Manpower", [{"title": "Star Manpower Consultancy", "reviews": 3, "type": "Employment agency"}])
    assert {s.id for s in agency} == {"maps", "maps_agency"}
    inst = maps_signals("CodeGuru Academy", [{"title": "CodeGuru Academy", "reviews": 60, "type": "Computer training school"}])
    assert "maps_institute" in {s.id for s in inst}


def test_maps_low_rating_is_a_warning():
    sigs = maps_signals("Bad Corp", [{"title": "Bad Corp", "rating": 1.9, "reviews": 57}])
    assert sigs[0].weight > 0


def test_maps_single_place_result_and_failure_are_handled():
    from app.scam import maps_places
    from app.serp import SerpError

    class One(FakeClient):
        def search(self, engine, **p):
            return {"place_results": {"title": "Infosys Pune", "reviews": 5000}}

    class Down(FakeClient):
        def search(self, engine, **p):
            raise SerpError("quota")

    engines, errors = [], []
    assert maps_places(One({}), "Infosys", engines, errors)[0]["title"] == "Infosys Pune" and engines == ["google_maps"]
    engines, errors = [], []
    assert maps_places(Down({}), "Infosys", engines, errors) is None and errors == ["quota"] and engines == []
    assert maps_url({"title": "X", "link": "https://maps.example/x"}) == "https://maps.example/x"


def test_maps_presence_counts_as_real_company_in_headline():
    from app.scam import _headline, Signal
    sigs = [Signal("impersonation", "x", 10), Signal("maps", "y", -10)]
    assert _headline("caution", sigs, True).startswith("Real company")


def test_maps_place_type_can_be_a_list():
    sigs = maps_signals("Tradexa", [{"title": "Tradexa", "reviews": 30, "type": ["Software company", "Employment agency"], "address": "Pune"}])
    assert sigs[0].id == "maps" and "Software company" in sigs[0].evidence[0]["snippet"]
    assert "maps_agency" in {s.id for s in sigs}


# ---------------------------------------------------------------- Hindi / Hinglish red flags
def _ids(text):
    return {s.id for s in posting_signals(Job("pasted", "", "X", "", "", text))}


def test_hinglish_offer_is_caught():
    ids = _ids("Congrats! Ghar baithe roz 2000 kamao. Bina interview joining. Registration fees 999 jama karo. Jaldi karo, aaj hi.")
    assert {"fee", "no_interview", "easy_money", "urgency"} <= ids


def test_hindi_offer_is_caught():
    ids = _ids("बधाई हो! घर बैठे रोज़ ₹1500 कमाएं। बिना इंटरव्यू सीधी जॉइनिंग। रजिस्ट्रेशन फीस ₹799 जमा करें (रिफंडेबल)। व्हाट्सएप करें।")
    assert {"fee", "no_interview", "easy_money", "chat_contact"} <= ids


def test_negated_fee_mentions_are_not_red_flags():
    assert "fee" not in _ids("Walk-in drive for 2026 graduates. No registration fee is charged at any stage.")
    assert "fee" not in _ids("TCS kisi bhi candidate se fees nahi leta. कोई फीस नहीं ली जाती।")
    assert "fee" in _ids("There is no interview. Pay registration fee of Rs 500 to confirm.")


# ---------------------------------------------------------------- look-alike domains
from app.scam import contact_signals


def test_lookalike_and_typosquat_domains_are_flagged():
    sigs = contact_signals("Offer from hr@infosys-careers.in, details at www.infosys-careers.in/offer", "Infosys", "infosys.com")
    assert [s.id for s in sigs] == ["lookalike_domain"] and "infosys-careers.in" in sigs[0].label
    assert contact_signals("Mail talent@wipr0.com", "Wipro", "wipro.com")[0].id == "lookalike_domain"


def test_own_domain_is_reassuring_and_free_mail_brand_is_flagged():
    assert [s.id for s in contact_signals("Write to careers@tcs.com", "TCS", "tcs.com")] == ["own_domain"]
    ids = [s.id for s in contact_signals("HR: infosys.recruit.hr@gmail.com", "Infosys", "infosys.com")]
    assert ids == ["brand_free_mail"]


def test_unrelated_domains_and_unknown_official_are_left_alone():
    assert contact_signals("Apply on naukri.com or mail me at abc@gmail.com", "Acme Labs", "acmelabs.in") == []
    assert contact_signals("hr@quikhire-hr.com", "Quikhire", "") == []


def test_lookalike_domain_raises_assessment():
    legit = {"knowledge_graph": {"title": "Infosys", "website": "https://www.infosys.com"}, "organic_results": []}
    fc = FakeClient({("google", "reviews"): legit})
    j = Job("pasted", "", "Infosys", "", "", "Your offer letter is attached. Contact hr@infosys-careers.in to accept.")
    r = assess(fc, j, "Infosys")
    assert "lookalike_domain" in {s.id for s in r.signals}


# ---------------------------------------------------------------- Google News signal
from app.scam import news_signals


def test_news_fraud_reports_count_and_impostor_news_does_not():
    items = [
        {"title": "Police bust fake job racket run by QuickEarn Solutions, 3 arrested", "link": "https://news.example/a", "source": {"name": "The Hindu"}},
        {"title": "QuickEarn Solutions duped 200 job aspirants of Rs 2 crore", "link": "https://news.example/b", "source": {"name": "TOI"}},
        {"title": "QuickEarn Solutions opens new office", "link": "https://news.example/c"},
    ]
    sigs = news_signals("QuickEarn Solutions", items)
    assert [s.id for s in sigs] == ["news_fraud"] and sigs[0].weight == 24 and len(sigs[0].evidence) == 2
    imp = news_signals("TCS", [{"title": "Beware of fake job offers in the name of TCS, police warn", "link": "https://n.example/x"}])
    assert [s.id for s in imp] == ["news_impersonation"]


def test_news_needs_jobs_context_and_company_mention():
    items = [{"title": "Infosys shares fall after fraud allegations at client", "link": "https://n.example/1"},
             {"title": "Fake job racket busted in Pune", "link": "https://n.example/2"}]
    assert news_signals("Infosys", items) == []


def test_institute_found_on_web_and_maps_counts_once():
    from app.scam import Signal, _merge_institute
    web = Signal("institute", "Looks like a training institute", 12, evidence=[{"link": "https://justdial.com/x"}])
    mp = Signal("maps_institute", "Maps: training institute", 10, evidence=[{"link": "https://maps.google.com/x"}])
    out = _merge_institute([web, mp, Signal("reviews", "r", -6)])
    assert [s.id for s in out] == ["institute", "reviews"]
    assert out[0].weight == 15 and len(out[0].evidence) == 2
    assert [s.id for s in _merge_institute([mp])] == ["maps_institute"]
