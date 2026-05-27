## ── venv (mirrors the official LS extension template) ────────────────────────
VENV_BIN      = python3 -m venv
VENV_DIR     ?= .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_RUN      = . $(VENV_ACTIVATE)

PACKAGE = localstack_file_api
TESTS   = tests

## ── venv bootstrap ───────────────────────────────────────────────────────────
venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): pyproject.toml
	test -d $(VENV_DIR) || $(VENV_BIN) $(VENV_DIR)
	$(VENV_RUN); pip install --upgrade pip setuptools plux
	$(VENV_RUN); pip install -e ".[dev]"
	touch $(VENV_DIR)/bin/activate

## ── install (official target) ────────────────────────────────────────────────
install: venv                                       ## Install into .venv + generate plux entrypoints
	$(VENV_RUN); python -m plux entrypoints

## ── dev mode (use alongside `localstack extensions dev enable .`) ────────────
install-dev: install                                ## Alias: same as install (dev extras already included)

## ── test ─────────────────────────────────────────────────────────────────────
test: venv                                          ## Run the test suite
	$(VENV_RUN); python -m pytest $(TESTS) -v

test-cov: venv                                      ## Tests + HTML coverage report (htmlcov/)
	$(VENV_RUN); python -m pytest $(TESTS) -v \
		--cov=$(PACKAGE) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=80
	@echo "Coverage report → htmlcov/index.html"

test-fast: venv                                     ## Run tests, stop on first failure
	$(VENV_RUN); python -m pytest $(TESTS) -x -q

## ── lint & format ────────────────────────────────────────────────────────────
lint: venv                                          ## Lint with ruff
	$(VENV_RUN); python -m ruff check $(PACKAGE) $(TESTS)

lint-fix: venv                                      ## Auto-fix ruff warnings
	$(VENV_RUN); python -m ruff check --fix $(PACKAGE) $(TESTS)

format: venv                                        ## Format with black + isort
	$(VENV_RUN); python -m black $(PACKAGE) $(TESTS)
	$(VENV_RUN); python -m isort $(PACKAGE) $(TESTS)

format-check: venv                                  ## Check formatting (CI)
	$(VENV_RUN); python -m black --check $(PACKAGE) $(TESTS)
	$(VENV_RUN); python -m isort --check-only $(PACKAGE) $(TESTS)

check: format-check lint test                       ## Full CI gate (format + lint + test)

## ── build & publish (official targets) ──────────────────────────────────────
dist: venv                                          ## Build sdist + wheel into dist/
	$(VENV_RUN); python -m build

publish: clean-dist venv dist                       ## Publish to PyPI via twine
	$(VENV_RUN); pip install --upgrade twine; twine upload dist/*

publish-test: clean-dist venv dist                  ## Publish to TestPyPI
	$(VENV_RUN); pip install --upgrade twine; twine upload --repository testpypi dist/*

## ── clean (official targets) ─────────────────────────────────────────────────
clean:                                              ## Remove venv + build artefacts
	rm -rf $(VENV_DIR)/
	rm -rf build/
	rm -rf .eggs/
	rm -rf *.egg-info/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -delete

clean-dist: clean                                   ## clean + remove dist/
	rm -rf dist/

clean-test:                                         ## Remove test/coverage artefacts only
	rm -rf .pytest_cache/ htmlcov/ .coverage coverage.xml

## ── help ─────────────────────────────────────────────────────────────────────
help:                                               ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
.PHONY: venv install install-dev test test-cov test-fast \
        lint lint-fix format format-check check \
        dist publish publish-test clean clean-dist clean-test help
