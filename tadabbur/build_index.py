"""Build the dense embedding index: one vector per ayah (surah name + ayah + Tafsir al-Muyassar).

    python -m tadabbur.build_index            # uses the `embed` role from config/models.yaml
"""
from __future__ import annotations

import argparse
import json
import logging

import numpy as np

from .corpus import Corpus
from .gateway import build_gateway
from .settings import get_settings

log = logging.getLogger("tadabbur.build_index")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    s = get_settings()
    corpus = Corpus.load(s.quran_path)
    gw = build_gateway(s)
    if not gw.available:
        raise SystemExit("No API key configured. Set OPENROUTER_API_KEY in .env first.")
    texts = corpus.dense_texts()
    vecs: list[list[float]] = []
    for k in range(0, len(texts), args.batch):
        vecs.extend(gw.embed("embed", texts[k:k + args.batch]))
        log.info("embedded %d / %d", len(vecs), len(texts))
    m = np.asarray(vecs, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-12
    s.index_dir.mkdir(parents=True, exist_ok=True)
    np.save(s.index_dir / "embeddings.npy", m)
    meta = {"n": len(texts), "dim": int(m.shape[1]), "model": gw.roles.get("embed", "embed"),
            "sha256_uthmani": corpus.q.get("sha256_uthmani")}
    (s.index_dir / "embeddings.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("saved %s (%d x %d)", s.index_dir / "embeddings.npy", *m.shape)


if __name__ == "__main__":
    main()
