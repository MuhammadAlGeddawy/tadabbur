"""Build demo data for Tadabbur pipeline 1.

Inputs (GitHub mirrors, see D21):
  - Tanzil Uthmani text (semnan-university-ai/checksum-quran): one ayah per line, per-surah files
  - Tafsir Al-Muyassar (spa5k/tafsir_api, ar-tafsir-muyassar): per-surah JSON
  - Qur'an QA 2023 Task A (ghazaleh-mahmoodi mirror): QPC passages, questions, qrels (evaluation only, D14)

Outputs:
  site/data/quran.json   {names, counts, uthmani[], muyassar[]}  (index = global ayah order)
  site/data/qqa23.json   {passages:[[id, s, a1, a2]], dev:[...], train:[...]}  (evaluation only)
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data-src")
OUT = os.path.join(ROOT, "site", "data")
os.makedirs(OUT, exist_ok=True)

NAMES = """الفاتحة البقرة آل_عمران النساء المائدة الأنعام الأعراف الأنفال التوبة يونس هود يوسف الرعد إبراهيم الحجر النحل الإسراء الكهف مريم طه الأنبياء الحج المؤمنون النور الفرقان الشعراء النمل القصص العنكبوت الروم لقمان السجدة الأحزاب سبأ فاطر يس الصافات ص الزمر غافر فصلت الشورى الزخرف الدخان الجاثية الأحقاف محمد الفتح الحجرات ق الذاريات الطور النجم القمر الرحمن الواقعة الحديد المجادلة الحشر الممتحنة الصف الجمعة المنافقون التغابن الطلاق التحريم الملك القلم الحاقة المعارج نوح الجن المزمل المدثر القيامة الإنسان المرسلات النبأ النازعات عبس التكوير الانفطار المطففين الانشقاق البروج الطارق الأعلى الغاشية الفجر البلد الشمس الليل الضحى الشرح التين العلق القدر البينة الزلزلة العاديات القارعة التكاثر العصر الهمزة الفيل قريش الماعون الكوثر الكافرون النصر المسد الإخلاص الفلق الناس""".split()
NAMES = [n.replace("_", " ") for n in NAMES]
assert len(NAMES) == 114, len(NAMES)

# Known ayah counts for a few surahs (sanity checks)
KNOWN = {1: 7, 2: 286, 3: 200, 9: 129, 26: 227, 36: 83, 55: 78, 108: 3, 114: 6}

counts, uthmani = [], []
for s in range(1, 115):
    with open(f"{SRC}/quran/data/uthmani-aya/{s}.txt", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.read().split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    counts.append(len(lines))
    uthmani.extend(lines)

for s, n in KNOWN.items():
    assert counts[s - 1] == n, (s, counts[s - 1], n)
assert sum(counts) == 6236, sum(counts)

# Cross-check per-surah files against the full uthmani.txt
with open(f"{SRC}/quran/data/uthmani.txt", encoding="utf-8") as f:
    full = [l for l in f.read().split("\n") if l.strip()]
assert full == uthmani, "per-surah files differ from uthmani.txt"

# Tafsir Al-Muyassar
muyassar = []
missing = 0
for s in range(1, 115):
    with open(f"{SRC}/tafsir/tafsir/ar-tafsir-muyassar/{s}.json", encoding="utf-8") as f:
        rows = json.load(f)
    by_ayah = {int(r["ayah"]): r["text"].strip() for r in rows}
    for a in range(1, counts[s - 1] + 1):
        t = by_ayah.get(a, "")
        if not t:
            missing += 1
        muyassar.append(t)

quran = {
    "source": {
        "quran": "Tanzil Quran Text (Uthmani), via github.com/semnan-university-ai/checksum-quran — verbatim; CC BY 3.0, tanzil.net",
        "tafsir": "Tafsir Al-Muyassar (King Fahd Complex), via github.com/spa5k/tafsir_api (ar-tafsir-muyassar)",
    },
    "names": NAMES,
    "counts": counts,
    "uthmani": uthmani,
    "muyassar": muyassar,
    "sha256_uthmani": hashlib.sha256("\n".join(uthmani).encode()).hexdigest(),
}
with open(f"{OUT}/quran.json", "w", encoding="utf-8") as f:
    json.dump(quran, f, ensure_ascii=False, separators=(",", ":"))

# Qur'an QA 2023 Task A (evaluation only)
TA = f"{SRC}/qqa23/Task A/data"
passages = []
with open(f"{TA}/Thematic_QPC/QQA23_TaskA_QPC_v1.1.tsv", encoding="utf-8") as f:
    for line in f:
        pid = line.split("\t")[0].strip()
        s, rng = pid.split(":")
        a1, a2 = rng.split("-")
        passages.append([pid, int(s), int(a1), int(a2)])
assert len(passages) == 1266, len(passages)


def load_split(name):
    qs = []
    with open(f"{TA}/QQA23_TaskA_{name}.tsv", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                qid, q = line.rstrip("\n").split("\t", 1)
                qs.append([qid.strip(), q.strip()])
    rel = {}
    with open(f"{TA}/qrels/QQA23_TaskA_qrels_{name}.gold", encoding="utf-8") as f:
        for line in f:
            p = line.split()
            if len(p) >= 4:
                rel.setdefault(p[0], []).append(p[2])
    return [[qid, q, rel.get(qid, [])] for qid, q in qs]


qqa = {
    "source": "Qur'an QA 2023 Task A (Malhas, Mansour & Elsayed 2023), via github.com/ghazaleh-mahmoodi/quran-qa_2023_shared-task — evaluation only (QPC licence CC BY-NC-ND)",
    "passages": passages,
    "train": load_split("train"),
    "dev": load_split("dev"),
}
with open(f"{OUT}/qqa23.json", "w", encoding="utf-8") as f:
    json.dump(qqa, f, ensure_ascii=False, separators=(",", ":"))

for k in ("train", "dev"):
    n0 = sum(1 for _, _, r in qqa[k] if r == ["-1"])
    print(k, "questions:", len(qqa[k]), "zero-answer:", n0, "no-qrels:", sum(1 for _, _, r in qqa[k] if not r))
print("ayat:", len(uthmani), "muyassar missing:", missing)
print("sizes KB:", {f: os.path.getsize(f"{OUT}/{f}") // 1024 for f in os.listdir(OUT)})
