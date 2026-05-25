"""Additional scorers for bhasha-test — WER, draft faithfulness, latency."""

from __future__ import annotations

import math
import re
from typing import Sequence


def _tokenize(text: str) -> list[str]:
    return text.strip().lower().split()


# ── Word Error Rate (WER) ─────────────────────────────────────────────


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute word error rate between reference and hypothesis transcripts.

    WER = (substitutions + deletions + insertions) / reference_word_count.
    Returns 0.0 for perfect match; 1.0 if reference is empty and hypothesis
    is non-empty.
    """
    ref = _tokenize(reference)
    hyp = _tokenize(hypothesis)

    if not ref and not hyp:
        return 0.0
    if not ref:
        return 1.0
    if not hyp:
        return 1.0

    n, m = len(ref), len(hyp)
    dp: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )

    return dp[n][m] / n


# ── Draft Faithfulness ────────────────────────────────────────────────

# Patterns for contact info extraction
_PHONE_RE = re.compile(r"\b\d{10,}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def _extract_contacts(text: str) -> set[str]:
    """Extract phone numbers and email addresses from text."""
    contacts: set[str] = set()
    contacts.update(_PHONE_RE.findall(text))
    contacts.update(_EMAIL_RE.findall(text))
    return contacts


def compute_draft_faithfulness(draft: str | None, sources: Sequence[str]) -> float:
    """Score how faithful a generated draft is to its source grievances.

    Extracts phone numbers and emails from the draft and from all source
    texts. A contact in the draft that does not appear in any source is
    considered unsupported (hallucinated).

    Returns a score in [0.0, 1.0]:
      1.0 = all contacts in draft are supported by sources.
      0.0 = every contact in draft is unsupported.
    """
    if not draft or not sources:
        return 0.0

    draft_contacts = _extract_contacts(draft)
    if not draft_contacts:
        return 1.0  # no contacts to hallucinate → perfect

    source_contacts: set[str] = set()
    for src in sources:
        source_contacts.update(_extract_contacts(src))

    supported = draft_contacts & source_contacts
    return len(supported) / len(draft_contacts)


# ── Latency ───────────────────────────────────────────────────────────


def compute_p95_latency(latencies: Sequence[float]) -> float:
    """Compute the 95th percentile of latency values."""
    if not latencies:
        return 0.0
    sorted_vals = sorted(latencies)
    idx = math.ceil(0.95 * len(sorted_vals)) - 1
    return sorted_vals[max(0, idx)]


def wer_score(reference: str, hypothesis: str) -> float:
    """Alias for compute_wer — used by evaluator integration."""
    return compute_wer(reference, hypothesis)


def draft_faithfulness_score(
    draft: str, grievance_text: str, expected_keywords: Sequence[str] | None = None
) -> float:
    """Convenience wrapper for compute_draft_faithfulness with keyword support."""
    return compute_draft_faithfulness(draft, [grievance_text])


def p95(values: Sequence[float]) -> float:
    """Alias for compute_p95_latency."""
    return compute_p95_latency(values)


def mean(values: Sequence[float]) -> float:
    """Compute arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)
