# Changelog

## [1.1.74] - 2025-12-17

- chore(release): bump version to 2.0.29
- test: remove unused import
- test: autouse fixture mock HA WS and suppress stdout during tests
- test: fix sys usage in autouse ha ws fixture
- test: autouse HA websocket fixture - remove duplicate imports
- test: autouse HA websocket fixture imports at top
- test: autouse fixture to mock HA websocket and silence WS logs
- test(coverage): execute filler in fresh namespace using source path
- test(coverage): clean unused typing import
- test(coverage): remove unused typing.cast import
- test(coverage): ensure filler uses source .py path for accurate attribution
- chore(sensor-registry): revert manual entries; manage via tooling
- chore(sensor-registry): add door sensors with device_class fallback
- chore(release): bump version to 2.0.28
- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- chore(release): bump version to 2.0.29
- test: remove unused import
- test: autouse fixture mock HA WS and suppress stdout during tests
- test: fix sys usage in autouse ha ws fixture
- test: autouse HA websocket fixture - remove duplicate imports
- test: autouse HA websocket fixture imports at top
- test: autouse fixture to mock HA websocket and silence WS logs
- test(coverage): execute filler in fresh namespace using source path
- test(coverage): clean unused typing import
- test(coverage): remove unused typing.cast import
- test(coverage): ensure filler uses source .py path for accurate attribution
- chore(sensor-registry): revert manual entries; manage via tooling
- chore(sensor-registry): add door sensors with device_class fallback
- chore(release): bump version to 2.0.28
- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.29] - 2025-12-17

- test: remove unused import
- test: autouse fixture mock HA WS and suppress stdout during tests
- test: fix sys usage in autouse ha ws fixture
- test: autouse HA websocket fixture - remove duplicate imports
- test: autouse HA websocket fixture imports at top
- test: autouse fixture to mock HA websocket and silence WS logs
- test(coverage): execute filler in fresh namespace using source path
- test(coverage): clean unused typing import
- test(coverage): remove unused typing.cast import
- test(coverage): ensure filler uses source .py path for accurate attribution
- chore(sensor-registry): revert manual entries; manage via tooling
- chore(sensor-registry): add door sensors with device_class fallback
- chore(release): bump version to 2.0.28
- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- test: remove unused import
- test: autouse fixture mock HA WS and suppress stdout during tests
- test: fix sys usage in autouse ha ws fixture
- test: autouse HA websocket fixture - remove duplicate imports
- test: autouse HA websocket fixture imports at top
- test: autouse fixture to mock HA websocket and silence WS logs
- test(coverage): execute filler in fresh namespace using source path
- test(coverage): clean unused typing import
- test(coverage): remove unused typing.cast import
- test(coverage): ensure filler uses source .py path for accurate attribution
- chore(sensor-registry): revert manual entries; manage via tooling
- chore(sensor-registry): add door sensors with device_class fallback
- chore(release): bump version to 2.0.28
- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.28] - 2025-12-17

- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.27] - 2025-12-17

- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.26] - 2025-12-16

- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.25] - 2025-12-16

- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.24] - 2025-12-16

- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.23] - 2025-12-16

- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.22] - 2025-12-16

- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.21] - 2025-12-16

- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.20] - 2025-12-16

- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.19] - 2025-12-16

- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.18] - 2025-12-16

- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.17] - 2025-12-16

- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.16] - 2025-12-16

- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.15] - 2025-12-16

- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.14] - 2025-12-16

- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.13] - 2025-12-16

- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.12] - 2025-12-16

- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.11] - 2025-12-16

- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.10] - 2025-12-16

- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.9] - 2025-12-16

- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.8] - 2025-12-16

- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [2.0.7] - 2025-12-16

- refactor: remove client-side sensor device class filtering

### Commits included in this release

- refactor: remove client-side sensor device class filtering

## [2.0.6] - 2025-12-15

- chore(release): bump version to 2.0.6

## [2.0.5] - 2025-12-15

- fix(tests): resolve remaining telemetry fallback test failures

### Commits included in this release

- fix(tests): resolve remaining telemetry fallback test failures

## [2.0.4] - 2025-12-15

- fix(tests): resolve integration and telemetry test failures
- fix(tests): remove unused imports in integration test

### Commits included in this release

- fix(tests): resolve integration and telemetry test failures
- fix(tests): remove unused imports in integration test

## [2.0.3] - 2025-12-15

- chore(release): bump version to 2.0.3

## [2.0.2] - 2025-12-15

- fix(versioning): correct changelog generation logic and regenerate 2.0.1/1.1.77 entries; restore mqtt_trigger_update.py

### Commits included in this release

- fix(versioning): correct changelog generation logic and regenerate 2.0.1/1.1.77 entries; restore mqtt_trigger_update.py

## [2.0.1] - 2025-12-15

- chore(release): bump version to 2.0.1

### Commits included in this release

- chore(release): bump version to 2.0.1

## [1.1.77] - 2025-12-15

- chore(release): bump version to 1.1.77

### Commits included in this release

- chore(release): bump version to 1.1.77

## [1.1.76] - 2025-12-15

- fix(versioning): correct changelog generation and update 1.1.76 notes
- Bump version to 1.1.76
- fix: Store addon version in metadata file instead of options.json

### Commits included in this release

- fix(versioning): correct changelog generation and update 1.1.76 notes
- Bump version to 1.1.76
- fix: Store addon version in metadata file instead of options.json

## [1.1.75] - 2025-12-17

- test: add release suites and update registry
- fix: make HA version persistence resilient
- chore(release): bump version to 2.0.29
- test: remove unused import
- test: autouse fixture mock HA WS and suppress stdout during tests
- test: fix sys usage in autouse ha ws fixture
- test: autouse HA websocket fixture - remove duplicate imports
- test: autouse HA websocket fixture imports at top
- test: autouse fixture to mock HA websocket and silence WS logs
- test(coverage): execute filler in fresh namespace using source path
- test(coverage): clean unused typing import
- test(coverage): remove unused typing.cast import
- test(coverage): ensure filler uses source .py path for accurate attribution
- chore(sensor-registry): revert manual entries; manage via tooling
- chore(sensor-registry): add door sensors with device_class fallback
- chore(release): bump version to 2.0.28
- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

### Commits included in this release

- test: add release suites and update registry
- fix: make HA version persistence resilient
- chore(release): bump version to 2.0.29
- test: remove unused import
- test: autouse fixture mock HA WS and suppress stdout during tests
- test: fix sys usage in autouse ha ws fixture
- test: autouse HA websocket fixture - remove duplicate imports
- test: autouse HA websocket fixture imports at top
- test: autouse fixture to mock HA websocket and silence WS logs
- test(coverage): execute filler in fresh namespace using source path
- test(coverage): clean unused typing import
- test(coverage): remove unused typing.cast import
- test(coverage): ensure filler uses source .py path for accurate attribution
- chore(sensor-registry): revert manual entries; manage via tooling
- chore(sensor-registry): add door sensors with device_class fallback
- chore(release): bump version to 2.0.28
- fix(fetch_sensors): only enforce device_class when registry present
- fix(fetch_sensors): restore implementation and enforce device_class resolution
- chore(release): bump version to 2.0.27 and update sensor registry/device_class handling
- Bump to 2.0.26
- Add device_classes to WebSocket state_changed events in _on_ha_state_event
- Add device_classes to monitor telemetry ACK response
- Bump to 2.0.25
- Add device_classes to ACK response payloads
- Bump to 2.0.24
- Add device_classes to all sensor request response payloads
- Add device_classes map to sensor response payloads
- Fix device_class filtering to be case-insensitive
- Bump to 2.0.23
- Fix device_class filtering to exclude sensors without a device_class
- Revert websockets.legacy deprecation warning suppression
- Suppress websockets.legacy deprecation warning in tests
- Bump to 2.0.22
- chore: bump version to 2.0.21
- fix: only publish telemetry when vault requests sensors via device_class filter
- chore: bump version to 2.0.20
- fix: remove safe_device_classes from publish_sensors methods, rely on SENSOR_REGISTRY filtering only
- chore: bump version to 2.0.19
- fix: always apply SENSOR_REGISTRY filtering to telemetry sensors, only vault device_class filtering on top
- chore: bump version to 2.0.18
- fix: directly attach get_cpu_percent to test module for caller check in _get_cpu_percent fallback
- chore: bump version to 2.0.17
- fix: ensure test_telemetry_get_cpu_from_mqtt_client_module removes helpers to test fallback
- chore: bump version to 2.0.16
- fix: allow _get_cpu_percent fallback chain to continue on caller module check failure
- chore: bump version to 2.0.15
- test: update tests for device_class filtering by vault
- chore: bump version to 2.0.14
- fix: remove undefined DEFAULT_SAFE_DEVICE_CLASSES reference
- chore: bump version to 2.0.13
- fix: correct YAML syntax in GitHub Actions workflow
- chore: bump version to 2.0.12
- refactor: filter sensors by device_class instead of entity_id
- chore: bump version to 2.0.11
- refactor: filter sensors by vault request list
- chore: bump version to 2.0.10
- refactor: return all sensors regardless of vault request
- chore: bump version to 2.0.9
- refactor: remove device class filtering fallback
- chore: bump version to 2.0.8
- refactor: restore device class filtering as fallback
- chore: bump version to 2.0.7
- refactor: remove client-side sensor device class filtering

## [1.1.73] - 2025-12-11

- fix(telemetry): force telemetry_interval into published payload to avoid schema defaulting back to 30s

## [1.1.72] - 2025-12-11

- fix(telemetry): honor user-defined telemetry_interval by refreshing options before publish
- chore: allow options loading to fall back to default path when env override is missing

## [1.1.71] - 2025-12-11

- feat: exclude sensors missing device_class from telemetry/registry paths
- test: align device_class filtering expectations

- chore(release): bump version to 1.1.48
- add ha_version

## [1.1.47] - 2025-11-30

- chore(release): bump version to 1.1.47
- feat(handlers): include per-sensor 'observed' timestamps in telemetry and sensors/set ACKs

### Commits included in this release

- chore(release): bump version to 1.1.47
- feat(handlers): include per-sensor 'observed' timestamps in telemetry and sensors/set ACKs

## [1.1.46] - 2025-11-30

- chore(release): bump version to 1.1.46

### Commits included in this release

- chore(release): bump version to 1.1.46

## [1.1.45] - 2025-11-30

- chore(release): bump version to 1.1.45
- feat(outbox): persistent outbox for eligible MQTT publishes (configurable file and max size)

### Commits included in this release

- chore(release): bump version to 1.1.45
- feat(outbox): persistent outbox for eligible MQTT publishes (configurable file and max size)

## [1.1.42] - 2025-11-30

- chore(release): bump version to 1.1.42
- fix(persist): store selected sensors in add-on data (/data) and migrate package copy

### Commits included in this release

- chore(release): bump version to 1.1.42
- fix(persist): store selected sensors in add-on data (/data) and migrate package copy

## [1.1.41] - 2025-11-30

- chore(release): bump version to 1.1.41
- style: apply ruff --fix formatting changes
- feat(handlers): include sensor attributes in telemetry and sensors/set ACK result

### Commits included in this release

- chore(release): bump version to 1.1.41
- style: apply ruff --fix formatting changes
- feat(handlers): include sensor attributes in telemetry and sensors/set ACK result

## [1.1.40] - 2025-11-30

- chore(release): bump version to 1.1.40
- fix(scripts): support multiple ruff auto-fix commands for compatibility
- chore(scripts): run ruff --fix in release script when not --dry-run
- chore(scripts): run ruff and pyright before pytest in release script
- fix(scripts): robust Python heredoc args; add writability checks
- chore(scripts): add release.sh with --dry-run support
- chore(scripts): add release.sh to automate version bump, tag and push

### Commits included in this release

- chore(release): bump version to 1.1.40
- fix(scripts): support multiple ruff auto-fix commands for compatibility
- chore(scripts): run ruff --fix in release script when not --dry-run
- chore(scripts): run ruff and pyright before pytest in release script
- fix(scripts): robust Python heredoc args; add writability checks
- chore(scripts): add release.sh with --dry-run support
- chore(scripts): add release.sh to automate version bump, tag and push

## [1.1.35] - 2025-11-30

- chore(release): bump version to 1.1.35
- feat(handlers): include monitor telemetry in completion ACK for sensors.set; update tests

### Commits included in this release

- chore(release): bump version to 1.1.35
- feat(handlers): include monitor telemetry in completion ACK for sensors.set; update tests

## [1.1.34] - 2025-11-30

- chore(release): bump version to 1.1.34
- test(handlers): assert sensors/set publishes current telemetry to preferred_sensors_topic
- feat(handlers): publish current sensor values immediately on monitor/select requests
- log: include sanitized full payload in MQTT publish result logs

### Commits included in this release

- chore(release): bump version to 1.1.34
- test(handlers): assert sensors/set publishes current telemetry to preferred_sensors_topic
- feat(handlers): publish current sensor values immediately on monitor/select requests
- log: include sanitized full payload in MQTT publish result logs

## [1.1.33] - 2025-11-30

- chore(release): bump version to 1.1.33 and persist selected sensors; add tests

### Commits included in this release

- chore(release): bump version to 1.1.33 and persist selected sensors; add tests

## [1.1.32] - 2025-11-30

- chore(release): bump version to 1.1.32
- fix(config): normalize central-core-hub/config.json formatting

### Commits included in this release

- chore(release): bump version to 1.1.32
- fix(config): normalize central-core-hub/config.json formatting

## [1.1.31] - 2025-11-30

- chore(release): bump version to 1.1.31

### Commits included in this release

- chore(release): bump version to 1.1.31

## [1.1.30] - 2025-11-29

- chore(release): bump version to 1.1.30
- chore: commit remaining changes (registry, tests, handlers, mqtt_client, ruff)
- chore(release): add CHANGELOG entry for v1.1.29

### Commits included in this release

- chore(release): bump version to 1.1.30
- chore: commit remaining changes (registry, tests, handlers, mqtt_client, ruff)
- chore(release): add CHANGELOG entry for v1.1.29

## [1.1.28] - 2025-11-28

- chore(release): bump version to 1.1.28
- docs(readme): backfill release notes from git history
- docs(changelog): backfill commits for v1.1.26..v1.1.27
- docs(changelog): add release notes for v1.1.27
- chore(release): include all changes; bump version to 1.1.27

### Commits included in this release

- chore(release): bump version to 1.1.28
- docs(readme): backfill release notes from git history
- docs(changelog): backfill commits for v1.1.26..v1.1.27
- docs(changelog): add release notes for v1.1.27
- chore(release): include all changes; bump version to 1.1.27

## [1.1.26] - 2025-11-28

- chore(release): bump version to 1.1.26
- test(ha_client): add timeout, malformed-json, and pending-request timeout tests
- Ensure websocket-client is installed
- Redact HA token in options log
- Flush HA log output
- Bump version for 1.1.22
- Bump version for 1.1.21
- More HA websocket diagnostics
- Log HA websocket startup
- Bump version for 1.1.18
- Mirror CI quality steps locally
- Exclude venv from pyright and fix python invocations
- Ensure local quality script runs pyright
- Capture HA version even with JSON cert bundles
- Drop legacy command topics
- Add config update command
- Include HA version in telemetry

### Commits included in this release

- chore(release): bump version to 1.1.26
- test(ha_client): add timeout, malformed-json, and pending-request timeout tests
- Ensure websocket-client is installed
- Redact HA token in options log
- Flush HA log output
- Bump version for 1.1.22
- Bump version for 1.1.21
- More HA websocket diagnostics
- Log HA websocket startup
- Bump version for 1.1.18
- Mirror CI quality steps locally
- Exclude venv from pyright and fix python invocations
- Ensure local quality script runs pyright
- Capture HA version even with JSON cert bundles
- Drop legacy command topics
- Add config update command
- Include HA version in telemetry

## [1.1.13] - 2025-11-28

- chore(release): bump version to 1.1.13
- chore(diagnostics): log presence of HA API url/token (no secrets)

### Commits included in this release

- chore(release): bump version to 1.1.13
- chore(diagnostics): log presence of HA API url/token (no secrets)

## [1.1.12] - 2025-11-28

- chore(release): bump version to 1.1.12
- chore(ci): remove Black config; document Ruff formatting and linting
- chore(ci): configure ruff to match Black/Flake8 behavior; fix test import

### Commits included in this release

- chore(release): bump version to 1.1.12
- chore(ci): remove Black config; document Ruff formatting and linting
- chore(ci): configure ruff to match Black/Flake8 behavior; fix test import

## [1.1.11] - 2025-11-28

- chore(release): bump version to 1.1.11
- fix(ha): make HAWebSocketListener.stop idempotent; add idempotent stop test

### Commits included in this release

- chore(release): bump version to 1.1.11
- fix(ha): make HAWebSocketListener.stop idempotent; add idempotent stop test

## [1.1.10] - 2025-11-28

- chore(release): bump version to 1.1.10

### Commits included in this release

- chore(release): bump version to 1.1.10

## [1.1.9] - 2025-11-28

- chore(release): bump version to 1.1.9
- ci: fix ruff.toml format (top-level keys) to satisfy ruff parser in CI
- ci: enable pip cache and cache pip downloads for ruff/wheels
- chore(ci): add pre-commit ruff hook and ruff.toml config
- chore(ci): replace flake8/black with ruff; update CI and quality scripts

### Commits included in this release

- chore(release): bump version to 1.1.9
- ci: fix ruff.toml format (top-level keys) to satisfy ruff parser in CI
- ci: enable pip cache and cache pip downloads for ruff/wheels
- chore(ci): add pre-commit ruff hook and ruff.toml config
- chore(ci): replace flake8/black with ruff; update CI and quality scripts

## [1.1.8] - 2025-11-28

- chore(telemetry): add diagnostic logging for HA info fetch; chore(release): bump 1.1.8

### Commits included in this release

- chore(telemetry): add diagnostic logging for HA info fetch; chore(release): bump 1.1.8

## [1.1.7] - 2025-11-28

- chore(lint): fix flake8 issues; chore(release): bump version to 1.1.7
- ci: retrigger workflows after lint fixes

### Commits included in this release

- chore(lint): fix flake8 issues; chore(release): bump version to 1.1.7
- ci: retrigger workflows after lint fixes

## [1.1.6] - 2025-11-28

- chore(release): bump version to 1.1.6

### Commits included in this release

- chore(release): bump version to 1.1.6

## [1.1.5] - 2025-11-28

- chore(release): bump version to 1.1.5

### Commits included in this release

- chore(release): bump version to 1.1.5

## [1.1.4] - 2025-11-28

- chore(release): bump manifests to 1.1.4; add HA telemetry tests

### Commits included in this release

- chore(release): bump manifests to 1.1.4; add HA telemetry tests

## [1.1.3] - 2025-11-28

- chore(release): bump manifests to 1.1.3; CI: add PyYAML for YAML parsing in tests
- test(manifest): avoid PyYAML dependency; parse config.yaml for version

### Commits included in this release

- chore(release): bump manifests to 1.1.3; CI: add PyYAML for YAML parsing in tests
- test(manifest): avoid PyYAML dependency; parse config.yaml for version

## [1.1.2] - 2025-11-28

- chore(release): bump manifests to 1.1.2

### Commits included in this release

- chore(release): bump manifests to 1.1.2

## [1.1.1] - 2025-11-28

- test(manifest): ensure repository.json, config.json and config.yaml versions are aligned (semver)
- test(mqtt): ensure on_connect accepts extra args (paho signature variants)
- test(mqtt): ensure on_disconnect accepts extra args to prevent paho thread crash
- fix(mqtt): make connect/disconnect callbacks tolerant to paho variations and prevent thread crashes

### Commits included in this release

- test(manifest): ensure repository.json, config.json and config.yaml versions are aligned (semver)
- test(mqtt): ensure on_connect accepts extra args (paho signature variants)
- test(mqtt): ensure on_disconnect accepts extra args to prevent paho thread crash
- fix(mqtt): make connect/disconnect callbacks tolerant to paho variations and prevent thread crashes

## [1.1.0] - 2025-11-28

- chore(release): bump manifests to 1.1.0

### Commits included in this release

- chore(release): bump manifests to 1.1.0

## [1.0.99] - 2025-11-28

- chore(release): bump version to 1.0.99

### Commits included in this release

- chore(release): bump version to 1.0.99

## [1.0.98] - 2025-11-28

- chore(release): bump version to 1.0.98; write addon_version on startup
- feat(version): prefer addon_version in /data/options.json to match Add-on UI
- feat(version): honor ADDON_VERSION env var override for reported addon version

### Commits included in this release

- chore(release): bump version to 1.0.98; write addon_version on startup
- feat(version): prefer addon_version in /data/options.json to match Add-on UI
- feat(version): honor ADDON_VERSION env var override for reported addon version

## [1.0.97] - 2025-11-28

- chore(release): bump version to 1.0.97
- fix(mqtt): make callbacks MQTTv5-compatible and resilient to broker failures

### Commits included in this release

- chore(release): bump version to 1.0.97
- fix(mqtt): make callbacks MQTTv5-compatible and resilient to broker failures

## [1.0.96] - 2025-11-28

- chore(release): bump version to 1.0.96
- fix(ci): ensure git available for VCS installs; pin shared package to v1.0.0
- chore(deps): pin central-core-mqtt-shared to v1.0.0

### Commits included in this release

- chore(release): bump version to 1.0.96
- fix(ci): ensure git available for VCS installs; pin shared package to v1.0.0
- chore(deps): pin central-core-mqtt-shared to v1.0.0

## [1.0.95] - 2025-11-27

- chore(release): bump version to 1.0.95
- fix(mqtt): import topics submodule when package doesn't re-export it

### Commits included in this release

- chore(release): bump version to 1.0.95
- fix(mqtt): import topics submodule when package doesn't re-export it

## [1.0.94] - 2025-11-27

- chore(release): bump version to 1.0.94
- fix(docker): install Python deps into a virtualenv to avoid PEP 668

### Commits included in this release

- chore(release): bump version to 1.0.94
- fix(docker): install Python deps into a virtualenv to avoid PEP 668

## [1.0.93] - 2025-11-27

- chore(release): bump version to 1.0.93
- chore: commit all outstanding changes

### Commits included in this release

- chore(release): bump version to 1.0.93
- chore: commit all outstanding changes

## [1.0.92] - 2025-11-27

- chore(release): bump version to 1.0.92
- test(fix): require requests in runtime; tests monkeypatch module requests
- fix(tests): allow fetch_sensors monkeypatch when requests missing

### Commits included in this release

- chore(release): bump version to 1.0.92
- test(fix): require requests in runtime; tests monkeypatch module requests
- fix(tests): allow fetch_sensors monkeypatch when requests missing

## [1.0.91] - 2025-11-27

- chore(release): bump version to 1.0.91
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore(release): update version metadata to 1.0.90
- fix(lint): address flake8/pyright issues in mqtt_client and tests shim

### Commits included in this release

- chore(release): bump version to 1.0.91
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore(release): update version metadata to 1.0.90
- fix(lint): address flake8/pyright issues in mqtt_client and tests shim

## [1.0.90] - 2025-11-27

- chore(release): bump version to 1.0.90
- chore(deps): install central-core-mqtt-shared from GitHub in requirements
- ci: fallback to installing central-core-mqtt-shared from GitHub when PyPI missing
- chore(release): bump version strings to 1.0.89

### Commits included in this release

- chore(release): bump version to 1.0.90
- chore(deps): install central-core-mqtt-shared from GitHub in requirements
- ci: fallback to installing central-core-mqtt-shared from GitHub when PyPI missing
- chore(release): bump version strings to 1.0.89

## [1.0.89] - 2025-11-27

- feat(mqtt): use central_core_mqtt_shared.topics for canonical topics and ack
- chore(release): bump version to 1.0.88

### Commits included in this release

- feat(mqtt): use central_core_mqtt_shared.topics for canonical topics and ack
- chore(release): bump version to 1.0.88

## [1.0.88] - 2025-11-27

- chore(release): bump version to 1.0.88
- chore(mqtt): require shared mqtt package for authoritative topic templates; remove local mqtt_topics
- chore(mqtt): remove legacy publishes and use shared topic templates; update docs
- fix(mqtt): use shared topic templates when available (mqtt_topics)
- fix(mqtt): align command topic namespace with Vault/mqtt-shared ()

### Commits included in this release

- chore(release): bump version to 1.0.88
- chore(mqtt): require shared mqtt package for authoritative topic templates; remove local mqtt_topics
- chore(mqtt): remove legacy publishes and use shared topic templates; update docs
- fix(mqtt): use shared topic templates when available (mqtt_topics)
- fix(mqtt): align command topic namespace with Vault/mqtt-shared ()

## [1.0.87] - 2025-11-27

- chore(release): publish v1.0.87 on main (bump metadata)
- Merge pull request #4 from elyobelyob/feature/vault-selected-sensors-reminder
- Merge pull request #3 from elyobelyob/copilot/create-mqtt-endpoints-documentation
- Merge pull request #2 from elyobelyob/copilot/add-mqtt-endpoints-md-file
- Initial plan
- Initial plan

### Commits included in this release

- chore(release): publish v1.0.87 on main (bump metadata)
- Merge pull request #4 from elyobelyob/feature/vault-selected-sensors-reminder
- Merge pull request #3 from elyobelyob/copilot/create-mqtt-endpoints-documentation
- Merge pull request #2 from elyobelyob/copilot/add-mqtt-endpoints-md-file
- Initial plan
- Initial plan

## [1.0.85] - 2025-11-27

- chore(release): bump version to 1.0.85
- chore(tests): update  formatting/edits

### Commits included in this release

- chore(release): bump version to 1.0.85
- chore(tests): update  formatting/edits

## [1.0.84] - 2025-11-27

- chore(release): bump version to 1.0.84

### Commits included in this release

- chore(release): bump version to 1.0.84

## [1.0.75] - 2025-11-27

- chore(release): bump version to 1.0.75
- chore: prepare release — tests hardening and pyright fixes
- Make Vault authoritative for sensor selection; publish selected_sensors reminder and harden imports/tests for static analysis
- Fix handlers topic matching and ack publishing; include last_changed/last_updated in fetch_sensors
- Fix handler telemetry path
- Restructure HA helpers and telemetry payloads
- Bump version metadata to 1.0.84
- Include HA timestamps in sensor telemetry
- Add release Makefile to enforce versioned tagging

### Commits included in this release

- chore(release): bump version to 1.0.75
- chore: prepare release — tests hardening and pyright fixes
- Make Vault authoritative for sensor selection; publish selected_sensors reminder and harden imports/tests for static analysis
- Fix handlers topic matching and ack publishing; include last_changed/last_updated in fetch_sensors
- Fix handler telemetry path
- Restructure HA helpers and telemetry payloads
- Bump version metadata to 1.0.84
- Include HA timestamps in sensor telemetry
- Add release Makefile to enforce versioned tagging

## [1.0.83] - 2025-11-26

- Bump version metadata to 1.0.83
- Allow selected sensor publish without requests module

### Commits included in this release

- Bump version metadata to 1.0.83
- Allow selected sensor publish without requests module

## [1.0.82] - 2025-11-26

- Add bandit config and harden MQTT logging

### Commits included in this release

- Add bandit config and harden MQTT logging

## [1.0.81] - 2025-11-26

- Bump version to 1.0.81

### Commits included in this release

- Bump version to 1.0.81

## [1.0.80] - 2025-11-26

- Log ack publishes with timestamp

### Commits included in this release

- Log ack publishes with timestamp

## [1.0.79] - 2025-11-26

- Harden shared MQTT fallback

### Commits included in this release

- Harden shared MQTT fallback

## [1.0.78] - 2025-11-26

- Remove legacy MQTT topics

### Commits included in this release

- Remove legacy MQTT topics

## [1.0.77] - 2025-11-26

- Bump version to 1.0.77
- Format and lint fixes

### Commits included in this release

- Bump version to 1.0.77
- Format and lint fixes

## [1.0.76] - 2025-11-26

- Adopt shared MQTT topic definitions
- Use multi-level command subscription wildcard
- Improve coverage: add telemetry tests and mark defensive telemetry branches; add handler coverage tests
- Annotate defensive branches in handlers.py with pragma:no cover for testability

### Commits included in this release

- Adopt shared MQTT topic definitions
- Use multi-level command subscription wildcard
- Improve coverage: add telemetry tests and mark defensive telemetry branches; add handler coverage tests
- Annotate defensive branches in handlers.py with pragma:no cover for testability

## [1.0.74] - 2025-11-21

- Bump versions to 1.0.74 and update CHANGELOG

### Commits included in this release

- Bump versions to 1.0.74 and update CHANGELOG

## [1.0.72] - 2025-11-21

- feat: publish selected sensor changes

### Commits included in this release

- feat: publish selected sensor changes

## [1.0.71] - 2025-11-20

- chore: bump to 1.0.71 and format handlers/tests

### Commits included in this release

- chore: bump to 1.0.71 and format handlers/tests

## [1.0.70] - 2025-11-20

- Remind Vault via MQTT; persist Vault-selected sensors; add tests and dev requirements
- Release v1.0.70: Version management system
- Version management: Automated versioning system
- Code quality: Add black & flake8 checks + formatting
- Security: Sanitize certificate data in logs
- Fix CI test path construction
- Release v1.0.69: Update version and fix test paths

### Commits included in this release

- Remind Vault via MQTT; persist Vault-selected sensors; add tests and dev requirements
- Release v1.0.70: Version management system
- Version management: Automated versioning system
- Code quality: Add black & flake8 checks + formatting
- Security: Sanitize certificate data in logs
- Fix CI test path construction
- Release v1.0.69: Update version and fix test paths

## [1.0.69] - 2025-11-20

- chore: Bump version to 1.0.69 for certificate logging security fix
- security: Redact all certificate fields in options logging
- fix: Update lambda parameter name to match build_telemetry signature

### Commits included in this release

- chore: Bump version to 1.0.69 for certificate logging security fix
- security: Redact all certificate fields in options logging
- fix: Update lambda parameter name to match build_telemetry signature

## [1.0.68] - 2025-11-19

- chore: Bump version to 1.0.68 for addon_version fix
- fix: Ensure addon_version is available in HA add-on environment
- test: Add tests for get_addon_version function

### Commits included in this release

- chore: Bump version to 1.0.68 for addon_version fix
- fix: Ensure addon_version is available in HA add-on environment
- test: Add tests for get_addon_version function

## [1.0.67] - 2025-11-19

- fix: Correct addon_version path resolution in telemetry payload

### Commits included in this release

- fix: Correct addon_version path resolution in telemetry payload

## [1.0.66] - 2025-11-19

- chore: Apply Black formatting and Flake8 linting fixes

### Commits included in this release

- chore: Apply Black formatting and Flake8 linting fixes

## [1.0.65] - 2025-11-19

- feat: Add addon_version and telemetry_interval to MQTT telemetry messages
- Release v1.0.64: Sanitize sensitive data in logs
- Release v1.0.63: Simplify cert config to bundle only
- Release v1.0.62: Add certificate bundle support
- Release v1.0.61: Hide sensitive config fields in UI
- Release v1.0.60: Support certificate content in config
- Release v1.0.59: Add test for container file presence
- Add test to verify required Python files exist for container deployment
- Fix Dockerfile to copy all Python files. Bump version to 1.0.58
- Fix Dockerfile to copy all Python files to root for proper imports
- Add debug logging for MQTT connection issues. Bump version to 1.0.57
- Add debug logging to diagnose MQTT connection issues
- Apply final Black formatting and bump version to 1.0.56
- Apply Black formatting to mqtt_runtime.py
- Add configurable telemetry_interval option, default 30s. Bump version to 1.0.55
- Increase telemetry publish frequency to 10s. Bump version to 1.0.54
- Add initial telemetry publish on MQTT connect. Bump version to 1.0.53
- Fix MQTT connection by updating to Callback API v2. Bump version to 1.0.52
- Update CHANGELOG.md and config.yaml for v1.0.51
- Add timestamps to logs, format code with Black, fix linting issues. Bump version to 1.0.51
- Release v1.0.50: comprehensive testing, friendly names in telemetry, Docker portability
- Bump config.yaml version to v1.0.49

### Commits included in this release

- feat: Add addon_version and telemetry_interval to MQTT telemetry messages
- Release v1.0.64: Sanitize sensitive data in logs
- Release v1.0.63: Simplify cert config to bundle only
- Release v1.0.62: Add certificate bundle support
- Release v1.0.61: Hide sensitive config fields in UI
- Release v1.0.60: Support certificate content in config
- Release v1.0.59: Add test for container file presence
- Add test to verify required Python files exist for container deployment
- Fix Dockerfile to copy all Python files. Bump version to 1.0.58
- Fix Dockerfile to copy all Python files to root for proper imports
- Add debug logging for MQTT connection issues. Bump version to 1.0.57
- Add debug logging to diagnose MQTT connection issues
- Apply final Black formatting and bump version to 1.0.56
- Apply Black formatting to mqtt_runtime.py
- Add configurable telemetry_interval option, default 30s. Bump version to 1.0.55
- Increase telemetry publish frequency to 10s. Bump version to 1.0.54
- Add initial telemetry publish on MQTT connect. Bump version to 1.0.53
- Fix MQTT connection by updating to Callback API v2. Bump version to 1.0.52
- Update CHANGELOG.md and config.yaml for v1.0.51
- Add timestamps to logs, format code with Black, fix linting issues. Bump version to 1.0.51
- Release v1.0.50: comprehensive testing, friendly names in telemetry, Docker portability
- Bump config.yaml version to v1.0.49

## [1.0.49] - 2025-11-19

- Bump version to v1.0.49

### Commits included in this release

- Bump version to v1.0.49

## [1.0.48] - 2025-11-18

- Bump version to v1.0.48
- chore(release): bump versions to 1.0.47 and add changelog entry
- docs: expand README and changelog with sensors command and telemetry details
- feat(commands): include HA readback attributes in telemetry and assert in tests
- fix(commands): use HA readback values after sensors/set and correct telemetry publish flow
- feat(commands): publish telemetry after sensors/set for successfully set sensors; test updated
- feat(commands): implement sensors/set handling (HA REST set state) and tests
- chore(docs): reorder CHANGELOG newest-first
- chore(release): bump add-on version to 1.0.46 and update changelog
- fix(test): add mqtt shim when paho-mqtt not installed to allow unit tests
- chore(release): add changelog entries and update repository.json version
- chore(release): bump add-on version to 1.0.45
- chore: ignore venv and test artifacts; add tests and remove legacy topic usage
- Feat: handle Vault 'sensors/poll' commands — ack, publish sensors to preferred and legacy topics, completion
- Chore: bump add-on config.yaml version to v1.0.44
- Chore: bump add-on version to v1.0.44

### Commits included in this release

- Bump version to v1.0.48
- chore(release): bump versions to 1.0.47 and add changelog entry
- docs: expand README and changelog with sensors command and telemetry details
- feat(commands): include HA readback attributes in telemetry and assert in tests
- fix(commands): use HA readback values after sensors/set and correct telemetry publish flow
- feat(commands): publish telemetry after sensors/set for successfully set sensors; test updated
- feat(commands): implement sensors/set handling (HA REST set state) and tests
- chore(docs): reorder CHANGELOG newest-first
- chore(release): bump add-on version to 1.0.46 and update changelog
- fix(test): add mqtt shim when paho-mqtt not installed to allow unit tests
- chore(release): add changelog entries and update repository.json version
- chore(release): bump add-on version to 1.0.45
- chore: ignore venv and test artifacts; add tests and remove legacy topic usage
- Feat: handle Vault 'sensors/poll' commands — ack, publish sensors to preferred and legacy topics, completion
- Chore: bump add-on config.yaml version to v1.0.44
- Chore: bump add-on version to v1.0.44

## [1.0.44] - 2025-11-18

- Feat: publish HA sensors on startup and hourly to MQTT
- Changelog: add entries for v1.0.41..v1.0.43

### Commits included in this release

- Feat: publish HA sensors on startup and hourly to MQTT
- Changelog: add entries for v1.0.41..v1.0.43

## [1.0.43] - 2025-11-18

- chore: commit workspace changes (requested)
- Fix: use timezone-aware UTC datetimes to avoid datetime.utcnow() deprecation
- Revert "Docs: add Tests section to README with pytest instructions"
- Docs: add Tests section to README with pytest instructions
- Tests: load mqtt_client by path to avoid hyphenated package import
- Add unit tests for vault payload, make mqtt import resilient, and add pytest workflow
- Document vault_topic option, schema versions, and add integration test instructions
- Add simple local integration script for mosquitto + client
- Add schema_version and publish Vault-transformed telemetry to
- Add optional vault_topic option to config schema
- Add optional vault_topic and dual-publish for telemetry
- Dockerfile: install py3-paho-mqtt via apk to avoid pip/PEP668 build errors
- Dockerfile: default BUILD_FROM fallback; bump to v1.0.41
- Bump add-on version to 1.0.40
- Convert to Python MQTT client; install python/paho-mqtt in Dockerfile
- Make mosquitto_sub persistent with logging; bump to v1.0.39
- Bump add-on version to 1.0.38
- Fix mqtt arg quoting for subscriber and sensor publish (build sub_extra, use eval)
- Fix network config in YAML and update to v1.0.37
- Update version to 1.0.36
- Add reconnection loop for MQTT subscriber to handle disconnections
- Fix workflow to set BUILD_FROM for multi-platform builds
- Update version to 1.0.35
- Update version to 1.0.34
- Use different client IDs for pub and sub to keep sub connection open
- Add maintainer to repository.json
- Update version to 1.0.33
- Update version to 1.0.32
- Fix process substitution for ash compatibility in sensor processing
- Set default client_id to 'home-assistant' to fix templated hostname issue
- Add host network to allow access to external MQTT broker
- Change shebang to /bin/sh and fix bash-specific syntax for compatibility
- Apply shfmt formatting to run.sh
- Reformat telemetry payload to reduce line length
- Fix shellcheck issues: remove redundant assignment, use parameter expansion for sed
- Fix shell syntax: use string concatenation for MQTT options, change shebang to /bin/bash
- Fix mosquitto_pub/sub calls using arrays to avoid eval quoting issues
- Read options from /data/options.json instead of env vars for reliability
- Make mqtt_host required in schema to ensure env var is set
- Add debug output for MQTT configuration
- Fix shell compatibility: replace associative array with eval for sh/bash
- Add icon.png and logo.png for HA add-on display, remove SVG versions
- Add linux/386 platform to workflow for i386 support
- Fix IP address gathering for BusyBox compatibility
- Add MQTT subscription to commands topic
- Add mosquitto-clients to Dockerfile for MQTT publishing
- Fix config.yaml: remove ports, fix client_id default, make options optional

### Commits included in this release

- chore: commit workspace changes (requested)
- Fix: use timezone-aware UTC datetimes to avoid datetime.utcnow() deprecation
- Revert "Docs: add Tests section to README with pytest instructions"
- Docs: add Tests section to README with pytest instructions
- Tests: load mqtt_client by path to avoid hyphenated package import
- Add unit tests for vault payload, make mqtt import resilient, and add pytest workflow
- Document vault_topic option, schema versions, and add integration test instructions
- Add simple local integration script for mosquitto + client
- Add schema_version and publish Vault-transformed telemetry to
- Add optional vault_topic option to config schema
- Add optional vault_topic and dual-publish for telemetry
- Dockerfile: install py3-paho-mqtt via apk to avoid pip/PEP668 build errors
- Dockerfile: default BUILD_FROM fallback; bump to v1.0.41
- Bump add-on version to 1.0.40
- Convert to Python MQTT client; install python/paho-mqtt in Dockerfile
- Make mosquitto_sub persistent with logging; bump to v1.0.39
- Bump add-on version to 1.0.38
- Fix mqtt arg quoting for subscriber and sensor publish (build sub_extra, use eval)
- Fix network config in YAML and update to v1.0.37
- Update version to 1.0.36
- Add reconnection loop for MQTT subscriber to handle disconnections
- Fix workflow to set BUILD_FROM for multi-platform builds
- Update version to 1.0.35
- Update version to 1.0.34
- Use different client IDs for pub and sub to keep sub connection open
- Add maintainer to repository.json
- Update version to 1.0.33
- Update version to 1.0.32
- Fix process substitution for ash compatibility in sensor processing
- Set default client_id to 'home-assistant' to fix templated hostname issue
- Add host network to allow access to external MQTT broker
- Change shebang to /bin/sh and fix bash-specific syntax for compatibility
- Apply shfmt formatting to run.sh
- Reformat telemetry payload to reduce line length
- Fix shellcheck issues: remove redundant assignment, use parameter expansion for sed
- Fix shell syntax: use string concatenation for MQTT options, change shebang to /bin/bash
- Fix mosquitto_pub/sub calls using arrays to avoid eval quoting issues
- Read options from /data/options.json instead of env vars for reliability
- Make mqtt_host required in schema to ensure env var is set
- Add debug output for MQTT configuration
- Fix shell compatibility: replace associative array with eval for sh/bash
- Add icon.png and logo.png for HA add-on display, remove SVG versions
- Add linux/386 platform to workflow for i386 support
- Fix IP address gathering for BusyBox compatibility
- Add MQTT subscription to commands topic
- Add mosquitto-clients to Dockerfile for MQTT publishing
- Fix config.yaml: remove ports, fix client_id default, make options optional

## [1.0.13] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.12] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.11] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.10] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.9] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.8] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.7-dockerfile] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.6] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.5] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.4] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.3] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.2] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.1] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.0] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [2.0.0] - 2025-11-28

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.1.24] - 2025-11-28

- Redact HA token in options log

### Commits included in this release

- Redact HA token in options log

## [1.1.23] - 2025-11-28

- Flush HA log output

### Commits included in this release

- Flush HA log output

## [1.1.22] - 2025-11-28

- Bump version for 1.1.22

### Commits included in this release

- Bump version for 1.1.22

## [1.1.21] - 2025-11-28

- Bump version for 1.1.21
- More HA websocket diagnostics

### Commits included in this release

- Bump version for 1.1.21
- More HA websocket diagnostics

## [1.1.19] - 2025-11-28

- Log HA websocket startup

### Commits included in this release

- Log HA websocket startup

## [1.1.18] - 2025-11-28

- Bump version for 1.1.18
- Mirror CI quality steps locally
- Exclude venv from pyright and fix python invocations
- Ensure local quality script runs pyright

### Commits included in this release

- Bump version for 1.1.18
- Mirror CI quality steps locally
- Exclude venv from pyright and fix python invocations
- Ensure local quality script runs pyright

## [1.1.17] - 2025-11-28

- Capture HA version even with JSON cert bundles

### Commits included in this release

- Capture HA version even with JSON cert bundles

## [1.1.16] - 2025-11-28

- Drop legacy command topics

### Commits included in this release

- Drop legacy command topics

## [1.1.15] - 2025-11-28

- Add config update command

### Commits included in this release

- Add config update command

## [1.1.14] - 2025-11-28

- Include HA version in telemetry
- chore(release): bump version to 1.1.13
- chore(diagnostics): log presence of HA API url/token (no secrets)
- chore(release): bump version to 1.1.12
- chore(ci): remove Black config; document Ruff formatting and linting
- chore(ci): configure ruff to match Black/Flake8 behavior; fix test import
- chore(release): bump version to 1.1.11
- fix(ha): make HAWebSocketListener.stop idempotent; add idempotent stop test
- chore(release): bump version to 1.1.10
- chore(release): bump version to 1.1.9
- ci: fix ruff.toml format (top-level keys) to satisfy ruff parser in CI
- ci: enable pip cache and cache pip downloads for ruff/wheels
- chore(ci): add pre-commit ruff hook and ruff.toml config
- chore(ci): replace flake8/black with ruff; update CI and quality scripts
- chore(telemetry): add diagnostic logging for HA info fetch; chore(release): bump 1.1.8
- chore(lint): fix flake8 issues; chore(release): bump version to 1.1.7
- ci: retrigger workflows after lint fixes
- chore(release): bump version to 1.1.6
- chore(release): bump version to 1.1.5
- chore(release): bump manifests to 1.1.4; add HA telemetry tests
- chore(release): bump manifests to 1.1.3; CI: add PyYAML for YAML parsing in tests
- test(manifest): avoid PyYAML dependency; parse config.yaml for version
- chore(release): bump manifests to 1.1.2
- test(manifest): ensure repository.json, config.json and config.yaml versions are aligned (semver)
- test(mqtt): ensure on_connect accepts extra args (paho signature variants)
- test(mqtt): ensure on_disconnect accepts extra args to prevent paho thread crash
- fix(mqtt): make connect/disconnect callbacks tolerant to paho variations and prevent thread crashes
- chore(release): bump manifests to 1.1.0
- chore(release): bump version to 1.0.99
- chore(release): bump version to 1.0.98; write addon_version on startup
- feat(version): prefer addon_version in /data/options.json to match Add-on UI
- feat(version): honor ADDON_VERSION env var override for reported addon version
- chore(release): bump version to 1.0.97
- fix(mqtt): make callbacks MQTTv5-compatible and resilient to broker failures
- chore(release): bump version to 1.0.96
- fix(ci): ensure git available for VCS installs; pin shared package to v1.0.0
- chore(deps): pin central-core-mqtt-shared to v1.0.0
- chore(release): bump version to 1.0.95
- fix(mqtt): import topics submodule when package doesn't re-export it
- chore(release): bump version to 1.0.94
- fix(docker): install Python deps into a virtualenv to avoid PEP 668
- chore(release): bump version to 1.0.93
- chore: commit all outstanding changes
- chore(release): bump version to 1.0.92
- test(fix): require requests in runtime; tests monkeypatch module requests
- fix(tests): allow fetch_sensors monkeypatch when requests missing
- chore(release): bump version to 1.0.91
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore(release): update version metadata to 1.0.90
- fix(lint): address flake8/pyright issues in mqtt_client and tests shim
- chore(release): bump version to 1.0.90
- chore(deps): install central-core-mqtt-shared from GitHub in requirements
- ci: fallback to installing central-core-mqtt-shared from GitHub when PyPI missing
- chore(release): bump version strings to 1.0.89
- feat(mqtt): use central_core_mqtt_shared.topics for canonical topics and ack
- chore(release): bump version to 1.0.88
- chore(release): bump version to 1.0.88
- chore(mqtt): require shared mqtt package for authoritative topic templates; remove local mqtt_topics
- chore(mqtt): remove legacy publishes and use shared topic templates; update docs
- fix(mqtt): use shared topic templates when available (mqtt_topics)
- fix(mqtt): align command topic namespace with Vault/mqtt-shared ()
- chore(release): publish v1.0.87 on main (bump metadata)
- Merge pull request #4 from elyobelyob/feature/vault-selected-sensors-reminder
- Merge pull request #3 from elyobelyob/copilot/create-mqtt-endpoints-documentation
- Merge pull request #2 from elyobelyob/copilot/add-mqtt-endpoints-md-file
- chore(release): bump version to 1.0.84
- chore(release): bump version to 1.0.75
- chore: prepare release — tests hardening and pyright fixes
- Make Vault authoritative for sensor selection; publish selected_sensors reminder and harden imports/tests for static analysis
- Fix handlers topic matching and ack publishing; include last_changed/last_updated in fetch_sensors
- Fix handler telemetry path
- Restructure HA helpers and telemetry payloads
- Bump version metadata to 1.0.84
- Include HA timestamps in sensor telemetry
- Add release Makefile to enforce versioned tagging
- Bump version metadata to 1.0.83
- Allow selected sensor publish without requests module
- Add bandit config and harden MQTT logging
- Bump version to 1.0.81
- Log ack publishes with timestamp
- Harden shared MQTT fallback
- Remove legacy MQTT topics
- Bump version to 1.0.77
- Format and lint fixes
- Adopt shared MQTT topic definitions
- Initial plan
- Initial plan
- Use multi-level command subscription wildcard
- Improve coverage: add telemetry tests and mark defensive telemetry branches; add handler coverage tests
- Annotate defensive branches in handlers.py with pragma:no cover for testability
- Bump versions to 1.0.74 and update CHANGELOG
- feat: publish selected sensor changes
- chore: bump to 1.0.71 and format handlers/tests
- Remind Vault via MQTT; persist Vault-selected sensors; add tests and dev requirements
- Release v1.0.70: Version management system
- Version management: Automated versioning system
- Code quality: Add black & flake8 checks + formatting
- Security: Sanitize certificate data in logs
- Fix CI test path construction
- Release v1.0.69: Update version and fix test paths
- chore: Bump version to 1.0.69 for certificate logging security fix
- security: Redact all certificate fields in options logging
- fix: Update lambda parameter name to match build_telemetry signature
- chore: Bump version to 1.0.68 for addon_version fix
- fix: Ensure addon_version is available in HA add-on environment
- test: Add tests for get_addon_version function
- fix: Correct addon_version path resolution in telemetry payload
- chore: Apply Black formatting and Flake8 linting fixes
- feat: Add addon_version and telemetry_interval to MQTT telemetry messages

### Commits included in this release

- Include HA version in telemetry
- chore(release): bump version to 1.1.13
- chore(diagnostics): log presence of HA API url/token (no secrets)
- chore(release): bump version to 1.1.12
- chore(ci): remove Black config; document Ruff formatting and linting
- chore(ci): configure ruff to match Black/Flake8 behavior; fix test import
- chore(release): bump version to 1.1.11
- fix(ha): make HAWebSocketListener.stop idempotent; add idempotent stop test
- chore(release): bump version to 1.1.10
- chore(release): bump version to 1.1.9
- ci: fix ruff.toml format (top-level keys) to satisfy ruff parser in CI
- ci: enable pip cache and cache pip downloads for ruff/wheels
- chore(ci): add pre-commit ruff hook and ruff.toml config
- chore(ci): replace flake8/black with ruff; update CI and quality scripts
- chore(telemetry): add diagnostic logging for HA info fetch; chore(release): bump 1.1.8
- chore(lint): fix flake8 issues; chore(release): bump version to 1.1.7
- ci: retrigger workflows after lint fixes
- chore(release): bump version to 1.1.6
- chore(release): bump version to 1.1.5
- chore(release): bump manifests to 1.1.4; add HA telemetry tests
- chore(release): bump manifests to 1.1.3; CI: add PyYAML for YAML parsing in tests
- test(manifest): avoid PyYAML dependency; parse config.yaml for version
- chore(release): bump manifests to 1.1.2
- test(manifest): ensure repository.json, config.json and config.yaml versions are aligned (semver)
- test(mqtt): ensure on_connect accepts extra args (paho signature variants)
- test(mqtt): ensure on_disconnect accepts extra args to prevent paho thread crash
- fix(mqtt): make connect/disconnect callbacks tolerant to paho variations and prevent thread crashes
- chore(release): bump manifests to 1.1.0
- chore(release): bump version to 1.0.99
- chore(release): bump version to 1.0.98; write addon_version on startup
- feat(version): prefer addon_version in /data/options.json to match Add-on UI
- feat(version): honor ADDON_VERSION env var override for reported addon version
- chore(release): bump version to 1.0.97
- fix(mqtt): make callbacks MQTTv5-compatible and resilient to broker failures
- chore(release): bump version to 1.0.96
- fix(ci): ensure git available for VCS installs; pin shared package to v1.0.0
- chore(deps): pin central-core-mqtt-shared to v1.0.0
- chore(release): bump version to 1.0.95
- fix(mqtt): import topics submodule when package doesn't re-export it
- chore(release): bump version to 1.0.94
- fix(docker): install Python deps into a virtualenv to avoid PEP 668
- chore(release): bump version to 1.0.93
- chore: commit all outstanding changes
- chore(release): bump version to 1.0.92
- test(fix): require requests in runtime; tests monkeypatch module requests
- fix(tests): allow fetch_sensors monkeypatch when requests missing
- chore(release): bump version to 1.0.91
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore: apply final formatting fixes to mqtt_client and tests shim
- chore(release): update version metadata to 1.0.90
- fix(lint): address flake8/pyright issues in mqtt_client and tests shim
- chore(release): bump version to 1.0.90
- chore(deps): install central-core-mqtt-shared from GitHub in requirements
- ci: fallback to installing central-core-mqtt-shared from GitHub when PyPI missing
- chore(release): bump version strings to 1.0.89
- feat(mqtt): use central_core_mqtt_shared.topics for canonical topics and ack
- chore(release): bump version to 1.0.88
- chore(release): bump version to 1.0.88
- chore(mqtt): require shared mqtt package for authoritative topic templates; remove local mqtt_topics
- chore(mqtt): remove legacy publishes and use shared topic templates; update docs
- fix(mqtt): use shared topic templates when available (mqtt_topics)
- fix(mqtt): align command topic namespace with Vault/mqtt-shared ()
- chore(release): publish v1.0.87 on main (bump metadata)
- Merge pull request #4 from elyobelyob/feature/vault-selected-sensors-reminder
- Merge pull request #3 from elyobelyob/copilot/create-mqtt-endpoints-documentation
- Merge pull request #2 from elyobelyob/copilot/add-mqtt-endpoints-md-file
- chore(release): bump version to 1.0.84
- chore(release): bump version to 1.0.75
- chore: prepare release — tests hardening and pyright fixes
- Make Vault authoritative for sensor selection; publish selected_sensors reminder and harden imports/tests for static analysis
- Fix handlers topic matching and ack publishing; include last_changed/last_updated in fetch_sensors
- Fix handler telemetry path
- Restructure HA helpers and telemetry payloads
- Bump version metadata to 1.0.84
- Include HA timestamps in sensor telemetry
- Add release Makefile to enforce versioned tagging
- Bump version metadata to 1.0.83
- Allow selected sensor publish without requests module
- Add bandit config and harden MQTT logging
- Bump version to 1.0.81
- Log ack publishes with timestamp
- Harden shared MQTT fallback
- Remove legacy MQTT topics
- Bump version to 1.0.77
- Format and lint fixes
- Adopt shared MQTT topic definitions
- Initial plan
- Initial plan
- Use multi-level command subscription wildcard
- Improve coverage: add telemetry tests and mark defensive telemetry branches; add handler coverage tests
- Annotate defensive branches in handlers.py with pragma:no cover for testability
- Bump versions to 1.0.74 and update CHANGELOG
- feat: publish selected sensor changes
- chore: bump to 1.0.71 and format handlers/tests
- Remind Vault via MQTT; persist Vault-selected sensors; add tests and dev requirements
- Release v1.0.70: Version management system
- Version management: Automated versioning system
- Code quality: Add black & flake8 checks + formatting
- Security: Sanitize certificate data in logs
- Fix CI test path construction
- Release v1.0.69: Update version and fix test paths
- chore: Bump version to 1.0.69 for certificate logging security fix
- security: Redact all certificate fields in options logging
- fix: Update lambda parameter name to match build_telemetry signature
- chore: Bump version to 1.0.68 for addon_version fix
- fix: Ensure addon_version is available in HA add-on environment
- test: Add tests for get_addon_version function
- fix: Correct addon_version path resolution in telemetry payload
- chore: Apply Black formatting and Flake8 linting fixes
- feat: Add addon_version and telemetry_interval to MQTT telemetry messages

## [1.0.64] - 2025-11-19

- Release v1.0.64: Sanitize sensitive data in logs

### Commits included in this release

- Release v1.0.64: Sanitize sensitive data in logs

## [1.0.63] - 2025-11-19

- Release v1.0.63: Simplify cert config to bundle only

### Commits included in this release

- Release v1.0.63: Simplify cert config to bundle only

## [1.0.62] - 2025-11-19

- Release v1.0.62: Add certificate bundle support

### Commits included in this release

- Release v1.0.62: Add certificate bundle support

## [1.0.61] - 2025-11-19

- Release v1.0.61: Hide sensitive config fields in UI

### Commits included in this release

- Release v1.0.61: Hide sensitive config fields in UI

## [1.0.60] - 2025-11-19

- Release v1.0.60: Support certificate content in config

### Commits included in this release

- Release v1.0.60: Support certificate content in config

## [1.0.59] - 2025-11-19

- Release v1.0.59: Add test for container file presence
- Add test to verify required Python files exist for container deployment

### Commits included in this release

- Release v1.0.59: Add test for container file presence
- Add test to verify required Python files exist for container deployment

## [1.0.58] - 2025-11-19

- Fix Dockerfile to copy all Python files. Bump version to 1.0.58
- Fix Dockerfile to copy all Python files to root for proper imports

### Commits included in this release

- Fix Dockerfile to copy all Python files. Bump version to 1.0.58
- Fix Dockerfile to copy all Python files to root for proper imports

## [1.0.57] - 2025-11-19

- Add debug logging for MQTT connection issues. Bump version to 1.0.57
- Add debug logging to diagnose MQTT connection issues

### Commits included in this release

- Add debug logging for MQTT connection issues. Bump version to 1.0.57
- Add debug logging to diagnose MQTT connection issues

## [1.0.56] - 2025-11-19

- Apply final Black formatting and bump version to 1.0.56
- Apply Black formatting to mqtt_runtime.py

### Commits included in this release

- Apply final Black formatting and bump version to 1.0.56
- Apply Black formatting to mqtt_runtime.py

## [1.0.55] - 2025-11-19

- Add configurable telemetry_interval option, default 30s. Bump version to 1.0.55

### Commits included in this release

- Add configurable telemetry_interval option, default 30s. Bump version to 1.0.55

## [1.0.54] - 2025-11-19

- Increase telemetry publish frequency to 10s. Bump version to 1.0.54

### Commits included in this release

- Increase telemetry publish frequency to 10s. Bump version to 1.0.54

## [1.0.53] - 2025-11-19

- Add initial telemetry publish on MQTT connect. Bump version to 1.0.53

### Commits included in this release

- Add initial telemetry publish on MQTT connect. Bump version to 1.0.53

## [1.0.52] - 2025-11-19

- Fix MQTT connection by updating to Callback API v2. Bump version to 1.0.52
- Update CHANGELOG.md and config.yaml for v1.0.51

### Commits included in this release

- Fix MQTT connection by updating to Callback API v2. Bump version to 1.0.52
- Update CHANGELOG.md and config.yaml for v1.0.51

## [1.0.51] - 2025-11-19

- Add timestamps to logs, format code with Black, fix linting issues. Bump version to 1.0.51

### Commits included in this release

- Add timestamps to logs, format code with Black, fix linting issues. Bump version to 1.0.51

## [1.0.50] - 2025-11-19

- Release v1.0.50: comprehensive testing, friendly names in telemetry, Docker portability
- Bump config.yaml version to v1.0.49
- Bump version to v1.0.49
- Bump version to v1.0.48

### Commits included in this release

- Release v1.0.50: comprehensive testing, friendly names in telemetry, Docker portability
- Bump config.yaml version to v1.0.49
- Bump version to v1.0.49
- Bump version to v1.0.48

## [1.0.47] - 2025-11-18

- chore(release): bump versions to 1.0.47 and add changelog entry
- docs: expand README and changelog with sensors command and telemetry details
- feat(commands): include HA readback attributes in telemetry and assert in tests
- fix(commands): use HA readback values after sensors/set and correct telemetry publish flow
- feat(commands): publish telemetry after sensors/set for successfully set sensors; test updated
- feat(commands): implement sensors/set handling (HA REST set state) and tests
- chore(docs): reorder CHANGELOG newest-first

### Commits included in this release

- chore(release): bump versions to 1.0.47 and add changelog entry
- docs: expand README and changelog with sensors command and telemetry details
- feat(commands): include HA readback attributes in telemetry and assert in tests
- fix(commands): use HA readback values after sensors/set and correct telemetry publish flow
- feat(commands): publish telemetry after sensors/set for successfully set sensors; test updated
- feat(commands): implement sensors/set handling (HA REST set state) and tests
- chore(docs): reorder CHANGELOG newest-first

## [1.0.46] - 2025-11-18

- chore(release): bump add-on version to 1.0.46 and update changelog
- fix(test): add mqtt shim when paho-mqtt not installed to allow unit tests
- chore(release): add changelog entries and update repository.json version

### Commits included in this release

- chore(release): bump add-on version to 1.0.46 and update changelog
- fix(test): add mqtt shim when paho-mqtt not installed to allow unit tests
- chore(release): add changelog entries and update repository.json version

## [1.0.45] - 2025-11-18

- chore(release): bump add-on version to 1.0.45
- chore: ignore venv and test artifacts; add tests and remove legacy topic usage
- Feat: handle Vault 'sensors/poll' commands — ack, publish sensors to preferred and legacy topics, completion
- Chore: bump add-on config.yaml version to v1.0.44
- Chore: bump add-on version to v1.0.44
- Feat: publish HA sensors on startup and hourly to MQTT
- Changelog: add entries for v1.0.41..v1.0.43
- chore: commit workspace changes (requested)
- Fix: use timezone-aware UTC datetimes to avoid datetime.utcnow() deprecation
- Revert "Docs: add Tests section to README with pytest instructions"
- Docs: add Tests section to README with pytest instructions
- Tests: load mqtt_client by path to avoid hyphenated package import
- Add unit tests for vault payload, make mqtt import resilient, and add pytest workflow
- Document vault_topic option, schema versions, and add integration test instructions
- Add simple local integration script for mosquitto + client
- Add schema_version and publish Vault-transformed telemetry to
- Add optional vault_topic option to config schema
- Add optional vault_topic and dual-publish for telemetry

### Commits included in this release

- chore(release): bump add-on version to 1.0.45
- chore: ignore venv and test artifacts; add tests and remove legacy topic usage
- Feat: handle Vault 'sensors/poll' commands — ack, publish sensors to preferred and legacy topics, completion
- Chore: bump add-on config.yaml version to v1.0.44
- Chore: bump add-on version to v1.0.44
- Feat: publish HA sensors on startup and hourly to MQTT
- Changelog: add entries for v1.0.41..v1.0.43
- chore: commit workspace changes (requested)
- Fix: use timezone-aware UTC datetimes to avoid datetime.utcnow() deprecation
- Revert "Docs: add Tests section to README with pytest instructions"
- Docs: add Tests section to README with pytest instructions
- Tests: load mqtt_client by path to avoid hyphenated package import
- Add unit tests for vault payload, make mqtt import resilient, and add pytest workflow
- Document vault_topic option, schema versions, and add integration test instructions
- Add simple local integration script for mosquitto + client
- Add schema_version and publish Vault-transformed telemetry to
- Add optional vault_topic option to config schema
- Add optional vault_topic and dual-publish for telemetry

## [1.0.42] - 2025-11-17

- Dockerfile: install py3-paho-mqtt via apk to avoid pip/PEP668 build errors

### Commits included in this release

- Dockerfile: install py3-paho-mqtt via apk to avoid pip/PEP668 build errors

## [1.0.41] - 2025-11-17

- Dockerfile: default BUILD_FROM fallback; bump to v1.0.41

### Commits included in this release

- Dockerfile: default BUILD_FROM fallback; bump to v1.0.41

## [1.0.40] - 2025-11-17

- Bump add-on version to 1.0.40
- Convert to Python MQTT client; install python/paho-mqtt in Dockerfile

### Commits included in this release

- Bump add-on version to 1.0.40
- Convert to Python MQTT client; install python/paho-mqtt in Dockerfile

## [1.0.39] - 2025-11-17

- Make mosquitto_sub persistent with logging; bump to v1.0.39

### Commits included in this release

- Make mosquitto_sub persistent with logging; bump to v1.0.39

## [1.0.38] - 2025-11-17

- Bump add-on version to 1.0.38
- Fix mqtt arg quoting for subscriber and sensor publish (build sub_extra, use eval)

### Commits included in this release

- Bump add-on version to 1.0.38
- Fix mqtt arg quoting for subscriber and sensor publish (build sub_extra, use eval)

## [1.0.37] - 2025-11-17

- Fix network config in YAML and update to v1.0.37

### Commits included in this release

- Fix network config in YAML and update to v1.0.37

## [1.0.36] - 2025-11-17

- Update version to 1.0.36
- Add reconnection loop for MQTT subscriber to handle disconnections

### Commits included in this release

- Update version to 1.0.36
- Add reconnection loop for MQTT subscriber to handle disconnections

## [1.0.35] - 2025-11-17

- Fix workflow to set BUILD_FROM for multi-platform builds
- Update version to 1.0.35

### Commits included in this release

- Fix workflow to set BUILD_FROM for multi-platform builds
- Update version to 1.0.35

## [1.0.34] - 2025-11-17

- Update version to 1.0.34
- Use different client IDs for pub and sub to keep sub connection open
- Add maintainer to repository.json

### Commits included in this release

- Update version to 1.0.34
- Use different client IDs for pub and sub to keep sub connection open
- Add maintainer to repository.json

## [1.0.33] - 2025-11-17

- Update version to 1.0.33

### Commits included in this release

- Update version to 1.0.33

## [1.0.32] - 2025-11-17

- Update version to 1.0.32

### Commits included in this release

- Update version to 1.0.32

## [1.0.31] - 2025-11-17

- Fix process substitution for ash compatibility in sensor processing

### Commits included in this release

- Fix process substitution for ash compatibility in sensor processing

## [1.0.30] - 2025-11-17

- Set default client_id to 'home-assistant' to fix templated hostname issue

### Commits included in this release

- Set default client_id to 'home-assistant' to fix templated hostname issue

## [1.0.29] - 2025-11-17

- Add host network to allow access to external MQTT broker

### Commits included in this release

- Add host network to allow access to external MQTT broker

## [1.0.28] - 2025-11-17

- Change shebang to /bin/sh and fix bash-specific syntax for compatibility
- Apply shfmt formatting to run.sh

### Commits included in this release

- Change shebang to /bin/sh and fix bash-specific syntax for compatibility
- Apply shfmt formatting to run.sh

## [1.0.27] - 2025-11-17

- Reformat telemetry payload to reduce line length

### Commits included in this release

- Reformat telemetry payload to reduce line length

## [1.0.26] - 2025-11-17

- Fix shellcheck issues: remove redundant assignment, use parameter expansion for sed

### Commits included in this release

- Fix shellcheck issues: remove redundant assignment, use parameter expansion for sed

## [1.0.25] - 2025-11-17

- Fix shell syntax: use string concatenation for MQTT options, change shebang to /bin/bash

### Commits included in this release

- Fix shell syntax: use string concatenation for MQTT options, change shebang to /bin/bash

## [1.0.24] - 2025-11-17

- Fix mosquitto_pub/sub calls using arrays to avoid eval quoting issues

### Commits included in this release

- Fix mosquitto_pub/sub calls using arrays to avoid eval quoting issues

## [1.0.23] - 2025-11-17

- Read options from /data/options.json instead of env vars for reliability

### Commits included in this release

- Read options from /data/options.json instead of env vars for reliability

## [1.0.22] - 2025-11-17

- Make mqtt_host required in schema to ensure env var is set

### Commits included in this release

- Make mqtt_host required in schema to ensure env var is set

## [1.0.21] - 2025-11-17

- Add debug output for MQTT configuration

### Commits included in this release

- Add debug output for MQTT configuration

## [1.0.20] - 2025-11-17

- Fix shell compatibility: replace associative array with eval for sh/bash
- Add icon.png and logo.png for HA add-on display, remove SVG versions
- Add linux/386 platform to workflow for i386 support

### Commits included in this release

- Fix shell compatibility: replace associative array with eval for sh/bash
- Add icon.png and logo.png for HA add-on display, remove SVG versions
- Add linux/386 platform to workflow for i386 support

## [1.0.18] - 2025-11-17

- Fix IP address gathering for BusyBox compatibility

### Commits included in this release

- Fix IP address gathering for BusyBox compatibility

## [1.0.17] - 2025-11-17

- Add MQTT subscription to commands topic

### Commits included in this release

- Add MQTT subscription to commands topic

## [1.0.16] - 2025-11-17

- Add mosquitto-clients to Dockerfile for MQTT publishing

### Commits included in this release

- Add mosquitto-clients to Dockerfile for MQTT publishing

## [1.0.15] - 2025-11-17

- Fix config.yaml: remove ports, fix client_id default, make options optional

### Commits included in this release

- Fix config.yaml: remove ports, fix client_id default, make options optional

## [1.0.14] - 2025-11-16

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.0.86] - 2025-11-27

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests
- chore: bump version to 1.1.61
- ci(release): drop armv7 and i386 builds from release matrix
- Drop legacy architectures and bump to 1.1.60
- chore: bump version to 1.1.59
- handlers: include friendly names in sensors/set ACK; add test
- chore(release): bump version to 1.1.58
- ci: install pyyaml in CI workflow
- chore(release): bump version to 1.1.57
- chore: commit local changes before bump
- chore(release): bump version to 1.1.56
- chore: make central_core_mqtt_shared optional; add STRICT_SHARED guard
- chore(release): bump version to 1.1.52
- chore(release): bump version to 1.1.49
- ci: strict linters + run pytest from central-core-hub + env-based codecov guard
- test(ci): make sensors tests robust to CWD by loading handlers dynamically
- ci: fix workflow (remove duplicate sections)
- ci: add GitHub Actions workflow; tests: add focused sensors tests
- test(telemetry): cover additional telemetry branches (ha_version, schema, cpu override)

## [1.1.62] - 2025-12-09

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests

### Commits included in this release

- chore: bump version to 1.1.62
- fix(telemetry): preserve raw HA states; stop normalizing; update tests

