#!/usr/bin/env python3
"""
Version management script for Central Core Hub Add-on.

Ensures consistent versioning across all configuration files:
- central-core-hub/config.json
- central-core-hub/config.yaml
- repository.json

Usage:
    python version_manager.py check          # Check current versions
    python version_manager.py validate       # Validate version consistency
    python version_manager.py bump patch     # Bump patch version (1.0.69 -> 1.0.70)
    python version_manager.py bump minor     # Bump minor version (1.0.69 -> 1.1.0)
    python version_manager.py bump major     # Bump major version (1.0.69 -> 2.0.0)
    python version_manager.py set 1.2.3      # Set specific version
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict


class VersionManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.version_files = {
            "config.json": repo_root / "central-core-hub" / "config.json",
            "config.yaml": repo_root / "central-core-hub" / "config.yaml",
            "repository.json": repo_root / "repository.json",
        }

    def get_current_versions(self) -> Dict[str, str]:
        """Get current version from each file."""
        versions = {}

        # config.json
        with open(self.version_files["config.json"], "r") as f:
            data = json.load(f)
            versions["config.json"] = data["version"]

        # config.yaml
        with open(self.version_files["config.yaml"], "r") as f:
            content = f.read()
            match = re.search(r'^version:\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                versions["config.yaml"] = match.group(1)

        # repository.json
        with open(self.version_files["repository.json"], "r") as f:
            data = json.load(f)
            versions["repository.json"] = data["version"]

        return versions

    def validate_versions(self) -> bool:
        """Check if all versions are consistent."""
        versions = self.get_current_versions()
        unique_versions = set(versions.values())

        if len(unique_versions) == 1:
            print("✅ All version files are consistent!")
            for file, version in versions.items():
                print(f"   {file}: {version}")
            return True
        else:
            print("❌ Version inconsistency detected!")
            for file, version in versions.items():
                print(f"   {file}: {version}")
            print(f"\nFound {len(unique_versions)} different versions: {sorted(unique_versions)}")
            return False

    def parse_version(self, version: str) -> tuple:
        """Parse version string into (major, minor, patch)."""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
        if not match:
            raise ValueError(f"Invalid version format: {version}")
        return tuple(int(x) for x in match.groups())

    def format_version(self, major: int, minor: int, patch: int) -> str:
        """Format version tuple into string."""
        return f"{major}.{minor}.{patch}"

    def bump_version(self, current_version: str, bump_type: str) -> str:
        """Bump version according to type."""
        major, minor, patch = self.parse_version(current_version)

        if bump_type == "patch":
            patch += 1
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")

        return self.format_version(major, minor, patch)

    def update_version_in_file(self, file_path: Path, new_version: str) -> None:
        """Update version in a specific file."""
        if file_path.name.endswith(".json"):
            # JSON files
            with open(file_path, "r") as f:
                data = json.load(f)

            data["version"] = new_version

            with open(file_path, "w") as f:
                json.dump(data, f, indent="\t" if file_path.name == "repository.json" else None)
                if file_path.name != "repository.json":
                    f.write("\n")  # Add newline for non-repository files

        elif file_path.name.endswith(".yaml"):
            # YAML files
            with open(file_path, "r") as f:
                content = f.read()

            # Replace version line
            content = re.sub(r'^version:\s*"[^"]*"', f'version: "{new_version}"', content, flags=re.MULTILINE)

            with open(file_path, "w") as f:
                f.write(content)

    def set_version(self, new_version: str, validate: bool = True) -> None:
        """Set version across all files."""
        if validate:
            # Validate new version format
            self.parse_version(new_version)

        print(f"Setting version to {new_version}...")

        for file_name, file_path in self.version_files.items():
            print(f"   Updating {file_name}...")
            self.update_version_in_file(file_path, new_version)

        print("✅ Version updated successfully!")

        if validate:
            self.validate_versions()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    repo_root = Path(__file__).parent
    manager = VersionManager(repo_root)

    if command == "check":
        versions = manager.get_current_versions()
        print("Current versions:")
        for file, version in versions.items():
            print(f"   {file}: {version}")

    elif command == "validate":
        if not manager.validate_versions():
            sys.exit(1)

    elif command == "bump":
        if len(sys.argv) < 3:
            print("Usage: python version_manager.py bump <patch|minor|major>")
            sys.exit(1)

        bump_type = sys.argv[2]
        versions = manager.get_current_versions()

        # Check consistency first
        if not manager.validate_versions():
            print("❌ Cannot bump version - files are inconsistent!")
            sys.exit(1)

        current_version = list(versions.values())[0]
        new_version = manager.bump_version(current_version, bump_type)

        print(f"Bumping {current_version} -> {new_version} ({bump_type})")
        manager.set_version(new_version, validate=False)

    elif command == "set":
        if len(sys.argv) < 3:
            print("Usage: python version_manager.py set <version>")
            sys.exit(1)

        new_version = sys.argv[2]
        manager.set_version(new_version)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
