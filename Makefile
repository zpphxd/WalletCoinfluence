.PHONY: help dev test up down seed migration migrate clean install format lint

help:
	@echo "Available targets:"
	@echo "  install    - Install dependencies with poetry"
	@echo "  dev        - Run development environment"
	@echo "  test       - Run tests with pytest"
	@echo "  up         - Start docker-compose services"
	@echo "  down       - Stop docker-compose services"
	@echo "  migration  - Generate new Alembic migration"
	@echo "  migrate    - Run Alembic migrations"
	@echo "  seed       - Seed database with initial data"
	@echo "  format     - Format code with black"
	@echo "  lint       - Lint code with ruff and mypy"
	@echo "  clean      - Clean cache and build files"

install:
	poetry install

dev:
	poetry run uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

test:
	poetry run pytest -v --cov=src --cov-report=html

up:
	docker-compose up -d

down:
	docker-compose down

migration:
	poetry run alembic revision --autogenerate -m "$(msg)"

migrate:
	poetry run alembic upgrade head

seed:
	poetry run python -m src.scripts.seed

format:
	poetry run black src tests
	poetry run ruff check --fix src tests

lint:
	poetry run ruff check src tests
	poetry run mypy src

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache
