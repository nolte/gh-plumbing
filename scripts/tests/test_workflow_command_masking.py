"""Tests for scripts/workflow_command_masking.py (#492).

The defect this guards against produces no error: a value with a line break
followed by `::warning::...` simply becomes a command of its own, and a
`name=$value` line gains a second entry. So the load-bearing cases are the
shapes that look fine -- a message that reads a variable assigned three lines
up, a `{ ...; } >> "$GITHUB_OUTPUT"` group, a Python f-string in a heredoc, a
check that sits after the print rather than before it, an allow-list entry
whose check was deleted.

Each synthetic case builds a repository under `tmp_path`. One test runs the
guard against this repository itself, and two run it against this
repository's files with one repair undone, so the guard holds for the real
workflows and would see the regression.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "workflow_command_masking.py"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("workflow_command_masking", MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# Registered first: @dataclass resolves its module through sys.modules.
sys.modules[_spec.name] = guard
_spec.loader.exec_module(guard)

PUBLISH = ".github/workflows/reusable-release-publish.yml"


def workflow(run: str, env: str = "          VALUE: ${{ inputs.value }}\n", name: str = "Step") -> str:
    body = "".join(f"          {line}\n" if line else "\n" for line in run.split("\n"))
    return (
        "name: W\non:\n  workflow_call:\njobs:\n  job:\n    runs-on: ubuntu-latest\n    steps:\n"
        f"      - name: {name}\n        env:\n{env}        run: |\n{body}"
    )


def write(root: pathlib.Path, rel: str, text: str) -> pathlib.Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def names(root: pathlib.Path, entries=()) -> list[tuple[int, str]]:
    findings, _ = guard.audit(root, tuple(entries))
    return [(f["line"], f["message"].split("`")[1]) for f in findings]


def check(tmp_path: pathlib.Path, run: str, **kwargs) -> list[str]:
    write(tmp_path, ".github/workflows/reusable-w.yaml", workflow(run, **kwargs))
    return [name for _, name in names(tmp_path)]


# --- what counts as a sink -------------------------------------------------


@pytest.mark.parametrize("line", [
    'echo "::error::bad $VALUE"',
    'echo "::warning title=x::${VALUE}"',
    "echo '::notice::'\"$VALUE\"",
    'echo "value=$VALUE" >> "$GITHUB_OUTPUT"',
    'echo "V=$VALUE" >> $GITHUB_ENV',
    'printf \'%s\\n\' "$VALUE" >> "${GITHUB_PATH}"',
    'echo "s=$VALUE" | tee -a "$GITHUB_STATE"',
    'echo "::error::$VALUE" >&2',
])
def test_a_raw_input_in_a_sink_is_a_finding(tmp_path, line):
    assert check(tmp_path, line) == ["VALUE"]


@pytest.mark.parametrize("line", [
    'echo "plain $VALUE"',
    'echo "x=$VALUE" >> "$GITHUB_STEP_SUMMARY"',
    "echo '::error::$VALUE'",
    '# echo "::error::$VALUE"',
    'echo "::error::${{ inputs.value }}"',
    'echo "::error::no value"',
])
def test_lines_outside_the_class_are_ignored(tmp_path, line):
    assert check(tmp_path, line) == []


def test_a_group_write_counts_line_by_line(tmp_path):
    run = '{\n  echo "a=fixed"\n  echo "b=$VALUE"\n} >> "$GITHUB_OUTPUT"'
    write(tmp_path, ".github/workflows/reusable-w.yaml", workflow(run))
    [(line, name)] = names(tmp_path)
    assert name == "VALUE"
    text = (tmp_path / ".github/workflows/reusable-w.yaml").read_text().splitlines()
    assert 'echo "b=$VALUE"' in text[line - 1], "the finding names the physical line"


def test_a_continued_line_is_one_sink(tmp_path):
    assert check(tmp_path, 'echo "::error::first" \\\n     "then $VALUE" >&2') == ["VALUE"]


# --- what counts as masked or constrained ------------------------------------


def test_masked_at_the_print(tmp_path):
    assert check(tmp_path, 'echo "::error::${VALUE//[[:cntrl:]]/?}"') == []


def test_masked_by_the_last_assignment(tmp_path):
    assert check(tmp_path, 'shown="${VALUE//[[:cntrl:]]/?}"\necho "::error::$shown"') == []


def test_reassigned_raw_after_the_mask(tmp_path):
    run = 'shown="${VALUE//[[:cntrl:]]/?}"\nshown="$VALUE"\necho "::error::$shown"'
    assert check(tmp_path, run) == ["shown"]


REFUSAL = 'if [[ "$VALUE" == *[[:cntrl:]]* ]]; then\n  echo "::error::${VALUE//[[:cntrl:]]/?}"\n  exit 1\nfi'


def test_refused_before_the_print(tmp_path):
    assert check(tmp_path, f'{REFUSAL}\necho "v=$VALUE" >> "$GITHUB_OUTPUT"') == []


def test_a_print_before_the_refusal_is_still_a_finding(tmp_path):
    assert check(tmp_path, f'echo "::notice::$VALUE"\n{REFUSAL}') == ["VALUE"]


def test_a_refusal_that_does_not_exit_proves_nothing(tmp_path):
    run = 'if [[ "$VALUE" == *[[:cntrl:]]* ]]; then\n  echo "odd"\nfi\necho "::notice::$VALUE"'
    assert check(tmp_path, run) == ["VALUE"]


def test_a_refused_value_reassigned_later_is_a_finding(tmp_path):
    assert check(tmp_path, f'{REFUSAL}\nVALUE=$(cat x)\necho "::notice::$VALUE"') == ["VALUE"]


def test_constants_and_numbers_are_clean(tmp_path):
    run = ('mode=merge\nif true; then mode="reset"; fi\nmsg="mode $mode"\n'
           'echo "mode=$mode" >> "$GITHUB_OUTPUT"\necho "::notice::$msg ${#VALUE}"\n'
           'echo "::notice::$FIXED"')
    assert check(tmp_path, run, env="          FIXED: release-cd.yml\n") == []


def test_a_message_built_from_a_raw_value_is_a_finding(tmp_path):
    assert check(tmp_path, 'msg="cannot use $VALUE"\necho "::error::$msg"') == ["msg"]


def test_command_output_is_not_a_constant(tmp_path):
    assert check(tmp_path, 'state=$(gh api x)\necho "::error::$state"') == ["state"]


def test_loop_and_read_variables_are_not_constants(tmp_path):
    run = ('for x in a b; do\n  echo "::error::$x"\ndone\n'
           'while IFS= read -r y; do\n  echo "::error::$y"\ndone < f\n'
           'mapfile -t z < f\necho "::error::$z"')
    assert check(tmp_path, run) == ["x", "y", "z"]


# --- Python and Node heredocs ------------------------------------------------


def test_python_f_string_needs_shown(tmp_path):
    run = ("python3 - <<'PY'\nimport sys\npath = sys.argv[0]\n"
           "print(f\"::error::bad {path} {len(path)}\")\nPY")
    assert check(tmp_path, run) == ["path"]


def test_python_shown_counts_only_when_the_heredoc_defines_it(tmp_path):
    body = "print(f\"::error::bad {shown(path)}\", file=sys.stderr)\nPY"
    assert check(tmp_path, f"python3 - <<'PY'\n{body}") == ["shown"]
    shutil.rmtree(tmp_path / ".github")
    defined = "def shown(value):\n    return value\n"
    assert check(tmp_path, f"python3 - <<'PY'\n{defined}{body}") == []


def test_node_template_needs_shown(tmp_path):
    run = ("node <<'NODE'\nconst shown = (v) => String(v);\nconst p = process.env.P;\n"
           "console.error(`::error::bad ${p} ${shown(p)}`);\nNODE")
    assert check(tmp_path, run) == ["p"]


def test_quoted_data_heredoc_is_not_shell(tmp_path):
    assert check(tmp_path, "cat > f.py <<'PY'\nprint('::error::$VALUE')\nPY") == []


# --- the allow-list ----------------------------------------------------------

REL = ".github/workflows/reusable-w.yaml"


def test_an_entry_covers_its_name_in_its_step_only(tmp_path):
    write(tmp_path, REL, workflow('total=$(jq length)\necho "::error::$total"'))
    entry = guard.Allowed(REL, "total", step="Step", reason="a number")
    assert names(tmp_path, [entry]) == []
    other = guard.Allowed(REL, "total", step="Other", reason="a number")
    assert [n for _, n in names(tmp_path, [other])] == ["total"]


def test_an_env_entry_needs_that_env_value_and_no_reassignment(tmp_path):
    entry = guard.Allowed(REL, "VALUE", env="${{ inputs.value }}", reason="checked upstream")
    write(tmp_path, REL, workflow('echo "::error::$VALUE"'))
    assert names(tmp_path, [entry]) == []
    write(tmp_path, REL, workflow('VALUE=$(cat x)\necho "::error::$VALUE"'))
    assert [n for _, n in names(tmp_path, [entry])] == ["VALUE"]


def test_an_after_entry_covers_lines_below_its_check_only(tmp_path):
    run = ('if [[ ! "$VALUE" =~ ^[0-9]+$ ]]; then\n  echo "::error::$VALUE"\n  exit 1\nfi\n'
           'echo "n=$VALUE" >> "$GITHUB_OUTPUT"')
    write(tmp_path, REL, workflow(run))
    entry = guard.Allowed(REL, "VALUE", after='if [[ ! "$VALUE" =~ ^[0-9]+$ ]]; then', reason="numeric")
    [(line, name)] = names(tmp_path, [entry])
    assert name == "VALUE" and line == 13, "the print inside the failing branch stays a finding"


def test_a_source_entry_goes_stale_with_its_check(tmp_path):
    entry = guard.Allowed(REL, "VALUE", env="${{ inputs.value }}", source=("Step", "check-line"), reason="r")
    write(tmp_path, REL, workflow('echo "::error::$VALUE"'))
    findings, stale = guard.audit(tmp_path, (entry,))
    assert len(findings) == 1 and stale == [entry]
    write(tmp_path, REL, workflow('# check-line\necho "::error::$VALUE"'))
    assert guard.audit(tmp_path, (entry,)) == ([], [])


def test_every_entry_says_why():
    for entry in guard.ALLOWED:
        assert len(entry.reason.strip()) > 5, entry


# --- the selector --------------------------------------------------------------


def test_non_reusable_workflows_are_not_selected(tmp_path):
    write(tmp_path, ".github/workflows/caller.yaml", workflow('echo "::error::$VALUE"'))
    assert guard.audit(tmp_path, ()) == ([], [])


def test_composite_actions_and_their_scripts_are_selected(tmp_path):
    write(tmp_path, "actions/a/action.yml",
          "name: A\nruns:\n  using: composite\n  steps:\n    - shell: bash\n      env:\n"
          "        V: ${{ inputs.v }}\n      run: echo \"::error::$V\"\n")
    write(tmp_path, "actions/a/run.sh", '#!/usr/bin/env bash\necho "::error::$1"\n')
    write(tmp_path, "actions/a/test/fixture.sh", 'echo "::error::$1"\n')
    found = {(f["path"], f["line"]) for f in guard.audit(tmp_path, ())[0]}
    assert found == {("actions/a/action.yml", 8), ("actions/a/run.sh", 2)}


def test_main_reports_and_fails(tmp_path, capsys):
    write(tmp_path, REL, workflow('echo "::error::$VALUE"'))
    assert guard.main(["--root", str(tmp_path)]) == 1
    assert f"::error file={REL},line=12::" in capsys.readouterr().out
    write(tmp_path, REL, workflow('echo "::error::fixed"'))
    assert guard.main(["--root", str(tmp_path)]) == 0


# --- this repository -------------------------------------------------------------


def test_this_repository_prints_only_masked_or_constrained_values():
    files = guard.candidate_files(REPO_ROOT)
    assert REPO_ROOT / PUBLISH in files
    assert REPO_ROOT / "actions" / "setup-vale" / "setup-vale.sh" in files
    findings, stale = guard.audit(REPO_ROOT)
    assert findings == []
    assert stale == [], "an ALLOWED entry that matches nothing hides nothing and should go"


def copy_with(tmp_path: pathlib.Path, rel: str, old: str, new: str) -> pathlib.Path:
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / ".github" / "workflows", root / ".github" / "workflows")
    shutil.copytree(REPO_ROOT / "actions", root / "actions")
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding="utf-8")
    return root


def test_undoing_one_mask_is_seen(tmp_path):
    root = copy_with(tmp_path, PUBLISH, "${EXPECTED_TARGET_SHA//[[:cntrl:]]/?}", "$EXPECTED_TARGET_SHA")
    findings, _ = guard.audit(root)
    assert [(f["path"], f["message"].split("`")[1]) for f in findings] == [(PUBLISH, "EXPECTED_TARGET_SHA")]


def test_removing_the_tag_refusal_is_seen_in_every_later_step(tmp_path):
    root = copy_with(tmp_path, PUBLISH, 'if [[ "$TAG" == *[[:cntrl:]]* ]]; then', 'if false; then')
    findings, stale = guard.audit(root)
    steps = {f["step"] for f in findings if f["path"] == PUBLISH}
    assert {"Resolve draft", "Publish (flip draft=false)", "Post-publish sanity",
            "Verify version-bearing-file alignment"} <= steps
    assert any(e.name == "TAG" and e.path == PUBLISH for e in stale)
