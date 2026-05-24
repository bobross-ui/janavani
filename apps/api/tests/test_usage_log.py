import json
import os
import tempfile
import threading
from pathlib import Path

from app.services import usage_log


# ── helpers ──────────────────────────────────────────────────────────────

def _read_jsonl_lines(path: str):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


# ── tests ────────────────────────────────────────────────────────────────

def test_log_call_writes_json_line():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "subdir", "usage.jsonl")
        usage_log.USAGE_LOG_PATH = log_path

        usage_log.log_call(
            endpoint="/v1/chat/completions",
            model="sarvam-m",
            language="hi",
            input_size_bytes=1234,
            latency_ms=567,
            status="200",
            retry_count=0,
        )

        lines = _read_jsonl_lines(log_path)
        assert len(lines) == 1
        entry = lines[0]

        assert entry["endpoint"] == "/v1/chat/completions"
        assert entry["model"] == "sarvam-m"
        assert entry["language"] == "hi"
        assert entry["input_size_bytes"] == 1234
        assert entry["latency_ms"] == 567
        assert entry["status"] == "200"
        assert entry["retry_count"] == 0
        assert entry["estimated_cost"] == 0.0
        # timestamp must be a valid ISO 8601 string
        assert "T" in entry["timestamp"]


def test_log_call_appends_multiple_calls():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "usage.jsonl")
        usage_log.USAGE_LOG_PATH = log_path

        usage_log.log_call(
            endpoint="/v1/tts",
            model="bulbul:v3",
            language="",
            input_size_bytes=100,
            latency_ms=200,
            status="200",
            retry_count=0,
        )
        usage_log.log_call(
            endpoint="/v1/stt",
            model="saarika:v2.5",
            language="hi-IN",
            input_size_bytes=999,
            latency_ms=333,
            status="500",
            retry_count=2,
        )

        lines = _read_jsonl_lines(log_path)
        assert len(lines) == 2
        assert lines[0]["endpoint"] == "/v1/tts"
        assert lines[1]["endpoint"] == "/v1/stt"
        assert lines[1]["status"] == "500"
        assert lines[1]["retry_count"] == 2


def test_log_call_is_thread_safe():
    """Basic concurrency test — 50 threads, every line must be valid JSON."""
    n_threads = 50
    n_calls_per_thread = 10

    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "usage.jsonl")
        usage_log.USAGE_LOG_PATH = log_path
        usage_log._reset_lock_for_testing()

        errors = []

        def worker(thread_id):
            for i in range(n_calls_per_thread):
                try:
                    usage_log.log_call(
                        endpoint="/v1/test",
                        model="sarvam-m",
                        language="",
                        input_size_bytes=1,
                        latency_ms=1,
                        status="200",
                        retry_count=0,
                    )
                except Exception as exc:
                    errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, "unexpected errors: %s" % errors

        lines = _read_jsonl_lines(log_path)
        assert len(lines) == n_threads * n_calls_per_thread, (
            "expected %d lines, got %d" % (n_threads * n_calls_per_thread, len(lines))
        )


def test_log_call_creates_directory():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "deeply", "nested", "dir", "usage.jsonl")
        usage_log.USAGE_LOG_PATH = log_path

        # Directory must not exist yet
        assert not os.path.exists(os.path.dirname(log_path))

        usage_log.log_call(
            endpoint="/v1/test",
            model="sarvam-m",
            language="",
            input_size_bytes=0,
            latency_ms=0,
            status="200",
            retry_count=0,
        )

        assert os.path.exists(log_path)
        lines = _read_jsonl_lines(log_path)
        assert len(lines) == 1
