"""Tests for scripts/required_check_triggers.py.

The defect this guards against (#462) is silent: a required context whose
workflow never runs on a fork pull request produces no error and no failed
check, only a pull request that stays blocked. So the load-bearing cases are
the shapes that look fine on a same-repository branch -- a push-only producer,
a `pull_request_target` producer, a context whose job was renamed away, a
producer that needs a write token a fork never gets.

Each test builds a repository under `tmp_path`; one test runs the check against
this repository itself, so the guard holds for the real declaration too.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "required_check_triggers.py"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("required_check_triggers", MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)

SETTINGS = """branches:
  - name: develop
    protection:
      required_status_checks:
        strict: true
        contexts:
          - static / Static CI Tests
"""

REUSABLE = """name: Reusable
on:
  workflow_call:
jobs:
  static:
    name: Static CI Tests
    runs-on: ubuntu-latest
    steps:
      - run: true
"""

CALLER = """name: Caller
{on}
permissions:
  contents: read
jobs:
  static:
{permissions}    uses: ./.github/workflows/reusable-static.yaml
"""


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def caller(on: str = "on:\n  pull_request:\n  push:", permissions: str = "") -> str:
    return CALLER.format(on=on, permissions=permissions)


@pytest.fixture
def repo(tmp_path):
    """A healthy repository: one required context, produced on pull requests, read-only."""
    write(tmp_path / ".github" / "settings.yml", SETTINGS)
    write(tmp_path / ".github" / "workflows" / "reusable-static.yaml", REUSABLE)
    write(tmp_path / ".github" / "workflows" / "build.yaml", caller())
    return tmp_path


def kinds(root: pathlib.Path) -> list[str]:
    return [f["kind"] for f in guard.audit(root)]


def test_clean_repository_has_no_findings(repo):
    assert guard.audit(repo) == []
    assert guard.main(["--root", str(repo)]) == 0


def test_push_only_producer_is_a_finding(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  push:\n    branches: [develop]"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["trigger"]
    assert "doesn't trigger on `pull_request`" in findings[0]["message"]
    assert findings[0]["context"] == "static / Static CI Tests"
    assert guard.main(["--root", str(repo)]) == 1


def test_pull_request_target_does_not_count(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  pull_request_target:"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["trigger"]
    assert "`pull_request_target` only" in findings[0]["message"]


def test_context_without_producer_is_a_finding(repo):
    (repo / ".github" / "workflows" / "build.yaml").unlink()
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["no-producer"]
    assert "can never report" in findings[0]["message"]


def test_renamed_reusable_job_orphans_the_context(repo):
    write(repo / ".github" / "workflows" / "reusable-static.yaml",
          REUSABLE.replace("Static CI Tests", "Static Checks"))
    assert kinds(repo) == ["no-producer"]


def test_reusable_only_file_is_not_a_producer(repo):
    # A reusable carrying a job with the caller's id reports nothing by itself.
    (repo / ".github" / "workflows" / "build.yaml").unlink()
    write(repo / ".github" / "workflows" / "reusable-caller.yaml",
          caller(on="on:\n  workflow_call:"))
    assert kinds(repo) == ["no-producer"]


def test_write_scope_on_producing_job_is_a_finding(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(permissions="    permissions:\n      contents: read\n"
                             "      pull-requests: write\n"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["write-permission"]
    assert "`pull-requests`" in findings[0]["message"]


def test_workflow_level_write_applies_when_job_has_no_block(repo):
    text = caller().replace("permissions:\n  contents: read", "permissions: write-all")
    write(repo / ".github" / "workflows" / "build.yaml", text)
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["write-permission"]
    assert "`write-all`" in findings[0]["message"]


def test_job_block_replaces_workflow_level_write(repo):
    text = caller(permissions="    permissions:\n      contents: read\n").replace(
        "permissions:\n  contents: read\njobs", "permissions: write-all\njobs")
    write(repo / ".github" / "workflows" / "build.yaml", text)
    assert kinds(repo) == []


def test_bare_on_parsed_as_true_is_read(repo):
    # PyYAML (YAML 1.1) turns the bare key `on` into the boolean True.
    workflow = guard.yaml.safe_load(caller())
    assert True in workflow and "on" not in workflow
    assert "pull_request" in guard.triggers(workflow)
    assert guard.audit(repo) == []


def test_quoted_on_key_is_read(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on='"on":\n  push:'))
    assert kinds(repo) == ["trigger"]


@pytest.mark.parametrize("on, ok", [
    ("on: pull_request", True),
    ("on: [push, pull_request]", True),
    ("on: push", False),
    ("on: [push, pull_request_target]", False),
])
def test_trigger_forms_string_list_mapping(repo, on, ok):
    write(repo / ".github" / "workflows" / "build.yaml", caller(on=on))
    assert (kinds(repo) == []) is ok


@pytest.mark.parametrize("config, fragment", [
    ("paths: ['docs/**']", "`paths`"),
    ("paths-ignore: ['docs/**']", "`paths-ignore`"),
    ("branches: [master]", "`branches` that exclude `develop`"),
    ("branches-ignore: ['dev*']", "`branches-ignore` that matches `develop`"),
    ("types: [opened, edited]", "`synchronize`"),
])
def test_narrowed_pull_request_trigger_is_a_finding(repo, config, fragment):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on=f"on:\n  pull_request:\n    {config}"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["trigger"]
    assert fragment in findings[0]["message"]


def test_matching_branches_and_full_types_pass(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  pull_request:\n    branches: ['dev*']\n"
                    "    types: [opened, edited, synchronize]"))
    assert kinds(repo) == []


def test_every_branch_and_every_producer_is_checked(repo):
    write(repo / ".github" / "settings.yml", SETTINGS + """  - name: master
    protection:
      required_status_checks:
        contexts:
          - lint
""")
    write(repo / ".github" / "workflows" / "lint.yaml",
          "on: push\npermissions: read-all\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n")
    write(repo / ".github" / "workflows" / "second.yaml",
          caller(on="on:\n  schedule:\n    - cron: '0 0 * * *'"))
    findings = guard.audit(repo)
    assert sorted((f["context"], f["kind"]) for f in findings) == [
        ("lint", "trigger"),
        ("static / Static CI Tests", "trigger"),
    ]


def test_remote_reusable_is_matched_by_job_id(repo):
    text = caller().replace("./.github/workflows/reusable-static.yaml",
                            "owner/repo/.github/workflows/reusable-static.yaml@v1")
    write(repo / ".github" / "workflows" / "build.yaml", text)
    assert kinds(repo) == []


def test_missing_settings_reports_nothing(tmp_path):
    assert guard.audit(tmp_path) == []


def test_findings_are_rendered_and_summarised(repo, monkeypatch, tmp_path_factory, capsys):
    summary = tmp_path_factory.mktemp("summary") / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    (repo / ".github" / "workflows" / "build.yaml").unlink()
    assert guard.main(["--root", str(repo)]) == 1
    captured = capsys.readouterr()
    assert "static / Static CI Tests" in captured.out
    assert "::error::1 required-check trigger finding(s)" in captured.err
    # The summary is Markdown: context, kind and message encoded and wrapped (#506).
    written = summary.read_text(encoding="utf-8")
    assert "<code>no&#45;producer</code>" in written
    assert "<code>static &#47; Static CI Tests</code>" in written
    assert "static / Static CI Tests" not in written


@pytest.mark.parametrize("branches, selected", [
    (["**", "!develop"], False),      # a later negation wins over the match-all
    (["!develop", "**"], True),       # ...and a later match wins over the negation
    (["release*"], False),
    (["release/*"], False),
    (["dev*"], True),
    (["*"], True),
])
def test_branch_filter_semantics_for_develop(branches, selected):
    assert guard.branch_selected("develop", branches) is selected


@pytest.mark.parametrize("pattern, branch, selected", [
    ("release*", "release/1", False),   # `*` doesn't cross `/`
    ("release/*", "release/1", True),
    ("release/**", "release/1/hotfix", True),
    ("release/*", "release/1/hotfix", False),
    ("v?1", "v1", True),                # `?`: zero or one of the preceding char
    ("v?1", "1", True),
    ("re+lease", "reeelease", True),
    ("[dm]aster", "master", True),
    ("feature\\*", "feature*", True),
    ("feature\\*", "featurex", False),
])
def test_branch_filter_pattern_characters(pattern, branch, selected):
    assert guard.branch_selected(branch, [pattern]) is selected


def test_negated_branch_filter_on_trigger_is_a_finding(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  pull_request:\n    branches: ['**', '!develop']"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["trigger"]
    assert "`branches` that exclude `develop`" in findings[0]["message"]


def test_job_condition_is_a_finding(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(permissions="    if: github.event_name == 'push'\n"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["job-condition"]
    assert "github.event_name == 'push'" in findings[0]["message"]


def test_no_permissions_anywhere_is_a_finding(repo):
    text = caller().replace("permissions:\n  contents: read\n", "")
    write(repo / ".github" / "workflows" / "build.yaml", text)
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["no-permissions"]
    assert "repository default" in findings[0]["message"]


def test_job_permissions_alone_satisfy_the_declaration(repo):
    text = caller(permissions="    permissions:\n      contents: read\n").replace(
        "permissions:\n  contents: read\njobs", "jobs")
    write(repo / ".github" / "workflows" / "build.yaml", text)
    assert kinds(repo) == []


def test_context_required_on_several_branches_is_reported_once(repo):
    write(repo / ".github" / "settings.yml", SETTINGS + """  - name: master
    protection:
      required_status_checks:
        contexts:
          - static / Static CI Tests
""")
    write(repo / ".github" / "workflows" / "build.yaml", caller(on="on: push"))
    findings = guard.audit(repo)
    assert [(f["context"], f["kind"]) for f in findings] == [
        ("static / Static CI Tests", "trigger"),
    ]


def test_distinct_problems_of_one_kind_are_joined(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  pull_request:\n    paths: ['a/**']\n    types: [opened]"))
    findings = guard.audit(repo)
    assert len(findings) == 1
    assert "`paths`" in findings[0]["message"] and "`synchronize`" in findings[0]["message"]


COMMONS = """branches:
  - name: develop
    protection:
      required_status_checks:
        contexts: []
  - name: master
    protection:
      required_status_checks:
        contexts:
          - static / Static CI Tests
"""


def test_commons_contexts_apply_when_settings_extend_them(repo):
    write(repo / ".github" / "settings.yml", "_extends: x:.github/commons-settings.yml\n")
    write(repo / ".github" / "commons-settings.yml", COMMONS)
    assert guard.required_contexts(
        guard.load_yaml(repo / ".github" / "settings.yml"),
        guard.load_yaml(repo / ".github" / "commons-settings.yml"),
    ) == [("master", "static / Static CI Tests")]
    write(repo / ".github" / "workflows" / "build.yaml", caller(on="on: push"))
    assert kinds(repo) == ["trigger"]


def test_commons_are_ignored_without_extends(repo):
    write(repo / ".github" / "settings.yml", "branches: []\n")
    write(repo / ".github" / "commons-settings.yml", COMMONS)
    write(repo / ".github" / "workflows" / "build.yaml", caller(on="on: push"))
    assert kinds(repo) == []


def test_own_entry_overrides_commons_entry_of_the_same_name(repo):
    write(repo / ".github" / "settings.yml", "_extends: x:y\n" + SETTINGS.replace(
        "develop", "master").replace("static / Static CI Tests", "other / Other"))
    write(repo / ".github" / "commons-settings.yml", COMMONS)
    contexts = guard.required_contexts(
        guard.load_yaml(repo / ".github" / "settings.yml"),
        guard.load_yaml(repo / ".github" / "commons-settings.yml"),
    )
    assert contexts == [("master", "other / Other")]


MATRIX_REUSABLE = """on:
  workflow_call:
jobs:
  coverage:
    name: Python Coverage
    strategy:
      matrix:
        python: ["3.13", "3.14"]
    runs-on: ubuntu-latest
    steps:
      - run: true
"""


def test_matrix_leg_of_reusable_job_is_produced(repo):
    write(repo / ".github" / "settings.yml",
          SETTINGS.replace("static / Static CI Tests", "static / Python Coverage (3.14)"))
    write(repo / ".github" / "workflows" / "reusable-static.yaml", MATRIX_REUSABLE)
    assert kinds(repo) == []


def test_matrix_leg_needs_a_matrix(repo):
    write(repo / ".github" / "settings.yml",
          SETTINGS.replace("static / Static CI Tests", "static / Static CI Tests (3.14)"))
    assert kinds(repo) == ["no-producer"]


def test_plain_matrix_job_context_is_produced(repo):
    write(repo / ".github" / "settings.yml",
          SETTINGS.replace("static / Static CI Tests", "lint (3.14)"))
    write(repo / ".github" / "workflows" / "lint.yaml", """on: pull_request
permissions:
  contents: read
jobs:
  lint:
    strategy:
      matrix:
        python: ["3.14"]
    runs-on: ubuntu-latest
    steps:
      - run: true
""")
    assert kinds(repo) == []


def test_expression_in_job_name_matches_by_prefix(repo):
    write(repo / ".github" / "settings.yml",
          SETTINGS.replace("static / Static CI Tests", "static / Static CI Tests on ubuntu"))
    write(repo / ".github" / "workflows" / "reusable-static.yaml",
          REUSABLE.replace("name: Static CI Tests",
                           "name: Static CI Tests on ${{ inputs.os }}"))
    assert kinds(repo) == []
    write(repo / ".github" / "settings.yml",
          SETTINGS.replace("static / Static CI Tests", "static / Lint on ubuntu"))
    assert kinds(repo) == ["no-producer"]


def test_name_starting_with_expression_does_not_match_everything(repo):
    # "" is a prefix of every context; such a job must not mask an orphan.
    write(repo / ".github" / "workflows" / "reusable-static.yaml",
          REUSABLE.replace("name: Static CI Tests", "name: ${{ inputs.label }} checks"))
    assert kinds(repo) == ["no-producer"]
    # The job id is the fallback, so a context naming it is still produced.
    write(repo / ".github" / "settings.yml",
          SETTINGS.replace("static / Static CI Tests", "static / static"))
    assert kinds(repo) == []


@pytest.mark.parametrize("pattern, branch, selected", [
    ("+foo", "+foo", True),          # nothing to quantify: a literal `+`
    ("?foo", "?foo", True),
    ("?foo", "foo", False),
    ("*?", "a?", True),              # after a wildcard: literal as well
    ("a++", "a+", True),             # a quantifier can't be quantified
    ("[z-a]", "a", False),           # rejected by `re`: matches nothing
])
def test_pattern_without_quantifiable_atom_never_raises(pattern, branch, selected):
    assert guard.branch_selected(branch, [pattern]) is selected


def test_malformed_branch_filter_does_not_crash_the_audit(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  pull_request:\n    branches: ['+foo', '[z-a]']"))
    assert kinds(repo) == ["trigger"]


def test_this_repository_has_no_findings():
    contexts = guard.required_contexts(
        guard.load_yaml(REPO_ROOT / ".github" / "settings.yml"),
        guard.load_yaml(REPO_ROOT / ".github" / "commons-settings.yml"),
    )
    # Guard against a vacuous pass: a moved settings file would yield no contexts.
    assert contexts
    assert guard.audit(REPO_ROOT) == []


def test_this_repository_branch_entries_apply_and_do_not_race():
    """#442: every own branch entry is a complete payload, and none shares a
    name with a commons entry, so neither merge behaviour of the Settings App
    can drop or race it."""
    settings = guard.load_yaml(REPO_ROOT / ".github" / "settings.yml")
    commons = guard.load_yaml(REPO_ROOT / ".github" / "commons-settings.yml")
    names = [e["name"] for e in settings.get("branches") or []]
    assert names  # not vacuous
    for name in names:
        assert guard.branch_protection_audit.entry_findings(settings, commons, name) == []


def push_restricted_commons_entries(commons) -> list[str]:
    """Names of commons branch entries that carry a push restriction.

    GitHub accepts `restrictions` only on organisation-owned repositories, and
    every consumer is user-owned, so such an entry fails its whole update with
    422 and applies nothing -- the `develop` entry until #442, the `master`
    entry until #481.
    """
    if not isinstance(commons, dict):
        return []
    return [
        entry.get("name")
        for entry in commons.get("branches") or []
        if isinstance(entry, dict)
        and (entry.get("protection") or {}).get("restrictions") is not None
    ]


def test_push_restricted_commons_entry_is_detected():
    commons = {"branches": [
        {"name": "master", "protection": {
            "required_pull_request_reviews": None,
            "required_status_checks": None,
            "enforce_admins": True,
            "restrictions": {"users": [], "teams": [], "apps": ["nolte-portfolio-app"]},
        }},
        {"name": "develop", "protection": {"restrictions": None}},
    ]}
    assert push_restricted_commons_entries(commons) == ["master"]
    assert push_restricted_commons_entries({}) == []
    assert push_restricted_commons_entries({"branches": []}) == []


def test_commons_carry_no_push_restricted_branch_entry():
    """#481: a commons branch entry with `restrictions` applies nothing on a
    user-owned consumer, and every consumer is user-owned (ADR-006)."""
    path = REPO_ROOT / ".github" / "commons-settings.yml"
    assert path.is_file()  # not vacuous: a moved file would pass silently
    assert push_restricted_commons_entries(guard.load_yaml(path)) == []


# --- Status producers (#465) ---------------------------------------------
#
# A guard that must not be rewritable by a fork runs under
# `pull_request_target`, which the rule above refuses for every other
# producer, and reports a commit status, which a fork can't write. The
# exemption is by context name, and the named workflow is held to the mirror
# rule: `pull_request_target` without `pull_request`, no checkout, a step that
# posts the status, and no write scope but `statuses`.

GUARD_PATH = ".github/workflows/fork-guard.yaml"

GUARD_SETTINGS = SETTINGS.replace("static / Static CI Tests", "fork-guard")

POST_STEP = """      - run: |
          gh api -X POST "repos/${GITHUB_REPOSITORY}/statuses/${HEAD_SHA}" \\
            -f state=success -f context=fork-guard
"""

GUARD_REUSABLE = """on:
  workflow_call:
permissions:
  contents: read
jobs:
  fork-guard:
    name: Protected Paths
    runs-on: ubuntu-latest
    permissions:
      contents: read
      statuses: write
    steps:
{steps}"""

GUARD_CALLER = """{on}
permissions:
  contents: read
jobs:
  fork-guard:
    permissions:
      contents: read
      statuses: write
    uses: ./.github/workflows/reusable-fork-guard.yaml
{extra}"""

CHECKOUT_STEP = ("      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803\n"
                 "        with:\n          persist-credentials: false\n")


@pytest.fixture
def guard_repo(tmp_path):
    """A healthy status producer: `pull_request_target`, no checkout, posts the status."""
    write(tmp_path / ".github" / "settings.yml", GUARD_SETTINGS)
    write(tmp_path / ".github" / "workflows" / "reusable-fork-guard.yaml",
          GUARD_REUSABLE.format(steps=POST_STEP))
    write(tmp_path / GUARD_PATH, guard_caller())
    return tmp_path


def guard_caller(on: str = "on:\n  pull_request_target:\n    types: [opened, synchronize, reopened]",
                 extra: str = "") -> str:
    return GUARD_CALLER.format(on=on, extra=extra)


def test_status_producer_on_pull_request_target_passes(guard_repo):
    assert guard.audit(guard_repo) == []


def test_status_context_is_not_matched_by_a_check_run_name(guard_repo, monkeypatch):
    # Without the exemption the plain context `fork-guard` would need a plain
    # job of that name -- the shape a fork could add itself.
    monkeypatch.setattr(guard, "STATUS_PRODUCERS", {})
    assert kinds(guard_repo) == ["no-producer"]


def test_missing_status_workflow_is_a_finding(guard_repo):
    (guard_repo / GUARD_PATH).unlink()
    findings = guard.audit(guard_repo)
    assert [f["kind"] for f in findings] == ["no-producer"]
    assert "doesn't exist" in findings[0]["message"]


@pytest.mark.parametrize("steps", [
    "      - run: true\n",
    POST_STEP.replace("context=fork-guard", "context=fork-guard-2"),
    POST_STEP.replace("/statuses/", "/check-runs/"),
])
def test_status_must_actually_be_posted(guard_repo, steps):
    write(guard_repo / ".github" / "workflows" / "reusable-fork-guard.yaml",
          GUARD_REUSABLE.format(steps=steps))
    findings = guard.audit(guard_repo)
    assert [f["kind"] for f in findings] == ["no-producer"]
    assert "no `run:` step" in findings[0]["message"]


def test_unlisted_pull_request_target_producer_is_still_refused(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(on="on:\n  pull_request_target:"))
    findings = guard.audit(repo)
    assert [f["kind"] for f in findings] == ["trigger"]
    assert "`pull_request_target` only" in findings[0]["message"]


@pytest.mark.parametrize("on, fragment", [
    ("on:\n  pull_request:\n  pull_request_target:", "also triggers on `pull_request`"),
    ("on: [pull_request, pull_request_target]", "also triggers on `pull_request`"),
    ("on: pull_request", "doesn't trigger on `pull_request_target`"),
    ("on: push", "doesn't trigger on `pull_request_target`"),
    ("on:\n  pull_request_target:\n    types: [opened]", "`pull_request_target` `types` without `synchronize`"),
    ("on:\n  pull_request_target:\n    paths: ['.github/**']", "filters `pull_request_target` by `paths`"),
    ("on:\n  pull_request_target:\n    branches: [master]", "`branches` that exclude `develop`"),
])
def test_status_producer_trigger_problems(guard_repo, on, fragment):
    write(guard_repo / GUARD_PATH, guard_caller(on=on))
    findings = guard.audit(guard_repo)
    assert [f["kind"] for f in findings] == ["trigger"]
    assert fragment in findings[0]["message"]


def test_checkout_in_called_reusable_is_a_finding(guard_repo):
    write(guard_repo / ".github" / "workflows" / "reusable-fork-guard.yaml",
          GUARD_REUSABLE.format(steps=CHECKOUT_STEP + POST_STEP))
    findings = guard.audit(guard_repo)
    assert [f["kind"] for f in findings] == ["checkout"]
    assert "`.github/workflows/reusable-fork-guard.yaml` job `fork-guard`" in findings[0]["message"]


def test_checkout_in_another_job_of_the_workflow_is_a_finding(guard_repo):
    # Every job of a `pull_request_target` workflow runs with the base token,
    # not only the one that posts the status.
    write(guard_repo / GUARD_PATH, guard_caller(extra=(
        "  other:\n    runs-on: ubuntu-latest\n    steps:\n" + CHECKOUT_STEP)))
    findings = guard.audit(guard_repo)
    assert [f["kind"] for f in findings] == ["checkout"]
    assert "job `other`" in findings[0]["message"]


def test_self_calling_reusable_does_not_recurse_forever(guard_repo):
    write(guard_repo / ".github" / "workflows" / "reusable-fork-guard.yaml",
          GUARD_REUSABLE.format(steps=POST_STEP)
          + "  again:\n    uses: ./.github/workflows/reusable-fork-guard.yaml\n")
    assert guard.audit(guard_repo) == []


def test_status_producer_keeps_the_other_rules(guard_repo):
    # `statuses: write` is the one scope it may hold; any other write, and a
    # job condition, are refused as for every producer.
    write(guard_repo / GUARD_PATH, guard_caller().replace(
        "      statuses: write\n    uses",
        "      statuses: write\n      pull-requests: write\n"
        "    if: github.event.pull_request.head.repo.fork\n    uses"))
    findings = guard.audit(guard_repo)
    assert sorted(f["kind"] for f in findings) == ["job-condition", "write-permission"]
    assert "`statuses`" not in next(
        f["message"] for f in findings if f["kind"] == "write-permission")


def test_status_scope_is_still_refused_for_check_run_producers(repo):
    write(repo / ".github" / "workflows" / "build.yaml",
          caller(permissions="    permissions:\n      contents: read\n"
                             "      statuses: write\n"))
    assert kinds(repo) == ["write-permission"]


def test_status_exemptions_name_existing_workflows():
    # A stale entry would silently exempt whatever later takes that path.
    for name in guard.STATUS_PRODUCERS.values():
        assert (REPO_ROOT / name).is_file(), name


def test_this_repository_requires_the_fork_guard_on_develop():
    contexts = guard.required_contexts(
        guard.load_yaml(REPO_ROOT / ".github" / "settings.yml"),
        guard.load_yaml(REPO_ROOT / ".github" / "commons-settings.yml"),
    )
    assert ("develop", "fork-guard") in contexts
