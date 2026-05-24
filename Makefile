.PHONY: api-test mobile-dev web-dev up down

api-test:
	cd apps/api && pytest -q

mobile-dev:
	cd apps/mobile && npx expo start

web-dev:
	cd apps/web && npm run dev

up:
	docker compose up --build

down:
	docker compose down
