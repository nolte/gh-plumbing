"""Tests for scripts/checkout_credentials.py.

The defect this guards against (#471) produces no error at all: a checkout
without `persist-credentials` works, and the job token simply stays readable by
every later step. So the load-bearing cases are the shapes that look fine -- a
checkout with other `with:` inputs but not this one, a `true` without a reason,
a reason that names no step, and the composite-action and job-less files the
selector must still reach.

One test runs the check against this repository itself, so the guard holds for
the real workflows too.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "checkout_credentials.py"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("checkout_credentials", MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(guard)

PIN = "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0"


def workflow(checkout_with: str = "", later: str = "      - name: Lint\n        run: true\n") -> str:
    return (
        "name: W\non:\n  pull_request:\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - name: Checkout\n        uses: {PIN}\n{checkout_with}{later}"
    )


def write(root: pathlib.Path, name: str, text: str) -> pathlib.Path:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def messages(root: pathlib.Path) -> list[str]:
    return [f["message"] for f in guard.audit(root)]


def test_explicit_false_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow("        with:\n          persist-credentials: false\n"))
    assert guard.audit(tmp_path) == []
    assert guard.main(["--root", str(tmp_path)]) == 0


def test_missing_key_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow())
    findings = guard.audit(tmp_path)
    assert len(findings) == 1
    assert findings[0]["job"] == "lint"
    assert findings[0]["line"] == 8  # the step, not the job
    assert "without an explicit" in findings[0]["message"]
    assert guard.main(["--root", str(tmp_path)]) == 1


def test_other_with_inputs_do_not_count_as_a_decision(tmp_path):
    write(tmp_path, "w.yaml", workflow("        with:\n          fetch-depth: 0\n"))
    assert len(messages(tmp_path)) == 1


def test_empty_with_block_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow("        with:\n"))
    assert len(messages(tmp_path)) == 1


def test_findings_are_printed_as_annotations(tmp_path, capsys):
    write(tmp_path, "w.yaml", workflow())
    assert guard.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("::error file=.github/workflows/w.yaml,line=8::job lint:")


def test_malformed_steps_are_skipped(tmp_path):
    write(tmp_path, "w.yaml", "on: push\njobs:\n  j:\n    steps: none\n")
    assert messages(tmp_path) == []


def test_quoted_false_string_is_clean(tmp_path):
    write(tmp_path, "w.yaml", workflow("        with:\n          persist-credentials: 'false'\n"))
    assert messages(tmp_path) == []


def test_true_without_comment_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow("        with:\n          persist-credentials: true\n"))
    found = messages(tmp_path)
    assert len(found) == 1
    assert "without a comment naming" in found[0]


def test_true_with_comment_naming_no_step_is_a_finding(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        "        with:\n          # Needed for pushing.\n          persist-credentials: true\n"))
    assert len(messages(tmp_path)) == 1


@pytest.mark.parametrize("with_block", [
    "        with:\n          # The \"Lint\" step pushes.\n          persist-credentials: true\n",
    "        with:\n          # The \"Lint\" step\n          # pushes.\n          persist-credentials: true\n",
    "        with:\n          persist-credentials: true # \"Lint\" pushes\n",
])
def test_true_with_comment_naming_a_later_step_is_clean(tmp_path, with_block):
    write(tmp_path, "w.yaml", workflow(with_block))
    assert messages(tmp_path) == []


def test_comment_naming_an_earlier_step_does_not_count(tmp_path):
    text = (
        "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - name: Mint token\n        run: true\n"
        f"      - uses: {PIN}\n        with:\n"
        "          # \"Mint token\" made the token.\n          persist-credentials: true\n"
    )
    write(tmp_path, "w.yaml", text)
    assert len(messages(tmp_path)) == 1


def test_comment_separated_by_a_key_line_does_not_count(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        "        with:\n          # The \"Lint\" step pushes.\n          fetch-depth: 0\n"
        "          persist-credentials: true\n"))
    assert len(messages(tmp_path)) == 1


def test_expression_value_needs_a_reason_like_true(tmp_path):
    write(tmp_path, "w.yaml", workflow(
        "        with:\n          persist-credentials: ${{ inputs.push }}\n"))
    assert len(messages(tmp_path)) == 1


def test_every_checkout_in_every_job_is_checked(tmp_path):
    text = (
        "on: push\njobs:\n"
        "  a:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - uses: {PIN}\n        with:\n          persist-credentials: false\n"
        "  b:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: true\n"
        f"      - uses: {PIN}\n"
        f"      - uses: {PIN}\n"
    )
    write(tmp_path, "w.yml", text)
    assert [f["job"] for f in guard.audit(tmp_path)] == ["b", "b"]


def test_other_actions_and_reusable_calls_are_ignored(tmp_path):
    text = (
        "on: push\njobs:\n"
        "  call:\n    uses: ./.github/workflows/other.yaml\n"
        "  j:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout-extra@v1\n"
        "      - uses: actions/setup-python@v6\n"
    )
    write(tmp_path, "w.yaml", text)
    assert messages(tmp_path) == []


def test_composite_action_is_checked(tmp_path):
    path = tmp_path / ".github" / "actions" / "setup" / "action.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "name: Setup\nruns:\n  using: composite\n  steps:\n"
        f"    - uses: {PIN}\n", encoding="utf-8")
    findings = guard.audit(tmp_path)
    assert [f["job"] for f in findings] == ["(composite)"]


def test_non_workflow_files_are_ignored(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "README.md").write_text(f"uses: {PIN}\n")
    write(tmp_path, "empty.yaml", "")
    assert guard.audit(tmp_path) == []


def test_this_repository_decides_every_checkout():
    files = guard.candidate_files(REPO_ROOT)
    # Guard against a vacuous pass: a moved workflow directory would scan nothing.
    assert any("checkout" in p.read_text(encoding="utf-8") for p in files)
    assert guard.audit(REPO_ROOT) == []


# --- its own output (#492) ---------------------------------------------------
#
# Job keys, `uses:` values and paths are repository text. Printed raw, a line
# break in one ends the annotation and starts a command of its own; a parser's
# traceback quotes the file. Both are escaped or withheld.


def test_a_hostile_job_key_stays_inside_its_annotation(tmp_path, capsys):
    text = workflow().replace("  lint:\n", '  "lint\\n::warning::injected ##[warning]x":\n')
    write(tmp_path, "w.yaml", text)
    assert guard.main(["--root", str(tmp_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("::error file=.github/workflows/w.yaml,line=8::job lint%0A::warning::injected")


def test_an_unparseable_file_is_one_finding_without_its_text(tmp_path, capsys):
    write(tmp_path, "w.yaml", "jobs: [\n  secret-line ::warning::from-yaml\n")
    (tmp_path / ".github" / "workflows" / "b.yaml").write_bytes(b"\xff\xfe broken")
    assert guard.main(["--root", str(tmp_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert all(line.startswith("::error file=.github/workflows/") and "could not be read or parsed" in line
               for line in lines)
    assert not any("secret-line" in line or "Traceback" in line for line in lines)


def test_a_hostile_path_is_escaped_and_the_success_line_neutralised(tmp_path, capsys):
    write(tmp_path, "x,line=1::y.yaml", workflow())
    assert guard.main(["--root", str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith("::error file=.github/workflows/x%2Cline=1%3A%3Ay.yaml,line=8::")
    root = tmp_path / "r##[warning]x"
    root.mkdir()
    assert guard.main(["--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "##[" not in out and "r#?[warning]x" in out
