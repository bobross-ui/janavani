.PHONY: api-test mobile-dev web-dev up down api-dev

api-test:
	cd apps/api && . .venv/bin/activate && pytest -q

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
