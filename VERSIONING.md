# Version Management

This repository uses automated version management to ensure consistency across all configuration files.

## Files That Contain Version Information

- `central-core-hub/config.json` - Add-on configuration
- `central-core-hub/config.yaml` - Alternative add-on configuration
- `repository.json` - Repository metadata

## Version Management Script

Use `version_manager.py` to manage versions safely:

```bash
# Check current versions
python version_manager.py check

# Validate version consistency
python version_manager.py validate

# Bump versions
python version_manager.py bump patch  # 1.0.69 -> 1.0.70
python version_manager.py bump minor  # 1.0.69 -> 1.1.0
python version_manager.py bump major  # 1.0.69 -> 2.0.0

# Set specific version
python version_manager.py set 1.2.3
```

## Quality Assurance

The `run_tests_with_quality.sh` script automatically validates version consistency before running tests:

```bash
./run_tests_with_quality.sh
```

This ensures that:
1. All version files are consistent
2. Code is properly formatted (black)
3. No linting issues (flake8)
4. All tests pass

## Release Process

1. Make your code changes
2. Run `./run_tests_with_quality.sh` to ensure everything works
3. Bump version: `python version_manager.py bump <patch|minor|major>`
4. Commit changes
5. Push to trigger CI/CD

The version management system prevents inconsistent versioning and ensures all files are updated atomically.