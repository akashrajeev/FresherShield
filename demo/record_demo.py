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

sys.path.insert(0, str(ROOT / "demo"))
from screenshots import OFFER, OFFER_COMPANY  # noqa: E402  (same invented scam offer as the README)

LETTER_PDF = ROOT / "demo" / "sample-offer-letter.pdf"  # built by demo/make_offer_pdf.py

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


T0 = [None]
MARKS = []
LINES = {}  # voiceover line number -> start time (s since page open)
GAP = 0.9  # silence after each voiceover line


def vo_durations():
    """Durations of demo/vo/lineN.wav if present (voiceover build), else {}."""
    import subprocess
    out = {}
    vo = ROOT / "demo" / "vo"
    for f in sorted(vo.glob("line*.wav")) if vo.exists() else []:
        n = int(f.stem[4:])
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout
        out[n] = float(d)
    return out


VO = vo_durations()


def line(n):
    """Start voiceover line n, first holding until line n-1 has finished."""
    prev = n - 1
    if prev in LINES and prev in VO:
        wait = LINES[prev] + VO[prev] + GAP - (time.monotonic() - T0[0])
        if wait > 0:
            time.sleep(wait)
    LINES[n] = round(time.monotonic() - T0[0], 2)
    mark(f"line {n}")


def mark(label):
    if T0[0] is not None:
        MARKS.append((round(time.monotonic() - T0[0], 2), label))


def caption(page, text):
    mark("caption: " + text)
    page.evaluate("""([t, css]) => {
      let c = document.getElementById('demo-cap');
      if (!c) { c = document.createElement('div'); c.id = 'demo-cap';
        c.style.cssText = css; document.body.appendChild(c); }
      c.textContent = t; }""", [text, CAPTION_CSS])


def overlay(page, inner_html):
    mark("overlay")
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
  <div style="font:400 15px/1.6 Inter,system-ui;color:#9aa1a9;margin-top:26px;max-width:560px">Live fresher jobs from Google Jobs, matched to your resume and cross-checked for scams on Google, Bing, Google Maps and Google News.</div>
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
        pg.on("dialog", lambda d: d.accept())
        T0[0] = time.monotonic()
        pg.goto(f"http://127.0.0.1:{PORT}/")
        pg.wait_for_timeout(1200)  # let fonts settle before the title card
        line(1)
        overlay(pg, TITLE_CARD)
        pg.wait_for_timeout(5000)
        line(2)
        clear_overlay(pg)

        caption(pg, "1. Paste your resume (or upload a PDF). Skills are read in the session, nothing is stored")
        slow_type(pg, "#resumeText", RESUME, delay=4)
        pg.click("#resumeBtn")
        pg.wait_for_selector("#skills .chip")
        pg.wait_for_timeout(2000)

        line(3)
        caption(pg, "2. Live fresher jobs from Google Jobs via SerpApi (engine=google_jobs)")
        pg.fill("#role", "")
        slow_type(pg, "#role", "python developer", delay=60)
        pg.click("#searchBtn")
        pg.wait_for_selector(".job")
        pg.wait_for_timeout(1500)
        caption(pg, "Ranked by fresher fit. Each card shows your skill match: what you have, and what's missing")
        pg.mouse.wheel(0, 380)
        pg.wait_for_timeout(3500)

        line(4)
        pg.locator("#scanBar").scroll_into_view_if_needed()
        pg.mouse.wheel(0, -160)
        pg.wait_for_function("document.querySelector('#scanEst').textContent.includes('listing')")
        caption(pg, "3. Scan the top 10 at once. The cost in SerpApi searches is shown before anything is spent")
        pg.hover("#scanBtn")
        pg.wait_for_timeout(4500)
        pg.click("#scanBtn")  # the confirm() prompt is accepted by the dialog handler
        pg.wait_for_function("document.querySelector('#scanEst').textContent.startsWith('Scanned')", timeout=180000)
        caption(pg, "Asks before spending, then checks each company once. Here: the tally for all 10")
        pg.wait_for_timeout(3000)

        def show(company, cap, hold=6500, scroll=140):
            card = pg.locator(".job", has_text=company).first
            card.locator(".rep").scroll_into_view_if_needed()
            pg.mouse.wheel(0, scroll)
            caption(pg, cap)
            pg.wait_for_timeout(hold)

        line(5)
        show("Tradexa", "Five SerpApi searches per company: Google + Bing complaints, footprint, Google Maps, Google News")
        caption(pg, "Maps: a real office with reviews. News: no fake-job racket reports. Every signal is linked")
        pg.wait_for_timeout(4000)
        line(6)
        show("Infosys BPM", "Big brands get flagged for impersonation (fake offer letters in their name), not called scams")

        line(7)
        caption(pg, "4. Got an offer on WhatsApp? Paste it (English, Hindi or Hinglish) and check before you reply")
        pg.click("text=Check an offer I got")
        pg.wait_for_timeout(1000)
        slow_type(pg, "#offerCompany", OFFER_COMPANY, delay=45)
        slow_type(pg, "#offerText", OFFER, delay=3)
        pg.click("#offerBtn")
        pg.wait_for_selector("#offerResult .rep")
        pg.locator("#offerResult .rep").scroll_into_view_if_needed()
        line(8)
        caption(pg, "Fee + no interview + WhatsApp HR. And ₹45,000/month for data entry is over twice the usual fresher pay")
        pg.wait_for_timeout(7000)
        pg.mouse.wheel(0, 300)
        pg.wait_for_timeout(3000)

        line(9)
        caption(pg, "5. The same report in Hindi or Malayalam, ready to share on WhatsApp with family")
        pg.select_option("#lang", "hi")
        pg.wait_for_function("document.querySelector('#offerResult .rep')?.getAttribute('lang') === 'hi'", timeout=30000)
        pg.locator("#offerResult .rep").scroll_into_view_if_needed()
        pg.wait_for_timeout(3500)
        pg.locator("#offerResult .wa").hover()
        pg.wait_for_timeout(2500)
        pg.select_option("#lang", "en")
        pg.wait_for_function("document.querySelector('#offerResult .rep')?.getAttribute('lang') === 'en'", timeout=30000)

        line(10)
        caption(pg, "6. Or upload the offer letter PDF. It reads the letter and finds the company name itself")
        pg.locator("#offerCompany").scroll_into_view_if_needed()
        pg.mouse.wheel(0, -200)
        pg.fill("#offerCompany", "")
        pg.fill("#offerText", "")
        pg.set_input_files("#offerFile", str(LETTER_PDF))
        pg.wait_for_timeout(1200)
        pg.click("#offerBtn")
        pg.wait_for_selector("#offerResult .rep", timeout=120000)
        pg.wait_for_function("document.querySelector('#offerCompany').value.length > 0")
        pg.wait_for_timeout(2000)
        pg.locator("#offerResult .rep").scroll_into_view_if_needed()
        pg.wait_for_timeout(4000)

        line(11)
        caption(pg, "Every rule and weight is documented. On 40 labelled offers: 20/20 scams caught, 1 false alarm")
        pg.click("text=How it works")
        pg.wait_for_timeout(6000)
        line(12)
        caption(pg, "")
        overlay(pg, END_CARD)
        pg.wait_for_timeout(int(max(4.5, VO.get(12, 0) + 1.5) * 1000))

        mark("end")
        (OUT / "timeline.tsv").write_text("".join(f"{t}\t{l}\n" for t, l in MARKS))
        (OUT / "vo_starts.tsv").write_text("".join(f"{n}\t{t}\n" for n, t in sorted(LINES.items())))
        video = pg.video.path()
        ctx.close()
        b.close()
    final = OUT / "freshershield-demo.webm"
    Path(video).replace(final)
    print(final)
    server.should_exit = True


if __name__ == "__main__":
    main()
