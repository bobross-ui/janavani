from __future__ import annotations

import math
import re
from typing import Optional, Sequence


# ── 1. Word Error Rate ──────────────────────────────────────────────────────

def _levenshtein_distance(a: list[str], b: list[str]) -> int:
    """Compute Levenshtein edit distance between two token sequences."""
    n, m = len(a), len(b)
    # Use two-row optimisation (O(n*m) time, O(m) space).
    prev = list(range(m + 1))
    curr = [0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,        # deletion
                curr[j - 1] + 1,    # insertion
                prev[j - 1] + cost, # substitution
            )
        prev, curr = curr, prev
    return prev[m]


def _simple_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate using manual Levenshtein on whitespace-tokenised words."""
    ref_tokens = reference.strip().split()
    hyp_tokens = hypothesis.strip().split()

    # Both empty → perfect match.
    if not ref_tokens and not hyp_tokens:
        return 0.0
    # Reference has words but hypothesis is empty → all deletions = 100% error.
    if not hyp_tokens:
        return 1.0
    # Hypothesis has words but reference is empty → all insertions.
    if not ref_tokens:
        return 1.0

    distance = _levenshtein_distance(ref_tokens, hyp_tokens)
    return distance / len(ref_tokens)


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate between *reference* and *hypothesis*.

    If the ``jiwer`` library is available it is used directly; otherwise a
    simple token-based WER is computed via Levenshtein distance on word
    tokens.  Both empty strings yield 0.0.

    Parameters
    ----------
    reference : str
        Ground-truth transcription.
    hypothesis : str
        System-generated transcription.

    Returns
    -------
    float
        WER value.  Lower is better.  May exceed 1.0 on very poor matches.
    """
    try:
        import jiwer  # type: ignore
        return jiwer.wer(reference, hypothesis)
    except ImportError:
        return _simple_wer(reference, hypothesis)


# ── 2. Draft Faithfulness (hallucinated contact info) ───────────────────────

_PHONE_RE = re.compile(r"\b\d{10}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def _extract_contacts(text: str) -> set[str]:
    """Return the set of phone numbers and email addresses found in *text*."""
    phones = set(_PHONE_RE.findall(text))
    emails = set(_EMAIL_RE.findall(text))
    return phones | emails


def compute_draft_faithfulness(draft_text: Optional[str], source_texts: list[str]) -> float:
    """Score how faithful a draft is to its source materials (0.0 – 1.0).

    Extracts 10-digit phone numbers and email addresses from the draft.
    Any contact detail found in the draft that does **not** appear anywhere
    in *source_texts* is treated as a hallucination.

    Parameters
    ----------
    draft_text : str
        The generated draft text (may be ``None`` or empty).
    source_texts : list[str]
        Original source texts the draft was generated from.

    Returns
    -------
    float
        1.0 = every contact detail in the draft is backed by a source.
        0.0 = draft is empty / ``None``, or every contact detail is
              unsupported.
    """
    if not draft_text:
        return 0.0

    draft_contacts = _extract_contacts(str(draft_text))
    if not draft_contacts:
        return 1.0  # Nothing to check → perfectly faithful.

    source_contacts: set[str] = set()
    for src in source_texts:
        source_contacts |= _extract_contacts(str(src))

    supported = draft_contacts & source_contacts
    return len(supported) / len(draft_contacts)


# ── 3. 95th Percentile Latency ──────────────────────────────────────────────

def compute_p95_latency(latencies_ms: Sequence[float]) -> float:
    """Return the 95th-percentile latency in milliseconds.

    Parameters
    ----------
    latencies_ms : list[float]
        List of latency measurements (ms).

    Returns
    -------
    float
        95th percentile.  Empty list returns 0.0.
    """
    if not latencies_ms:
        return 0.0

    sorted_latencies = sorted(latencies_ms)
    n = len(sorted_latencies)

    # Use the "nearest-rank" method: index = ceil(0.95 * n) - 1
    idx = math.ceil(0.95 * n) - 1
    return sorted_latencies[idx]
