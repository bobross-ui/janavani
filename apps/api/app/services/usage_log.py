"""Usage-log service — thread-safe JSONL append-only logger.

Writes one JSON line per Sarvam API call to a configurable file path.
The file path is a module-level variable so tests can point it at a
temporary location without touching environment or settings.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Module-level config — tests can override this before calling log_call.
USAGE_LOG_PATH: str = "data/sarvam_usage.jsonl"

_write_lock = threading.Lock()


def log_call(
    endpoint: str,
    model: str,
    language: str,
    input_size_bytes: int,
    latency_ms: int,
    status: str,
    retry_count: int,
) -> None:
    """Append one JSON line to the usage-log file (thread-safe).

    Creates the parent directory if it does not exist.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "model": model,
        "language": language,
        "input_size_bytes": input_size_bytes,
        "latency_ms": latency_ms,
        "status": status,
        "retry_count": retry_count,
        "estimated_cost": 0.0,
    }

    path = Path(USAGE_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(entry, ensure_ascii=False) + "\n"

    with _write_lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)


def _reset_lock_for_testing() -> None:
    """Replace the module-level lock (test helper only)."""
    global _write_lock
    _write_lock = threading.Lock()
