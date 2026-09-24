from app.jobs import Job
from app.scam import pay_signal, stated_pay


def job(title, text):
    return Job("x", title, "Acme", "", "", text)


def test_stated_pay_units():
    assert stated_pay("Salary ₹45,000 per month")[0] == 540000
    assert stated_pay("CTC ₹12 LPA")[0] == 1200000
    assert stated_pay("Stipend 25k per month")[0] == 300000
    assert stated_pay("Rs 1.2 lakh per month")[0] == 1440000
    assert stated_pay("pay Rs 1,500 processing fee") is None  # small sums are not salaries


def test_data_entry_high_pay_is_flagged_against_role_band():
    s = pay_signal(job("Data Entry Operator", "Work from home. Salary ₹45,000 per month. No experience."))
    assert s.id == "pay_role" and s.weight == 20
    assert s.params["role"] == "data entry" and s.params["stated"] == "₹5.4 LPA"
    assert s.evidence and s.evidence[0]["link"].startswith("https://")


def test_normal_pay_is_not_flagged():
    assert pay_signal(job("Telecaller", "Salary Rs 18,000/month")) is None
    assert pay_signal(job("Software Engineer", "CTC ₹12 LPA for 2026 graduates")) is None


def test_product_company_pay_needs_to_be_extreme():
    assert pay_signal(job("Software Engineer", "CTC ₹24 LPA")) is None
    assert pay_signal(job("Software Engineer", "CTC ₹40 LPA for freshers")).id == "pay_role"


def test_unknown_role_uses_generic_cap_and_per_day_pitch():
    assert pay_signal(job("Associate", "Package ₹20 LPA")).id == "pay"
    assert pay_signal(job("", "Part time kaam, mobile se daily 3000 kamai.")).id == "pay"
