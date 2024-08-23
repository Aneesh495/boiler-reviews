PYTHON ?= venv/bin/python
PIP ?= venv/bin/pip
DATABASE_URL ?= sqlite:///instance/boiler_reviews.sqlite3
export DATABASE_URL

.PHONY: bootstrap dev demo test test-integration test-e2e test-solver migrate-legacy-dry-run benchmark acceptance verify census

bootstrap:
	@test -x "$(PYTHON)" || (python3 -m venv venv && venv/bin/pip install -r requirements.txt)
	@mkdir -p instance evidence docs/generated
	@test -f .env || cp .env.example .env
	@$(PYTHON) -m boiler_reviews.db.migrate upgrade

dev:
	@$(PYTHON) -m boiler_reviews.web run

demo:
	@$(PYTHON) -m boiler_reviews.cli demo

test:
	@$(PYTHON) -m pytest -q

test-integration:
	@$(PYTHON) -m pytest -q -m integration

test-e2e:
	@$(PYTHON) -m pytest -q -m e2e

test-solver:
	@$(PYTHON) -m pytest -q -m solver

migrate-legacy-dry-run:
	@$(PYTHON) -m boiler_reviews.cli migrate-legacy --dry-run

benchmark:
	@$(PYTHON) -m boiler_reviews.cli benchmark

acceptance:
	@$(PYTHON) -m boiler_reviews.cli acceptance

verify:
	@$(PYTHON) -m boiler_reviews.cli verify

census:
	@$(PYTHON) -m boiler_reviews.cli census
