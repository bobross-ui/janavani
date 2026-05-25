.PHONY: api-test mobile-dev web-dev up down api-dev bhasha-test demo

api-test:
	cd apps/api && . .venv/bin/activate && pytest -q

bhasha-test:
	cd packages/bhasha-test && PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/pytest -q && PYTHONPATH=src:../../apps/api ../../apps/api/.venv/bin/python3 -m bhasha_test evaluate fixtures/janavani_seed.json --output /tmp/janavani-bhasha-test-report.json

api-dev:
	cd apps/api && set -a && . ../../.env && set +a && . .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

mobile-dev:
	cd apps/mobile && npx expo start

web-dev:
	cd apps/web && npm run dev

up:
	docker compose up --build

down:
	docker compose down

demo:
	docker compose down -v 2>/dev/null; true
	docker compose up --build -d postgres redis api web
	@echo "Waiting for API health check..."
	@n=0; while [ $$n -lt 30 ]; do \
		curl -sf http://localhost:8000/health > /dev/null 2>&1 && break; \
		sleep 2; n=$$((n+1)); \
	done; \
	if [ $$n -ge 30 ]; then \
		echo "ERROR: API did not become healthy within 60s"; exit 1; \
	fi
	@echo "API healthy — seeding demo data..."
	docker compose up --build --exit-code-from seed seed
	@echo ""
	@echo " Dashboard:  http://localhost:3000"
	@echo " API:        http://localhost:8000"
	@echo " API docs:   http://localhost:8000/docs"
	@echo ""
