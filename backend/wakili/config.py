from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
DATA_DIR = PACKAGE_DIR / "data"
JURISDICTIONS_DIR = DATA_DIR / "jurisdictions"
CORPORA_DIR = DATA_DIR / "corpora"
DEMO_DIR = DATA_DIR / "demo"

RUNTIME_DIR = Path(os.getenv("WAKILI_RUNTIME_DIR", PROJECT_ROOT / "runtime")).resolve()
UPLOADS_DIR = RUNTIME_DIR / "uploads"
EXPORTS_DIR = RUNTIME_DIR / "exports"
GENERATED_DIR = RUNTIME_DIR / "generated"
AVATARS_DIR = RUNTIME_DIR / "avatars"
DB_PATH = Path(os.getenv("WAKILI_DB_PATH", RUNTIME_DIR / "wakili.db")).resolve()

HOST = os.getenv("WAKILI_HOST", "127.0.0.1")
PORT = int(os.getenv("WAKILI_PORT", "8765"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("WAKILI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("WAKILI_OPENAI_MODEL", "gpt-4o-mini").strip()
CODEX_MODEL = os.getenv("WAKILI_CODEX_MODEL", "codex-mini-latest").strip()

DEFAULT_JURISDICTION = os.getenv("WAKILI_DEFAULT_JURISDICTION", "ke")


def ensure_directories() -> None:
    for path in (RUNTIME_DIR, UPLOADS_DIR, EXPORTS_DIR, GENERATED_DIR, AVATARS_DIR):
        path.mkdir(parents=True, exist_ok=True)
