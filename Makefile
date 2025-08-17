# Freqtrade MCP Server Makefile

.PHONY: help install install-dev test lint format type-check clean run

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv pip install -r requirements.txt

install-dev:  ## Install development dependencies
	uv pip install -r requirements.txt
	uv pip install -e ".[dev]"

test:  ## Run tests
	pytest tests/ -v

lint:  ## Run linting
	ruff check src/
	ruff check tests/

format:  ## Format code
	black src/ tests/
	ruff check --fix src/ tests/

type-check:  ## Run type checking
	mypy src/

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:  ## Run the MCP server
	python run_server.py

build:  ## Build package
	python -m build

check-all: lint type-check test  ## Run all checks

.DEFAULT_GOAL := help