# Changelog

All notable changes to this add-on will be documented in this file.

## 1.0.0 - 2025-11-15
- Initial add-on repository layout and metadata
- `config.yaml` and `config.json` added
- Simple `icon.svg` and `logo.svg` added
## 1.0.43 - 2025-11-18
- Merge: added `Tests` section to `README.md` (on `docs/readme-tests` branch)
- Fix: use timezone-aware UTC datetimes to avoid `datetime.utcnow()` deprecation
- Misc: small workspace commits and housekeeping

## 1.0.42 - 2025-11-17
- Docker: install `py3-paho-mqtt` via `apk` to avoid pip/PEP668 build errors

## 1.0.41 - 2025-11-17
- Dockerfile: default `BUILD_FROM` fallback; updated configs and bumped version to `v1.0.41`
