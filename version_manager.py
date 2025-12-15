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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


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

    def _git_commits_between(self, prev_tag: Optional[str] = None, new_tag: Optional[str] = None) -> List[str]:
        """Return commit summary lines between prev_tag and new_tag or HEAD.

        - If both tags provided, attempt `git log --pretty=format:%s prev_tag..new_tag`.
        - If only prev_tag provided, use `prev_tag..HEAD`.
        - If prev_tag not provided or git fails, fall back to last 20 commits on HEAD.
        """
        try:
            if prev_tag and new_tag:
                range_ref = f"v{prev_tag}..v{new_tag}"
            elif prev_tag:
                range_ref = f"v{prev_tag}..HEAD"
            else:
                range_ref = None

            if range_ref:
                out = subprocess.check_output(["git", "log", "--pretty=format:%s", range_ref], cwd=self.repo_root)
                lines = out.decode("utf-8").strip().splitlines()
                # Return found lines (even if empty, do not fallback)
                return [f"- {line}" for line in lines if line]
        except Exception:
            pass

        try:
            # Fallback only if no prev_tag matched or git failed
            out = subprocess.check_output(["git", "log", "--pretty=format:%s", "-n", "20", "HEAD"], cwd=self.repo_root)
            lines = out.decode("utf-8").strip().splitlines()
            return [f"- {line}" for line in lines if line]
        except Exception:
            return []

    def _find_previous_tag(self, new_version: str) -> str:
        """Return the most recent tag (by tag creation date) that is not new_version.

        Returns empty string if none found.
        """
        try:
            out = subprocess.check_output([
                "git",
                "for-each-ref",
                "--sort=-taggerdate",
                "--format=%(refname:short)",
                "refs/tags",
            ], cwd=self.repo_root)
            tags = [t.strip() for t in out.decode("utf-8").splitlines() if t.strip()]
            # strip leading 'v' if present
            tags = [t[1:] if t.startswith("v") else t for t in tags]
            for t in tags:
                if t != new_version:
                    return t
        except Exception:
            pass
        return ""

    def backfill_missing_tags(self) -> None:
        """Backfill changelog entries for any git tags not already present.

        Walks tags in chronological order (taggerdate ascending) and for each
        tag that does not have a `## [<tag>]` entry in the changelogs, inserts
        a release section with commits between the previous tag and the tag.
        """
        try:
            out = subprocess.check_output([
                "git",
                "for-each-ref",
                "--sort=taggerdate",
                "--format=%(refname:short)",
                "refs/tags",
            ], cwd=self.repo_root)
            tags = [t.strip() for t in out.decode("utf-8").splitlines() if t.strip()]
            # strip leading 'v' if present
            tags = [t[1:] if t.startswith("v") else t for t in tags]
        except Exception as exc:
            print(f"Warning: cannot list git tags: {exc}")
            return

        changelog_paths = [self.repo_root / "CHANGELOG.md", self.repo_root / "central-core-hub" / "CHANGELOG.md"]

        prev_tag = None
        for tag in tags:
            # check if tag already present in any changelog
            present = False
            for path in changelog_paths:
                if path.exists():
                    content = path.read_text()
                    if re.search(rf"^## \[{re.escape(tag)}\]", content, flags=re.MULTILINE):
                        present = True
                        break

            if present:
                prev_tag = tag
                continue

            # get tag date (try annotated tag date, fall back to commit date)
            try:
                out = subprocess.check_output(["git", "log", "-1", "--format=%aI", f"v{tag}"], cwd=self.repo_root)
                tag_date = out.decode("utf-8").strip().split("T")[0]
            except Exception:
                tag_date = datetime.now(timezone.utc).date().isoformat()

            # get commits between prev_tag and tag
            commits = self._git_commits_between(prev_tag if prev_tag else None, tag)

            # update changelogs with explicit date and commits
            self.update_changelogs(prev_tag or "", tag, date_str=tag_date, commits=commits)

            prev_tag = tag

    def update_changelogs(
        self,
        previous_version: str,
        new_version: str,
        date_str: Optional[str] = None,
        commits: List[str] | None = None,
    ) -> None:
        """Append a dated changelog entry to both top-level and add-on CHANGELOGs.

        The entry includes the commit messages between the previous version tag
        and HEAD as bullet points. If no commits are discovered, a single
        bump line is added.
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).date().isoformat()

        # Build the release block
        header = f"## [{new_version}] - {date_str}\n\n"

        if commits is None:
            commits = self._git_commits_between(previous_version, new_version)

        if commits:
            body = "\n".join(commits) + "\n\n"
            commits_section = "### Commits included in this release\n\n" + "\n".join(commits) + "\n\n"
        else:
            body = f"- chore(release): bump version to {new_version}\n\n"
            commits_section = ""

        release_block = header + body + commits_section

        # Files to update
        changelog_paths = [self.repo_root / "CHANGELOG.md", self.repo_root / "central-core-hub" / "CHANGELOG.md"]

        for path in changelog_paths:
            try:
                if not path.exists():
                    # create a minimal changelog if missing
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with open(path, "w") as f:
                        f.write("# Changelog\n\n")

                content = path.read_text()

                # If an entry for this version already exists, replace it
                existing_pattern = rf"^## \[{re.escape(new_version)}\].*?(?=^## \[|\Z)"
                if re.search(existing_pattern, content, flags=re.DOTALL | re.MULTILINE):
                    new_content = re.sub(existing_pattern, release_block, content, flags=re.DOTALL | re.MULTILINE)
                    path.write_text(new_content)
                    print(f"Replaced existing changelog entry for {new_version}: {path}")
                else:
                    # Insert new release block after title (after first header line)
                    parts = content.split("\n", 2)
                    if len(parts) >= 2 and parts[0].startswith("#"):
                        # preserve first header and an existing blank line if present
                        remainder = content[len(parts[0]) + 1 :]
                        new_content = parts[0] + "\n\n" + release_block + remainder.lstrip()
                    else:
                        new_content = release_block + content

                    path.write_text(new_content)
                    print(f"Updated changelog: {path}")
            except Exception as exc:
                print(f"Warning: failed to update changelog {path}: {exc}")

    def set_version(self, new_version: str, validate: bool = True, update_changelog: bool = True) -> None:
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
        # Optionally update changelogs when setting version
        if update_changelog:
            try:
                # determine previous tag (by taggerdate) for a clean commit range
                previous = self._find_previous_tag(new_version)
                if not previous:
                    # if no previous tag found, leave previous as None so we fallback to recent commits
                    previous = None

                commits = self._git_commits_between(prev_tag=previous)
                # pass the previous tag string (empty or real) and commits to update_changelogs
                self.update_changelogs(previous or "", new_version, commits=commits)
            except Exception as exc:  # pragma: no cover - best-effort
                print(f"Warning: changelog update failed: {exc}")


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

    elif command == "backfill":
        # Backfill changelogs for all tags
        manager.backfill_missing_tags()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
