"""F10: the add-on image is built from exact versions.

Every hub builds the Dockerfile itself, so a `>=` range, a movable git tag or
a `:latest` base image means different hubs can run different code for the
same release.
"""

import pathlib
import re

ADDON = pathlib.Path(__file__).resolve().parents[2]


def _requirements(path):
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            yield line


def test_runtime_requirements_are_exact():
    for line in _requirements(ADDON / "requirements.txt"):
        if " @ git+" in line:
            assert re.search(r"\.git@[0-9a-f]{40}$", line), f"git dependency not pinned to a commit: {line}"
        else:
            assert re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[0-9][0-9A-Za-z.\-]*", line), f"not an exact pin: {line}"


def test_base_image_is_not_latest():
    assert ":latest" not in (ADDON / "build.yaml").read_text()
    assert ":latest" not in (ADDON / "Dockerfile").read_text()
