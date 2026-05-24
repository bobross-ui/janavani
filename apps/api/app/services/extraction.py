import re
from typing import Optional

from app.schemas import ExtractionResult

# ── Category keyword mapping ──────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "water_supply": [
        "paani", "pani", "पानी", "पाणी", "नल", "nal", "water",
        "pipe", "nal jal", "tanker", "टैंकर",
    ],
    "sanitation": [
        "kachra", "कचरा", "garbage", "waste", "gandagi", "गंदगी",
        "safai", "सफाई", "nala", "नाला", "drain", "sewer", "toilet",
        "शौचालय", "swachh",
    ],
    "roads": [
        "sadak", "सड़क", "road", "gaddha", "pothole", "footpath",
        "rasta", "रास्ता", "path", "broken road",
    ],
    "electricity": [
        "bijli", "बिजली", "light", "electricity", "current",
        "batti", "बत्ती", "power cut", "load shedding", "transformer",
    ],
    "ration": [
        "ration", "राशन", "PDS", "fair price shop", "pds", "सार्वजनिक वितरण",
    ],
    "pension": [
        "pension", "पेंशन", "penshan", "vriddha", "vruddha",
        "widow", "vidhwa", "वृद्धा",
    ],
    "health": [
        "doctor", "डॉक्टर", "hospital", "aspatal", "davai", "दवा",
        "swasthya", "स्वास्थ्य", "clinic", "phc", "treatment",
    ],
    "education": [
        "school", "स्कूल", "vidyalaya", "college", "teacher",
        "shiksha", "शिक्षा", "adhyapak", "madrasa",
    ],
    "agriculture": [
        "kisan", "किसान", "fasal", "फसल", "khet", "खेत",
        "sinchai", "सिंचाई", "beej", "बीज", "crop",
    ],
    "corruption": [
        "rishwat", "घूस", "bhrashtachar", "भ्रष्टाचार", "bribe",
    ],
}

# ── Department mapping ────────────────────────────────────────────────

CATEGORY_TO_DEPARTMENT: dict[str, str] = {
    "water_supply": "water_department",
    "sanitation": "sanitation_department",
    "roads": "public_works",
    "electricity": "electricity_department",
    "ration": "food_department",
    "pension": "social_welfare",
    "health": "health_department",
    "education": "education_department",
    "agriculture": "agriculture_department",
    "corruption": "anti_corruption",
    "other": "general_admin",
}


# ── Ward extraction ───────────────────────────────────────────────────

WARD_RE = re.compile(
    r"(?:वार्ड|ward)\s*(?:no\.?|number|num|#)?\s*(\d{1,3})",
    re.IGNORECASE,
)


def _extract_ward(text: str) -> str:
    m = WARD_RE.search(text)
    return m.group(1) if m else ""


# ── Urgency detection ─────────────────────────────────────────────────

URGENCY_HIGH_PATTERNS = [
    "aaj se", "aaj hi", "आज से", "आज ही", "kal se",
    "abhi", "अभी", "right now", "emergency", "critical",
    "teen din se", "चार दिन से", "पांच दिन से",
    "hafta", "हफ़्ता", "mahina", "महीना",
    "no water", "no electricity", "no power",
    "nahi aa", "nahi ho", "नहीं आ", "नहीं हो",
]


def _detect_urgency(text: str) -> str:
    lower = text.lower()
    for pattern in URGENCY_HIGH_PATTERNS:
        if pattern in lower:
            return "high"
    return "medium"


# ── Normalization ─────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Strip excess whitespace."""
    return " ".join(text.split())


# ── Main extraction ───────────────────────────────────────────────────


def _normalize_language(lang: str) -> str:
    """Normalize a language code to Sarvam-compatible format (e.g. 'hi' → 'hi-IN')."""
    if not lang:
        return "hi-IN"
    if "-" in lang:  # already has region suffix like 'hi-IN' or 'hi-Latn'
        return lang
    return lang + "-IN"


def extract_grievance(
    text: str, language: str = "hi-IN"
) -> ExtractionResult:
    """Extract structured fields from grievance text using keyword rules."""
    language = _normalize_language(language)
    normalized = _normalize(text)
    lower = normalized.lower()

    # Classify
    best_category = "other"
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_category = category

    department = CATEGORY_TO_DEPARTMENT.get(best_category, "general_admin")
    ward = _extract_ward(normalized)
    urgency = _detect_urgency(lower)
    pii_redacted = normalized  # placeholder — PII redaction is a separate step

    return ExtractionResult(
        category=best_category,
        department=department,
        urgency=urgency,
        ward=ward,
        landmark="",
        language=language,
        normalized_text=normalized,
        pii_redacted_text=pii_redacted,
    )
