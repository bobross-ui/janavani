import re

# ── Patterns ──────────────────────────────────────────────────────────

# 10-digit Indian mobile number
PHONE_RE = re.compile(r"\b\d{10}\b")

# 12-digit Aadhaar-like number
AADHAAR_RE = re.compile(r"\b\d{12}\b")

# Email
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


# ── Redaction ─────────────────────────────────────────────────────────


def redact_phone_numbers(text: str) -> str:
    return PHONE_RE.sub("[PHONE_REDACTED]", text)


def redact_aadhaar(text: str) -> str:
    return AADHAAR_RE.sub("[ID_REDACTED]", text)


def redact_emails(text: str) -> str:
    return EMAIL_RE.sub("[EMAIL_REDACTED]", text)


def redact_all(text: str) -> str:
    """Apply all redaction rules in order."""
    text = redact_phone_numbers(text)
    text = redact_aadhaar(text)
    text = redact_emails(text)
    return text
