"""Tests for the Vale steps of reusable-release-publish.yml (#488).

The release-notes check splits failures on purpose. A Vale download that fails
warns and lets the publish go on; a checksum mismatch -- or any other refusal
by actions/setup-vale -- fails the run before the publish step; a `vale sync`
failure warns; a Vale error in the notes blocks. Getting that split wrong
either blocks every release on a flaky download or lets a replaced asset slip
through as "download trouble", and neither shows in a normal run.

The step's `run:` body is read from the workflow file itself and run under
bash against stubs for `gh` and `vale`, with the install step's outcome and
`result` output as the runner would pass them. The install itself is covered by
test_setup_vale.py.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "reusable-release-publish.yml"

GH_STUB = """#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
printf '%s' "$STUB_BODY"
"""

VALE_STUB = """#!/usr/bin/env bash
echo "vale $*" >> "$STUB_LOG"
if [[ "$1" == "sync" ]]; then exit "$STUB_SYNC_EXIT"; fi
exit "$STUB_CHECK_EXIT"
"""


def steps() -> list[dict]:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return doc["jobs"]["publish"]["steps"]


def step(name: str) -> dict:
    [found] = [s for s in steps() if s.get("name") == name]
    return found


@pytest.fixture
def run(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in (("gh", GH_STUB), ("vale", VALE_STUB)):
        path = stubs / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(step("Check the release notes with Vale")["run"], encoding="utf-8")
    log = tmp_path / "calls.log"

    def _run(outcome: str, result: str, *, body: str = "Fixes the thing.", sync: int = 0, check: int = 0):
        log.write_text("", encoding="utf-8")
        env = {
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "TAG": "v9.9.9",
            "GH_TOKEN": "unused",
            "VALE_OUTCOME": outcome,
            "VALE_RESULT": result,
            "STUB_LOG": str(log),
            "STUB_BODY": body,
            "STUB_SYNC_EXIT": str(sync),
            "STUB_CHECK_EXIT": str(check),
        }
        proc = subprocess.run(["bash", "-e", str(script)], cwd=tmp_path, env=env,
                              capture_output=True, text=True, check=False)
        calls = [line for line in log.read_text(encoding="utf-8").splitlines() if line]
        return proc, calls

    return _run


# --- the four outcomes of #488 P2 AC2 --------------------------------------


def test_download_failure_warns_and_skips(run):
    proc, calls = run("failure", "download-failed")
    assert proc.returncode == 0
    assert "::warning::Could not download Vale" in proc.stdout
    assert calls == [], "nothing else runs once the check is skipped"


def test_checksum_mismatch_fails_the_run(run):
    proc, calls = run("failure", "checksum-mismatch")
    assert proc.returncode == 1
    assert "::error::Installing Vale failed with result 'checksum-mismatch'" in proc.stdout
    assert calls == []


def test_vale_sync_failure_warns_and_skips(run):
    proc, calls = run("success", "installed", sync=1)
    assert proc.returncode == 0
    assert "::warning::'vale sync' could not fetch the style packages" in proc.stdout
    assert not any(c.startswith("vale --minAlertLevel") for c in calls)


def test_vale_error_in_the_notes_blocks(run):
    proc, calls = run("success", "installed", check=1)
    assert proc.returncode == 1
    assert "carry Vale errors" in proc.stdout
    assert "vale --minAlertLevel=error release-notes.vale.md" in calls


# --- the rest of the split -------------------------------------------------


def test_clean_notes_pass(run):
    proc, calls = run("success", "installed")
    assert proc.returncode == 0
    assert "Release notes pass Vale at error level." in proc.stdout
    assert calls[-1] == "vale --minAlertLevel=error release-notes.vale.md"


@pytest.mark.parametrize("result", ["invalid-pin", "unsupported-platform", "run-failed", "", "something-new"])
def test_every_other_install_failure_fails_closed(run, result):
    proc, calls = run("failure", result)
    assert proc.returncode == 1
    assert "::error::Installing Vale failed" in proc.stdout
    assert calls == []


def test_empty_notes_warn_after_a_good_install(run):
    proc, calls = run("success", "installed", body="  \n")
    assert proc.returncode == 0
    assert "are empty; nothing to check" in proc.stdout
    assert not any(c.startswith("vale") for c in calls)


# --- wiring ----------------------------------------------------------------


def test_install_step_feeds_the_check_and_tolerates_its_own_failure():
    names = [s.get("name") for s in steps()]
    checkout = names.index("Check out gh-plumbing at the pinned commit")
    install = names.index("Install Vale (checksum-verified)")
    check = names.index("Check the release notes with Vale")
    freshness = names.index("Check documentation freshness")
    publish = names.index("Publish (flip draft=false)")
    assert checkout < install < check < freshness < publish
    assert names.index("Align version-bearing files (primary path)") < checkout

    inst = steps()[install]
    assert inst["uses"] == "./.gh-plumbing/actions/setup-vale"
    assert inst["with"] == {"version-file": ".gh-plumbing/.vale-version"}
    assert inst["continue-on-error"] is True
    assert "secrets" not in str(inst), "no secret reaches the action"

    env = steps()[check]["env"]
    assert env["VALE_OUTCOME"] == "${{ steps.vale.outcome }}"
    assert env["VALE_RESULT"] == "${{ steps.vale.outputs.result }}"

    co = steps()[checkout]
    assert co["with"]["ref"] == "${{ job.workflow_sha }}"
    assert co["with"]["path"] == ".gh-plumbing"
    assert "continue-on-error" not in co


def test_one_pinned_checkout_serves_both_gates():
    pinned = [s for s in steps() if s.get("with", {}).get("ref") == "${{ job.workflow_sha }}"]
    assert len(pinned) == 1
    assert ".gh-plumbing/scripts/docs_freshness.py" in step("Check documentation freshness")["run"]


def test_no_unverified_install_is_left():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "sudo tar" not in text
    assert "VALE_VERSION" not in text
