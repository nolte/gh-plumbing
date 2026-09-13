"""Tests for scripts/branch_protection_audit.py.

The load-bearing cases are the ones where the two enforcement mechanisms
disagree about how much is known. Enforcement comes from classic branch
protection AND rulesets, and either read can fail on its own -- so "enforced
nothing" and "could not be read" are different answers, and the audit is only
useful if it never returns one when it means the other (#421).

Every test drives `audit_repo` with both API calls stubbed, so no test touches
the network or needs a token.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "branch_protection_audit.py"
_spec = importlib.util.spec_from_file_location("branch_protection_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(audit)

REPO = "nolte/example"
BRANCH = "develop"

DECLARES_THREE = {
    "_extends": "gh-plumbing:.github/commons-settings.yml",
    "branches": [
        {
            "name": BRANCH,
            "protection": {
                "required_status_checks": {
                    "contexts": ["static / Static CI Tests", "docs / MkDocs Build", "actionlint / Workflow Lint"]
                }
            },
        }
    ],
}


def ruleset_payload(*contexts):
    """A /rules/branches response enforcing `contexts`."""
    return [
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": c} for c in contexts]},
        }
    ]


def classic_payload(*contexts):
    """A /branches/{branch}/protection response enforcing `contexts`."""
    return {
        "required_status_checks": {"contexts": list(contexts), "strict": True},
        "enforce_admins": {"enabled": True},
        "restrictions": None,
    }


@pytest.fixture
def stub(monkeypatch):
    """Stub both endpoints. `rules` and `protection` may be a value or Forbidden."""

    def configure(rules, protection, settings=DECLARES_THREE):
        def fake_api(path, token):
            payload = rules if "/rules/branches/" in path else protection
            if payload is audit.Forbidden:
                raise audit.Forbidden(path)
            return payload

        monkeypatch.setattr(audit, "api", fake_api)
        monkeypatch.setattr(audit, "read_yaml_file", lambda *a, **k: settings)

    return configure


def test_ruleset_contexts_survive_an_unreadable_classic_read(stub):
    """The regression #421 reports: two contexts read, `Enforced 0` printed.

    The ruleset read succeeds and returns two contexts; the classic read is
    refused. The contexts that were read must still be counted.
    """
    stub(ruleset_payload("docs / MkDocs Build", "static / Static CI Tests"), audit.Forbidden)

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["live"] == ["docs / MkDocs Build", "static / Static CI Tests"]
    assert result["ruleset"] == ["docs / MkDocs Build", "static / Static CI Tests"]
    # None, not []: nothing is known about classic protection here.
    assert result["classic"] is None


def test_gap_with_unreadable_classic_is_unknown_not_drift(stub):
    """A context no ruleset enforces may still be enforced by the unreadable half.

    `drift` asserts the context is absent. The evidence does not support that,
    so the verdict stays `unreadable` -- but the count must be honest.
    """
    stub(ruleset_payload("docs / MkDocs Build", "static / Static CI Tests"), audit.Forbidden)

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["status"] == "unreadable"
    assert result["missing"] == ["actionlint / Workflow Lint"]
    assert len(result["live"]) == 2, "the two contexts that were read must be counted"


def test_ruleset_covering_everything_is_ok_even_when_classic_is_unreadable(stub):
    """#421's third acceptance criterion: such a repository must not fail the job.

    Classic protection can only add to a complete ruleset, so the answer is
    complete even though half of it could not be read.
    """
    stub(
        ruleset_payload(
            "static / Static CI Tests", "docs / MkDocs Build", "actionlint / Workflow Lint"
        ),
        audit.Forbidden,
    )

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["status"] == "ok"
    assert result["missing"] == []


def test_both_reads_refused_is_unreadable_with_nothing_enforced(stub):
    """`unreadable` keeps its original meaning when genuinely nothing was read."""
    stub(audit.Forbidden, audit.Forbidden)

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["status"] == "unreadable"
    assert result["live"] == []


def test_classic_and_ruleset_union_still_gates(stub):
    """Regression guard: the readable path must keep merging both mechanisms."""
    stub(
        ruleset_payload("docs / MkDocs Build"),
        classic_payload("static / Static CI Tests", "actionlint / Workflow Lint"),
    )

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["status"] == "ok"
    assert result["live"] == [
        "actionlint / Workflow Lint",
        "docs / MkDocs Build",
        "static / Static CI Tests",
    ]


def test_read_and_empty_is_unprotected_not_unreadable(stub):
    """The distinction #421 asks for: read successfully and enforcing nothing."""
    stub([], None)

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["status"] == "unprotected"
    assert result["live"] == []


def test_genuine_drift_is_still_reported(stub):
    """The finding the audit exists for must survive the fix."""
    stub([], classic_payload("static / Static CI Tests", "docs / MkDocs Build"))

    result = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert result["status"] == "drift"
    assert result["missing"] == ["actionlint / Workflow Lint"]


def test_render_distinguishes_unreadable_classic_from_absent(stub):
    """`(none)` claims a fact; an unreadable endpoint supports no such claim."""
    stub(ruleset_payload("docs / MkDocs Build"), audit.Forbidden)
    unreadable = audit.audit_repo(REPO, BRANCH, {}, "t")

    stub([], classic_payload("static / Static CI Tests"), settings={"branches": []})
    absent = audit.audit_repo(REPO, BRANCH, {}, "t")

    assert "(not readable with this token)" in audit.render([unreadable])
    assert "(none)" in audit.render([absent])


def test_render_counts_enforced_from_live(stub):
    """The summary table is what a reader sees first; it must match the detail."""
    stub(ruleset_payload("docs / MkDocs Build", "static / Static CI Tests"), audit.Forbidden)

    report = audit.render([audit.audit_repo(REPO, BRANCH, {}, "t")])

    assert "| 3 | 2 |" in report, "declared 3, enforced 2 -- never `| 3 | 0 |` (#421)"
