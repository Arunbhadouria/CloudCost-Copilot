.PHONY: up down seed test eval lint build logs clean

# Default: start all services
up:
	docker-compose up -d --build || docker compose up -d --build

down:
	docker-compose down || docker compose down

logs:
	docker-compose logs -f || docker compose logs -f

# Seed database with real-format CSV sample and synthetic seeds
seed:
	@if docker-compose ps 2>/dev/null | grep -q cloudcost-api || docker compose ps 2>/dev/null | grep -q cloudcost-api; then \
		echo "Seeding inside Docker container..."; \
		docker-compose exec -T api python /app/scripts/seed.py || docker compose exec -T api python /app/scripts/seed.py; \
	else \
		echo "Seeding using local environment..."; \
		python scripts/seed.py; \
	fi

# Run backend unit tests and frontend build
test:
	@if docker compose ps | grep -q cloudcost-api; then \
		echo "Running tests inside Docker..."; \
		docker compose exec -T api pytest -v; \
	else \
		echo "Running local pytest..."; \
		pytest -v; \
	fi
	cd frontend && npm run build

# Run evaluation harness across held-out seeds
eval:
	@if docker compose ps | grep -q cloudcost-api; then \
		echo "Running evaluation harness inside Docker..."; \
		docker compose exec -T api python /app/backend/app/services/evaluation.py --seeds 100 101 102; \
	else \
		echo "Running local evaluation harness..."; \
		python backend/app/services/evaluation.py --seeds 100 101 102; \
	fi

# Lint backend and frontend
lint:
	cd frontend && npm run lint || true

# Sync live GCP project resources
sync-gcp:
	@if docker compose ps | grep -q cloudcost-api; then \
		docker compose exec -T api python /app/scripts/sync_gcp.py --project $(or $(PROJECT),big-formula-489906-e6); \
	else \
		python scripts/sync_gcp.py --project $(or $(PROJECT),big-formula-489906-e6); \
	fi

clean:
	docker compose down -v
	rm -rf backend/.pytest_cache frontend/dist

