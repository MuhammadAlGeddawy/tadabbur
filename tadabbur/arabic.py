"""Arabic normalization, light stemming and tokenization.

Uthmani script is matched to modern spelling: diacritics and Quranic annotation marks are removed,
hamza/alef forms unified, and words with a dagger alef are indexed in both spellings
(e.g. العٰلمين -> العلمين and العالمين; الصلوٰة -> الصلاة).
"""
from __future__ import annotations

import re

_MARKS = re.compile("[ؐ-ًؚ-ٟۖ-ۜ۟-ۦ۪ۨ-ۭ࣓-ࣿـ]")
_NON_ARABIC = re.compile("[^ء-ي\\s]")
_SPACES = re.compile(r"\s+")

_MAP = [
    ("ۧ", "ي"),  # small high yeh -> yeh
    ("ٱ", "ا"), ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),  # alef forms
    ("ى", "ي"),  # alef maqsura -> yeh
    ("ة", "ه"),  # ta marbuta -> heh
    ("ؤ", "و"),  # waw hamza -> waw
    ("ئ", "ي"),  # yeh hamza -> yeh
    ("ی", "ي"), ("ک", "ك"),  # Persian yeh / kaf
]


def _base_map(s: str) -> str:
    for a, b in _MAP:
        s = s.replace(a, b)
    return s


def _clean(s: str) -> str:
    s = _MARKS.sub("", _base_map(s))
    s = _NON_ARABIC.sub(" ", s)
    return _SPACES.sub(" ", s).strip()


def normalize_variants(text: str) -> list[str]:
    """One or two normalized variants (dagger alef removed vs. written as alef)."""
    t = str(text or "")
    if "ٰ" not in t:
        return [_clean(t)]
    a = _clean(t.replace("ٰ", ""))
    b = _clean(t.replace("وٰ", "ا").replace("ٰ", "ا"))
    return [a] if a == b else [a, b]


def normalize(text: str) -> str:
    return normalize_variants(text)[0]


STOPWORDS = {
    _base_map(w)
    for w in (
        "من في على علي الي الى عن ان إن أن ما لا لم لن هو هي هم هن انت انتم نحن انا هذا هذه ذلك تلك هؤلاء الذي التي الذين اللذين "
        "كان كانت يكون قد و او أو ثم بل يا اذا اذ كل بعض غير عند مع منه منها فيه فيها عليه عليها له لها لهم به بها بهم الا الي "
        "ماذا لماذا كيف هل متي اين كم اي اية ايه الايه الايات القران قران يقول قال قالوا ذكر ذكرت تذكر يذكر وردت ورد "
        "حتي لكن لكي كي لان ليس ليست وما ومن وفي وعلي وهو وهي ولا ثمه ايضا تعالي سبحانه الله"
    ).split()
}
# "الله" is a ranking stopword only (it occurs in ~2,700 ayat); the guard still sees it.

_PREFIXES = ["وال", "فال", "بال", "كال", "لل", "ال"]
_SUFFIXES = ["هما", "كما", "ها", "ان", "ات", "ون", "ين", "يه", "هم", "هن", "كم", "نا", "ه", "ي"]


def stem(w: str) -> str:
    x = w
    for p in _PREFIXES:
        if x.startswith(p) and len(x) - len(p) >= 2:
            x = x[len(p):]
            break
    if len(x) > 3 and x[0] in ("و", "ف"):
        x = x[1:]
    for s in _SUFFIXES:
        if x.endswith(s) and len(x) - len(s) >= 3:
            x = x[: -len(s)]
            break
    return x


def tokens(text: str) -> list[str]:
    """Index/query tokens: normalized, stopwords removed, light-stemmed; dagger-alef variants merged."""
    lists = [v.split(" ") for v in normalize_variants(text)]
    n = max(len(l) for l in lists)
    out: list[str] = []
    for i in range(n):
        forms: list[str] = []
        for l in lists:
            if i >= len(l):
                continue
            w = l[i]
            if not w or len(w) < 2 or w in STOPWORDS:
                continue
            s = stem(w)
            if s not in forms:
                forms.append(s)
        out.extend(forms)
    return out


_DROP_IN_KEY = re.compile("[اء]")


def guard_key(text: str) -> list[str]:
    """Spelling-insensitive word keys used by the Quran-quote guard (alef and lone hamza dropped)."""
    t = normalize(str(text or "").replace("وٰ", "ا"))
    return [k for k in (_DROP_IN_KEY.sub("", w) for w in t.split(" ") if w) if k]
