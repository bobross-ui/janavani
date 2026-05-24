# Sarvam AI Integration Runbook

Janavani uses Sarvam AI (sarvam.ai) for speech-to-text (STT),
STT-with-translate, text translation (Mayura), text-to-speech (TTS/Bulbul),
and chat completion (draft generation). This runbook covers setup,
architecture, endpoints, fallback, costs, and operational procedures.

---

## 1. Quickstart

```bash
# 1. Get an API key at https://sarvam.ai
# 2. Set environment variables
export AI_PROVIDER=sarvam
export SARVAM_API_KEY="sk-..."

# 3. (Optional) configure .env
echo 'AI_PROVIDER=sarvam' >> apps/api/.env
echo 'SARVAM_API_KEY=sk-...' >> apps/api/.env
echo 'SARVAM_FALLBACK_ON_ERROR=true' >> apps/api/.env

# 4. Start the API
cd apps/api
uvicorn app.main:app --reload

# 5. Run the bhasha-test comparison (see section 9)
python -m bhasha_test compare fixtures/cases.json --output data/compare.json
```

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  FastAPI Routes                                                │
│  grievances.py  ──┐                                            │
│  tts.py           ├── Depends(get_request_ai_provider)         │
│  admin.py (draft)─┘     (request-scoped provider)              │
│                       │                                        │
│              ┌────────▼────────┐                                │
│              │  AIProvider      │  Protocol (duck-typed)        │
│              │  (Protocol)      │                                │
│              └───┬──────┬──────┘                                │
│                  │      │                                       │
│     ┌────────────▼─┐  ┌─▼──────────────┐                       │
│     │ LocalAIProvider│  │FallbackAIProvider│                    │
│     │ (deterministic) │  │ ┌──────────────┐│                    │
│     └────────────────┘  │ │SarvamAIProvider│                    │
│                          │ │(primary)      │                    │
│                          │ └───────┬───────┘│                    │
│                          │ ┌───────▼───────┐│                    │
│                          │ │LocalAIProvider ││                    │
│                          │ │(fallback)      ││                    │
│                          │ └───────────────┘│                    │
│                          └──────────────────┘                    │
│                                       │                         │
│                               ┌───────▼───────┐                 │
│                               │  SarvamClient  │                 │
│                               │  (httpx)       │                 │
│                               └───────┬───────┘                 │
│                                       │                         │
│                          ┌────────────▼─────────────┐           │
│                          │  Sarvam AI REST APIs     │           │
│                          │  api.sarvam.ai           │           │
│                          └──────────────────────────┘           │
│                                                                  │
│  Abstraction boundary: AIProvider Protocol                      │
│  Every route calls provider.transcribe_audio(),                  │
│  provider.translate_text(), provider.synthesize_speech(), etc.   │
│  No route imports SarvamAIProvider directly.                    │
└────────────────────────────────────────────────────────────────┘
```

### Call flow by feature

| Feature | Route | Provider method | Sarvam endpoint |
|---------|-------|-----------------|-----------------|
| Audio grievance | POST /grievances/audio | transcribe_audio | /speech-to-text |
| Audio + translate | (future) | transcribe_audio_translate | /speech-to-text-translate |
| Cluster pivot translation | POST /grievances | translate_text | /translate |
| Text-to-speech | POST /tts | synthesize_speech | /text-to-speech |
| Draft generation | POST /admin/clusters/{id}/draft | generate_draft | /v1/chat/completions |
| Extraction | POST /grievances | extract_grievance | not yet implemented (local only) |

Key files:

- apps/api/app/services/ai_provider.py  — AIProvider protocol, LocalAIProvider,
  SarvamAIProvider, FallbackAIProvider, CircuitBreaker, get_ai_provider()
- apps/api/app/services/sarvam_client.py — SarvamClient (httpx wrapper with
  retry, rate-limit detection, usage logging)
- apps/api/app/services/usage_log.py — JSONL usage logger
- apps/api/app/config.py — all Sarvam settings
- apps/api/app/routes/grievances.py — get_request_ai_provider() factory

---

## 3. Endpoints

| Sarvam API Path | Janavani Feature | Config Key | Model Config Key |
|-----------------|-----------------|------------|------------------|
| /speech-to-text | Audio transcription | — | sarvam_stt_model (saarika:v2.5) |
| /speech-to-text-translate | Audio + translate | — | sarvam_stt_translate_model (saaras:v2.5) |
| /translate | Text translation (Mayura) | — | sarvam_translate_model (mayura:v1) |
| /text-to-speech | TTS (Bulbul) | — | sarvam_tts_model (bulbul:v3) |
| /v1/chat/completions | Draft generation | — | sarvam_chat_model (sarvam-m) |

All endpoints require the header api-subscription-key: <your key>.

Client configuration (config.py):

```python
sarvam_api_base: str = "https://api.sarvam.ai"
sarvam_timeout_seconds: float = 30.0
sarvam_max_retries: int = 2
```

### Endpoint details

/speech-to-text — STT
  Method: POST multipart
  Input: audio file (field "file", up to 10 MB), model, language_code
  Response: { "transcript": "...", "language_code": "hi-IN", "confidence": 0.95 }
  Guard: audio > 10 MB rejected before API call with SarvamError

/speech-to-text-translate — STT with translation
  Method: POST multipart
  Input: audio file (field "file", up to 10 MB), model, language_code (target)
  Response: { "transcript": "...", "language_code": "en-IN", "confidence": 0.90 }
  Guard: same 10 MB limit

/translate — Mayura text translation
  Method: POST JSON
  Payload: { "model": "mayura:v1", "input": "text", "target_language_code": "en-IN",
             "source_language_code": "hi-IN" (optional) }
  Response: { "translated_text": "..." }
  Optimization: skips API call when source == target (no-op)
  Caching: in-memory per-provider-instance, keyed by (hash(text), target, source)
  Guard: validates non-empty translated_text string

/text-to-speech — Bulbul TTS
  Method: POST JSON
  Payload: { "model": "bulbul:v3", "inputs": ["text"], "target_language_code": "hi-IN",
             "speaker": "default" }
  Response: { "audios": ["base64-encoded-wav"] }
  Guard: text > 500 characters rejected before API call

/v1/chat/completions — Draft generation
  Method: POST JSON
  Payload: { "model": "sarvam-m", "messages": [...], "temperature": 0.2 }
  Response: OpenAI-compatible { "choices": [{ "message": { "content": "..." } }] }
  Guard: validates response shape, checks for PII leaks (phone/email regex)
  Only pii_redacted_text from grievances is used; raw_text is never sent

---

## 4. Provider selection

Provider is selected per-request via FastAPI dependency injection.

### Default selection

get_ai_provider() in ai_provider.py reads AI_PROVIDER setting:

- AI_PROVIDER=local → LocalAIProvider (deterministic, no API key needed)
- AI_PROVIDER=sarvam → if SARVAM_FALLBACK_ON_ERROR=true:
    FallbackAIProvider(SarvamAIProvider(), LocalAIProvider())
  else:
    SarvamAIProvider() (raw, no fallback wrapper)
- If SarvamAIProvider init fails (e.g. missing SARVAM_API_KEY) and
  fallback is enabled → silently returns LocalAIProvider

### Request-scoped override (X-AI-Provider header)

get_request_ai_provider() in grievances.py reads the X-AI-Provider header:

1. If ALLOW_PROVIDER_OVERRIDE=false (production default): header is ignored,
   returns get_ai_provider()
2. If ALLOW_PROVIDER_OVERRIDE=true (testing/eval):
   - X-AI-Provider: local → LocalAIProvider
   - X-AI-Provider: sarvam → HTTP 503 (Sarvam override not yet available)
   - unknown value → HTTP 400 (Unsupported AI provider override)
3. This is gated by ALLOW_PROVIDER_OVERRIDE — must be explicitly enabled

### Dependency chain

```python
# grievances.py
async def submit_grievance(
    provider: AIProvider = Depends(get_request_ai_provider),
    ...
)
# tts.py
async def synthesize_text_to_speech(
    provider: AIProvider = Depends(get_request_ai_provider),
    ...
)
```

Every route that needs AI uses Depends(get_request_ai_provider).

---

## 5. Fallback behavior

### FallbackAIProvider

Wraps a primary provider (SarvamAIProvider) and fallback (LocalAIProvider).
On any SarvamError from the primary, the fallback is called transparently.

Behavior per method:
- transcribe_audio → on SarvamError, returns LocalAIProvider result
  (transcript="[local: audio transcription not available]", confidence=0.0)
- translate_text → on SarvamError, returns input text unchanged
- synthesize_speech → on SarvamError, returns empty bytes
- generate_draft → on SarvamError, returns LocalAIProvider template draft
- extract_grievance → Sarvam currently raises NotImplementedError, so
  callers get local extraction

### Circuit breaker

A module-level CircuitBreaker (_sarvam_circuit_breaker) shared across
all request-scoped FallbackAIProvider instances:

- Failure threshold: 3 consecutive failures within a 60-second window
- Recovery timeout: 30 seconds after the circuit opens
- When open, FallbackAIProvider skips the primary entirely and goes
  straight to fallback (logs a warning)
- On first success after recovery timeout, circuit resets to closed
- Successes reset failure counters immediately

Configuration (hardcoded defaults, not in settings):
- failure_threshold = 3
- recovery_seconds = 30.0
- failure_window_seconds = 60.0

### Init-time fallback

If SarvamAIProvider() constructor fails (e.g., no SARVAM_API_KEY set)
and SARVAM_FALLBACK_ON_ERROR=true, get_ai_provider() catches the
NotImplementedError and returns a plain LocalAIProvider.

### When local takes over

| Scenario | Behavior |
|----------|----------|
| SARVAM_API_KEY not set | Return LocalAIProvider at init |
| Sarvam API timeout/5xx/transport error | FallbackAIProvider catches, uses local |
| Sarvam returns 429 | SarvamRateLimitError raised (no fallback) |
| Circuit open | All calls go to local for 30s |
| SarvamError (4xx, bad response) | FallbackAIProvider catches, uses local |

---

## 6. Cost model

Rough estimates based on Sarvam public pricing. All USD approximate.

| Endpoint | Model | Approx cost | Unit |
|----------|-------|-------------|------|
| /speech-to-text | saarika:v2.5 | ~$0.005/min | per audio minute |
| /speech-to-text-translate | saaras:v2.5 | ~$0.008/min | per audio minute |
| /translate | mayura:v1 | ~$0.00002/char | per character |
| /text-to-speech | bulbul:v3 | ~$0.005/1K chars | per 1,000 characters |
| /v1/chat/completions | sarvam-m | ~$0.30/1M tokens | per million tokens |

### bhasha-test run cost estimate

A typical bhasha-test run with 50 cases:

- 50 calls to extract_grievance → currently local (no Sarvam cost)
- If extraction is implemented on Sarvam: ~50 chat completions
  ~50 × 500 tokens × $0.30/1M ≈ < $0.01

Full pipeline per real grievance (audio flow):
- STT: ~$0.005 (assume ~1 min audio)
- Translate (pivot): ~$0.00002 × 200 chars ≈ < $0.01
- Total per grievance: ~$0.01

Draft generation: ~$0.00015 per draft (~500 tokens)

---

## 7. Rate limits

Sarvam's current free/developer tier limits:
- ~100 requests/minute across all endpoints
- ~1,000 requests/day

Production plans may have higher limits.

### What happens when limits are hit

- Sarvam returns HTTP 429
- SarvamClient._post() detects 429 and raises SarvamRateLimitError
- 429 responses are NOT retried (unlike 5xx/timeout)
- The usage log entry records status="429"
- If wrapped in FallbackAIProvider: SarvamRateLimitError is a subclass of
  SarvamError, so fallback takes over (circuit breaker records failure)

### Retry behavior

- 5xx responses: retried up to SARVAM_MAX_RETRIES times (default: 2)
- Timeouts (httpx.TimeoutException): retried
- Transport errors (httpx.HTTPError): retried
- 4xx (except 429): NOT retried, raised immediately as SarvamError
- Retry backoff: exponential, 0.1s × 2^(retry_count-1), capped at 1.0s

### Mitigation when rate-limited

1. Enable SARVAM_FALLBACK_ON_ERROR=true (default) — local provider takes over
2. Check data/sarvam_usage.jsonl for 429 entries
3. Wait for rate-limit window to reset (~1 minute)
4. Consider batching or throttling high-volume test runs

---

## 8. Adding a new Sarvam endpoint

Checklist to add a new Sarvam API feature:

1. Add config key in config.py
   - New model name setting (e.g., sarvam_new_model: str = "model:v1")
   - Any new timeout/retry overrides if needed

2. Add method to SarvamClient (sarvam_client.py)
   - If JSON payload: use self.post_json(path, payload)
   - If multipart/audio: use self.post_audio_bytes() or post_multipart()
   - The client handles auth headers, logging, retries, rate-limit detection

3. Add method to AIProvider Protocol (ai_provider.py)
   - Define the method signature with type hints
   - Add stub to LocalAIProvider (return a sensible default/no-op)
   - Implement in SarvamAIProvider
   - Add delegation method in FallbackAIProvider._call_with_fallback()

4. Add tests (apps/api/tests/)
   - Unit test for SarvamClient method (mocked HTTP via FakeSarvamClient)
   - Unit test for SarvamAIProvider method (validate response parsing)
   - Unit test for FallbackAIProvider delegation (primary fails → fallback)
   - Integration test with provider factory if endpoint is route-facing

5. Wire into a route (if user-facing)
   - Add Depends(get_request_ai_provider) to the route
   - Call provider.new_method(...)

Example — adding a hypothetical sentiment endpoint:

```python
# config.py
sarvam_sentiment_model: str = "bhav:v1"

# ai_provider.py (Protocol)
def analyze_sentiment(self, text: str) -> float: ...

# sarvam_client.py usage:
response = self._client.post_json("/v1/sentiment", {
    "model": settings.sarvam_sentiment_model,
    "input": text,
})
```

---

## 9. Comparing to local (bhasha-test)

bhasha-test has a built-in compare command that runs both providers on
the same fixture and prints a delta report.

```bash
cd /path/to/janavani
python -m bhasha_test compare fixtures/cases.json --output data/compare.json
```

Output:

```
--- local ---
total_cases=50 passed_cases=42 overall_score=0.850 redaction_safety=0.920

--- sarvam ---
total_cases=50 passed_cases=0 overall_score=0.000 redaction_safety=0.000
  error: sarvam provider not available — extraction not implemented

--- delta ---
overall_score_local=0.850
overall_score_sarvam=0.000
overall_score_delta=+0.850
```

Note: Sarvam currently shows extraction not implemented because
SarvamAIProvider.extract_grievance() raises NotImplementedError.
The comparison is still useful for the full pipeline when Sarvam
extraction is added.

For individual provider evaluation:

```bash
python -m bhasha_test evaluate fixtures/cases.json --provider local
python -m bhasha_test evaluate fixtures/cases.json --provider sarvam
```

The compare command internally:

1. Loads the JSON fixture (array of cases with text, language, expected, sensitive)
2. Creates LocalAIProvider and SarvamAIProvider instances
3. Calls provider.extract_grievance() for each case
4. Scores field accuracy (category, department, urgency, ward)
   and redaction safety
5. Prints a per-provider summary and a delta between them

---

## 10. Usage log

Every Sarvam API call is logged to a JSONL file for auditing, cost
tracking, and debugging.

Default location: apps/api/data/sarvam_usage.jsonl

Format (one JSON object per line):

```json
{"timestamp": "2026-05-25T12:34:56.789Z", "endpoint": "/speech-to-text",
 "model": "saarika:v2.5", "language": "hi-IN", "input_size_bytes": 45678,
 "latency_ms": 1234, "status": "200", "retry_count": 0,
 "estimated_cost": 0.0}
```

Fields:

- timestamp — UTC ISO 8601
- endpoint — API path (e.g., /speech-to-text, /translate, /v1/chat/completions)
- model — model name sent to Sarvam
- language — language code (first found from payload fields)
- input_size_bytes — payload size in bytes (audio bytes or JSON)
- latency_ms — round-trip time including retries
- status — HTTP status code, "timeout", "transport_error", or "error"
- retry_count — number of retries before final result
- estimated_cost — reserved for future cost calculation (currently 0.0)

Logging is thread-safe (threading.Lock on file append).
The log file path can be overridden for tests via usage_log.USAGE_LOG_PATH.

### Querying the usage log

```bash
# Count calls by endpoint
jq -r '.endpoint' data/sarvam_usage.jsonl | sort | uniq -c | sort -rn

# Total calls with errors
jq 'select(.status != "200")' data/sarvam_usage.jsonl | wc -l

# Latency percentiles (requires jq + datamash or Python)
python -c "
import json, statistics
lines = [json.loads(l) for l in open('data/sarvam_usage.jsonl')]
lats = [l['latency_ms'] for l in lines]
lats.sort()
print(f'p50={lats[len(lats)//2]} p95={lats[int(len(lats)*0.95)]} p99={lats[int(len(lats)*0.99)]}')
"

# Rate limit hits
jq 'select(.status == "429")' data/sarvam_usage.jsonl
```
