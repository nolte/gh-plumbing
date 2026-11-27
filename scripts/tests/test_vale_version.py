"""Tests for scripts/vale_version.py (#488).

The load-bearing case is the Renovate bump: VALE_VERSION moves, the checksum
line stays, and nothing else notices until a release run downloads the new
asset. The second is the quiet drift between `.vale-version` and the asdf pin.
One test runs the check against this repository, so the committed pins hold.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "vale_version.py"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("vale_version", MODULE_PATH)
check = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(check)

SHA = "fc72e64454d6bd7af91905d4faebbf411bae3eec17bb572f4101311212bc0d9e"


def pin(version: str = "3.15.2", asset_version: str | None = None) -> str:
    return (
        "# comment\n\n"
        f"VALE_VERSION={version}\n"
        f"VALE_SHA256={SHA}  vale_{asset_version or version}_Linux_64-bit.tar.gz\n"
    )


def repo(tmp_path: pathlib.Path, vale_version: str | None, tool_versions: str | None = "python 3.14.0\nvale 3.15.2\n"):
    if vale_version is not None:
        (tmp_path / ".vale-version").write_text(vale_version, encoding="utf-8")
    if tool_versions is not None:
        (tmp_path / ".tool-versions").write_text(tool_versions, encoding="utf-8")
    return tmp_path


def test_agreeing_pins_are_clean(tmp_path):
    root = repo(tmp_path, pin())
    assert check.audit(root) == []
    assert check.main(["--root", str(root)]) == 0


def test_renovate_bump_with_the_old_checksum_line_fails(tmp_path, capsys):
    root = repo(tmp_path, pin("3.16.0", asset_version="3.15.2"), "vale 3.16.0\n")
    [finding] = check.audit(root)
    assert "checksum of vale 3.15.2, but VALE_VERSION is 3.16.0" in finding
    assert "vale_3.16.0_checksums.txt" in finding
    assert check.main(["--root", str(root)]) == 1
    assert "VALE_SHA256" in capsys.readouterr().err


def test_tool_versions_disagreeing_fails(tmp_path):
    root = repo(tmp_path, pin(), "vale 3.17.0\n")
    [finding] = check.audit(root)
    assert ".tool-versions pins vale 3.17.0, .vale-version pins 3.15.2" in finding


def test_both_drifts_are_reported_together(tmp_path):
    root = repo(tmp_path, pin("3.16.0", asset_version="3.15.2"), "vale 3.15.2\n")
    assert len(check.audit(root)) == 2


@pytest.mark.parametrize("tool_versions", [None, "python 3.14.0\n", "valet 1.0.0\n"])
def test_nothing_to_compare_without_a_vale_tool_line(tmp_path, tool_versions):
    assert check.audit(repo(tmp_path, pin(), tool_versions)) == []


def test_no_vale_version_file_is_nothing_to_check(tmp_path):
    assert check.audit(repo(tmp_path, None, "vale 9.9.9\n")) == []


@pytest.mark.parametrize("text, expected", [
    ("", "exactly one VALE_VERSION line, found 0"),
    (pin() + "VALE_VERSION=3.15.2\n", "exactly one VALE_VERSION line, found 2"),
    ("VALE_VERSION=3.15.2\n", "exactly one VALE_SHA256 line, found 0"),
    ("VALE_VERSION=3.15.2;id\n" + pin().splitlines()[-1] + "\n", "malformed line"),
    ("VALE_VERSION=3.15.2\n" + f"VALE_SHA256={SHA} vale_3.15.2_Linux_64-bit.tar.gz\n", "malformed line"),
    (pin() + "export FOO=bar\n", "unexpected line"),
])
def test_malformed_files_fail(tmp_path, text, expected):
    findings = check.audit(repo(tmp_path, text))
    assert any(expected in f for f in findings), findings


def test_crlf_line_endings_are_accepted(tmp_path):
    assert check.audit(repo(tmp_path, pin().replace("\n", "\r\n"))) == []


def test_this_repository_pins_agree():
    assert check.audit(REPO_ROOT) == []


def test_renovate_manager_matches_the_committed_file():
    """The custom manager in the shared preset finds VALE_VERSION here.

    Renovate evaluates these patterns with its own regex engine; the subset
    used here (named groups, character classes, anchors) reads the same in
    Python, so this proves the pattern and the file agree, not the engine.
    """
    preset = json.loads((REPO_ROOT / "renovate-configs" / "common.json").read_text(encoding="utf-8"))
    [manager] = [m for m in preset["customManagers"] if m.get("depNameTemplate") == "vale-cli/vale"]
    file_pattern = manager["managerFilePatterns"][0]
    assert file_pattern.startswith("/") and file_pattern.endswith("/")
    assert re.search(file_pattern[1:-1], ".vale-version")
    assert re.search(file_pattern[1:-1], "sub/dir/.vale-version")
    assert not re.search(file_pattern[1:-1], ".vale-version.bak")
    text = (REPO_ROOT / ".vale-version").read_text(encoding="utf-8")
    [match_string] = manager["matchStrings"]
    found = [m.group("currentValue") for m in re.finditer(match_string.replace("(?<", "(?P<"), text, re.MULTILINE)]
    assert found == ["3.15.2"]
    assert manager["datasourceTemplate"] == "github-releases"
    assert re.fullmatch(manager["extractVersionTemplate"].replace("(?<", "(?P<"), "v3.15.2").group("version") == "3.15.2"
    [rule] = [r for r in preset["packageRules"] if r.get("matchPackageNames") == ["vale-cli/vale"]]
    assert rule["automerge"] is False
