# Changelog

All notable changes to this repository are documented in this file.

## [1.1.27] - 2025-11-28
  - Add TTL-aware in-memory `ha_version` cache (timestamped) and `get_ha_version(ttl_seconds)` API.
  - Persist discovered `ha_version` to add-on options and expose `OPTIONS_PATH` for tests.
  - Add `on_ha_version` callback to `HAWebSocketListener` allowing the client to perform a one-shot telemetry publish when HA version is discovered.
  - Make `HAWebSocketListener.stop()` idempotent and robust to repeated calls.
  - Wire `HAWebSocketListener` startup/stop into `CentralCoreClient` and pass `on_ha_version` callback.
  - Prefer TTL-aware `get_ha_version(ttl_seconds=300)` when available.
  - Add `_on_ha_version()` to trigger a one-shot telemetry publish when version changes.
  - Add unit tests for HA version TTL and one-shot publish behavior.
  - Add additional targeted telemetry and topics tests.
  - Linting: continue using `ruff` as the unified linter/formatter; auto-fixed a small unused-import in tests.

### Commits included in this release

The following commit messages were extracted from git for the range `v1.1.26..v1.1.27`:

- chore(release): include all changes; bump version to 1.1.27 (1f730f9)
- Temporary release: bumped version as an intermediate step during development.

### Commits included in this release

The following commit messages were extracted from git for the range `v1.1.25..v1.1.26`:

- chore(release): bump version to 1.1.26 (7076e68)
- test(ha_client): add timeout, malformed-json, and pending-request timeout tests (56785e5)
## [1.1.25] - (previous)
- Baseline prior to recent HA websocket and telemetry improvements.

### Notes
- Tag `v1.1.27` created and pushed to `origin`.
- If you want a GitHub release entry created from this tag, I can draft release notes and create the release on GitHub.
## Unreleased

- Bump version to `1.0.97` for next development cycle.

## v1.0.72 - 2025-11-21

- Remind Vault via MQTT when sensors are selected (publish selected sensors to Vault topic).
- Persist Vault-authoritative `selected_sensors` in `CentralCoreClient` so Vault remains authoritative.
- Add extensive unit tests for `handlers.py`, `telemetry.py`, and `mqtt_runtime.py`.
- Add `requirements-dev.txt` with test and lint dependencies.

## Earlier

- See repository history for prior release notes.
