from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv; load_dotenv()


BACKEND_DIR = Path(__file__).resolve().parents[2]
STORAGE_ROOT = Path(
    os.environ.get("STORAGE_ROOT", BACKEND_DIR / "storages")
).resolve()
DB_PATH = STORAGE_ROOT / "database" / "food_receipts.db"
UPLOAD_DIR = STORAGE_ROOT / "uploads"

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or None
MODEL_NAME = os.environ["MODEL_NAME"]
TIMEZONE = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Jakarta"))
