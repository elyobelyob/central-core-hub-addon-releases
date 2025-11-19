# Changelog

All notable changes to this add-on will be documented in this file.

## 1.0.51 - 2025-11-19
- Feat: added UTC timestamps to all log messages for better debugging
- Chore: formatted code with Black and fixed Flake8 linting issues
- Chore: updated version metadata and repository listing to `1.0.51`

### Details (v1.0.51)
- Feat: all print statements replaced with timestamped logging using ISO 8601 UTC format
- Chore: code reformatted with Black for consistent style
- Chore: resolved all Flake8 linting warnings and errors
- Chore: bumped package metadata and repository version to `1.0.51`

## 1.0.50 - 2025-11-19
- Test: comprehensive unit test suite with 95%+ coverage; Docker-based cross-platform testing
- Feat: include friendly names and enabled status in sensor telemetry payloads
- Chore: updated version metadata and repository listing to `1.0.50`
- Fix: removed hard-coded paths in tests for portability

### Details (v1.0.50)
- Test: added extensive unit tests covering MQTT command handling, telemetry publishing, HA API integration, TLS configuration, and error scenarios
- Test: achieved 95% code coverage with 137 passing tests
- Test: verified cross-platform reliability via Docker testing
- Feat: sensor telemetry now includes `names` (friendly names) and `enabled` (disabled_by status) maps
- Chore: bumped package metadata and repository version to `1.0.50`
- Fix: test paths now use dynamic resolution instead of hard-coded user paths

## 1.0.49 - 2025-11-18
- Release: bump to `1.0.49` and minor housekeeping
- Chore: updated version metadata and repository listing

### Details (v1.0.49)
- Feat: enhanced sensor telemetry with attributes and readback values
- Test: additional unit tests for HA API mocking and telemetry assertions

## 1.0.48 - 2025-11-18
- Docs: updated README with sensor telemetry examples
- Chore: version bump to `1.0.48`

## 1.0.47 - 2025-11-18
- Docs: expanded README and CHANGELOG with sensor telemetry and command details
- Chore: bumped package metadata and repository version to `1.0.47`

## 1.0.46 - 2025-11-18
- Release: bump to `1.0.46` and minor housekeeping
- Chore: updated version metadata and repository listing

### Details (v1.0.46)
- Feat: support `sensors/set` command to set states via Home Assistant REST API and publish authoritative telemetry immediately after.
- Feat: read back entity `state` and `attributes` from HA after setting and include both `data` and `attributes` in `hubs/<client_id>/telemetry/sensors` payloads.
- Test: expanded unit tests to stub POST/GET and assert telemetry and attributes are published.

## 1.0.45 - 2025-11-18
- Chore: remove legacy MQTT topic publishing (development mode uses preferred Vault topics only)
- Test: add additional unit tests and increase coverage; add `.gitignore` to ignore virtualenv and test artifacts

## 1.0.44 - 2025-11-18
- Feat: Add Vault-compatible sensors command handling (`hubs/<id>/cmd/sensors/poll`) with ACK and completion responses
- Feat: Publish HA sensors on startup and hourly to preferred Vault topic
- Test: add unit tests and CI test workflow; improve test coverage

## 1.0.43 - 2025-11-18
- Merge: added `Tests` section to `README.md` (on `docs/readme-tests` branch)
- Fix: use timezone-aware UTC datetimes to avoid `datetime.utcnow()` deprecation
- Misc: small workspace commits and housekeeping

## 1.0.42 - 2025-11-17
- Docker: install `py3-paho-mqtt` via `apk` to avoid pip/PEP668 build errors

## 1.0.41 - 2025-11-17
- Dockerfile: default `BUILD_FROM` fallback; updated configs and bumped version to `v1.0.41`

## 1.0.0 - 2025-11-15
- Initial add-on repository layout and metadata
- `config.yaml` and `config.json` added
- Simple `icon.svg` and `logo.svg` added
