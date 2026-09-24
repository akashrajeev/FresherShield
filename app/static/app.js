const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab,.panel").forEach((e) => e.classList.remove("active"));
    t.classList.add("active");
    $("#" + t.dataset.tab).classList.add("active");
  })
);

function meter(stats, account) {
  if (!stats) return;
  let txt = `SerpApi: ${stats.live_calls} live · ${stats.cache_hits} cached`;
  if (account && account.total_searches_left != null) txt += ` · ${account.total_searches_left} credits left`;
  if (stats.offline) txt += " · offline (cache only)";
  $("#meter").textContent = txt;
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

async function refreshStatus() {
  try { const s = await api("/api/status"); meter(s.stats, s.account); } catch (_) {}
}
refreshStatus();

// ---------------------------------------------------------------- resume
$("#resumeBtn").addEventListener("click", async () => {
  const fd = new FormData();
  const f = $("#resumeFile").files[0];
  if (f) fd.append("file", f);
  fd.append("text", $("#resumeText").value);
  $("#resumeBtn").disabled = true;
  try {
    const r = await api("/api/resume", { method: "POST", body: fd });
    $("#skills").innerHTML = r.skills.length
      ? r.skills.map((s) => `<span class="chip ok">${esc(s)}</span>`).join("")
      : `<span class="muted small">No skills recognised. Try pasting a skills line.</span>`;
    if (lastJobs) runSearch(); // re-score cached results with the resume (free, served from cache)
  } catch (e) {
    $("#skills").innerHTML = `<span class="flag">${esc(e.message)}</span>`;
  } finally { $("#resumeBtn").disabled = false; }
});

// ---------------------------------------------------------------- jobs
let lastJobs = null;
$("#searchBtn").addEventListener("click", runSearch);
$("#role").addEventListener("keydown", (e) => e.key === "Enter" && runSearch());

async function runSearch() {
  const role = $("#role").value.trim();
  if (!role) return;
  $("#searchBtn").disabled = true;
  $("#status").innerHTML = `<span class="spinner"></span>Searching Google Jobs via SerpApi…`;
  try {
    const q = new URLSearchParams({ role, location: $("#location").value.trim() || "India" });
    const r = await api("/api/jobs?" + q);
    lastJobs = r.jobs;
    meter(r.stats);
    $("#status").textContent = `${r.jobs.length} listings for “${r.query}” in ${r.location}, sorted by fresher fit.`;
    renderJobs(r.jobs);
    estimateScan();
  } catch (e) {
    $("#status").innerHTML = `<span class="flag">${esc(e.message)}</span>`;
  } finally { $("#searchBtn").disabled = false; refreshStatus(); }
}

function pill(v, good = 70, ok = 45) {
  if (v == null) return ["-", ""];
  const c = v >= good ? "var(--accent)" : v >= ok ? "var(--warn)" : "var(--bad)";
  return [v + "%", c];
}

function renderJobs(jobs) {
  const root = $("#results");
  root.innerHTML = "";
  jobs.forEach((j) => {
    const el = $("#jobTpl").content.firstElementChild.cloneNode(true);
    el.dataset.jobId = j.job_id;
    $(".title", el).textContent = j.title;
    $(".thumb", el).src = j.thumbnail || "";
    const bits = [j.company, j.location, j.via && "via " + j.via, j.posted_at, j.schedule_type, j.salary].filter(Boolean);
    $(".meta", el).textContent = bits.join(" · ");
    $(".flags", el).innerHTML = (j.quick_flags || []).map((f) => `<span class="flag">${esc(f)}</span>`).join("");
    const [fv, fc] = pill(j.fresher_score);
    $(".fit b", el).textContent = fv; $(".fit b", el).style.color = fc;
    $(".fit", el).title = (j.fresher_reasons || []).join("\n");
    if (j.match) {
      const [mv, mc] = pill(j.match.score, 60, 35);
      $(".match b", el).textContent = mv; $(".match b", el).style.color = mc;
      $(".skillrow", el).innerHTML =
        j.match.matched.map((s) => `<span class="chip ok">✓ ${esc(s)}</span>`).join("") +
        j.match.missing.map((s) => `<span class="chip miss">+ ${esc(s)}</span>`).join("");
    } else {
      $(".match b", el).textContent = "-";
      $(".match", el).title = "Add your resume to see your match";
    }
    const links = j.apply_options || [];
    if (links.length) { $(".apply", el).href = links[0].link; $(".apply", el).textContent = `Apply via ${links[0].title}` + (links.length > 1 ? ` (+${links.length - 1})` : ""); }
    else $(".apply", el).remove();
    $(".desc", el).textContent = j.description;
    $(".descBtn", el).addEventListener("click", () => $(".desc", el).classList.toggle("hidden"));
    $(".checkBtn", el).addEventListener("click", async (ev) => {
      const b = ev.currentTarget;
      b.disabled = true;
      $(".report", el).innerHTML = `<span class="muted"><span class="spinner"></span>Cross-checking “${esc(j.company)}” on Google, Bing, Maps and News…</span>`;
      try {
        const r = await runCheck($(".report", el), { job_id: j.job_id });
        meter(r.stats);
      } catch (e) {
        $(".report", el).innerHTML = `<span class="flag">${esc(e.message)}</span>`;
      } finally { b.disabled = false; refreshStatus(); }
    });
    root.appendChild(el);
  });
}

// ---------------------------------------------------------------- scan all listings
// Before scanning, ask the server what it would cost: companies already in the local cache
// are free, and a company that appears twice is only searched once.
const SCAN_MAX = 10;
let scanPlan = null;

function scanIds() { return (lastJobs || []).slice(0, SCAN_MAX).map((j) => j.job_id); }

async function estimateScan() {
  const ids = scanIds();
  $("#scanBar").classList.toggle("hidden", !ids.length);
  if (!ids.length) return;
  $("#scanEst").textContent = "Working out the cost…";
  try {
    scanPlan = await api("/api/check-batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_ids: ids, dry_run: true }) });
    const p = scanPlan;
    const n = (k, w) => `${k} ${w}${k === 1 ? "" : "s"}`;
    let t = `${n(p.jobs, "listing")}, ${n(p.companies, "company").replace("companys", "companies")}. `;
    t += p.searches ? `Uses about ${n(p.searches, "SerpApi search").replace("searchs", "searches")}${p.cached ? ` (${p.cached} already cached)` : ""}` : "All cached: free";
    if (p.credits_left != null) t += `. ${p.credits_left} credits left`;
    if (!p.affordable) t += p.offline ? ". Offline: some companies have no cached results" : ". Not enough credits for all of them";
    $("#scanEst").textContent = t + ".";
  } catch (e) { $("#scanEst").textContent = e.message; }
}

$("#scanBtn").addEventListener("click", async () => {
  const ids = scanIds();
  if (!ids.length) return;
  if (scanPlan && scanPlan.searches > 0 && !confirm(`This will use about ${scanPlan.searches} SerpApi searches. Continue?`)) return;
  const b = $("#scanBtn");
  b.disabled = true;
  const cards = ids.map((id) => document.querySelector(`[data-job-id="${CSS.escape(id)}"]`)).filter(Boolean);
  cards.forEach((el) => { $(".report", el).innerHTML = `<span class="muted"><span class="spinner"></span>Checking…</span>`; });
  try {
    const r = await api("/api/check-batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_ids: ids, lang: langSel.value }) });
    meter(r.stats);
    const counts = { high: 0, caution: 0, low: 0, unknown: 0 };
    cards.forEach((el) => {
      const rep = r.reports[el.dataset.jobId];
      const box = $(".report", el);
      if (!rep) { box.innerHTML = ""; return; }
      box.dataset.req = JSON.stringify({ job_id: el.dataset.jobId });
      box.innerHTML = renderReport(rep);
      counts[rep.level] = (counts[rep.level] || 0) + 1;
    });
    $("#scanEst").textContent = `Scanned ${cards.length}: ${counts.high} high risk, ${counts.caution} caution, ${counts.low} low risk${counts.unknown ? `, ${counts.unknown} unknown` : ""}.`;
    scanPlan = null;
  } catch (e) {
    $("#scanEst").textContent = e.message;
  } finally { b.disabled = false; refreshStatus(); }
});

// ---------------------------------------------------------------- report language + export
const langSel = $("#lang");
langSel.value = localStorage.getItem("fs-lang") || "en";
const shareTexts = new Map(); // report element id -> plain-text report
let repSeq = 0;

// Render a report into `box` and remember the request, so switching language can re-ask
// the server. Re-checks hit the local cache, so a language switch costs no SerpApi credits.
async function runCheck(box, body) {
  const r = await api("/api/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, lang: langSel.value }) });
  box.dataset.req = JSON.stringify(body);
  box.innerHTML = renderReport(r.report);
  return r;
}

langSel.addEventListener("change", async () => {
  localStorage.setItem("fs-lang", langSel.value);
  document.documentElement.lang = langSel.value;
  for (const box of document.querySelectorAll("[data-req]")) {
    try { await runCheck(box, JSON.parse(box.dataset.req)); } catch (_) {}
  }
  refreshStatus();
});
document.documentElement.lang = langSel.value;

document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-act]");
  if (!b) return;
  const rep = b.closest(".rep");
  const text = shareTexts.get(rep.id) || "";
  if (b.dataset.act === "copy") {
    try { await navigator.clipboard.writeText(text); } catch (_) {
      const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove();
    }
    const old = b.textContent; b.textContent = "✓ " + b.dataset.done; setTimeout(() => (b.textContent = old), 1600);
  } else if (b.dataset.act === "print") {
    document.body.classList.add("printing"); rep.classList.add("print-target");
    window.print();
    document.body.classList.remove("printing"); rep.classList.remove("print-target");
  }
});

function renderReport(r) {
  const ui = r.ui || {};
  const id = "rep" + ++repSeq;
  shareTexts.set(id, r.share_text || "");
  const sigs = r.signals.map((s) => {
    const cls = s.weight > 0 ? "pos" : s.weight < 0 ? "neg" : "";
    const ev = (s.evidence || []).filter((e) => e.link).map((e) => `<a href="${esc(e.link)}" target="_blank" rel="noopener" title="${esc(e.snippet || "")}">${esc(e.source || "source")}${e.engine ? " (" + esc(e.engine) + ")" : ""}: ${esc((e.title || "").slice(0, 60))}</a>`).join("");
    return `<div class="sig"><span class="w ${cls}">${s.weight > 0 ? "+" : ""}${s.weight}</span><span>${esc(s.label)}${s.detail ? `<span class="det">${esc(s.detail)}</span>` : ""}${ev ? `<span class="ev">${ev}</span>` : ""}</span></div>`;
  }).join("");
  const wa = "https://wa.me/?text=" + encodeURIComponent(r.share_text || "");
  return `<div class="rep ${r.level}" id="${id}" lang="${esc(r.lang || "en")}">
    <div class="printhead">🛡️ FresherShield · ${esc(r.company || ui.pasted || "")}</div>
    <div class="rephead"><span class="badge ${r.level}">${esc(r.level_label || r.level)}</span>
      <div class="gauge"><i style="width:${r.risk_score}%"></i></div><b title="${esc(ui.score || "")}">${r.risk_score}/100</b></div>
    <p style="margin:8px 0 6px">${esc(r.headline)}</p>
    ${sigs}
    <div class="engines">${esc(ui.engines || "Engines queried")}: ${r.engines_used.length ? r.engines_used.join(", ") : esc(ui.engines_none || "none")}${r.errors.length ? " · " + esc(r.errors.join("; ")) : ""}</div>
    <div class="repactions">
      <button class="secondary small" data-act="copy" data-done="${esc(ui.copied || "Copied")}">${esc(ui.copy || "Copy as text")}</button>
      <a class="wa small" href="${wa}" target="_blank" rel="noopener">${esc(ui.whatsapp || "Share on WhatsApp")}</a>
      <button class="secondary small" data-act="print">${esc(ui.print || "Print")}</button>
    </div>
    <div class="printfoot">${esc(ui.footer || "")}</div>
  </div>`;
}

// ---------------------------------------------------------------- pasted offer
$("#offerBtn").addEventListener("click", async () => {
  const text = $("#offerText").value.trim();
  const company = $("#offerCompany").value.trim();
  const file = $("#offerFile").files[0];
  if (file) return checkOfferFile(file, company);
  if (!text && !company) return;
  $("#offerBtn").disabled = true;
  $("#offerResult").innerHTML = `<p class="muted"><span class="spinner"></span>Checking the message${company ? " and cross-searching “" + esc(company) + "”" : ""}…</p>`;
  try {
    $("#offerResult").innerHTML = `<div class="offerRep" style="margin-top:12px"></div>`;
    const r = await runCheck($("#offerResult .offerRep"), { offer_text: text, company, use_web: !!company });
    meter(r.stats);
  } catch (e) {
    $("#offerResult").innerHTML = `<span class="flag">${esc(e.message)}</span>`;
  } finally { $("#offerBtn").disabled = false; refreshStatus(); }
});

// Offer letter PDF: the server extracts the text and guesses the company if the box is empty.
async function checkOfferFile(file, company) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("company", company);
  fd.append("lang", langSel.value);
  $("#offerBtn").disabled = true;
  $("#offerResult").innerHTML = `<p class="muted"><span class="spinner"></span>Reading ${esc(file.name)}…</p>`;
  try {
    const r = await api("/api/check-file", { method: "POST", body: fd });
    if (!company && r.company_guess) $("#offerCompany").value = r.company_guess;
    $("#offerResult").innerHTML = `<div class="offerRep" style="margin-top:12px">${renderReport(r.report)}</div>`;
    meter(r.stats);
  } catch (e) {
    $("#offerResult").innerHTML = `<span class="flag">${esc(e.message)}</span>`;
  } finally { $("#offerBtn").disabled = false; refreshStatus(); }
}
