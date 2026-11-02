// Offline evaluation of the pipeline-1 recall stage on Qur'an QA 2023 Task A (train + dev).
// No LLM here: the question text is the only query view. Results are ayah rankings mapped to QPC passages.
const fs = require("fs");
const path = require("path");
const C = require("../site/retrieval.js");

const quran = JSON.parse(fs.readFileSync(path.join(__dirname, "../site/data/quran.json"), "utf8"));
const qqa = JSON.parse(fs.readFileSync(path.join(__dirname, "../site/data/qqa23.json"), "utf8"));

const t0 = Date.now();
const corpus = new C.Corpus(quran);
console.log(`index built in ${Date.now() - t0} ms; vocab ayah=${corpus.ayahIdx.df.size} tafsir=${corpus.tafsirIdx.df.size}`);
const toPassages = C.passageMapper(corpus, qqa.passages);

const configs = {
  "ayah text only": { fields: ["ayah"] },
  "tafsir only": { fields: ["tafsir"] },
  "ayah + tafsir (RRF)": { fields: ["ayah", "tafsir"] },
};

const results = {};
fs.mkdirSync(path.join(__dirname, "runs"), { recursive: true });
for (const split of ["train", "dev", "all"]) {
  const qs = split === "all" ? [...qqa.train, ...qqa.dev] : qqa[split];
  for (const [name, cfg] of Object.entries(configs)) {
    const scores = [], runLines = [];
    for (const [qid, q, rel] of qs) {
      const { fused } = corpus.retrieve([q], { depth: 300, limit: 300, fields: cfg.fields });
      const ranked = toPassages(fused.map(([i]) => i)).slice(0, 100);
      scores.push(C.scoreQuestion(ranked, rel));
      ranked.slice(0, 10).forEach((pid, r) => runLines.push(`${qid}\tQ0\t${pid}\t${r + 1}\t${(10 - r).toFixed(3)}\ttadabbur`));
    }
    results[`${split} | ${name}`] = C.summarize(scores);
    if (split !== "all") fs.writeFileSync(path.join(__dirname, "runs", `${split}_${name.replace(/[^a-z]+/gi, "_")}.tsv`), runLines.join("\n") + "\n");
  }
}
console.table(Object.fromEntries(Object.entries(results).map(([k, v]) => [k, Object.fromEntries(Object.entries(v).map(([a, b]) => [a, typeof b === "number" && a !== "n" ? +b.toFixed(4) : b]))])));
fs.writeFileSync(path.join(__dirname, "recall_results.json"), JSON.stringify(results, null, 2));
