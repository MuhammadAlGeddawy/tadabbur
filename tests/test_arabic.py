import json
from pathlib import Path

from tadabbur import arabic as A

FIX = json.loads((Path(__file__).parent / "fixtures_js_tokens.json").read_text(encoding="utf-8"))


def test_parity_with_reference_tokenizer():
    for x in FIX:
        assert A.normalize_variants(x["text"]) == x["norm"]
        assert A.tokens(x["text"]) == x["tokens"]


def test_uthmani_matches_modern_spelling():
    assert "العالمين" in A.normalize_variants("ٱلْعَٰلَمِينَ")
    assert "الصلاه" in A.normalize_variants("ٱلصَّلَوٰةَ")
    assert "ابراهيم" in A.normalize_variants("إِبْرَٰهِـۧمَ")


def test_guard_key_is_spelling_insensitive():
    assert A.guard_key("ٱلْعَٰلَمِينَ") == A.guard_key("العالمين")
    assert A.guard_key("وَءَاتُوا۟") == A.guard_key("وآتوا")
