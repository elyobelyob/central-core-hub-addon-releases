"""Behaviour tests for version_manager.py.

Every test works on a throwaway copy of the three version files under
tmp_path, never on the real repo. Git is stubbed through
``subprocess.check_output`` so no test depends on the repo's tags or history.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("version_manager_under_test", str(_ROOT / "version_manager.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vm = _load()

_YAML = 'name: "Central Core Hub"\nversion: "{v}"\nslug: central_core_hub\n'


def _make_repo(root: pathlib.Path, json_v="1.0.5", yaml_v="1.0.5", repo_v="1.0.5"):
    hub = root / "central-core-hub"
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "config.json").write_text(json.dumps({"name": "Central Core Hub", "version": json_v}))
    (hub / "config.yaml").write_text(_YAML.format(v=yaml_v))
    (root / "repository.json").write_text(json.dumps({"name": "repo", "version": repo_v}, indent="\t"))
    return vm.VersionManager(root)


class _Git:
    """Stub for subprocess.check_output that answers a few git commands."""

    def __init__(self, tags_desc=None, tags_asc=None, log=None, range_log=None, tag_dates=None, fail=()):
        self.tags_desc = tags_desc or []
        self.tags_asc = tags_asc or []
        self.log = log or []
        self.range_log = range_log or {}
        self.tag_dates = tag_dates or {}
        self.fail = set(fail)
        self.calls = []

    def __call__(self, args, cwd=None):
        self.calls.append(list(args))
        if args[1] == "for-each-ref":
            key = "desc" if args[2] == "--sort=-taggerdate" else "asc"
            if key in self.fail:
                raise subprocess.CalledProcessError(1, args)
            tags = self.tags_desc if key == "desc" else self.tags_asc
            return "\n".join(tags).encode()
        if args[1] == "log" and args[2] == "-1":
            tag = args[-1]
            if tag not in self.tag_dates:
                raise subprocess.CalledProcessError(1, args)
            return self.tag_dates[tag].encode()
        if args[1] == "log" and "-n" in args:
            if "head" in self.fail:
                raise subprocess.CalledProcessError(1, args)
            return "\n".join(self.log).encode()
        if args[1] == "log":
            rng = args[-1]
            if rng not in self.range_log:
                raise subprocess.CalledProcessError(128, args)
            return "\n".join(self.range_log[rng]).encode()
        raise AssertionError(f"unexpected git call {args}")


# --- reading and validating -------------------------------------------------


def test_get_current_versions_reads_all_three_files(tmp_path):
    m = _make_repo(tmp_path, "1.2.3", "1.2.3", "1.2.3")
    assert m.get_current_versions() == {
        "config.json": "1.2.3",
        "config.yaml": "1.2.3",
        "repository.json": "1.2.3",
    }


def test_yaml_without_quoted_version_is_left_out(tmp_path):
    m = _make_repo(tmp_path)
    (tmp_path / "central-core-hub" / "config.yaml").write_text("version: 1.0.5\n")
    assert "config.yaml" not in m.get_current_versions()


def test_validate_true_when_consistent(tmp_path, capsys):
    m = _make_repo(tmp_path)
    assert m.validate_versions() is True
    assert "consistent" in capsys.readouterr().out


def test_validate_false_and_lists_versions_when_inconsistent(tmp_path, capsys):
    m = _make_repo(tmp_path, json_v="1.0.5", yaml_v="1.0.6", repo_v="1.0.5")
    assert m.validate_versions() is False
    out = capsys.readouterr().out
    assert "inconsistency" in out
    assert "['1.0.5', '1.0.6']" in out


# --- parsing and bumping ----------------------------------------------------


@pytest.mark.parametrize(
    "kind,expected",
    [("patch", "1.4.10"), ("minor", "1.5.0"), ("major", "2.0.0")],
)
def test_bump_version(kind, expected, tmp_path):
    m = vm.VersionManager(tmp_path)
    assert m.bump_version("1.4.9", kind) == expected


def test_bump_rejects_unknown_kind(tmp_path):
    with pytest.raises(ValueError, match="Invalid bump type"):
        vm.VersionManager(tmp_path).bump_version("1.0.0", "huge")


@pytest.mark.parametrize("bad", ["1.0", "v1.0.0", "1.0.0-rc1", "", "a.b.c"])
def test_parse_version_rejects_non_semver(bad, tmp_path):
    with pytest.raises(ValueError, match="Invalid version format"):
        vm.VersionManager(tmp_path).parse_version(bad)


# --- writing ----------------------------------------------------------------


def test_update_version_in_file_keeps_each_file_format(tmp_path):
    m = _make_repo(tmp_path)
    for path in m.version_files.values():
        m.update_version_in_file(path, "9.8.7")

    cfg_json = (tmp_path / "central-core-hub" / "config.json").read_text()
    assert cfg_json == '{"name":"Central Core Hub","version":"9.8.7"}\n'  # compact single line
    repo_json = (tmp_path / "repository.json").read_text()
    assert '\t"version": "9.8.7"' in repo_json  # tab-indented
    cfg_yaml = (tmp_path / "central-core-hub" / "config.yaml").read_text()
    assert cfg_yaml == _YAML.format(v="9.8.7")  # only the version line changed
    assert m.get_current_versions() == dict.fromkeys(m.version_files, "9.8.7")


def test_update_version_ignores_other_file_types(tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text('version: "1.0.0"\n')
    vm.VersionManager(tmp_path).update_version_in_file(other, "2.0.0")
    assert other.read_text() == 'version: "1.0.0"\n'


def test_set_version_rejects_bad_version_before_touching_files(tmp_path, monkeypatch):
    m = _make_repo(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git())
    with pytest.raises(ValueError):
        m.set_version("1.0")
    assert set(m.get_current_versions().values()) == {"1.0.5"}


def test_set_version_updates_files_and_changelogs(tmp_path, monkeypatch):
    m = _make_repo(tmp_path)
    git = _Git(
        tags_desc=["v1.0.6", "v1.0.5"],
        range_log={"v1.0.5..HEAD": ["Add door sensor filter", "chore(release): bump to 1.0.5"]},
    )
    monkeypatch.setattr(vm.subprocess, "check_output", git)

    m.set_version("1.0.6")

    assert set(m.get_current_versions().values()) == {"1.0.6"}
    for path in (tmp_path / "CHANGELOG.md", tmp_path / "central-core-hub" / "CHANGELOG.md"):
        text = path.read_text()
        assert text.startswith("# Changelog\n\n## [1.0.6] - ")
        assert "- Add door sensor filter" in text
        assert "bump to 1.0.5" not in text  # release-bump commits are skipped


def test_set_version_without_changelog_leaves_changelog_alone(tmp_path, monkeypatch):
    m = _make_repo(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [1.0.5]\n- old\n")
    monkeypatch.setattr(vm.subprocess, "check_output", _Git())
    m.set_version("1.0.6", update_changelog=False)
    assert "## [1.0.5]" in (tmp_path / "CHANGELOG.md").read_text()


def test_set_version_falls_back_to_recent_commits_without_tags(tmp_path, monkeypatch):
    m = _make_repo(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(log=["First commit"], fail={"desc"}))
    m.set_version("1.0.6")
    assert "- First commit" in (tmp_path / "CHANGELOG.md").read_text()


# --- git helpers ------------------------------------------------------------


def test_find_previous_tag_skips_the_new_version(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(tags_desc=["v2.0.0", "1.9.0"]))
    assert m._find_previous_tag("2.0.0") == "1.9.0"


def test_find_previous_tag_empty_when_only_new_tag(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(tags_desc=["v2.0.0"]))
    assert m._find_previous_tag("2.0.0") == ""


def test_commits_between_two_tags_uses_tag_range_and_caps_at_ten(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    lines = [f"change {i}" for i in range(15)] + ["Bump version to 1.0.2", "chore: bump deps"]
    git = _Git(range_log={"v1.0.1..v1.0.2": lines})
    monkeypatch.setattr(vm.subprocess, "check_output", git)
    out = m._git_commits_between("1.0.1", "1.0.2")
    assert out == [f"- change {i}" for i in range(10)]
    assert git.calls == [["git", "log", "--pretty=format:%s", "v1.0.1..v1.0.2"]]


def test_commits_between_falls_back_when_range_missing(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(log=["recent"]))
    assert m._git_commits_between("0.0.1") == ["- recent"]


def test_commits_between_returns_empty_when_git_unavailable(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(fail={"head"}))
    assert m._git_commits_between() == []


def test_update_changelogs_without_commits_writes_bump_line(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(fail={"head"}))
    m.update_changelogs("1.0.0", "1.0.1", date_str="2026-01-02")
    expected = "# Changelog\n\n## [1.0.1] - 2026-01-02\n\n- chore(release): bump version to 1.0.1\n\n"
    assert (tmp_path / "CHANGELOG.md").read_text() == expected
    assert (tmp_path / "central-core-hub" / "CHANGELOG.md").read_text() == expected


def test_update_changelogs_reports_write_failure_and_continues(tmp_path, capsys):
    m = vm.VersionManager(tmp_path)
    # A directory where the top-level changelog file should be makes the write fail.
    (tmp_path / "CHANGELOG.md").mkdir()
    m.update_changelogs("1.0.0", "1.0.1", date_str="2026-01-02", commits=["- x"])
    assert "Warning: failed to update changelog" in capsys.readouterr().out
    assert "## [1.0.1]" in (tmp_path / "central-core-hub" / "CHANGELOG.md").read_text()


def test_backfill_adds_only_missing_tags_with_tag_dates(tmp_path, monkeypatch):
    m = vm.VersionManager(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [1.0.0] - 2025-01-01\n")
    git = _Git(
        tags_asc=["v1.0.0", "v1.0.1", "v1.0.2"],
        tag_dates={"v1.0.1": "2025-02-03T10:00:00+00:00"},  # v1.0.2 has no date -> today
        range_log={"v1.0.0..v1.0.1": ["fix a"], "v1.0.1..v1.0.2": ["fix b"]},
    )
    monkeypatch.setattr(vm.subprocess, "check_output", git)
    seen = []
    monkeypatch.setattr(
        m, "update_changelogs", lambda prev, new, date_str=None, commits=None: seen.append((prev, new, date_str, commits))
    )

    m.backfill_missing_tags()

    assert [s[:2] for s in seen] == [("1.0.0", "1.0.1"), ("1.0.1", "1.0.2")]
    assert seen[0][2] == "2025-02-03"
    assert seen[0][3] == ["- fix a"]
    assert seen[1][3] == ["- fix b"]
    assert len(seen[1][2]) == 10  # ISO date fallback


def test_backfill_warns_when_tags_cannot_be_listed(tmp_path, monkeypatch, capsys):
    m = vm.VersionManager(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(fail={"asc"}))
    m.backfill_missing_tags()
    assert "cannot list git tags" in capsys.readouterr().out
    assert not (tmp_path / "CHANGELOG.md").exists()


# --- command line -----------------------------------------------------------


def _run_main(monkeypatch, tmp_path, *argv):
    monkeypatch.setattr(sys, "argv", ["version_manager.py", *argv])
    monkeypatch.setattr(vm, "__file__", str(tmp_path / "version_manager.py"))
    vm.main()


def test_main_without_command_prints_usage_and_exits(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, tmp_path)
    assert exc.value.code == 1
    assert "Usage:" in capsys.readouterr().out


def test_main_unknown_command_exits(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, tmp_path, "frobnicate")
    assert exc.value.code == 1
    assert "Unknown command: frobnicate" in capsys.readouterr().out


def test_main_check_prints_versions(monkeypatch, tmp_path, capsys):
    _make_repo(tmp_path, "3.1.4", "3.1.4", "3.1.4")
    _run_main(monkeypatch, tmp_path, "check")
    out = capsys.readouterr().out
    assert "config.json: 3.1.4" in out and "repository.json: 3.1.4" in out


def test_main_validate_exits_nonzero_when_inconsistent(monkeypatch, tmp_path):
    _make_repo(tmp_path, repo_v="1.0.4")
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, tmp_path, "validate")
    assert exc.value.code == 1


def test_main_validate_passes_when_consistent(monkeypatch, tmp_path):
    _make_repo(tmp_path)
    _run_main(monkeypatch, tmp_path, "validate")  # no SystemExit


@pytest.mark.parametrize("cmd", ["bump", "set"])
def test_main_bump_and_set_need_an_argument(cmd, monkeypatch, tmp_path):
    _make_repo(tmp_path)
    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, tmp_path, cmd)
    assert exc.value.code == 1


def test_main_bump_refuses_when_files_disagree(monkeypatch, tmp_path, capsys):
    _make_repo(tmp_path, yaml_v="1.0.4")
    with pytest.raises(SystemExit):
        _run_main(monkeypatch, tmp_path, "bump", "patch")
    assert "Cannot bump" in capsys.readouterr().out
    assert vm.VersionManager(tmp_path).get_current_versions()["config.json"] == "1.0.5"


def test_main_bump_patch_moves_every_file(monkeypatch, tmp_path):
    _make_repo(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(fail={"desc", "head"}))
    _run_main(monkeypatch, tmp_path, "bump", "minor")
    assert set(vm.VersionManager(tmp_path).get_current_versions().values()) == {"1.1.0"}


def test_main_set_writes_requested_version(monkeypatch, tmp_path):
    _make_repo(tmp_path)
    monkeypatch.setattr(vm.subprocess, "check_output", _Git(fail={"desc", "head"}))
    _run_main(monkeypatch, tmp_path, "set", "2.3.4")
    assert set(vm.VersionManager(tmp_path).get_current_versions().values()) == {"2.3.4"}


def test_main_backfill_calls_backfill(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(vm.VersionManager, "backfill_missing_tags", lambda self: called.append(self.repo_root))
    _run_main(monkeypatch, tmp_path, "backfill")
    assert called == [tmp_path]
