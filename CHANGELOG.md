# Changelog

All notable changes to this repository are documented in this file.

## [1.1.29] - 2025-11-29

- Centralized sensor selection and registry
  - Added `central-core-hub/SENSOR_REGISTRY.yaml` as the single source-of-truth for which `sensor.*` and `binary_sensor.*` entities the add-on will provide to Vault.
  - Registry supports `allow`/`deny` modes and `fnmatch`-style wildcard patterns (e.g. `sensor.*temperature*`).
  - Runtime mtime-backed caching with `reload_sensor_registry()` for immediate application of updates.
  - All publish paths (full telemetry, selected sensors, HA websocket state events) consult the registry and only publish allowed entities.

- Remote updates via MQTT
  - Implemented a Vault command handler on `hubs/{client_id}/v1/cmd/registry/set` that atomically writes the registry file, reloads the runtime cache, and publishes an immediate ACK and a completion response with `set`/`failed` results.
  - Writes are performed atomically (temp file + rename) to avoid partial writes or corruption.
  - Token-based validation was implemented in the handler but remains disabled by default (no token configured) — token enforcement kept off per request.

- Home Assistant and telemetry improvements
  - Telemetry now includes discovered Home Assistant core information (`ha_version`) via a TTL-aware cache and an `on_ha_version` callback for one-shot publishes.
  - HA websocket listener made idempotent and robust to repeated start/stop calls.

- Tests, linting, and quality
  - Added unit tests for registry semantics (allow/deny/wildcards) and for the registry-via-MQTT flow.
  - Full test suite: 221 passed, 1 skipped (local run).
  - Migrated linting/config to `ruff` and updated `ruff.toml` to the new `lint` table layout to silence deprecation warnings.

- Misc
  - Ensure selected sensors are persisted for Vault authority and that reminder/publish flows respect the registry.
  - Version bumped and release tag `v1.1.29` created and pushed.

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
