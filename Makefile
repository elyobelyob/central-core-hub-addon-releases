.PHONY: release

# Usage:
#   make release VERSION=1.0.87 [GIT_BRANCH=main]
# This bumps version files via version_manager.py, commits, tags, and pushes.
release:
	@if [ -z "$(VERSION)" ]; then echo "VERSION is required (e.g. make release VERSION=1.0.87)"; exit 1; fi
	@echo "Setting version to $(VERSION)"
	python3 version_manager.py set $(VERSION)
	git add central-core-hub/config.json central-core-hub/config.yaml repository.json
	git commit -m "Bump version metadata to $(VERSION)"
	git tag -a v$(VERSION) -m "v$(VERSION)"
	git push origin $(or $(GIT_BRANCH),main)
	git push origin v$(VERSION)
