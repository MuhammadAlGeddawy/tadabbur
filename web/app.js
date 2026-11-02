"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const EXAMPLES = [
  ["الصبر عند البلاء", "MSA"],
  ["إزاي أصبر لما ربنا يبتليني بحاجة صعبة؟", "Egyptian"],
  ["وش جزاء اللي يبر أمه وأبوه؟", "Gulf"],
  ["forgiving people who wronged you", "English"],
  ["قصة الأخ اللي إخواته رموه في البير", "story"],
  ["ezay rabena by2bal el tawba", "Franco"],
];
const LANG = { msa: "MSA", egyptian: "Egyptian", gulf: "Gulf", levantine: "Levantine", maghrebi: "Maghrebi", franco: "Franco-Arabic", english: "English", other: "Other" };
const GRADE = { 3: ["g3", "Direct"], 2: ["g2", "Implicit / story"], 1: ["g1", "Related"] };
let busy = false, llm = false;

function route() {
  const v = (location.hash || "#search").slice(1) === "how" ? "how" : "search";
  $("#view-search").hidden = v !== "search";
  $("#view-how").hidden = v !== "how";
  document.querySelectorAll("nav a").forEach((a) => a.dataset.view === v ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
}
window.addEventListener("hashchange", route);

function steps(res) {
  const t = res?.trace?.timings_ms || {}, tr = res?.trace || {}, u = res?.understanding;
  const sec = (ms) => (ms == null ? "" : `${(ms / 1000).toFixed(1)} s`);
  const rows = [
    ["Understand query", u ? "done" : "skip", sec(t.understand), u ? `${esc(LANG[u.language] || u.language)} · ${esc(u.intent)}<br><span class="ar" dir="rtl">${esc(u.msa)}</span>${(u.classical || []).map((c) => `<br><span class="ar" dir="rtl">${esc(c)}</span>`).join("")}` : "Skipped (keyword mode)"],
    ["Retrieve candidates", res ? "done" : "", sec(t.retrieve), res ? `${(tr.views || []).length} views · ${tr.dense ? "keyword + embeddings" : "keyword only"} → ${tr.candidates ?? res.results.length} candidates` : ""],
    ["Rank", t.rerank != null ? "done" : "skip", sec(t.rerank), t.rerank != null ? (res.no_answer ? "No relevant ayah" : `${res.results.length} ayat kept`) : "Skipped (keyword mode)"],
    ["Guard and render", res ? "done" : "", "", res && res.mode === "full" ? `${tr.dropped_ids || 0} unknown IDs dropped · ${tr.withheld_reasons || 0} reasons withheld` : ""],
  ];
  $("#steps").innerHTML = rows.map(([n, st, tm, kv]) => `<li class="${st}"><span class="dot"></span><div><b>${n}</b> <span class="t">${tm}</span><div class="kv">${kv}</div></div></li>`).join("");
}
function running() {
  $("#steps").innerHTML = ["Understand query", "Retrieve candidates", "Rank", "Guard and render"].map((n, i) => `<li class="${i === 0 ? "run" : ""}"><span class="dot"></span><div><b>${n}</b></div></li>`).join("");
}

function card(r, mode) {
  const g = mode === "full" ? GRADE[r.grade] || GRADE[1] : ["kw", "Keyword match"];
  const why = mode !== "full" ? "" : r.why_withheld
    ? `<div class="guarded">The explanation was withheld because it reproduced Quranic wording. See the tafsir below.</div>`
    : r.why ? `<p class="why ${r.why_lang === "en" ? "en" : ""}" dir="${r.why_lang === "en" ? "ltr" : "rtl"}">${esc(r.why)} <span class="src">— based on al-Tafsir al-Muyassar</span></p>` : "";
  return `<article class="card">
    <div class="top"><span class="ref" dir="rtl">سورة ${esc(r.surah_name)}<span class="num">${r.surah}:${r.ayah}</span></span><span class="grade ${g[0]}">${g[1]}</span></div>
    <p class="ayah" lang="ar">${esc(r.text)} ﴿${Number(r.ayah).toLocaleString("ar-EG")}﴾</p>
    ${why}
    <details class="tafsir"><summary>Tafsir al-Muyassar</summary><p lang="ar">${esc(r.tafsir)}</p></details>
  </article>`;
}

async function search() {
  const q = $("#q").value.trim();
  if (!q || busy) return;
  busy = true; $("#go").disabled = true; $("#notice").hidden = true;
  $("#status").textContent = llm ? "Searching… this usually takes a few seconds." : "Searching…";
  $("#results").innerHTML = `<div class="empty">Working on it…</div>`;
  running();
  const t0 = performance.now();
  try {
    const r = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: q }) });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(r.status === 429 ? "Too many searches. Wait a minute and try again." : (typeof e.detail === "string" ? e.detail : "The search failed. Try again."));
    }
    const res = await r.json();
    steps(res);
    if (res.notice) { $("#notice").hidden = false; $("#notice").textContent = res.notice; }
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    const label = res.mode === "full" ? `${esc(LANG[res.understanding?.language] || "")} query · ${secs} s` : `Keyword mode · ${secs} s`;
    const head = `<div class="rhead"><h2>${res.no_answer ? "No relevant ayah found" : `${res.results.length} ayat`}</h2><span class="meta">${label}</span></div>`;
    $("#results").innerHTML = head + (res.no_answer
      ? `<div class="empty">None of the candidate ayat discuss this concept. Try describing it differently.</div>`
      : res.results.map((x) => card(x, res.mode)).join(""));
    $("#status").textContent = "Done.";
  } catch (e) {
    $("#status").textContent = e.message || "The search failed. Try again.";
    $("#results").innerHTML = `<div class="empty">No results to show.</div>`;
    steps(null);
  } finally { busy = false; $("#go").disabled = false; }
}

async function boot() {
  route();
  for (const [q, tag] of EXAMPLES) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.dir = "auto";
    b.innerHTML = `${esc(q)}<small>${esc(tag)}</small>`;
    b.onclick = () => { $("#q").value = q; search(); };
    $("#examples").append(b);
  }
  steps(null);
  try {
    const h = await (await fetch("/api/health")).json();
    llm = !!h.llm;
    $("#status").textContent = `${h.ayat.toLocaleString()} ayat indexed · ${h.llm ? "AI ranking on" : "keyword mode (no API key configured)"}${h.dense ? " · embeddings on" : ""}.`;
  } catch { $("#status").textContent = "The server isn't reachable. Check that it is running."; }
}
$("#qform").addEventListener("submit", (e) => { e.preventDefault(); search(); });
$("#q").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); search(); } });
boot();
