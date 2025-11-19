# Changelog

All notable changes to this add-on will be documented in this file.

## 1.0.61 - 2025-11-19
- Security: changed certificate and password config fields to password type for UI hiding
- Chore: updated version metadata and repository listing to `1.0.61`

### Details (v1.0.61)
- Security: MQTT password, CA cert, client cert, and client key fields now use "password" schema type to hide sensitive data in Home Assistant UI
- Chore: bumped package metadata and repository version to `1.0.61`

## 1.0.60 - 2025-11-19
- Feature: support certificate content in config options, automatically writes to temp files for MQTT TLS
- Test: added tests for certificate content and path handling
- Chore: updated version metadata and repository listing to `1.0.60`

### Details (v1.0.60)
- Feature: MQTT certificate options now accept either file paths or certificate content (detected by "-----BEGIN" prefix)
- Test: added `test_cert_content_handling` and `test_cert_path_handling` to verify cert handling logic
- Chore: bumped package metadata and repository version to `1.0.60`

## 1.0.59 - 2025-11-19
- Test: added test to verify required Python files exist for Dockerfile copy operations
- Chore: updated version metadata and repository listing to `1.0.59`

### Details (v1.0.59)
- Test: added `test_container_files_present_for_dockerfile_copy` to ensure all necessary module files are present before deployment
- Chore: bumped package metadata and repository version to `1.0.59`

## 1.0.58 - 2025-11-19
- Fix: corrected Dockerfile to copy all Python files for proper module imports in container
- Chore: updated version metadata and repository listing to `1.0.58`

### Details (v1.0.58)
- Fix: Dockerfile now copies *.py files to root directory to ensure relative imports work in the container
- Chore: bumped package metadata and repository version to `1.0.58`

## 1.0.57 - 2025-11-19
- Fix: added debug logging for MQTT connection troubleshooting
- Chore: updated version metadata and repository listing to `1.0.57`

### Details (v1.0.57)
- Fix: added logging of loaded options and MQTT configuration on startup
- Fix: added validation to ensure mqtt_host is configured before attempting connection
- Chore: bumped package metadata and repository version to `1.0.57`

## 1.0.56 - 2025-11-19
- Chore: applied Black code formatting
- Chore: updated version metadata and repository listing to `1.0.56`

### Details (v1.0.56)
- Chore: code reformatted with Black for consistent style
- Chore: bumped package metadata and repository version to `1.0.56`

## 1.0.55 - 2025-11-19
- Feat: made telemetry publish interval configurable (default 30s)
- Chore: updated version metadata and repository listing to `1.0.55`

### Details (v1.0.55)
- Feat: added `telemetry_interval` config option to control how often telemetry is published (in seconds)
- Chore: bumped package metadata and repository version to `1.0.55`

## 1.0.54 - 2025-11-19
- Feat: increased telemetry publish frequency from 30s to 10s for more responsive monitoring
- Chore: updated version metadata and repository listing to `1.0.54`

### Details (v1.0.54)
- Feat: telemetry now publishes every 10 seconds instead of 30 for better real-time updates
- Chore: bumped package metadata and repository version to `1.0.54`

## 1.0.53 - 2025-11-19
- Feat: publish initial telemetry on MQTT connect for immediate state availability
- Chore: updated version metadata and repository listing to `1.0.53`

### Details (v1.0.53)
- Feat: on MQTT connection, publish both sensors (if HA configured) and telemetry immediately
- Chore: bumped package metadata and repository version to `1.0.53`

## 1.0.52 - 2025-11-19
- Fix: updated MQTT client to use Callback API version 2 to resolve deprecation warnings and improve compatibility
- Chore: updated version metadata and repository listing to `1.0.52`

### Details (v1.0.52)
- Fix: MQTT client initialization now uses `callback_api_version=2` when available, falling back gracefully for older paho-mqtt versions
- Chore: bumped package metadata and repository version to `1.0.52`

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
