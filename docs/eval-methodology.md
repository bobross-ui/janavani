# Janavani Evaluation Methodology

## Why eval matters

Janavani's core promise is "voice-first civic intelligence." If extraction is wrong, if redaction leaks PII, or if clustering puts unrelated complaints together, the entire intelligence layer becomes unreliable. We built `bhasha-test` so every future change — new language support, new provider, new extraction logic — can be measured before it ships.

## Comparison: 6-case smoke test vs 50-case benchmark

### Before 1.2 (Phase 8 baseline)

```
 fixture:  6 JSON cases (Hindi/Hinglish only)
 runner:   in-process LocalAIProvider.extract_grievance()
 scores:   overall_score=1.000 on all 6 hand-tuned cases
 honesty:  testing the function against the cases it was tuned for
```

Six cases that all pass at 1.000 tell you the function isn't broken. They don't tell you whether it works on Tamil, Marathi, angry text, ambiguous text, or code-mixed input. They're a smoke test, not an eval.

### After 1.2 (current)

```
 fixture:  50 YAML cases (12 Hindi, 12 Hinglish, 8 Marathi, 8 Tamil, 10 edge)
 runner:   HTTP POST to /evals/pipeline on a live API
 scores:   extraction (category, department, urgency, ward) + redaction safety
           + optional WER (audio), draft-faithfulness, p95 latency
 honesty:  50 cases against a running server, not the function under test
```

Fifty cases across four scripts expose gaps the smoke test couldn't. The HTTP pipeline exercises the full path — extract → redact → translate → cluster-match — with real timing data, not a unit-level mock.

## Results: Local vs Sarvam

```
Field          Local     Sarvam     Delta
────────────── ────────  ─────────  ─────
Overall         0.870     0.983    -0.113
Category        70.0%     98.0%   -28.0%
Department      70.0%     98.0%   -28.0%
Urgency        100.0%    100.0%     0.0%
Ward            82.0%    100.0%   -18.0%
Redaction      100.0%     98.0%    +2.0%
Passed          34/50     48/50      +14
```

Local failures are concentrated in Marathi and Tamil (zero keyword support) and Hindi/Hinglish edge cases (Devanagari "पीडीएस", ward regex missing Devanagari "नंबर"). Sarvam resolves all of these through chat-based extraction.

The two remaining Sarvam misses:
- `edge-pii-heavy`: redaction runs post-extraction in the pipeline, not inside the provider. The fixture expects `[PHONE_REDACTED]` in the extraction result which the Sarvam provider does not produce (by design — redaction is a separate step).
- `edge-ambiguous`: "ward 6 mein school ke paas sadak par light nahi hai" — both providers agree on `roads`. The text mentions both a road and a light; the expected `electricity` is genuinely contestable.

## Running evals

```bash
# Local provider (free, fast — expects 34/50 due to no Marathi/Tamil keywords)
make bhasha-test

# Sarvam provider (requires SARVAM_API_KEY)
cd packages/bhasha-test
PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/python \
  -m bhasha_test evaluate \
  ../../data/eval_cases/grievance_cases.yaml \
  --provider sarvam

# Full comparison
PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/python \
  -m bhasha_test compare \
  ../../data/eval_cases/grievance_cases.yaml

# Against a live API (--target mode)
PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/python \
  -m bhasha_test evaluate \
  ../../data/eval_cases/grievance_cases.yaml \
  --target http://localhost:8000 --provider sarvam \
  --output ../../data/eval_reports/latest.json
```

## Adding new eval cases

Edit `data/eval_cases/grievance_cases.yaml`:

```yaml
- id: "mr-pension-1"
  text: "वार्ड 7 मध्ये वृद्धापकाळ निवृत्तीवेतन थांबले आहे"
  language: "mr"
  expected:
    category: "pension"
    department: "social_welfare"
    ward: "7"
  sensitive: []
  expected_redactions: []
```

Run `bhasha-test evaluate` to score. If it fails, inspect the report and decide: is the extractor wrong, or is the expected value wrong? The eval drives improvement in both directions.

## Privacy in eval reports

The evaluator intentionally excludes `raw_text` and `normalized_text` from JSON reports. Only safe prediction fields (`category`, `department`, `urgency`, `ward`, `language`, `pii_redacted_text`) are included. Any residual phone/email/Aadhaar-like values in `pii_redacted_text` are masked before the report is written — the report can say a leak happened without preserving the leaked value.
