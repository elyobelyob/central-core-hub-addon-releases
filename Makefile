.PHONY: release coverage

PYTHON ?= .venv/bin/python
# Local coverage floor (CI does not run this target). Raise it when coverage
# goes up; never lower it to make a change pass.
COVERAGE_FAIL_UNDER ?= 96

# Usage: make coverage
coverage:
	$(PYTHON) -m coverage run --source=. --omit='*/tests/*,*/test_*,.venv/*' -m pytest -q
	$(PYTHON) -m coverage report --fail-under=$(COVERAGE_FAIL_UNDER)

# Usage:
#   make release VERSION=1.0.89 [GIT_BRANCH=main]
# This bumps version files via version_manager.py, commits, tags, and pushes.
release:
	@if [ -z "$(VERSION)" ]; then echo "VERSION is required (e.g. make release VERSION=1.0.89)"; exit 1; fi
	@echo "Setting version to $(VERSION)"
	python3 version_manager.py set $(VERSION)
	git add central-core-hub/config.json central-core-hub/config.yaml repository.json
	git commit -m "Bump version metadata to $(VERSION)"
	git tag -a v$(VERSION) -m "v$(VERSION)"
	git push origin $(or $(GIT_BRANCH),main)
	git push origin v$(VERSION)
