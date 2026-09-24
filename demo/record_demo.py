"""Record the demo video: runs the app locally and drives it with Playwright.

    pip install playwright && python demo/record_demo.py
Output: demo/out/freshershield-demo.webm (convert with ffmpeg if needed).
Uses whatever is in the local SerpApi cache, so re-recording costs no credits.
"""
import sys
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "demo" / "out"
PORT = 8765

RESUME = """Akash Kumar - B.Tech Computer Science, 2026
Skills: Python, Django, SQL, Git, HTML, CSS, JavaScript, REST APIs, Data Structures and Algorithms
Projects: college placement portal (Django + PostgreSQL), weather bot (Python, REST APIs)"""

OFFER = """Congratulations!! You are shortlisted for Amazon Work From Home Data Entry job.
Earn Rs 3000 per day, no experience needed, no interview.
Pay Rs 1999 registration fee (100% refundable) to confirm your seat.
Limited slots. Contact HR Priya on WhatsApp 98xxxxxx21 today only."""


def caption(page, text):
    page.evaluate("""t => {
      let c = document.getElementById('demo-cap');
      if (!c) { c = document.createElement('div'); c.id = 'demo-cap';
        c.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:99;background:#1f6feb;color:#fff;padding:10px 18px;border-radius:10px;font:600 17px system-ui;box-shadow:0 6px 24px #0008;max-width:90%;text-align:center';
        document.body.appendChild(c); }
      c.textContent = t; }""", text)


def slow_type(page, sel, text, delay=12):
    page.click(sel)
    page.keyboard.type(text, delay=delay)


def main():
    from app.main import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    time.sleep(2)
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(viewport={"width": 1280, "height": 760}, record_video_dir=str(OUT), record_video_size={"width": 1280, "height": 760})
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{PORT}/")
        caption(pg, "FresherShield: find real first jobs in India, and spot scam postings before you apply")
        pg.wait_for_timeout(4500)

        caption(pg, "1. Paste your resume (or upload a PDF). Skills are extracted locally.")
        slow_type(pg, "#resumeText", RESUME, delay=4)
        pg.click("#resumeBtn")
        pg.wait_for_selector("#skills .chip")
        pg.wait_for_timeout(2500)

        caption(pg, "2. Live fresher jobs from Google Jobs via SerpApi (engine=google_jobs)")
        pg.fill("#role", "")
        slow_type(pg, "#role", "python developer", delay=60)
        pg.click("#searchBtn")
        pg.wait_for_selector(".job")
        pg.wait_for_timeout(1500)
        caption(pg, "Ranked by fresher fit. Each card shows your skill match: what you have and what's missing")
        pg.mouse.wheel(0, 380)
        pg.wait_for_timeout(4500)

        def check(company, cap, hold=7000):
            card = pg.locator(".job", has_text=company).first
            card.scroll_into_view_if_needed()
            caption(pg, cap)
            card.locator(".checkBtn").click()
            card.locator(".rep").wait_for()
            card.locator(".rep").scroll_into_view_if_needed()
            pg.mouse.wheel(0, 120)
            pg.wait_for_timeout(hold)

        check("Tradexa", "3. Scam check: Google + Bing complaint search and a legitimacy footprint, all via SerpApi")
        caption(pg, "Knowledge Graph, AmbitionBox reviews, MCA registry and own website: low risk, every signal linked")
        pg.wait_for_timeout(5000)
        check("Infosys BPM", "Big brands get flagged for impersonation (fake offer letters), not called scams")
        check("Java By Kiran", "A 'job' from a training institute: flagged, with a complaint about non-refundable fees")

        caption(pg, "4. Got an offer on WhatsApp? Paste it and check before you reply")
        pg.click("text=Check an offer I got")
        pg.wait_for_timeout(1200)
        slow_type(pg, "#offerCompany", "Amazon", delay=60)
        slow_type(pg, "#offerText", OFFER, delay=3)
        pg.click("#offerBtn")
        pg.wait_for_selector("#offerResult .rep")
        pg.locator("#offerResult .rep").scroll_into_view_if_needed()
        caption(pg, "Fee request + WhatsApp recruiter + no interview = high risk, and scammers are known to impersonate Amazon")
        pg.wait_for_timeout(9000)
        pg.mouse.wheel(0, 500)
        pg.wait_for_timeout(4000)

        caption(pg, "5. The scoring is open: every weight and rule is documented in the repo")
        pg.click("text=How it works")
        pg.wait_for_timeout(7000)
        caption(pg, "FresherShield - github.com/akashrajeev/FresherShield - built on SerpApi")
        pg.wait_for_timeout(4000)

        video = pg.video.path()
        ctx.close()
        b.close()
    final = OUT / "freshershield-demo.webm"
    Path(video).replace(final)
    print(final)
    server.should_exit = True


if __name__ == "__main__":
    main()
