# Changelog

All notable changes to this add-on will be documented in this file.

## 1.0.46 - 2025-11-18
- Release: bump to `1.0.46` and minor housekeeping
- Chore: updated version metadata and repository listing

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
