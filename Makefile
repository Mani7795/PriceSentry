# PriceSentry — convenience commands

.PHONY: help up down restart logs psql shell-scraper shell-api \
        scrape-once bootstrap-reviews embed-reviews test clean

help:
	@echo "PriceSentry — useful targets"
	@echo "  make up                  Start the local stack (Postgres, scraper, API)"
	@echo "  make down                Stop the stack (preserves data)"
	@echo "  make restart             Restart all services"
	@echo "  make logs                Tail logs from all services"
	@echo "  make psql                Open a psql shell against the local Postgres"
	@echo "  make shell-scraper       Open a bash shell in the scraper container"
	@echo "  make shell-api           Open a bash shell in the api container"
	@echo "  make scrape-once         Run the scraper one time against \$$SCRAPE_TARGET"
	@echo "  make bootstrap-reviews   Load Amazon Pet Supplies reviews from Hugging Face"
	@echo "  make embed-reviews       Embed any reviews missing embeddings"
	@echo "  make test                Run smoke tests"
	@echo "  make clean               Remove containers AND data (destructive)"

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=200

psql:
	docker compose exec postgres psql -U pricesentry -d pricesentry

shell-scraper:
	docker compose exec scraper bash

shell-api:
	docker compose exec api bash

scrape-once:
	docker compose exec scraper python -m scraper.main --once

bootstrap-reviews:
	docker compose exec scraper python /app/scripts/bootstrap_amazon_reviews.py --limit 50000 --batch-size 500

embed-reviews:
	docker compose exec scraper python /app/scripts/embed_reviews.py --batch-size 64

test:
	docker compose exec scraper pytest -q /app/tests

clean:
	docker compose down -v
