/* Tadabbur retrieval core \u2014 shared by the demo page (browser) and the offline evaluation (Node).
 * Arabic normalization, light stemming, multi-field BM25, Reciprocal Rank Fusion,
 * Quran-span guard, and Qur'an QA 2023 metrics (MAP@10 / MRR with the official no-answer rule).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.TadabburCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---------- Normalization ----------
  const MARKS = /[\u0610-\u061a\u064b-\u065f\u06d6-\u06dc\u06df-\u06e6\u06e8\u06ea-\u06ed\u08d3-\u08ff\u0640]/g;

  function baseMap(s) {
    return s
      .replace(/\u06e7/g, "\u064a") // small high yeh -> yeh (e.g. Ibrahim in Uthmani script)
      .replace(/[\u0671\u0623\u0625\u0622]/g, "\u0627") // alef wasla / hamza forms -> alef
      .replace(/\u0649/g, "\u064a") // alef maqsura -> yeh
      .replace(/\u0629/g, "\u0647") // ta marbuta -> heh
      .replace(/\u0624/g, "\u0648") // waw hamza -> waw
      .replace(/\u0626/g, "\u064a") // yeh hamza -> yeh
      .replace(/\u06cc/g, "\u064a").replace(/\u06a9/g, "\u0643"); // Persian yeh / kaf
  }

  /** Returns 1 or 2 normalized variants (dagger alef removed vs. written as alef). */
  function normalizeVariants(text) {
    let t = String(text || "");
    const hasDagger = t.indexOf("\u0670") >= 0;
    const clean = (x) => baseMap(x).replace(MARKS, "").replace(/[^\u0621-\u064a\s]/g, " ").replace(/\s+/g, " ").trim();
    if (!hasDagger) return [clean(t)];
    const a = clean(t.replace(/\u0670/g, ""));
    const b = clean(t.replace(/\u0648\u0670/g, "\u0627").replace(/\u0670/g, "\u0627"));
    return a === b ? [a] : [a, b];
  }
  function normalize(text) { return normalizeVariants(text)[0]; }

  const STOP = new Set((
    "\u0645\u0646 \u0641\u064a \u0639\u0644\u0649 \u0639\u0644\u064a \u0627\u0644\u064a \u0627\u0644\u0649 \u0639\u0646 \u0627\u0646 \u0625\u0646 \u0623\u0646 \u0645\u0627 \u0644\u0627 \u0644\u0645 \u0644\u0646 \u0647\u0648 \u0647\u064a \u0647\u0645 \u0647\u0646 \u0627\u0646\u062a \u0627\u0646\u062a\u0645 \u0646\u062d\u0646 \u0627\u0646\u0627 \u0647\u0630\u0627 \u0647\u0630\u0647 \u0630\u0644\u0643 \u062a\u0644\u0643 \u0647\u0624\u0644\u0627\u0621 \u0627\u0644\u0630\u064a \u0627\u0644\u062a\u064a \u0627\u0644\u0630\u064a\u0646 \u0627\u0644\u0644\u0630\u064a\u0646 " +
    "\u0643\u0627\u0646 \u0643\u0627\u0646\u062a \u064a\u0643\u0648\u0646 \u0642\u062f \u0648 \u0627\u0648 \u0623\u0648 \u062b\u0645 \u0628\u0644 \u064a\u0627 \u0627\u0630\u0627 \u0627\u0630 \u0643\u0644 \u0628\u0639\u0636 \u063a\u064a\u0631 \u0639\u0646\u062f \u0645\u0639 \u0645\u0646\u0647 \u0645\u0646\u0647\u0627 \u0641\u064a\u0647 \u0641\u064a\u0647\u0627 \u0639\u0644\u064a\u0647 \u0639\u0644\u064a\u0647\u0627 \u0644\u0647 \u0644\u0647\u0627 \u0644\u0647\u0645 \u0628\u0647 \u0628\u0647\u0627 \u0628\u0647\u0645 \u0627\u0644\u0627 \u0627\u0644\u064a " +
    "\u0645\u0627\u0630\u0627 \u0644\u0645\u0627\u0630\u0627 \u0643\u064a\u0641 \u0647\u0644 \u0645\u062a\u064a \u0627\u064a\u0646 \u0643\u0645 \u0627\u064a \u0627\u064a\u0629 \u0627\u064a\u0647 \u0627\u0644\u0627\u064a\u0647 \u0627\u0644\u0627\u064a\u0627\u062a \u0627\u0644\u0642\u0631\u0627\u0646 \u0642\u0631\u0627\u0646 \u064a\u0642\u0648\u0644 \u0642\u0627\u0644 \u0642\u0627\u0644\u0648\u0627 \u0630\u0643\u0631 \u0630\u0643\u0631\u062a \u062a\u0630\u0643\u0631 \u064a\u0630\u0643\u0631 \u0648\u0631\u062f\u062a \u0648\u0631\u062f " +
    "\u062d\u062a\u064a \u0644\u0643\u0646 \u0644\u0643\u064a \u0643\u064a \u0644\u0627\u0646 \u0644\u064a\u0633 \u0644\u064a\u0633\u062a \u0648\u0645\u0627 \u0648\u0645\u0646 \u0648\u0641\u064a \u0648\u0639\u0644\u064a \u0648\u0647\u0648 \u0648\u0647\u064a \u0648\u0644\u0627 \u062b\u0645\u0647 \u0627\u064a\u0636\u0627 \u062a\u0639\u0627\u0644\u064a \u0633\u0628\u062d\u0627\u0646\u0647 \u0627\u0644\u0644\u0647"
  ).split(/\s+/).map((w) => baseMap(w)));
  // Note: "\u0627\u0644\u0644\u0647" is a stopword for ranking only (it occurs in ~2,700 ayat); it still appears in the guard n-grams.

  const PREFIXES = ["\u0648\u0627\u0644", "\u0641\u0627\u0644", "\u0628\u0627\u0644", "\u0643\u0627\u0644", "\u0644\u0644", "\u0627\u0644"];
  const SUFFIXES = ["\u0647\u0645\u0627", "\u0643\u0645\u0627", "\u0647\u0627", "\u0627\u0646", "\u0627\u062a", "\u0648\u0646", "\u064a\u0646", "\u064a\u0647", "\u0647\u0645", "\u0647\u0646", "\u0643\u0645", "\u0646\u0627", "\u0647", "\u064a"];

  function stem(w) {
    let x = w;
    for (const p of PREFIXES) if (x.startsWith(p) && x.length - p.length >= 2) { x = x.slice(p.length); break; }
    if (x.length > 3 && (x[0] === "\u0648" || x[0] === "\u0641")) x = x.slice(1);
    for (const s of SUFFIXES) if (x.endsWith(s) && x.length - s.length >= 3) { x = x.slice(0, -s.length); break; }
    return x;
  }

  /** Tokens for indexing/querying: normalized, stopwords removed, light-stemmed; dagger-alef variants merged. */
  function tokens(text) {
    const out = [];
    const lists = normalizeVariants(text).map((v) => v.split(" "));
    const n = Math.max(...lists.map((l) => l.length));
    for (let i = 0; i < n; i++) {
      const forms = new Set();
      for (const l of lists) {
        const w = l[i];
        if (!w || w.length < 2 || STOP.has(w)) continue;
        forms.add(stem(w));
      }
      for (const f of forms) out.push(f);
    }
    return out;
  }

  // ---------- BM25 ----------
  class BM25 {
    constructor(docsTokens, k1 = 1.2, b = 0.75) {
      this.k1 = k1; this.b = b; this.N = docsTokens.length;
      this.len = new Float64Array(this.N); this.tf = new Array(this.N); this.df = new Map();
      let total = 0;
      docsTokens.forEach((toks, i) => {
        const m = new Map();
        for (const t of toks) m.set(t, (m.get(t) || 0) + 1);
        this.tf[i] = m; this.len[i] = toks.length; total += toks.length;
        for (const t of m.keys()) this.df.set(t, (this.df.get(t) || 0) + 1);
      });
      this.avg = total / Math.max(1, this.N);
      this.post = new Map();
      this.tf.forEach((m, i) => { for (const [t, c] of m) { if (!this.post.has(t)) this.post.set(t, []); this.post.get(t).push([i, c]); } });
    }
    idf(t) { const d = this.df.get(t) || 0; return Math.log(1 + (this.N - d + 0.5) / (d + 0.5)); }
    search(qTokens, k = 100) {
      const scores = new Map();
      const uniq = [...new Set(qTokens)];
      for (const t of uniq) {
        const p = this.post.get(t); if (!p) continue;
        const idf = this.idf(t);
        for (const [i, c] of p) {
          const s = idf * (c * (this.k1 + 1)) / (c + this.k1 * (1 - this.b + this.b * this.len[i] / this.avg));
          scores.set(i, (scores.get(i) || 0) + s);
        }
      }
      return [...scores.entries()].sort((x, y) => y[1] - x[1]).slice(0, k);
    }
  }

  /** Reciprocal Rank Fusion over several ranked lists of [docIndex, score]. */
  function rrf(lists, k = 60, limit = 100) {
    const agg = new Map();
    for (const l of lists) l.forEach(([i], r) => agg.set(i, (agg.get(i) || 0) + 1 / (k + r + 1)));
    return [...agg.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit);
  }

  // ---------- Corpus ----------
  class Corpus {
    /** quran: {names, counts, uthmani[], muyassar[]} */
    constructor(quran) {
      this.q = quran; this.ids = []; this.start = [0];
      quran.counts.forEach((c, si) => { for (let a = 1; a <= c; a++) this.ids.push(`${si + 1}:${a}`); this.start.push(this.start[si] + c); });
      this.index = new Map(this.ids.map((id, i) => [id, i]));
      this.ayahIdx = new BM25(quran.uthmani.map(tokens));
      this.tafsirIdx = new BM25(quran.muyassar.map(tokens));
      this.guard = new QuranGuard(quran.uthmani, quran.counts);
    }
    idx(s, a) { return this.start[s - 1] + a - 1; }
    /** views: array of query strings. Returns fused [[docIndex, rrfScore]], plus per-list traces. */
    retrieve(views, { depth = 100, limit = 50, fields = ["ayah", "tafsir"] } = {}) {
      const lists = [], trace = [];
      for (const v of views) {
        const qt = tokens(v);
        if (!qt.length) continue;
        if (fields.includes("ayah")) { const l = this.ayahIdx.search(qt, depth); lists.push(l); trace.push({ view: v, field: "ayah", top: l.slice(0, 5).map(([i]) => this.ids[i]) }); }
        if (fields.includes("tafsir")) { const l = this.tafsirIdx.search(qt, depth); lists.push(l); trace.push({ view: v, field: "tafsir", top: l.slice(0, 5).map(([i]) => this.ids[i]) }); }
      }
      return { fused: rrf(lists, 60, limit), trace };
    }
  }

  // ---------- Guard: block Quran-like spans in generated prose ----------
  // Words are compared in a spelling-insensitive key (normalized, alef removed) so Uthmani orthography
  // (\u0627\u0644\u0639\u0670\u0644\u0645\u064a\u0646 / \u0627\u0644\u0639\u0627\u0644\u0645\u064a\u0646, \u0627\u0644\u0631\u062d\u0645\u0670\u0646 / \u0627\u0644\u0631\u062d\u0645\u0646) matches modern spelling. N-grams run across ayah boundaries
  // within a surah, so quotes of several short ayat are caught too.
  const DROP_IN_KEY = new RegExp("[\\u0627\\u0621]", "g"); // alef and lone hamza
  const guardKey = (text) => normalize(String(text || "").replace(new RegExp("\\u0648\\u0670", "g"), "\u0627"))
    .split(" ").filter(Boolean).map((w) => w.replace(DROP_IN_KEY, "")).filter(Boolean);
  class QuranGuard {
    constructor(uthmani, counts, n = 5) {
      this.n = n; this.grams = new Set();
      let k = 0;
      const surahs = counts || [uthmani.length];
      for (const c of surahs) {
        const w = [];
        for (let a = 0; a < c; a++) w.push(...guardKey(uthmani[k++]));
        for (let i = 0; i + n <= w.length; i++) this.grams.add(w.slice(i, i + n).join(" "));
      }
    }
    /** Returns {ok, hits[]} \u2014 hits are runs of n consecutive words found in the Quran. */
    check(text) {
      const w = guardKey(text), hits = [];
      for (let i = 0; i + this.n <= w.length; i++) { const g = w.slice(i, i + this.n).join(" "); if (this.grams.has(g)) hits.push(g); }
      return { ok: hits.length === 0, hits: [...new Set(hits)] };
    }
  }

  // ---------- Qur'an QA 2023 Task A evaluation (passage level) ----------
  function passageMapper(corpus, passages) {
    const ofAyah = new Int32Array(corpus.ids.length).fill(-1);
    passages.forEach(([pid, s, a1, a2], pi) => { for (let a = a1; a <= a2; a++) ofAyah[corpus.idx(s, a)] = pi; });
    return (ayahIndices) => {
      const seen = new Set(), out = [];
      for (const i of ayahIndices) { const p = ofAyah[i]; if (p >= 0 && !seen.has(p)) { seen.add(p); out.push(passages[p][0]); } }
      return out;
    };
  }

  /** Official-style scoring: AP@10 (trec map_cut_10: divided by |R|) and reciprocal rank;
   *  zero-answer questions score 1 only if the run is exactly ["-1"]. */
  function scoreQuestion(ranked, rel) {
    if (rel.length === 1 && rel[0] === "-1") { const ok = ranked.length === 1 && ranked[0] === "-1" ? 1 : 0; return { ap10: ok, rr: ok, r10: ok, r50: ok, zero: true }; }
    const R = new Set(rel);
    let hits = 0, sumP = 0, rr = 0;
    ranked.slice(0, 10).forEach((d, k) => { if (R.has(d)) { hits++; sumP += hits / (k + 1); } });
    for (let k = 0; k < ranked.length; k++) if (R.has(ranked[k])) { rr = 1 / (k + 1); break; }
    const recall = (K) => ranked.slice(0, K).filter((d) => R.has(d)).length / R.size;
    return { ap10: sumP / R.size, rr, r10: recall(10), r50: recall(50), zero: false };
  }
  function summarize(scores) {
    const m = (k, f = () => true) => { const xs = scores.filter(f).map((s) => s[k]); return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0; };
    return { n: scores.length, map10: m("ap10"), mrr: m("rr"), recall10_answerable: m("r10", (s) => !s.zero), recall50_answerable: m("r50", (s) => !s.zero), zero_answer_acc: m("ap10", (s) => s.zero) };
  }

  return { normalize, normalizeVariants, tokens, stem, BM25, rrf, Corpus, QuranGuard, passageMapper, scoreQuestion, summarize };
});
