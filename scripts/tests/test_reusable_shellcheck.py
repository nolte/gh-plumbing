"""Behavioural tests for the `Run ShellCheck` step of reusable-shellcheck.yaml.

The step decides what the workflow promises: which files are linted, and that
the job fails exactly when a finding is at or above `fail_level`. The first
version went through reviewdog/action-shellcheck and broke that promise on
pull requests, where any finding ShellCheck could fix failed the job (run
46065761938 on #519). These tests hold the contract.

Each test reads the step's real `run:` body from the workflow file and runs it
under bash in a throwaway directory. ShellCheck is a stub at the path the
install step unpacks to: it records its arguments and prints a canned `json1`
report, so the tests need no ShellCheck and judge the step, not the linter.
`find`, `awk` and `jq` are the real tools.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "reusable-shellcheck.yaml"
VERSION = "9.9.9"

STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "$STUB_ARGS"
printf '%s' "$STUB_REPORT"
exit "$STUB_STATUS"
"""


def step_body() -> str:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    found = [s for s in doc["jobs"]["shellcheck"]["steps"] if s.get("name") == "Run ShellCheck"]
    assert len(found) == 1
    return found[0]["run"]


def finding(level: str, file: str = "./a.sh", message: str = "msg", code: int = 2086) -> dict:
    return {"file": file, "line": 3, "endLine": 3, "column": 6, "endColumn": 11,
            "level": level, "code": code, "message": message, "fix": None}


@pytest.fixture
def run(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    temp = tmp_path / "temp"
    stub = temp / f"shellcheck-v{VERSION}" / "shellcheck"
    stub.parent.mkdir(parents=True)
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    args_file = tmp_path / "args"

    def _run(findings=(), status=None, files=("a.sh",), **inputs):
        for name in files:
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "RUNNER_TEMP": str(temp),
            "SHELLCHECK_VERSION": VERSION,
            "STUB_ARGS": str(args_file),
            "STUB_REPORT": json.dumps({"comments": list(findings)}),
            "STUB_STATUS": str((1 if findings else 0) if status is None else status),
            "INPUT_FAIL_LEVEL": inputs.get("fail_level", "error"),
            "INPUT_PATH": inputs.get("path", "."),
            "INPUT_PATTERN": inputs.get("pattern", "*.sh"),
            "INPUT_EXCLUDE": inputs.get("exclude", "*/.git/*"),
            "INPUT_SHEBANGS": inputs.get("shebangs", "false"),
            "INPUT_SHELLCHECK_FLAGS": inputs.get("flags", "--external-sources"),
        }
        if args_file.exists():
            args_file.unlink()
        proc = subprocess.run(["bash", "-c", step_body()], cwd=work, env=env,
                              capture_output=True, text=True, check=False)
        proc.linted = sorted(a for a in called(args_file) if a.startswith("./"))
        proc.args_seen = called(args_file)
        return proc

    _run.work = work
    return _run


def called(args_file: pathlib.Path) -> list[str]:
    if not args_file.exists():
        return []
    return [a for a in args_file.read_text(encoding="utf-8").split("\0") if a]


LEVELS = ["style", "info", "warning", "error"]


@pytest.mark.parametrize("fail_level, failing", [
    ("error", {"error"}),
    ("warning", {"warning", "error"}),
    ("info", {"info", "warning", "error"}),
    ("any", {"style", "info", "warning", "error"}),
    ("none", set()),
])
@pytest.mark.parametrize("level", LEVELS)
def test_job_fails_exactly_at_or_above_fail_level(run, fail_level, failing, level):
    proc = run(findings=[finding(level)], fail_level=fail_level)
    assert proc.returncode == (1 if level in failing else 0), proc.stdout + proc.stderr


@pytest.mark.parametrize("level, kind", [
    ("error", "error"), ("warning", "warning"), ("info", "notice"), ("style", "notice")])
def test_every_finding_is_annotated_whatever_the_fail_level(run, level, kind):
    proc = run(findings=[finding(level)], fail_level="none")
    assert proc.returncode == 0
    assert proc.stdout.splitlines() == [
        f"::{kind} file=a.sh,line=3,col=6,title=ShellCheck SC2086 ({level})::msg"]


def test_a_fixable_finding_below_fail_level_passes(run):
    """The case the reviewdog action failed on a pull request (#519)."""
    fixable = finding("info") | {"fix": {"replacements": [{"line": 3, "replacement": '"'}]}}
    assert run(findings=[fixable]).returncode == 0


def test_no_findings_passes_without_output(run):
    proc = run()
    assert (proc.returncode, proc.stdout) == (0, "")


def test_no_matching_file_passes_without_running_shellcheck(run):
    proc = run(files=("README.md",))
    assert proc.returncode == 0
    assert proc.stdout == "No matching files found to check.\n"
    assert proc.args_seen == []


def test_unknown_fail_level_is_refused_before_shellcheck_runs(run):
    proc = run(fail_level="fatal")
    assert proc.returncode == 2
    assert proc.stdout.startswith("::error title=ShellCheck::Input 'fail_level' must be")
    assert proc.args_seen == []


def test_shellcheck_that_could_not_run_fails_the_job(run):
    proc = run(status=4)
    assert proc.returncode == 4
    assert "::error title=ShellCheck::ShellCheck could not run" in proc.stdout


def test_pattern_and_exclude_select_the_files(run):
    proc = run(files=("a.sh", "sub/b.sh", "vendor/c.sh", ".git/hooks/d.sh", "e.bash", "notes.txt"),
               pattern="*.sh\n*.bash", exclude="*/.git/*\n*/vendor/*")
    assert proc.linted == ["./a.sh", "./e.bash", "./sub/b.sh"]


def test_path_limits_the_search_and_is_not_read_as_an_option(run):
    proc = run(files=("a.sh", "sub/b.sh", "-delete/c.sh"), path="sub\n-delete")
    assert proc.linted == ["./-delete/c.sh", "./sub/b.sh"]
    assert (run.work / "a.sh").exists()


@pytest.mark.parametrize("path", ["nope", "sub\nnope", "  sub"])
def test_a_path_that_does_not_exist_fails_instead_of_passing_empty(run, path):
    proc = run(files=("a.sh", "sub/b.sh"), path=path)
    assert proc.returncode == 2
    assert proc.stdout == "::error title=ShellCheck::An entry of input 'path' does not exist in the checkout.\n"
    assert proc.args_seen == []


def test_multi_line_inputs_from_a_yaml_block_keep_working(run):
    """A `|` block ends in a line end; a file edited on Windows adds `\\r`."""
    proc = run(files=("a.sh", "sub/b.bash", "vendor/c.sh"), path=".\r\n",
               pattern="*.sh\r\n*.bash\r\n", exclude="*/.git/*\r\n*/vendor/*\r\n",
               flags="--external-sources\n--severity=warning\n")
    assert proc.linted == ["./a.sh", "./sub/b.bash"]
    assert proc.args_seen[:3] == ["--external-sources", "--severity=warning", "--format=json1"]


@pytest.mark.parametrize("shebang, linted", [
    ("#!/bin/sh", True), ("#!/usr/bin/env bash", True), ("#!/bin/bash -eu", True),
    ("#! /bin/dash", True), ("#!/usr/bin/env -S ksh", True), ("#!/bin/sh\r", True),
    ("#!/usr/bin/env zsh", False), ("#!/usr/bin/fish", False),
    ("#!/usr/bin/env python3 # sh", False), ("#!/usr/bin/env python3", False),
])
def test_shebang_has_to_name_a_shell_shellcheck_reads(run, shebang, linted):
    (run.work / "tool").write_text(shebang + "\necho hi\n", encoding="utf-8")
    assert ("./tool" in run(shebangs="true").linted) is linted


def test_shebang_files_are_linted_only_when_asked(run):
    work = run.work
    (work / "bin").mkdir()
    (work / "bin" / "deploy tool").write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
    (work / "bin" / "notes").write_text("plain text\n#!/bin/sh\n", encoding="utf-8")
    (work / "bin" / "script.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    assert run().linted == ["./a.sh"]
    assert run(shebangs="true").linted == ["./a.sh", "./bin/deploy tool"]


def test_flags_are_split_and_the_format_stays_json1(run):
    proc = run(flags="--external-sources --exclude=SC2086 --format=gcc")
    seen = proc.args_seen
    assert seen[:3] == ["--external-sources", "--exclude=SC2086", "--format=gcc"]
    # The workflow's own format comes last, and the file list after `--`.
    assert seen[3:5] == ["--format=json1", "--"]


@pytest.mark.parametrize("file, message", [
    ("./a\n::error::injected.sh", "msg"),
    ("./a.sh", "x\n::warning::injected"),
    ("./a.sh", "x\r::warning::injected"),
    ("./a,line=1::x.sh", "msg"),
    ("./a,title=x.sh", "msg"),
])
def test_repository_content_cannot_start_a_second_command(run, file, message):
    proc = run(findings=[finding("info", file=file, message=message)])
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, proc.stdout
    assert lines[0].startswith("::notice file=")
    # One line is one command. Its property list is what sits between the
    # first two `::`: four properties, so three commas, none added by a value.
    head = lines[0].split("::", 2)[1]
    assert head.count(",") == 3, head
