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
    assert "no-producer" in summary.read_text(encoding="utf-8")


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
