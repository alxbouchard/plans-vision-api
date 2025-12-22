# Makefile for Plans Vision API

.PHONY: help install dev test run clean lint format fixtures

# Default target
help:
	@echo "Plans Vision API - Available commands:"
	@echo ""
	@echo "  make install    Install production dependencies"
	@echo "  make dev        Install development dependencies"
	@echo "  make test       Run all tests"
	@echo "  make run        Run development server"
	@echo "  make clean      Remove generated files"
	@echo "  make lint       Run linters"
	@echo "  make format     Format code"
	@echo "  make fixtures   Generate test fixtures"
	@echo ""

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
dev:
	pip install -e ".[dev]"

# Run all tests
test:
	pytest tests/ -v

# Run tests with coverage
coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

# Run development server
run:
	uvicorn src.main:app --reload --port 8000

# Run production server (single worker for SQLite)
run-prod:
	uvicorn src.main:app --host 0.0.0.0 --port 8000

# Clean generated files
clean:
	rm -rf __pycache__ .pytest_cache htmlcov .coverage
	rm -rf src/__pycache__ tests/__pycache__
	rm -rf uploads/*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run linters
lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

# Format code
format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# Generate test fixtures
fixtures:
	python testdata/generate_fixtures.py

# Database operations
db-reset:
	rm -f plans_vision.db
	@echo "Database reset. Will be recreated on next run."

# Check health
health:
	curl -s http://localhost:8000/health | python -m json.tool
