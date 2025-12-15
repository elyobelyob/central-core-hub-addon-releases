# Test Coverage: telemetry_helpers.py

**Status**: ✅ 100% coverage (35/35 statements)

## Coverage Report
```
Name                   Stmts   Miss  Cover
------------------------------------------
telemetry_helpers.py      35      0   100%
```

**Tests**: 18 passing  
**Location**: `tests/unit/test_telemetry_helpers_coverage.py`

## Functions Tested

### `attach_ha_timestamps(attrs, sensor)`
- Timestamp normalization (`+00:00` → `Z`)
- None/missing values handling
- Non-string value handling

### `build_sensor_maps(filtered)`
- Multiple sensor processing
- Disabled sensors (`disabled_by` attribute)
- Missing/empty `entity_id` handling
- Name fallbacks: `friendly_name` → `name` → `entity_id`
- Timestamp normalization in attributes

### `build_sensor_event_payload(entity_id, attrs, state_value)`
- JSON payload generation
- Timestamp in Z format
- Enabled/disabled status
- Name fallback logic

## Key Features
- **Timestamp normalization**: All timestamps converted from `+00:00` to `Z` format
- **Robust error handling**: Graceful handling of missing/malformed data
- **Fallback logic**: Multiple levels of fallback for sensor names

## Run Tests
```bash
pytest tests/unit/test_telemetry_helpers_coverage.py --cov=telemetry_helpers --cov-report=term-missing -v
```

---
**Module**: telemetry_helpers.py | **Coverage**: 100%
