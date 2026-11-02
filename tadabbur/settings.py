"""Runtime settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines); real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("TADABBUR_DATA_DIR", ROOT / "data")))
    models_config: Path = field(default_factory=lambda: Path(os.getenv("TADABBUR_MODELS_CONFIG", ROOT / "config" / "models.yaml")))
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("TADABBUR_CACHE_DIR", ROOT / ".cache" / "llm")))
    cache_enabled: bool = field(default_factory=lambda: _env_bool("TADABBUR_CACHE", True))
    # Spend controls: hard cap on LLM calls per UTC day, and per-client request rate.
    max_llm_calls_per_day: int = field(default_factory=lambda: int(os.getenv("TADABBUR_MAX_LLM_CALLS_PER_DAY", "2000")))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.getenv("TADABBUR_RATE_LIMIT_PER_MINUTE", "20")))
    candidates: int = field(default_factory=lambda: int(os.getenv("TADABBUR_CANDIDATES", "40")))
    max_query_chars: int = 300

    @property
    def quran_path(self) -> Path:
        return self.data_dir / "quran.json"

    @property
    def qqa_path(self) -> Path:
        return self.data_dir / "qqa23.json"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"


def get_settings() -> Settings:
    return Settings()
