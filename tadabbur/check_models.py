"""Check that every OpenRouter model in config/models.yaml exists on OpenRouter today.

    python -m tadabbur.check_models
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import yaml

from .settings import get_settings


def main() -> None:
    cfg = yaml.safe_load(get_settings().models_config.read_text(encoding="utf-8"))
    wanted = []
    for m in cfg["model_list"]:
        p = m["litellm_params"]
        if "openrouter.ai" in str(p.get("api_base", "")):
            wanted.append((m["model_name"], p["model"].split("/", 1)[1]))
    req = urllib.request.Request("https://openrouter.ai/api/v1/models")
    if os.getenv("OPENROUTER_API_KEY"):
        req.add_header("Authorization", f"Bearer {os.environ['OPENROUTER_API_KEY']}")
    ids = set()
    for path in ("https://openrouter.ai/api/v1/models", "https://openrouter.ai/api/v1/embeddings/models"):
        try:
            req.full_url = path
            with urllib.request.urlopen(req, timeout=30) as r:
                ids |= {m["id"] for m in json.load(r).get("data", [])}
        except Exception as e:  # the embeddings listing may not exist on every API version
            print(f"note: could not read {path}: {e}")
    missing = 0
    for alias, model in wanted:
        ok = model in ids
        missing += not ok
        print(f"{'OK     ' if ok else 'MISSING'} {alias:28s} {model}")
    if missing:
        print("\nEdit config/models.yaml and replace the missing IDs with current ones from https://openrouter.ai/models")
        sys.exit(1)


if __name__ == "__main__":
    main()
