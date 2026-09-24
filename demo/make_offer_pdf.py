"""Build demo/sample-offer-letter.pdf: a fake offer letter for the demo and for trying the upload.

The company name is invented and the letter combines common fee-scam patterns
(security deposit, no interview, 24-hour deadline, gmail HR). Run: python demo/make_offer_pdf.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "sample-offer-letter.pdf"

HTML = """<html><body style="font:14px/1.6 Georgia,serif;color:#222;margin:70px 80px">
<div style="font:bold 22px Georgia;letter-spacing:.04em">BRIGHTWAVE INFOTECH PRIVATE LIMITED</div>
<div style="color:#666;font-size:12px">Plot 14, Sector 5, Noida, Uttar Pradesh &nbsp;·&nbsp; brightwave.hr.dept@gmail.com</div>
<hr style="margin:18px 0 28px">
<div style="font:bold 16px Georgia;text-align:center;margin-bottom:24px">OFFER LETTER</div>
<p>Date: 22 September 2026</p>
<p>Dear Candidate,</p>
<p>Congratulations! Based on your profile, Brightwave Infotech Private Limited is pleased to offer you the
post of <b>Trainee Software Engineer</b>. You have been selected directly, and no interview is required.</p>
<p>Your salary will be <b>Rs 65,000 per month</b> during training.</p>
<p>To confirm your joining, please pay a <b>refundable security deposit of Rs 4,500</b> within 24 hours.
The amount will be returned with your first salary. Seats are limited and this offer will lapse if the
deposit is not received today.</p>
<p>For payment details contact our HR team on WhatsApp.</p>
<p style="margin-top:36px">Regards,<br>HR Department<br>Brightwave Infotech Private Limited</p>
</body></html>"""

if __name__ == "__main__":
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(HTML)
        pg.pdf(path=str(OUT), format="A4")
        b.close()
    print(OUT)
