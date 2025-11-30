import json
import re
from pathlib import Path
import yaml


def _read_json(path: Path):
    with path.open() as f:
        return json.load(f)


def _read_yaml_version(path: Path):
    """Parse the YAML manifest and return its top-level `version` value.

    Uses PyYAML's `safe_load` for correctness. Tests / CI must ensure
    `pyyaml` is installed before running this test.
    """
    with path.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return None
    v = data.get("version")
    if v is None:
        return None
    return str(v).strip()


def test_versions_aligned_across_manifests():
    """Ensure versions in repository.json, config.json and config.yaml match.

    Home Assistant reads the repository add-on listing and the add-on
    manifest; these must be kept aligned so the UI shows the expected
    version. This test fails if any of the three canonical files differ
    or if the value is not a simple semver (MAJOR.MINOR.PATCH) without a
    leading `v`.
    """
    repo_root = Path(__file__).resolve().parents[3]
    repo_json = repo_root / "repository.json"
    addon_cfg_json = repo_root / "central-core-hub" / "config.json"
    addon_cfg_yaml = repo_root / "central-core-hub" / "config.yaml"

    r = _read_json(repo_json)
    cj = _read_json(addon_cfg_json)
    cy_ver = _read_yaml_version(addon_cfg_yaml)

    v_repo = str(r.get("version") or "").strip()
    v_json = str(cj.get("version") or "").strip()
    v_yaml = str(cy_ver or "").strip()

    assert v_repo, f"no version found in {repo_json}"
    assert v_json, f"no version found in {addon_cfg_json}"
    assert v_yaml, f"no version found in {addon_cfg_yaml}"

    # All three must match exactly
    assert v_repo == v_json == v_yaml, (
        f"Version mismatch: repository.json={v_repo}, config.json={v_json}, config.yaml={v_yaml}"
    )

    # Ensure it's a simple semver (no leading 'v')
    assert not v_repo.startswith("v"), "version should not start with 'v'"
    assert re.match(r"^\d+\.\d+\.\d+$", v_repo), f"version '{v_repo}' is not a MAJOR.MINOR.PATCH numeric semver"
