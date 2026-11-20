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
import re

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


# --- #442: entries that apply nothing, or race the commons -------------------

COMPLETE = {
    "required_pull_request_reviews": None,
    "required_status_checks": {"strict": True, "contexts": ["static / Static CI Tests"]},
    "enforce_admins": True,
    "restrictions": None,
}


def settings_with(protection, extends=True):
    doc = {"branches": [{"name": BRANCH, "protection": protection}]}
    if extends:
        doc["_extends"] = "gh-plumbing:.github/commons-settings.yml"
    return doc


def test_complete_entry_has_no_findings():
    assert audit.entry_findings(settings_with(dict(COMPLETE)), {"branches": []}, BRANCH) == []


@pytest.mark.parametrize("field", audit.REQUIRED_PROTECTION_FIELDS)
def test_each_absent_required_field_is_named(field):
    protection = {k: v for k, v in COMPLETE.items() if k != field}
    findings = audit.entry_findings(settings_with(protection), {"branches": []}, BRANCH)
    assert len(findings) == 1
    assert f"`{field}`" in findings[0]


def test_null_counts_as_present():
    protection = dict(COMPLETE, required_status_checks=None)
    assert audit.entry_findings(settings_with(protection), {"branches": []}, BRANCH) == []


def test_same_branch_in_commons_and_repository_is_a_race():
    commons = {"branches": [{"name": BRANCH, "protection": dict(COMPLETE)}]}
    findings = audit.entry_findings(settings_with(dict(COMPLETE)), commons, BRANCH)
    assert len(findings) == 1
    assert "concatenates" in findings[0]


def test_commons_entry_alone_is_no_race():
    commons = {"branches": [{"name": BRANCH, "protection": dict(COMPLETE)}]}
    assert audit.entry_findings({"_extends": "x"}, commons, BRANCH) == []


def test_commons_are_ignored_without_extends():
    commons = {"branches": [{"name": BRANCH, "protection": dict(COMPLETE)}]}
    assert audit.entry_findings(settings_with(dict(COMPLETE), extends=False), commons, BRANCH) == []


def test_incomplete_entry_is_reported_by_the_audit(stub):
    stub(ruleset_payload(), classic_payload("static / Static CI Tests"),
         settings=settings_with({"required_status_checks": {"contexts": ["static / Static CI Tests"]}}))
    result = audit.audit_repo(REPO, BRANCH, {"branches": []}, "token")
    assert result["status"] == "ok"
    assert any("omits" in n for n in result["notes"])


def test_enforce_admins_note_reads_the_repository_entry(stub):
    unapplied = dict(classic_payload("static / Static CI Tests"), enforce_admins={"enabled": False})
    stub(ruleset_payload(), unapplied, settings=settings_with(dict(COMPLETE)))
    result = audit.audit_repo(REPO, BRANCH, {"branches": []}, "token")
    assert any("looks unapplied" in n for n in result["notes"])


# --- the step summary (#506) ----------------------------------------------------

HOSTILE = "[x](u) @user #1 <img src=x> |b| `c`"


def test_the_summary_encodes_settings_and_api_text(stub):
    """Context names, the branch and `_extends` come from settings.yml or the API.

    The summary is Markdown: each such value is entity-encoded inside <code>,
    so none adds a link, an image, a mention or a table cell. The plain report
    for the log is the one it always was.
    """
    settings = {
        "_extends": HOSTILE,
        "branches": [{"name": BRANCH, "protection": {"required_status_checks": {"contexts": [HOSTILE, "ok"]}}}],
    }
    stub(ruleset_payload("ok"), classic_payload(HOSTILE + " live"), settings=settings)
    result = audit.audit_repo(REPO + HOSTILE, BRANCH, {}, "t")
    assert any(HOSTILE in n for n in result["notes"]), "a note quotes a context"

    markdown = audit.render([result])
    rest = re.sub(r"<code>[^<]*</code>", "", markdown)
    for fragment in ("[x](", "<img", "@user", "#1", "|b|", "`c`"):
        assert fragment not in rest, fragment
    for element in re.findall(r"<code>([^<]*)</code>", markdown):
        assert not re.search(r"[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]", re.sub(r"&#[0-9]+;", "", element))
    table = [line for line in markdown.splitlines() if line.startswith("| <code>")]
    assert len(table) == 1 and table[0].count("|") == 6, "one row, five cells"

    plain = audit.render([result], markdown=False)
    assert f"`{REPO + HOSTILE}`" in plain and f"declared but not enforced: {HOSTILE}" in plain


def test_a_note_without_a_markdown_form_is_encoded_whole():
    result = {"repo": REPO, "branch": BRANCH, "status": "drift", "notes": [f"raw {HOSTILE}"]}
    assert f"- {audit.md_code('raw ' + HOSTILE)}" in audit.render([result])
