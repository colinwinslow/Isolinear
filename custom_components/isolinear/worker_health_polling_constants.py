"""Constants for durable worker health polling."""

from __future__ import annotations

import re
from pathlib import Path

DATA_WORKER_HEALTH_POLLING = "worker_health_polling"
DATA_WORKER_HEALTH_POLLING_CANCEL = "worker_health_polling_cancel"
DATA_WORKER_HEALTH_POLLING_GENERATIONS = "worker_health_polling_generations"
DATA_WORKER_HEALTH_POLLING_TIMER = "worker_health_polling_timer"
DATA_WORKER_HEALTH_POLLING_SETUP = "worker_health_polling_setup"
DATA_WORKER_HEALTH_POLLING_STORE = "worker_health_polling_storage_helper"

POLLING_STORAGE_KEY = "isolinear_worker_health_polling"
POLLING_STORAGE_VERSION = 1
READY_POLL_CADENCE_SECONDS = 300
FAILURE_BACKOFF_SECONDS = (30, 60, 120, 300, 900)
POLLING_HEALTH_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
POLLING_HEALTH_SECRET_RE = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|worker_token",
    re.IGNORECASE,
)
POLLING_LOADED_FORBIDDEN_RE = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token",
    re.IGNORECASE,
)

WORKER_HEALTH_POLLING_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "schemas"
    / "integration-worker-health-polling-state.schema.json"
)
