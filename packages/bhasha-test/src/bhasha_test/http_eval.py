"""HTTP-based eval provider — POSTs to /evals/pipeline instead of calling in-process."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class PipelineHttpError(Exception):
    """Raised when the pipeline HTTP call fails."""


def _post_pipeline(target_url: str, input_text: str, language: str, provider: str) -> dict[str, Any]:
    """POST to /evals/pipeline and return the parsed JSON response."""
    url = target_url.rstrip("/") + "/evals/pipeline"
    payload = json.dumps({"input_text": input_text, "language": language}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-AI-Provider": provider,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise PipelineHttpError(f"HTTP {e.code} from {url}: {body}") from e
    except urllib.error.URLError as e:
        raise PipelineHttpError(f"Could not reach {url}: {e.reason}") from e


class HttpEvalProvider:
    """Wraps POST /evals/pipeline to look like an ExtractionProvider.

    The pipeline endpoint returns PipelineResult which has category,
    department, urgency, ward, landmark, pii_redacted_text. We remap
    that into the dict shape the evaluator expects.
    """

    def __init__(self, target_url: str, provider_name: str = "local"):
        self._target = target_url
        self._provider = provider_name

    def extract_grievance(self, text: str, language: str = "hi") -> dict[str, Any]:
        data = _post_pipeline(self._target, text, language, self._provider)
        # PipelineResult → ExtractionResult-compatible dict
        return {
            "category": data.get("category", "other"),
            "department": data.get("department", ""),
            "urgency": data.get("urgency", "medium"),
            "ward": data.get("ward", ""),
            "landmark": data.get("landmark", ""),
            "language": language,
            "normalized_text": data.get("pii_redacted_text", ""),
            "pii_redacted_text": data.get("pii_redacted_text", ""),
        }
