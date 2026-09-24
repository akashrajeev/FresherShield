"""Offer-letter upload: text extraction, company guess, report (no network)."""
from fastapi.testclient import TestClient

from app import main
from app.main import guess_company
from tests.test_core import FakeClient

LETTER = """OFFER LETTER
Brightwave Infotech Private Limited
Dear Candidate, Congratulations! Brightwave Infotech Private Limited is pleased to offer you the post of Trainee.
To confirm, pay a refundable security deposit of Rs 4,500 within 24 hours. No interview required.
HR Department, Brightwave Infotech Private Limited"""


def test_guess_company_picks_the_repeated_legal_name():
    assert guess_company(LETTER) == "Brightwave Infotech Private Limited"
    assert guess_company("hello there") == ""


def test_check_file_endpoint_with_text_letter(monkeypatch):
    fc = FakeClient({})
    monkeypatch.setattr(main, "client", fc)
    r = TestClient(main.app).post("/api/check-file", files={"file": ("offer.txt", LETTER.encode(), "text/plain")}, data={"lang": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["company_guess"] == "Brightwave Infotech Private Limited"
    ids = {s["id"] for s in body["report"]["signals"]}
    assert {"fee", "no_interview"} <= ids and body["report"]["level"] == "high" and body["report"]["lang"] == "hi"
    assert any("Brightwave Infotech" in (c[1] or "") for c in fc.calls)  # searched by short name


def test_check_file_rejects_empty(monkeypatch):
    monkeypatch.setattr(main, "client", FakeClient({}))
    r = TestClient(main.app).post("/api/check-file", files={"file": ("x.txt", b"   ", "text/plain")})
    assert r.status_code == 400
