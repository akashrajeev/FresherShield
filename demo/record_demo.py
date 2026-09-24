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

CAPTION_CSS = (
    "position:fixed;left:36px;bottom:30px;z-index:98;"
    "background:rgba(22,24,29,.94);color:#f7f5f0;"
    "padding:13px 20px 13px 17px;border-left:3px solid #2f9c82;border-radius:6px;"
    "font:500 16px/1.5 Inter,system-ui,sans-serif;max-width:620px;text-align:left;"
    "box-shadow:0 10px 30px rgba(0,0,0,.28)"
)

OVERLAY_CSS = (
    "position:fixed;inset:0;z-index:999;display:flex;flex-direction:column;"
    "align-items:center;justify-content:center;background:#16181d;color:#f7f5f0;"
    "font-family:Inter,system-ui,sans-serif;text-align:center;padding:0 90px"
)


def caption(page, text):
    page.evaluate("""([t, css]) => {
      let c = document.getElementById('demo-cap');
      if (!c) { c = document.createElement('div'); c.id = 'demo-cap';
        c.style.cssText = css; document.body.appendChild(c); }
      c.textContent = t; }""", [text, CAPTION_CSS])


def overlay(page, inner_html):
    page.evaluate("""([h, css]) => {
      let o = document.getElementById('demo-ovl');
      if (!o) { o = document.createElement('div'); o.id = 'demo-ovl';
        o.style.cssText = css; document.body.appendChild(o); }
      o.innerHTML = h; o.style.display = 'flex'; }""", [inner_html, OVERLAY_CSS])


def clear_overlay(page):
    page.evaluate("() => { const o = document.getElementById('demo-ovl'); if (o) o.style.display = 'none'; }")


def slow_type(page, sel, text, delay=12):
    page.click(sel)
    page.keyboard.type(text, delay=delay)


TITLE_CARD = """
  <div style="font:600 13px Inter,system-ui;letter-spacing:.22em;color:#2f9c82;margin-bottom:22px">SERPAPI INDIA HACKATHON 2026</div>
  <div style="font:600 52px/1.15 Fraunces,Georgia,serif;letter-spacing:-.01em;max-width:820px">FresherShield</div>
  <div style="font:500 21px/1.5 Fraunces,Georgia,serif;color:#c9c4b8;margin-top:14px;max-width:700px">Find a real first job. Dodge the fake ones.</div>
  <div style="font:400 15px/1.6 Inter,system-ui;color:#9aa1a9;margin-top:26px;max-width:560px">Live fresher jobs from Google Jobs, matched to your resume and cross-checked for scams on Google and Bing.</div>
"""

END_CARD = """
  <div style="font:600 44px/1.15 Fraunces,Georgia,serif;letter-spacing:-.01em">FresherShield</div>
  <div style="font:500 16px Inter,system-ui;color:#c9c4b8;margin-top:16px">github.com/akashrajeev/FresherShield</div>
  <div style="font:400 13.5px Inter,system-ui;color:#9aa1a9;margin-top:10px;letter-spacing:.06em">BUILT ON SERPAPI &nbsp;·&nbsp; KNOWLEDGE &amp; PUBLIC INTEREST TRACK</div>
"""


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
        pg.wait_for_timeout(1200)  # let fonts settle before the title card
        overlay(pg, TITLE_CARD)
        pg.wait_for_timeout(5000)
        clear_overlay(pg)

        caption(pg, "1. Paste your resume (or upload a PDF) — skills are read locally, nothing leaves the session")
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
        caption(pg, "Ranked by fresher fit — each card shows your skill match: what you have, and what's missing")
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

        check("Tradexa", "3. Scam check: Google + Bing complaint search plus a legitimacy footprint, all via SerpApi")
        caption(pg, "Knowledge Graph, AmbitionBox reviews, MCA registry and its own website — low risk, every signal linked")
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

        caption(pg, "5. The scoring is open — every weight and rule is documented in the repo")
        pg.click("text=How it works")
        pg.wait_for_timeout(6500)
        caption(pg, "")
        overlay(pg, END_CARD)
        pg.wait_for_timeout(4500)

        video = pg.video.path()
        ctx.close()
        b.close()
    final = OUT / "freshershield-demo.webm"
    Path(video).replace(final)
    print(final)
    server.should_exit = True


if __name__ == "__main__":
    main()
