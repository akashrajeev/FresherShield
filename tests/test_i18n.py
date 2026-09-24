"""Hindi/Malayalam report translations and the plain-text export (no network, no credits)."""
from fastapi.testclient import TestClient

from app import main
from app.i18n import DETAILS, HEADLINES, LABELS, LEVELS, UI, share_text, translate_report
from app.jobs import Job
from app.scam import HEADLINES as EN_HEADLINES, assess, maps_signals, posting_signals
from tests.test_core import FakeClient

SCAM_TEXT = ("Congratulations! Work from home data entry job. Earn Rs 3000 per day, no interview. "
             "Pay Rs 1999 registration fee (refundable). WhatsApp HR on 9876543210.")


def _scam_report():
    fc = FakeClient({})
    return assess(fc, Job("pasted", "", "QuickEarn Solutions", "", "", SCAM_TEXT), "QuickEarn Solutions").to_dict()


def test_every_language_covers_every_level_headline_and_ui_string():
    for lang in ("hi", "ml"):
        assert set(LEVELS[lang]) == set(LEVELS["en"])
        assert set(HEADLINES[lang]) == set(EN_HEADLINES)
        assert set(UI[lang]) == set(UI["en"])
        assert set(DETAILS[lang]) <= set(LABELS[lang])


def test_every_signal_the_engine_can_emit_has_a_translation():
    ids = {s.id for s in posting_signals(Job("1", "t", "Confidential", "", "", SCAM_TEXT + " test@gmail.com hurry, limited seats"))}
    ids |= {s.id for s in maps_signals("Star Manpower", [{"title": "Star Manpower", "type": "Employment agency", "reviews": 3}])}
    ids |= {s.id for s in maps_signals("CodeGuru Academy", [{"title": "CodeGuru Academy", "type": "Training institute"}])}
    ids |= {"boards", "unknown_apply", "no_apply", "web_scam", "complaint_sites", "impersonation", "web_clean", "kg",
            "reviews", "registry", "official_site", "institute", "no_footprint", "maps_absent",
            "lookalike_domain", "own_domain", "brand_free_mail", "news_fraud", "news_impersonation"}
    for lang in ("hi", "ml"):
        assert ids <= set(LABELS[lang]), ids - set(LABELS[lang])


def test_hindi_report_translates_labels_and_keeps_numbers():
    rep = _scam_report()
    hi = translate_report(rep, "hi")
    assert hi["level_label"] == "ज़्यादा जोखिम" and hi["headline"].startswith("पहले पैसे")
    fee = next(s for s in hi["signals"] if s["id"] == "fee")
    assert "फ़ीस" in fee["label"] and fee["weight"] == 35
    assert hi["risk_score"] == rep["risk_score"] and rep["signals"][0]["label"].startswith("Asks for money")  # original untouched


def test_malayalam_fills_params_into_labels():
    sig = maps_signals("Tradexa", [{"title": "Tradexa", "reviews": 41, "rating": 4.6}])[0]
    rep = {"company": "Tradexa", "level": "low", "risk_score": 10, "headline": "x", "headline_key": "low_clean",
           "headline_params": {}, "signals": [{"id": sig.id, "label": sig.label, "weight": sig.weight, "detail": "", "evidence": [], "params": sig.params}]}
    ml = translate_report(rep, "ml")
    assert ml["signals"][0]["label"] == "Google Maps-ൽ 1 ലിസ്റ്റിംഗ് ★ 4.6/5 · 41"


def test_unknown_language_falls_back_to_english():
    rep = _scam_report()
    assert translate_report(rep, "fr")["headline"] == rep["headline"]


def test_share_text_is_whatsapp_ready():
    txt = share_text(_scam_report(), "en")
    assert txt.startswith("🛡️ FresherShield: QuickEarn Solutions")
    assert "HIGH RISK" in txt and "(+35)" in txt and "1930" in txt and "github.com/akashrajeev/FresherShield" in txt
    assert "पैसे न दें" in share_text(_scam_report(), "hi")


def test_check_endpoint_returns_localized_report_and_share_text(monkeypatch):
    monkeypatch.setattr(main, "client", FakeClient({}))
    r = TestClient(main.app).post("/api/check", json={"company": "QuickEarn Solutions", "offer_text": SCAM_TEXT, "lang": "ml"})
    assert r.status_code == 200
    rep = r.json()["report"]
    assert rep["lang"] == "ml" and rep["level_label"] == "ഉയർന്ന അപകടസാധ്യത"
    assert rep["share_text"].startswith("🛡️ FresherShield") and "ഫലം" in rep["share_text"]
