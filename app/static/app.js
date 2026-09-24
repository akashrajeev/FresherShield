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
      $(".report", el).innerHTML = `<span class="muted"><span class="spinner"></span>Cross-checking “${esc(j.company)}” on Google + Bing…</span>`;
      try {
        const r = await api("/api/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: j.job_id }) });
        $(".report", el).innerHTML = renderReport(r.report);
        meter(r.stats);
      } catch (e) {
        $(".report", el).innerHTML = `<span class="flag">${esc(e.message)}</span>`;
      } finally { b.disabled = false; refreshStatus(); }
    });
    root.appendChild(el);
  });
}

function renderReport(r) {
  const sigs = r.signals.map((s) => {
    const cls = s.weight > 0 ? "pos" : s.weight < 0 ? "neg" : "";
    const ev = (s.evidence || []).filter((e) => e.link).map((e) => `<a href="${esc(e.link)}" target="_blank" rel="noopener" title="${esc(e.snippet || "")}">${esc(e.source || "source")}${e.engine ? " (" + esc(e.engine) + ")" : ""}: ${esc((e.title || "").slice(0, 60))}</a>`).join("");
    return `<div class="sig"><span class="w ${cls}">${s.weight > 0 ? "+" : ""}${s.weight}</span><span>${esc(s.label)}${s.detail ? `<span class="det">${esc(s.detail)}</span>` : ""}${ev ? `<span class="ev">${ev}</span>` : ""}</span></div>`;
  }).join("");
  return `<div class="rep ${r.level}">
    <div class="rephead"><span class="badge ${r.level}">${r.level === "low" ? "low risk" : r.level === "caution" ? "caution" : r.level === "high" ? "high risk" : "unknown"}</span>
      <div class="gauge"><i style="width:${r.risk_score}%"></i></div><b>${r.risk_score}/100</b></div>
    <p style="margin:8px 0 6px">${esc(r.headline)}</p>
    ${sigs}
    <div class="engines">Engines queried: ${r.engines_used.length ? r.engines_used.join(", ") : "none (posting text only)"}${r.errors.length ? " · " + esc(r.errors.join("; ")) : ""}</div>
  </div>`;
}

// ---------------------------------------------------------------- pasted offer
$("#offerBtn").addEventListener("click", async () => {
  const text = $("#offerText").value.trim();
  const company = $("#offerCompany").value.trim();
  if (!text && !company) return;
  $("#offerBtn").disabled = true;
  $("#offerResult").innerHTML = `<p class="muted"><span class="spinner"></span>Checking the message${company ? " and cross-searching “" + esc(company) + "”" : ""}…</p>`;
  try {
    const r = await api("/api/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ offer_text: text, company, use_web: !!company }) });
    $("#offerResult").innerHTML = `<div style="margin-top:12px">${renderReport(r.report)}</div>`;
    meter(r.stats);
  } catch (e) {
    $("#offerResult").innerHTML = `<span class="flag">${esc(e.message)}</span>`;
  } finally { $("#offerBtn").disabled = false; refreshStatus(); }
});
