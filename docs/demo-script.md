# Janavani Demo Script

Runnable end-to-end against a fresh clone. For portfolio reviewers, recruiters,
or anyone evaluating the project.

**Prerequisites:** Docker, git.

## 1. Clone and start

```bash
git clone https://github.com/bobross-ui/janavani.git
cd janavani
make demo
```

Wait for the output:

```
API healthy — seeding demo data...
seed-1 exited with code 0

 Dashboard:  http://localhost:3000
 API:        http://localhost:8000
 API docs:   http://localhost:8000/docs
```

If the API fails health check (Docker not running, port conflict), the script
exits with an error message instead of printing URLs.

## 2. What you're looking at

**Dashboard** (`http://localhost:3000`)
- Four issue clusters: Water (Ward 8), Garbage (Ward 11), Roads (Ward 4), Electricity (Ward 2)
- Stats strip: total clusters, total grievances, avg urgency
- Filterable by ward and category
- Each cluster card shows title, category, grievance count, supporter count, urgency

**Admin workflow** (`http://localhost:3000/admin`)
- Lists all clusters with status management
- "Generate draft" button creates a formal complaint letter via Sarvam-M
- Draft includes ward, department, grievance count, and redacted citizen samples

**Eval reports** (`http://localhost:3000/evals`)
- Shows the most recent `bhasha-test` run if a report exists
- Summary cards: cases passed, extraction score, redaction safety, overall
- Per-field accuracy table + case-by-case breakdown

## 3. Try the API directly

```bash
# Health check
curl http://localhost:8000/health

# List clusters
curl http://localhost:8000/clusters | python3 -m json.tool

# Submit a grievance (text)
curl -X POST http://localhost:8000/grievances \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo-user-1","text":"ward 8 mein paani nahi aa raha","language":"hi-Latn"}'

# Run the eval pipeline (no persist)
curl -X POST http://localhost:8000/evals/pipeline \
  -H "Content-Type: application/json" \
  -d '{"input_text":"ward 8 mein paani ki samasya","language":"hi-Latn"}'
```

## 4. Run the eval harness

```bash
# Local provider — fast, no API key needed.
# Expects 34/50 (keyword extraction doesn't cover Marathi/Tamil).
make bhasha-test

# Sarvam comparison (requires SARVAM_API_KEY in .env)
cd packages/bhasha-test
PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/python \
  -m bhasha_test evaluate \
  ../../data/eval_cases/grievance_cases.yaml \
  --provider sarvam
```

Expected output: 48/50 cases passing with Sarvam (98% category accuracy).

## 5. Mobile app (optional)

```bash
make mobile-dev
```

Opens Expo dev server. Scan the QR code with Expo Go on Android. On the submit
screen, type a grievance — text works with the default local provider.

Voice input requires a Sarvam API key (`SARVAM_API_KEY` in `.env`) because
speech-to-text and translation are Sarvam-only capabilities. With the key set,
speak a grievance; the complaint is transcribed, extracted, redacted, and
routed to the API.

## 6. Tear down

```bash
make down
```

Wipes Docker containers. Volumes persist unless you run `docker compose down -v`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `make demo` times out | Docker daemon not running. Start Docker Desktop. |
| Port 8000/3000 already in use | `lsof -i :8000` or `:3000` to find the process. |
| Dashboard shows "No issue clusters yet" | Seed didn't run. `docker compose up seed` manually. |
| Eval page shows 404 | No report yet. Run `bhasha-test evaluate ... --output data/eval_reports/latest.json`. |
| `make api-test` fails | Missing venv. `cd apps/api && uv sync`. |
