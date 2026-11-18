"""Tests for scripts/builtin_action_cache.py (#494).

The defect this guards against produces no error at all: a setup-node step
without `package-manager-cache` works, and its post step quietly saves npm's
cache after the install and test commands ran. So the load-bearing cases are
the shapes that look fine -- a setup-node step with other inputs but not this
one, a cache input on an action that caches only when asked, and the
composite-action files the selector must still reach.

One test runs the check against this repository itself, so the guard holds for
the real workflows too.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "builtin_action_cache.py"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("builtin_action_cache", MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)

NODE = "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38 # v6.5.0"
PYTHON = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0"
TFLINT = "terraform-linters/setup-tflint@6e1e0642c0289bd619021bf6b34e3c08ed1e005a # v6.3.0"


def workflow(uses: str, with_block: str = "") -> str:
    return (
        "name: W\non:\n  push:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - uses: {uses}\n{with_block}"
        "      - name: Test\n        run: npm test\n"
    )


def write(root: pathlib.Path, name: str, text: str) -> pathlib.Path:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def messages(root: pathlib.Path) -> list[str]:
    return [f["message"] for f in guard.audit(root)]


# --- actions/setup-node ------------------------------------------------------

def test_setup_node_with_cache_off_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        NODE, "        with:\n          node-version: '24'\n          package-manager-cache: false\n"))
    assert guard.audit(tmp_path) == []
    assert guard.main(["--root", str(tmp_path)]) == 0


def test_setup_node_quoted_false_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        NODE, "        with:\n          package-manager-cache: 'false'\n"))
    assert messages(tmp_path) == []


def test_setup_node_without_the_key_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(NODE, "        with:\n          node-version: '24'\n"))
    findings = guard.audit(tmp_path)
    assert len(findings) == 1
    assert findings[0]["job"] == "test"
    assert findings[0]["line"] == 8  # the step, not the job
    assert "without `with.package-manager-cache: false`" in findings[0]["message"]
    assert guard.main(["--root", str(tmp_path)]) == 1


def test_setup_node_without_a_with_block_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(NODE))
    assert len(messages(tmp_path)) == 1


def test_setup_node_with_cache_true_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        NODE, "        with:\n          package-manager-cache: true\n"))
    findings = guard.audit(tmp_path)
    assert len(findings) == 1
    assert findings[0]["line"] == 10  # the key's line
    assert "not a literal `false`" in findings[0]["message"]


def test_setup_node_expression_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        NODE, "        with:\n          package-manager-cache: ${{ inputs.cache }}\n"))
    assert len(messages(tmp_path)) == 1


def test_setup_node_explicit_cache_input_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        NODE, "        with:\n          package-manager-cache: false\n          cache: npm\n"))
    found = messages(tmp_path)
    assert len(found) == 1
    assert "`with.cache: npm`" in found[0]


def test_setup_node_cache_without_the_off_switch_is_two_findings(tmp_path):
    write(tmp_path, "w.yaml", workflow(NODE, "        with:\n          cache: npm\n"))
    assert len(messages(tmp_path)) == 2


# --- actions/setup-python ----------------------------------------------------

def test_setup_python_without_cache_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow(PYTHON, "        with:\n          python-version: '3.14'\n"))
    assert messages(tmp_path) == []


def test_setup_python_without_a_with_block_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow(PYTHON))
    assert messages(tmp_path) == []


@pytest.mark.parametrize("value", ["pip", "''", "false"])
def test_setup_python_with_any_cache_input_is_a_finding(tmp_path, value):
    write(tmp_path, "w.yaml", workflow(PYTHON, f"        with:\n          cache: {value}\n"))
    found = messages(tmp_path)
    assert len(found) == 1
    assert "reusable-pre-commit.yaml" in found[0]


# --- terraform-linters/setup-tflint ------------------------------------------

def test_setup_tflint_default_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow(TFLINT, "        with:\n          tflint_version: v0.60.0\n"))
    assert messages(tmp_path) == []


def test_setup_tflint_cache_false_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow(TFLINT, "        with:\n          cache: false\n"))
    assert messages(tmp_path) == []


@pytest.mark.parametrize("value", ["true", "${{ inputs.cache }}"])
def test_setup_tflint_cache_on_is_a_finding(tmp_path, value):
    write(tmp_path, "w.yaml", workflow(TFLINT, f"        with:\n          cache: {value}\n"))
    assert len(messages(tmp_path)) == 1


# --- shapes the YAML node tree hides ----------------------------------------

def test_duplicate_key_with_a_later_true_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        NODE, "        with:\n          package-manager-cache: false\n"
              "          package-manager-cache: true\n"))
    findings = guard.audit(tmp_path)
    assert [f["line"] for f in findings] == [11]


def test_duplicate_with_block_is_checked_too(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        PYTHON, "        with:\n          python-version: '3.14'\n"
                "        with:\n          cache: pip\n"))
    assert len(messages(tmp_path)) == 1


def test_duplicate_uses_key_cannot_hide_the_action(tmp_path):
    write(tmp_path, "w.yaml", workflow(f"{NODE}\n        uses: actions/checkout@v6"))
    assert len(messages(tmp_path)) == 1


def test_merge_key_in_with_is_a_finding(tmp_path):
    text = (
        "x-cache: &c\n  cache: pip\n"
        "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: {PYTHON}\n        with:\n          <<: *c\n"
    )
    write(tmp_path, "w.yaml", text)
    found = messages(tmp_path)
    assert len(found) == 1
    assert "merge key" in found[0] and "`with:`" in found[0]


def test_merge_key_on_the_step_is_a_finding(tmp_path):
    text = (
        "x-step: &s\n  with:\n    cache: pip\n"
        "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: {PYTHON}\n        <<: *s\n"
    )
    write(tmp_path, "w.yaml", text)
    found = messages(tmp_path)
    assert len(found) == 1
    assert "merge key" in found[0] and "the step" in found[0]


# --- output -------------------------------------------------------------------

def test_hostile_job_key_and_value_cannot_inject_workflow_commands(tmp_path, capsys):
    text = (
        "on: push\njobs:\n"
        '  "x\\n::warning::injected-from-job-name\\r\\n::add-mask::foo %0A":\n'
        "    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: {PYTHON}\n        with:\n"
        "          cache: |\n            pip\n"
        "            ::error file=README.md,line=1::injected-from-value\n"
        "            ::add-mask::foo\n"
    )
    write(tmp_path, "w.yaml", text)
    findings = guard.audit(tmp_path)
    assert len(findings) == 1
    assert guard.main(["--root", str(tmp_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if line.startswith("::")] == lines
    assert len(lines) == len(findings)
    assert all(line.startswith("::error file=") for line in lines)
    assert "%0A::warning::" in lines[0]
    assert "%250A" in lines[0]  # a literal `%` is escaped, not passed through


def test_escape_property_covers_separators():
    assert guard.escape_property("a:b,c%d\ne") == "a%3Ab%2Cc%25d%0Ae"


def test_long_values_are_shortened(tmp_path):
    write(tmp_path, "w.yaml", workflow(PYTHON, "        with:\n          cache: " + "p" * 500 + "\n"))
    found = messages(tmp_path)
    assert "p" * guard.ECHO_LIMIT + "..." in found[0]
    assert "p" * (guard.ECHO_LIMIT + 1) not in found[0]


# --- selector and file discovery ---------------------------------------------

def test_findings_are_printed_as_annotations(tmp_path, capsys):
    write(tmp_path, "w.yaml", workflow(NODE))
    assert guard.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("::error file=.github/workflows/w.yaml,line=8::job test:")


def test_non_matching_actions_and_reusable_calls_are_ignored(tmp_path):
    text = (
        "on: push\njobs:\n"
        "  call:\n    uses: ./.github/workflows/other.yaml\n"
        "  j:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/setup-node-extra@v1\n"
        "      - uses: actions/setup-go@v6\n        with:\n          cache: true\n"
        "      - uses: actions/setup-node\n"
        "      - run: true\n"
    )
    write(tmp_path, "w.yaml", text)
    assert messages(tmp_path) == []


@pytest.mark.parametrize("uses, with_block", [
    ("actions/setup-node/@v6", ""),
    ("actions//setup-python@v6", "        with:\n          cache: pip\n"),
    ("'actions\\setup-node@v6'", ""),
])
def test_selector_resolves_uses_like_the_runner(tmp_path, uses, with_block):
    # The runner splits the repository part on `/` and `\` and drops empty
    # segments, so each of these names the guarded action.
    write(tmp_path, "w.yaml", workflow(uses, with_block))
    assert len(messages(tmp_path)) == 1


def test_selector_is_case_insensitive(tmp_path):
    write(tmp_path, "w.yaml", workflow("Actions/Setup-Node@v6"))
    assert len(messages(tmp_path)) == 1


def test_every_step_in_every_job_is_checked(tmp_path):
    text = (
        "on: push\njobs:\n"
        "  a:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: {NODE}\n        with:\n          package-manager-cache: false\n"
        "  b:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: {NODE}\n"
        f"      - uses: {PYTHON}\n        with:\n          cache: pip\n"
    )
    write(tmp_path, "w.yml", text)
    assert [f["job"] for f in guard.audit(tmp_path)] == ["b", "b"]


@pytest.mark.parametrize("directory", [".github/actions/setup", "actions/setup"])
def test_composite_action_is_checked(tmp_path, directory):
    path = tmp_path / directory / "action.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "name: Setup\nruns:\n  using: composite\n  steps:\n"
        f"    - uses: {NODE}\n", encoding="utf-8")
    findings = guard.audit(tmp_path)
    assert [f["job"] for f in findings] == ["(composite)"]


def test_malformed_and_non_workflow_files_are_ignored(tmp_path):
    write(tmp_path, "steps.yaml", "on: push\njobs:\n  j:\n    steps: none\n")
    write(tmp_path, "empty.yaml", "")
    write(tmp_path, "scalar-step.yaml", "on: push\njobs:\n  j:\n    steps:\n      - just text\n")
    (tmp_path / ".github" / "workflows" / "README.md").write_text(f"uses: {NODE}\n")
    assert guard.audit(tmp_path) == []


def test_clean_run_names_the_actions_it_checked(tmp_path, capsys):
    assert guard.main(["--root", str(tmp_path)]) == 0
    assert "actions/setup-node" in capsys.readouterr().out


def test_this_repository_turns_off_every_builtin_cache():
    files = guard.candidate_files(REPO_ROOT)
    # Guard against a vacuous pass: a moved workflow directory would scan nothing.
    assert any("actions/setup-node@" in p.read_text(encoding="utf-8") for p in files)
    assert guard.audit(REPO_ROOT) == []
