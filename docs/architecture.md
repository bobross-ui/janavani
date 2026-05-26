# Janavani Architecture

## Request flow

```
┌──────────────────────────────────────────────────────────┐
│                      Citizen App                         │
│              (Expo React Native — Android)               │
│  ┌─────────┐                    ┌─────────────────────┐  │
│  │  Text   │                    │     Voice (mic)     │  │
│  └────┬────┘                    └──────────┬──────────┘  │
│       │  POST /grievances                  │ POST        │
│       │  {text, language}                  │ /grievances │
│       │                                    │ /audio      │
│       │                                    │ {multipart} │
└───────┼────────────────────────────────────┼─────────────┘
        │                                    │
        ▼                                    ▼
┌───────────────────────────────────────────────────────────┐
│                     FastAPI Backend                       │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              AIProvider (protocol)                   │  │
│  │                                                     │  │
│  │  ┌──────────────┐  ┌───────────────┐               │  │
│  │  │ LocalProvider │  │SarvamAIProvider│              │  │
│  │  │ ──────────── │  │ ──────────────│              │  │
│  │  │ extract (kw) │  │ extract (chat) │              │  │
│  │  │ translate:    │  │ translate:     │              │  │
│  │  │   no-op       │  │   Mayura API   │              │  │
│  │  │ STT: not      │  │ STT: Saarika   │              │  │
│  │  │  available    │  │ STT-translate: │              │  │
│  │  │ TTS: not      │  │   Saaras       │              │  │
│  │  │  available    │  │ TTS: Bulbul    │              │  │
│  │  │ draft: echo   │  │ draft: Sarvam-M│              │  │
│  │  └──────────────┘  └───────────────┘               │  │
│  │                                                     │  │
│  │  FallbackAIProvider wraps primary (Sarvam) +         │  │
│  │  fallback (Local). On SarvamError → local.          │  │
│  │  Circuit breaker opens after 3 failures/60s.        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────┐   ┌───────────┐   ┌──────────────────────┐  │
│  │ Extract │──▶│  Redact   │──▶│ Translate → pivot (en)│  │
│  └─────────┘   └───────────┘   └──────────┬───────────┘  │
│                                           │              │
│                                           ▼              │
│                              ┌────────────────────────┐  │
│                              │  Cluster matching       │  │
│                              │  (category + ward +     │  │
│                              │   token overlap /       │  │
│                              │   future: embeddings)   │  │
│                              └────────────┬───────────┘  │
│                                           │              │
│                      ┌────────────────────┘              │
│                      ▼                                   │
│              ┌──────────────┐                            │
│              │   Postgres   │                            │
│              │  (pgvector   │                            │
│              │   planned    │                            │
│              │   for 1.3)   │                            │
│              └──────────────┘                            │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                   Web Dashboard                           │
│              (Next.js 14 — port 3000)                     │
│                                                           │
│  /           Public cluster map + stats                  │
│  /admin      Admin workflow (drafts, status)             │
│  /evals      Evaluation reports (bhasha-test output)     │
└───────────────────────────────────────────────────────────┘
```

## Provider abstraction

The `AIProvider` protocol defines six methods. Every provider — `LocalAIProvider`, `SarvamAIProvider`, or a future provider — implements this surface:

```python
class AIProvider(Protocol):
    def extract_grievance(text, language) -> ExtractionResult
    def translate_text(text, target, source=None) -> str
    def transcribe_audio(audio_bytes, language_code) -> TranscriptionResult
    def transcribe_audio_translate(audio_bytes, target) -> TranscriptionResult
    def synthesize_speech(text, language, speaker) -> bytes
    def generate_draft(cluster_context) -> str
```

`LocalAIProvider` implements extraction via keyword matching, template-based
draft generation, and no-op translations. It cannot perform STT or TTS (methods
return placeholders or raise `SarvamError` indicating the capability is unavailable).

`SarvamAIProvider` delegates to Sarvam's REST API: Saarika for STT, Saaras for STT-translate, Mayura for translation, Bulbul for TTS, and Sarvam-M for chat-based extraction and draft generation. Extraction uses a structured JSON prompt; any parse failure or PII leak raises `SarvamError`, triggering the fallback chain.

## Services layer

| Service | File | Role |
|---------|------|------|
| `extraction.py` | Keyword sets, ward regex, urgency patterns | Shared by LocalAIProvider |
| `redaction.py` | Phone/Aadhaar/email regex redaction | Called post-extraction |
| `clustering.py` | Hybrid cosine/Jaccard + category + haversine | Cluster suggestion |
| `embeddings.py` | Lazy-loaded multilingual-e5-small model | Semantic similarity vectors |
| `ai_provider.py` | Provider protocol + implementations + fallback | All AI operations |
| `sarvam_client.py` | HTTP client with retry + auth | Sarvam API calls |
| `audio_storage.py` | File-based audio persistence | Save/load/delete audio |
| `geocoding.py` | Haversine distance + demo ward inference | Location-aware matching |

## Clustering architecture

Janavani uses a three-gate approach for cluster matching:

```
Grievance arrives
     │
     ▼
┌─────────────────────────┐
│ Gate 1: CATEGORY (hard) │  water ≠ garbage, always enforced
└────────────┬────────────┘
             │ pass
             ▼
┌─────────────────────────┐
│ Gate 2: TEXT SIMILARITY │
│                         │
│ Primary: cosine on      │  "no water supply" matches
│   embeddings (τ=0.78)   │  "taps are dry" (no shared
│                         │  words, same meaning)
│ Fallback: Jaccard token │  Only when embeddings model
│   overlap (τ=0.15)      │  not installed (dev/demo)
└────────────┬────────────┘
             │ pass
             ▼
┌─────────────────────────┐
│ Gate 3: LOCATION        │
│                         │
│ Same ward number   OR   │  Ward boundary override:
│ Haversine ≤ 300m        │  two complaints 200m apart
│                         │  in different wards still
│                         │  match (same intersection)
└────────────┬────────────┘
             │ pass
             ▼
       CLUSTER MATCH
```

All three gates must pass. Category prevents cross-topic false positives regardless of text similarity. Text (cosine) catches synonyms and cross-language complaints after English-pivot translation. Location ensures spatial relevance — a water complaint in Mumbai doesn't cluster with a water complaint in Delhi even if both say "water not coming."

**In production**, the embedding model is always loaded and Jaccard is never used. The Python candidate loop is replaced by a pgvector ANN query directly in Postgres. The architecture (category → cosine → location) is production-correct; the implementation is demo-grade.

## Data model (simplified)

```
User ──< Grievance >── IssueCluster
                     │
                     ├── category, department, urgency
                     ├── ward, landmark
                     ├── normalized_text (English pivot)
                     ├── pii_redacted_text
                     └── latitude, longitude (wired in 1.4)
```

## Router map

| Prefix | Purpose |
|--------|---------|
| `/health` | Liveness check |
| `/grievances` | Submit text grievance |
| `/grievances/audio` | Submit voice grievance |
| `/clusters` | List / detail public clusters |
| `/admin` | Admin cluster management + drafts |
| `/tts` | Text-to-speech acknowledgment |
| `/evals/pipeline` | End-to-end pipeline (no persist) for bhasha-test |
| `/evals/latest` | Most recent eval report |
