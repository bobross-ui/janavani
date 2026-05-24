.PHONY: api-test mobile-dev web-dev up down api-dev bhasha-test

api-test:
	cd apps/api && . .venv/bin/activate && pytest -q

bhasha-test:
	cd packages/bhasha-test && PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/pytest -q && PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/python3 -m bhasha_test evaluate fixtures/janavani_seed.json --output /tmp/janavani-bhasha-test-report.json

api-dev:
	cd apps/api && . .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

mobile-dev:
	cd apps/mobile && npx expo start

web-dev:
	cd apps/web && npm run dev

up:
	docker compose up --build

down:
	docker compose down
