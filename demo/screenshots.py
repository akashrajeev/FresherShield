"""Capture the README screenshots: runs the app locally and drives it with Playwright.

    pip install playwright && playwright install chromium && python demo/screenshots.py
Writes PNGs to docs/screenshots/. Uses the local SerpApi cache, so re-running costs
no credits once the searches below have been made once.
"""
import sys
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "screenshots"
PORT = 8766

RESUME = "B.Tech Computer Science, 2026. Skills: Python, Django, SQL, Git, HTML, CSS, JavaScript, REST APIs"
# A composite of common fee-scam messages; the company name is invented (see docs/EXAMPLES.md).
OFFER_COMPANY = "Quikhire Global Staffing"
OFFER = """Congratulations!! You are shortlisted for Work From Home Data Entry job at Quikhire Global Staffing.
Salary Rs 45,000/month, no experience needed, no interview, direct joining.
Pay Rs 1,999 registration fee (100% refundable) to confirm your seat. Limited slots.
Contact HR Neha on WhatsApp 98xxxxxx21 or quikhire.hr@gmail.com today only."""


def serve():
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(2.5)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1.5)
        pg.goto(f"http://127.0.0.1:{PORT}/")
        pg.evaluate("localStorage.setItem('fs-lang','en')")
        pg.reload()
        pg.wait_for_load_state("networkidle")

        # 1) job search with resume match
        pg.fill("#resumeText", RESUME)
        pg.click("#resumeBtn")
        pg.wait_for_selector("#skills .chip")
        pg.click("#searchBtn")
        pg.wait_for_selector(".job", timeout=60000)
        time.sleep(1)
        pg.screenshot(path=str(OUT / "jobs.png"))

        # 2) scam report on a real listing
        first = pg.locator(".job").first
        first.locator(".checkBtn").click()
        first.locator(".rep").wait_for(timeout=90000)
        first.scroll_into_view_if_needed()
        time.sleep(0.8)
        first.screenshot(path=str(OUT / "job-report.png"))

        # 3) pasted scam offer
        pg.click("button[data-tab=offer]")
        pg.fill("#offerCompany", OFFER_COMPANY)
        pg.fill("#offerText", OFFER)
        pg.click("#offerBtn")
        pg.wait_for_selector("#offerResult .rep", timeout=90000)
        time.sleep(0.8)
        pg.locator("#offer").screenshot(path=str(OUT / "offer-report.png"))

        # 4) same report in Hindi (served from cache)
        pg.select_option("#lang", "hi")
        pg.wait_for_function("document.querySelector('#offerResult .rep')?.getAttribute('lang') === 'hi'", timeout=30000)
        time.sleep(1.5)
        pg.locator("#offerResult .rep").screenshot(path=str(OUT / "offer-report-hi.png"))
        pg.select_option("#lang", "ml")
        pg.wait_for_function("document.querySelector('#offerResult .rep')?.getAttribute('lang') === 'ml'", timeout=30000)
        time.sleep(1.5)
        pg.locator("#offerResult .rep").screenshot(path=str(OUT / "offer-report-ml.png"))

        # 5) print view of the Hindi report, as a PDF-style page image
        pg.select_option("#lang", "hi")
        pg.wait_for_function("document.querySelector('#offerResult .rep')?.getAttribute('lang') === 'hi'", timeout=30000)
        pg.evaluate("document.body.classList.add('printing'); document.querySelector('#offerResult .rep').classList.add('print-target')")
        pg.emulate_media(media="print")
        time.sleep(0.8)
        pg.screenshot(path=str(OUT / "print-hi.png"))
        b.close()
    print("saved to", OUT)


if __name__ == "__main__":
    main()
