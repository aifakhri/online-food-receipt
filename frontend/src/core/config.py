from __future__ import annotations

import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 180
CONNECT_TIMEOUT_SECONDS = 5
ACCEPTED_TYPES = ["png", "jpg", "jpeg", "webp", "pdf"]
