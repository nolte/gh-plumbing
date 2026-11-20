"""Tests for scripts/workflow_command_masking.py (#492).

The defect this guards against produces no error: a value with a line break
followed by `::warning::...`, or with `##[warning]...` anywhere in a log line,
simply becomes a command of its own, and a `name=$value` line gains a second
entry. So the load-bearing cases are the shapes that look fine -- a message
that reads a variable assigned three lines up, a `{ ...; } >> "$GITHUB_OUTPUT"`
group, a Python f-string in a heredoc, a mask that handles line ends but not
`##[`, a check that sits after the print rather than before it, a check whose
`exit` never runs, an allow-list entry whose check was deleted or commented
out.

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
HELPER = guard.SHELL_SHOWN
REFUSAL = ('if [[ "$VALUE" == *[[:cntrl:]]* || "$VALUE" == *\'##[\'* ]]; then\n'
           '  echo "::error::$(shown "$VALUE")"\n  exit 1\nfi')


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
    # Plain log lines: '##[' needs no line break and no '::' prefix.
    'echo "plain $VALUE"',
    'printf \'Matched: %s\\n\' "$VALUE"',
    'if true; then echo "x $VALUE"; fi',
    'echo "x $VALUE" >&2',
])
def test_a_raw_input_in_a_sink_is_a_finding(tmp_path, line):
    assert check(tmp_path, line) == ["VALUE"]


@pytest.mark.parametrize("line", [
    'echo "$VALUE" > file.txt',
    'echo "$VALUE" | jq .',
    "echo '::error::$VALUE'",
    '# echo "::error::$VALUE"',
    'echo "::error::${{ inputs.value }}"',
    'echo "::error::no value"',
    'x=$(echo "$VALUE")',
    'gh api "x/$VALUE" 2>/dev/null || echo \'\'',
    'printf -v x \'%s\' "$VALUE"',
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


def test_a_group_into_a_file_is_not_a_log_line(tmp_path):
    assert check(tmp_path, '{\n  echo "### $VALUE"\n} >> out.md') == []


def test_a_group_into_the_summary_counts_line_by_line(tmp_path):
    # Successor of the case above for $GITHUB_STEP_SUMMARY, which is no longer
    # outside the class (#506): Markdown, read by the summary rule.
    write(tmp_path, REL, workflow('{\n  echo "### fixed"\n  echo "### $VALUE"\n} >> "$GITHUB_STEP_SUMMARY"'))
    [finding] = guard.audit(tmp_path, ())[0]
    assert finding["message"].startswith("`VALUE` reaches a step-summary write unencoded")
    text = (tmp_path / REL).read_text().splitlines()
    assert 'echo "### $VALUE"' in text[finding["line"] - 1], "the finding names the physical line"


def test_a_heredoc_into_an_env_file_counts_line_by_line(tmp_path):
    assert check(tmp_path, 'cat >> "$GITHUB_OUTPUT" <<EOF\nk=$VALUE\nEOF') == ["VALUE"]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, "cat >> \"$GITHUB_OUTPUT\" <<'EOF'\nk=$VALUE\nEOF") == [], "quoted: no expansion"


def test_a_continued_line_is_one_sink(tmp_path):
    assert check(tmp_path, 'echo "::error::first" \\\n     "then $VALUE" >&2') == ["VALUE"]


# --- what counts as masked ---------------------------------------------------


def test_masked_by_the_helper_at_the_print(tmp_path):
    assert check(tmp_path, f'{HELPER}\necho "x $(shown "$VALUE")"\necho "::error::$(shown "${{VALUE}}")"') == []


def test_masked_by_the_last_assignment(tmp_path):
    assert check(tmp_path, f'{HELPER}\nshown_v=$(shown "$VALUE")\necho "::error::$shown_v"') == []


def test_the_helper_must_be_the_canonical_one(tmp_path):
    weak = 'shown() { printf \'%s\' "${1//[[:cntrl:]]/?}"; }'
    # The weak helper's own printf of "$1" is a raw print too.
    assert check(tmp_path, f'{weak}\necho "x $(shown "$VALUE")"') == ["1", guard.LEADING, "VALUE"]


def test_a_control_character_mask_alone_no_longer_counts(tmp_path):
    # It keeps a value on one line but leaves '##[' for the older syntax.
    assert check(tmp_path, 'echo "x ${VALUE//[[:cntrl:]]/?}"') == ["VALUE"]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, 'echo "x ${SAFE//[[:cntrl:]]/$VALUE}"', env="          SAFE: fixed\n") == ["VALUE"]


def test_reassigned_raw_after_the_mask(tmp_path):
    run = f'{HELPER}\nshown_v=$(shown "$VALUE")\nshown_v="$VALUE"\necho "::error::$shown_v"'
    assert check(tmp_path, run) == ["shown_v"]


def test_an_append_keeps_the_name_unclean(tmp_path):
    assert check(tmp_path, 'x="lit"\nx+="$VALUE"\necho "::error::$x"') == ["x"]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, f'{HELPER}\nx=$(shown "$VALUE")\nx+="$VALUE"\necho "::error::$x"') == ["x"]


# --- refusals ------------------------------------------------------------------


def test_refused_before_the_print(tmp_path):
    assert check(tmp_path, f'{HELPER}\n{REFUSAL}\necho "v=$VALUE" >> "$GITHUB_OUTPUT"\necho "x $VALUE"') == []


def test_a_print_before_the_refusal_is_still_a_finding(tmp_path):
    assert check(tmp_path, f'{HELPER}\necho "::notice::$VALUE"\n{REFUSAL}') == ["VALUE"]


def test_a_refusal_of_control_characters_only_proves_nothing(tmp_path):
    run = 'if [[ "$VALUE" == *[[:cntrl:]]* ]]; then\n  exit 1\nfi\necho "x $VALUE"'
    assert check(tmp_path, run) == ["VALUE"]


@pytest.mark.parametrize("branch", [
    '  echo "will not exit"',               # no exit at all
    '  # exit 1',                           # a comment
    '  ( exit 1 )',                         # a subshell
    '  if false; then\n    exit 1\n  fi',   # nested, conditional
    '  :\nelse\n  exit 0',                  # only in the else-branch
])
def test_a_refusal_needs_a_real_exit_on_its_own_path(tmp_path, branch):
    run = f'if [[ "$VALUE" == *[[:cntrl:]]* || "$VALUE" == *\'##[\'* ]]; then\n{branch}\nfi\necho "x $VALUE"'
    assert check(tmp_path, run) == ["VALUE"]


def test_exit_0_ends_the_body_too(tmp_path):
    # A skip (warn, then exit 0) stops the step just as well as a failure.
    run = 'if [[ "$VALUE" == *[[:cntrl:]]* || "$VALUE" == *\'##[\'* ]]; then\n  exit 0\nfi\necho "x $VALUE"'
    assert check(tmp_path, run) == []


def test_a_refused_value_reassigned_later_is_a_finding(tmp_path):
    assert check(tmp_path, f'{HELPER}\n{REFUSAL}\nVALUE=$(cat x)\necho "::notice::$VALUE"') == ["VALUE"]


def test_a_reassignment_after_the_print_inside_a_loop_counts(tmp_path):
    run = f'{HELPER}\n{REFUSAL}\nwhile true; do\n  echo "x $VALUE"\n  VALUE=$(cat x)\ndone'
    assert check(tmp_path, run) == ["VALUE"]


# --- constants and numbers -----------------------------------------------------


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

PY_HELPER = f"def shown(value):\n    {guard.PY_SHOWN_RETURN}\n"


def test_python_f_string_needs_shown(tmp_path):
    run = ("python3 - <<'PY'\nimport sys\npath = sys.argv[0]\n"
           "print(f\"::error::bad {path} {len(path)}\")\nPY")
    assert check(tmp_path, run) == ["path"]


def test_python_plain_print_is_a_sink(tmp_path):
    assert check(tmp_path, "python3 - <<'PY'\nline = input()\nprint('x', line)\nPY") == ["line"]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, f"python3 - <<'PY'\n{PY_HELPER}line = input()\nprint('x', shown(line))\nPY") == []


def test_python_stdout_into_a_file_is_not_a_log_line(tmp_path):
    run = "python3 - <<'PY' > out.json\nline = input()\nprint('x', line)\nprint('x', line, file=sys.stderr)\nPY"
    write(tmp_path, ".github/workflows/reusable-w.yaml", workflow(run))
    [(line, name)] = names(tmp_path)
    assert name == "line" and line == 15, "only the stderr print"


def test_python_shown_counts_only_when_the_heredoc_defines_it_canonically(tmp_path):
    body = "print(f\"::error::bad {shown(path)}\", file=sys.stderr)\nPY"
    assert check(tmp_path, f"python3 - <<'PY'\n{body}") == ["shown"]
    shutil.rmtree(tmp_path / ".github")
    weak = "def shown(value):\n    return re.sub(r'[\\x00-\\x1f]', '?', str(value))\n"
    assert check(tmp_path, f"python3 - <<'PY'\n{weak}{body}") == ["shown"]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, f"python3 - <<'PY'\n{PY_HELPER}{body}") == []


def test_node_template_and_plain_log_need_shown(tmp_path):
    run = (f"node <<'NODE'\n{guard.JS_SHOWN}\nconst p = process.env.P;\n"
           "console.error(`::error::bad ${p} ${shown(p)}`);\nconsole.log(p);\nNODE")
    assert check(tmp_path, run) == ["p", "p", guard.LEADING], "console.log(p) also begins with the value"


def test_node_stdout_into_the_summary_is_not_a_log_line(tmp_path):
    # Not a log line -- but the summary rule reads it (#506): raw, it is a
    # step-summary finding, and only that.
    run = "node <<'NODE' >> \"$GITHUB_STEP_SUMMARY\"\nconst p = process.env.P;\nconsole.log(`${p}`);\nNODE"
    write(tmp_path, REL, workflow(run))
    [finding] = guard.audit(tmp_path, ())[0]
    assert finding["message"].startswith("`p` reaches a step-summary write unencoded")


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


def test_an_after_entry_needs_its_check_as_code(tmp_path):
    run = '# if [[ ! "$VALUE" =~ ^[0-9]+$ ]]; then\necho "n=$VALUE" >> "$GITHUB_OUTPUT"'
    write(tmp_path, REL, workflow(run))
    entry = guard.Allowed(REL, "VALUE", after='if [[ ! "$VALUE" =~ ^[0-9]+$ ]]; then', reason="numeric")
    assert [n for _, n in names(tmp_path, [entry])] == ["VALUE"]


def test_a_source_entry_goes_stale_with_its_check(tmp_path):
    entry = guard.Allowed(REL, "VALUE", env="${{ inputs.value }}", source=("Step", "check-line"), reason="r")
    write(tmp_path, REL, workflow('echo "::error::$VALUE"'))
    findings, stale = guard.audit(tmp_path, (entry,))
    assert len(findings) == 1 and stale == [entry]
    write(tmp_path, REL, workflow('# check-line\necho "::error::$VALUE"'))
    findings, stale = guard.audit(tmp_path, (entry,))
    assert len(findings) == 1 and stale == [entry], "a comment is not a check"
    write(tmp_path, REL, workflow(': check-line\necho "::error::$VALUE"'))
    assert guard.audit(tmp_path, (entry,)) == ([], [])


def test_every_entry_says_why():
    for entry in guard.ALLOWED:
        assert len(entry.reason.strip()) > 5, entry


def test_call_site_entries_are_scoped_and_say_they_are_unchecked():
    for entry in guard.ALLOWED:
        if entry.name in ("2", "result"):
            assert "NOT checked by this guard" in entry.reason, entry
    [fork] = [e for e in guard.ALLOWED if e.name == "2"]
    assert fork.step is not None


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
    write(tmp_path, "actions/a/tests/scanned.sh", 'echo "::error::$1"\n')
    found = {(f["path"], f["line"]) for f in guard.audit(tmp_path, ())[0]}
    assert found == {("actions/a/action.yml", 8), ("actions/a/run.sh", 2), ("actions/a/tests/scanned.sh", 1)}


# --- its own output --------------------------------------------------------------


def output_lines(capsys) -> list[str]:
    return capsys.readouterr().out.splitlines()


def test_main_reports_and_fails(tmp_path, capsys):
    write(tmp_path, REL, workflow('echo "::error::$VALUE"'))
    assert guard.main(["--root", str(tmp_path)]) == 1
    assert f"::error file={REL},line=12::" in capsys.readouterr().out
    write(tmp_path, REL, workflow('echo "::error::fixed"'))
    assert guard.main(["--root", str(tmp_path)]) == 0


def test_a_hostile_step_name_stays_inside_its_annotation(tmp_path, capsys):
    write(tmp_path, REL, workflow('echo "::error::$VALUE"', name='"a\\n::warning::injected-by-step-name"'))
    assert guard.main(["--root", str(tmp_path)]) == 1
    [line] = output_lines(capsys)
    assert line.startswith("::error file=") and "a%0A::warning::injected-by-step-name" in line


def test_a_hostile_path_is_escaped_as_a_property(tmp_path, capsys):
    write(tmp_path, "actions/x,line=1::y/run.sh", 'echo "::error::$1"\n')
    assert guard.main(["--root", str(tmp_path)]) == 1
    [line] = output_lines(capsys)
    assert line.startswith("::error file=actions/x%2Cline=1%3A%3Ay/run.sh,line=1::")


def test_an_unparseable_file_is_one_finding_without_its_text(tmp_path, capsys):
    write(tmp_path, REL, "jobs: [\n  secret-line ::warning::from-yaml\n")
    (tmp_path / ".github/workflows/reusable-b.yaml").write_bytes(b"\xff\xfe broken")
    assert guard.main(["--root", str(tmp_path)]) == 1
    lines = output_lines(capsys)
    assert len(lines) == 2
    assert all(line.startswith("::error file=.github/workflows/reusable-") for line in lines)
    assert all("could not be read or parsed" in line for line in lines)
    assert not any("secret-line" in line or "Traceback" in line for line in lines)


def test_long_values_are_capped(tmp_path, capsys):
    write(tmp_path, REL, workflow('echo "::error::$VALUE"', name="n" * 1000))
    guard.main(["--root", str(tmp_path)])
    [line] = output_lines(capsys)
    assert "n" * 200 + "..." in line and "n" * 201 not in line


def test_the_success_line_neutralises_the_root(tmp_path, capsys):
    root = tmp_path / "r##[warning]x"
    root.mkdir()
    assert guard.main(["--root", str(root)]) == 0
    [line] = output_lines(capsys)
    assert "##[" not in line and "r#?[warning]x" in line


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
    root = copy_with(tmp_path, PUBLISH, '$(shown "$EXPECTED_TARGET_SHA")', "$EXPECTED_TARGET_SHA")
    findings, _ = guard.audit(root)
    assert [(f["path"], f["message"].split("`")[1]) for f in findings] == [(PUBLISH, "EXPECTED_TARGET_SHA")]


@pytest.mark.parametrize("new", ["if false; then", """if [[ "$TAG" == *[[:cntrl:]]* ]]; then"""])
def test_weakening_the_tag_refusal_is_seen_in_every_later_step(tmp_path, new):
    root = copy_with(tmp_path, PUBLISH, guard.TAG_REFUSAL, new)
    findings, stale = guard.audit(root)
    steps = {f["step"] for f in findings if f["path"] == PUBLISH}
    assert {"Resolve draft", "Publish (flip draft=false)", "Post-publish sanity",
            "Verify version-bearing-file alignment"} <= steps
    assert any(e.name == "TAG" and e.path == PUBLISH for e in stale)


# --- the line-start and seam rules ------------------------------------------------


@pytest.mark.parametrize("line", [
    f'{HELPER}\necho "$(shown "$VALUE")"',
    f'{HELPER}\necho "  $(shown "$VALUE") tail"',
    f'{HELPER}\necho -n "$(shown "$VALUE")"',
    f'{HELPER}\nprintf \'%s\\n\' "$(shown "$VALUE")" >&2',
    f'{HELPER}\nprintf \'  %s\\n\' "$(shown "$VALUE")"',
])
def test_a_log_line_must_not_begin_with_a_value(tmp_path, line):
    assert check(tmp_path, line) == [guard.LEADING]


@pytest.mark.parametrize("line", [
    f'{HELPER}\necho "x $(shown "$VALUE")"',
    f'{HELPER}\nprintf \'gh: %s\\n\' "$(shown "$VALUE")" >&2',
    f'{HELPER}\nprintf \'%s\\n\' "$(shown "$VALUE")" >> out.txt',
    f'{HELPER}\n{{\n  echo "uploaded<<EOF"\n  printf \'%s\\n\' "$(shown "$VALUE")"\n}} >> "$GITHUB_OUTPUT"',
    'echo "::error::$(shown "$VALUE")"\n' + HELPER,
])
def test_a_literal_first_or_a_non_log_line_is_fine(tmp_path, line):
    assert check(tmp_path, line) == []


def test_python_and_node_lines_must_not_begin_with_a_value(tmp_path):
    run = f"python3 - <<'PY'\n{PY_HELPER}line = input()\nprint(shown(line))\nprint(f\"{{shown(line)}}\")\nPY"
    assert check(tmp_path, run) == [guard.LEADING, guard.LEADING]
    shutil.rmtree(tmp_path / ".github")
    run = f"node <<'NODE'\n{guard.JS_SHOWN}\nconsole.log(`  ${{shown(1)}}`);\nconsole.log(`x ${{shown(1)}}`);\nNODE"
    assert check(tmp_path, run) == [guard.LEADING]


def test_a_leading_value_entry_needs_its_step(tmp_path):
    write(tmp_path, REL, workflow(f'{HELPER}\necho "$(shown "$VALUE")"'))
    entry = guard.Allowed(REL, guard.LEADING, step="Step", reason="a literal at every call site")
    assert names(tmp_path, [entry]) == []


@pytest.mark.parametrize("line", [
    'echo "id #$(shown "$VALUE")"',
    'echo "id #"$(shown "$VALUE")',
    'echo "x $(shown "$VALUE")[0]"',
    'echo "x $(shown "$VALUE")#"',
    'echo "x $(shown "$VALUE")$(shown "$VALUE")"',
])
def test_a_mask_next_to_a_seam_character_is_a_finding(tmp_path, line):
    assert check(tmp_path, f"{HELPER}\n{line}") == [guard.SEAM_NAME]


def test_the_seam_cases_really_re_form_the_prefix():
    import subprocess
    script = (f"{HELPER}\n"
              'a="#[x"; b="##"; c="x#"; d="#[y"\n'
              'echo "id #$(shown "$a")"; echo "x $(shown "$b")[0]"; echo "x $(shown "$c")$(shown "$d")"\n')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    assert out.splitlines() == ["id ##[x", "x ##[0]", "x x##[y"]


# --- the step summary (#506) ------------------------------------------------------

MD = "\n".join(guard.SHELL_MD)
JS_MD = "\n".join(guard.JS_MD)
SUMMARY = '>> "$GITHUB_STEP_SUMMARY"'


def summary_names(tmp_path, run: str, entries=(), **kwargs) -> list[str]:
    write(tmp_path, REL, workflow(run, **kwargs))
    findings, _ = guard.audit(tmp_path, tuple(entries))
    return [f["message"].split("`")[1] for f in findings]


@pytest.mark.parametrize("line", [
    f'echo "x=$VALUE" {SUMMARY}',
    f'echo "| Tag | \\`$VALUE\\` |" {SUMMARY}',
    f'printf -- "- %s\\n" "$VALUE" {SUMMARY}',
    f'{{ echo; echo "- $VALUE"; }} {SUMMARY}',
    'echo "x $VALUE" >> "${GITHUB_STEP_SUMMARY}"',
    'echo "x $VALUE" >> $GITHUB_STEP_SUMMARY',
])
def test_a_raw_value_on_a_summary_line_is_a_finding(tmp_path, line):
    # Successor of the summary write test_lines_outside_the_class_are_ignored
    # used to list.
    assert summary_names(tmp_path, line) == ["VALUE"]


def test_the_log_mask_is_not_a_summary_mask(tmp_path):
    run = f'{HELPER}\necho "- $(shown "$VALUE")" {SUMMARY}\nshown_v=$(shown "$VALUE")\necho "- $shown_v" {SUMMARY}'
    assert summary_names(tmp_path, run) == ["VALUE", "shown_v"]


def test_a_refusal_is_not_a_summary_mask(tmp_path):
    assert summary_names(tmp_path, f'{HELPER}\n{REFUSAL}\necho "x $VALUE"\necho "x $VALUE" {SUMMARY}') == ["VALUE"]


def test_a_log_entry_does_not_cover_the_summary_and_back(tmp_path):
    run = f'echo "::notice::x $VALUE"\necho "x $VALUE" {SUMMARY}'
    log = guard.Allowed(REL, "VALUE", step="Step", reason="checked upstream")
    assert summary_names(tmp_path, run, [log]) == ["VALUE"]
    summary = guard.Allowed(REL, "VALUE", step="Step", reason="checked upstream", sink="summary")
    assert summary_names(tmp_path, run, [summary]) == ["VALUE"]
    assert summary_names(tmp_path, run, [log, summary]) == []


@pytest.mark.parametrize("line", [
    f'coverage report --format=markdown {SUMMARY}',
    f'{{\n  echo "## Coverage"\n  coverage report --format=markdown\n}} {SUMMARY}',
    f'echo "x $(cat notes.md)" {SUMMARY}',
    f'echo "x `cat notes.md`" {SUMMARY}',
    f'jq -r .body r.json | head -n 5 {SUMMARY}',
    'echo "fixed" | tee -a "$GITHUB_STEP_SUMMARY"',
    f'jq -r . <<EOF {SUMMARY}\n{{}}\nEOF',
    f'{MD}\nmd_pre "$(coverage report)" {SUMMARY}',
])
def test_command_output_appended_to_the_summary_is_a_finding(tmp_path, line):
    assert summary_names(tmp_path, line) == [guard.OUTPUT_NAME]


@pytest.mark.parametrize("line", [
    f'echo "x $(md_code "$VALUE")" {SUMMARY}',
    f'echo "x $(md_code "${{VALUE}}")" {SUMMARY}',
    f'{{ echo "### Fixed"; echo; md_pre "$VALUE"; }} {SUMMARY}',
    f'cell=$(md_code "$VALUE")\necho "| x | $cell |" {SUMMARY}',
    f'cell="_(empty)_"\nif [[ -n "$VALUE" ]]; then\n  cell=$(md_code "$VALUE")\nfi\necho "| x | $cell |" {SUMMARY}',
    f'{{\n  for v in a b; do echo "- $(md_code "$v")"; done\n  echo "n=${{#VALUE}}"\n}} {SUMMARY}',
    f'report=$(coverage report)\n{{ echo "## Coverage"; md_pre "$report"; }} {SUMMARY}',
    f'echo "- \\`gh release edit\\` was **not** called." {SUMMARY}',
    f"cat {SUMMARY} <<'EOF'\n- $VALUE stays literal\nEOF",
    f'{{\n  echo "x" >&2\n  echo "fixed" > out.md\n}} {SUMMARY}',
    f'{{\n  while IFS= read -r v; do echo "- $(md_code "$v")"; done < list.txt\n  x="a b"\n}} {SUMMARY}',
])
def test_encoded_constant_or_redirected_elsewhere_is_fine(tmp_path, line):
    assert summary_names(tmp_path, f"{MD}\n{line}") == []


def test_an_env_file_write_inside_a_summary_group_stays_the_log_rule_s(tmp_path):
    write(tmp_path, REL, workflow(f'{{\n  echo "v=$VALUE" >> "$GITHUB_OUTPUT"\n}} {SUMMARY}'))
    [finding] = guard.audit(tmp_path, ())[0]
    assert finding["message"].startswith("`VALUE` reaches a log line or env-file write unmasked")


def test_the_summary_helpers_must_be_the_canonical_ones(tmp_path):
    weak = 'md_code() { printf \'<code>%s</code>\' "$1"; }'
    # `1`: the weak helper's own printf is a raw log print.
    assert summary_names(tmp_path, f'{weak}\necho "x $(md_code "$VALUE")" {SUMMARY}') == ["1", "VALUE"]
    shutil.rmtree(tmp_path / ".github")
    # Every line of the block: md_code without the md_pre line is not enough.
    partial = "\n".join(guard.SHELL_MD[:2])
    assert summary_names(tmp_path, f'{partial}\necho "x $(md_code "$VALUE")" {SUMMARY}') == ["VALUE"]


def test_the_bare_encoder_is_not_a_summary_mask(tmp_path):
    # Unwrapped, `@name` and `#1` still link.
    assert summary_names(tmp_path, f'{MD}\necho "x $(md_enc "$VALUE")" {SUMMARY}') == ["VALUE"]


def test_an_unquoted_heredoc_into_the_summary_expands(tmp_path):
    assert summary_names(tmp_path, f"cat {SUMMARY} <<EOF\n- '$VALUE'\nEOF") == ["VALUE"]
    shutil.rmtree(tmp_path / ".github")
    assert summary_names(tmp_path, f'{MD}\ncat {SUMMARY} <<EOF\n- $(md_code "$VALUE")\nEOF') == []


def test_a_node_heredoc_into_the_summary_needs_md(tmp_path):
    raw = ("node <<'NODE' >> \"$GITHUB_STEP_SUMMARY\"\nconst p = process.env.P;\n"
           "const rows = [1].map((k) => `| ${k} | ${p} |`).join('\\n');\n"
           "process.stdout.write(\n  `## T\\n${rows}\\n`\n);\nconsole.log(p);\nconsole.log('x' + p);\n"
           "console.error(`::error::${shown(p)}`);\nNODE")
    # `shown`: the log rule's finding for the stderr line, which it reads.
    assert summary_names(tmp_path, raw) == ["shown", "k", "p", "rows", "p", "'x' + p"]
    shutil.rmtree(tmp_path / ".github")
    clean = (f"node <<'NODE' >> \"$GITHUB_STEP_SUMMARY\"\n{JS_MD}\nconst p = process.env.P;\n"
             "console.log('## T');\nconsole.log(`| ${mdCode(p)} | ${mdCode(p.length)} |`);\n"
             "process.stdout.write(mdPre(p));\nNODE")
    assert summary_names(tmp_path, clean) == []
    shutil.rmtree(tmp_path / ".github")
    weak = clean.replace(guard.JS_MD[0], "const mdEnc = (value) => String(value);")
    assert summary_names(tmp_path, weak) == ["mdCode", "mdPre"], "one finding per name and line"


def test_a_python_heredoc_into_the_summary_needs_md(tmp_path):
    raw = "python3 - <<'PY' >> \"$GITHUB_STEP_SUMMARY\"\nimport os\nv = os.environ['V']\nprint(f\"| {v} |\")\nprint(v)\nPY"
    assert summary_names(tmp_path, raw) == ["v", "v"]
    shutil.rmtree(tmp_path / ".github")
    clean = ("python3 - <<'PY' >> \"$GITHUB_STEP_SUMMARY\"\nimport os, re\n" + guard.PY_MD
             + "v = os.environ['V']\nprint(f\"| {md_code(v)} | {len(v)} |\")\nprint(md_pre(v))\nprint('fixed')\nPY")
    assert summary_names(tmp_path, clean) == []


def test_the_summary_entries_say_why_and_are_scoped():
    summary = [e for e in guard.ALLOWED if e.sink == "summary"]
    assert summary, "the triggerer, the run URL and REASON"
    assert all(e.step is not None for e in summary)
    assert {e.sink for e in guard.ALLOWED} == {"log", "summary"}


def test_undoing_one_summary_encoding_is_seen(tmp_path):
    root = copy_with(tmp_path, PUBLISH, 'echo "- All gates passed for $(md_code "$TAG")."',
                     'echo "- All gates passed for \\`$TAG\\`."')
    findings, _ = guard.audit(root)
    assert [(f["step"], f["message"].split("`")[1]) for f in findings] == [("Dry-run summary", "TAG")]


@pytest.mark.parametrize("rel, old, new", [
    (".github/workflows/reusable-python-coverage.yaml", 'md_pre "$report"', "coverage report --format=markdown"),
    (".github/workflows/reusable-nodejs-coverage.yaml", "${mdCode(total[k].pct)}%", "${total[k].pct}%"),
    (".github/workflows/reusable-release-archive.yml", 'echo "Attached to draft $(md_code "$TAG") before publish:"',
     'echo "Attached to draft \\`$TAG\\` before publish:"'),
])
def test_undoing_an_encoding_in_a_sibling_is_seen(tmp_path, rel, old, new):
    root = copy_with(tmp_path, rel, old, new)
    findings, _ = guard.audit(root)
    assert [f["path"] for f in findings] == [rel]


# --- review bypasses (#506): each closed, each a fixture -----------------------

PY_SUMMARY = "python3 - <<'PY' >> \"$GITHUB_STEP_SUMMARY\"\nimport os, re, sys\n" + guard.PY_MD
NODE_SUMMARY = f"node <<'NODE' >> \"$GITHUB_STEP_SUMMARY\"\n{JS_MD}\n"


@pytest.mark.parametrize("run", [
    # a compound command redirected as a whole
    f'for v in a b; do\n  echo "x $VALUE"\ndone {SUMMARY}',
    f'for v in a; do echo "x $VALUE"; done {SUMMARY}',
    f'if true; then\n  echo "x $VALUE"\nfi {SUMMARY}',
    f'while read -r line; do\n  echo "x $VALUE"\ndone < list.txt {SUMMARY}',
    f'for v in a; do\n  if true; then\n    echo "x $VALUE"\n  fi\ndone {SUMMARY}',
    # tee into the summary with its own stdout thrown away
    'echo "x $VALUE" | tee -a "$GITHUB_STEP_SUMMARY" > /dev/null',
    'echo "x $VALUE" > >(tee -a "$GITHUB_STEP_SUMMARY")',
    # a second statement or redirect on the same line
    f'echo "x $VALUE" {SUMMARY}; echo done >&2',
    f'true > /dev/null; echo "x $VALUE" {SUMMARY}',
    f'{{\n  echo "x $VALUE"; echo y > /dev/null\n}} {SUMMARY}',
    f'{{\n  echo y > /dev/null; echo "x $VALUE"\n}} {SUMMARY}',
    # a group whose `{` shares a line with its first statement
    f'{{ echo "x $VALUE"\n  echo y\n}} {SUMMARY}',
    f'{{ echo y\n  echo "x $VALUE"\n}} {SUMMARY}',
    # the clobber operator
    'echo "x $VALUE" >| "$GITHUB_STEP_SUMMARY"',
])
def test_a_raw_value_reaching_the_summary_another_way_is_a_finding(tmp_path, run):
    found = summary_names(tmp_path, run)
    assert "VALUE" in found, found
    assert all(n in ("VALUE", guard.OUTPUT_NAME) for n in found), found


def test_a_summary_finding_inside_a_compound_is_named_once_as_such(tmp_path):
    write(tmp_path, REL, workflow(f'for v in a b; do\n  echo "x $VALUE"\ndone {SUMMARY}'))
    [finding] = guard.audit(tmp_path, ())[0]
    assert finding["message"].startswith("`VALUE` reaches a step-summary write unencoded")


def test_encoded_values_in_compounds_are_fine(tmp_path):
    run = (f'{MD}\nfor v in a b; do\n  echo "- $(md_code "$v")"\ndone {SUMMARY}\n'
           f'{{ echo "### x"\n  echo "- $(md_code "$VALUE")"\n}} {SUMMARY}\n'
           f'if true; then\n  md_pre "$VALUE"\nfi {SUMMARY}')
    assert summary_names(tmp_path, run) == []


def test_the_masked_assignment_must_hold_on_every_path(tmp_path):
    run = f'{MD}\nx="$VALUE"; if false; then x=$(md_code "$VALUE"); fi; echo "$x" {SUMMARY}'
    assert summary_names(tmp_path, run) == ["x"]
    shutil.rmtree(tmp_path / ".github")
    run = f'{MD}\nx="$VALUE"\nif false; then\n  x=$(md_code "$VALUE")\nfi\necho "$x" {SUMMARY}'
    assert summary_names(tmp_path, run) == ["x"]


@pytest.mark.parametrize("run", [
    f'cat "$VALUE" - <<EOF {SUMMARY}\nfixed\nEOF',
    f"cat notes.md <<'EOF' {SUMMARY}\nfixed\nEOF",
])
def test_cat_with_more_than_its_heredoc_prints_a_file(tmp_path, run):
    assert guard.OUTPUT_NAME in summary_names(tmp_path, run)


@pytest.mark.parametrize("line", [
    'print(md_code("a"), end=os.environ["V"])',
    'print(md_code("a"), sep=v)',
    "print('a'); print(v)",
    "print('x ' + v)  # file=sys.stderr",
    "print('x', file=sys.stderr); print(v)",
])
def test_python_summary_prints_need_every_part_encoded(tmp_path, line):
    run = PY_SUMMARY + f"v = os.environ['V']\n{line}\nPY"
    assert summary_names(tmp_path, run) != [], line


def test_python_stderr_and_literal_keywords_stay_fine(tmp_path):
    run = PY_SUMMARY + ("v = os.environ['V']\nprint(md_code(v), end='')\nprint(md_code(v), sep=' ', flush=True)\n"
                        "print(f'::error::{shown(v)}', file=sys.stderr) if False else None\nPY")
    # the stderr line is the log rule's: shown is not defined here
    assert summary_names(tmp_path, run) == ["shown"]


@pytest.mark.parametrize("redefinition", [
    'unset -f md_code; md_code() { cat <<< "$1"; }',
    'md_code() { cat <<< "$1"; }',
    'function md_enc { printf %s "$1"; }',
    "alias md_code=echo",
])
def test_a_later_shell_redefinition_voids_the_helper(tmp_path, redefinition):
    run = f'{MD}\n{redefinition}\necho "x $(md_code "$VALUE")" {SUMMARY}'
    assert "VALUE" in summary_names(tmp_path, run)


@pytest.mark.parametrize("redefinition", ["md_code = str", "from html import escape as md_code",
                                          "def md_enc(value):\n    return value"])
def test_a_later_python_redefinition_voids_the_helper(tmp_path, redefinition):
    run = PY_SUMMARY + f"{redefinition}\nv = os.environ['V']\nprint(md_code(v))\nPY"
    assert "md_code" in summary_names(tmp_path, run)


@pytest.mark.parametrize("redefinition", ["{\n  const mdCode = (v) => v;\n  console.log(mdCode(p));\n}",
                                          "let mdEnc = String;", "mdCode = (v) => v;"])
def test_a_later_node_redefinition_voids_the_helper(tmp_path, redefinition):
    run = NODE_SUMMARY + f"const p = process.env.P;\n{redefinition}\nconsole.log(mdCode(p));\nNODE"
    assert "mdCode" in summary_names(tmp_path, run)


def test_env_file_clobber_is_an_env_file_write(tmp_path):
    # `>|` writes the env file just as `>` does; the #505 rule reads it now.
    assert check(tmp_path, 'echo "v=$VALUE" >| "$GITHUB_OUTPUT"') == ["VALUE"]


def test_an_env_file_loop_is_still_read_line_by_line(tmp_path):
    run = 'for v in a; do\n  echo "v=$VALUE"\ndone >> "$GITHUB_OUTPUT"'
    assert check(tmp_path, run) == ["VALUE"]


@pytest.mark.parametrize("run", [
    f'for v in a; do\n  echo "x $VALUE" >&2\ndone {SUMMARY}',
    f'{{\n  echo "x $VALUE" >&2\n}} {SUMMARY}',
    '{\n  echo "x $VALUE" >&2\n} > out.txt',
])
def test_a_stderr_line_inside_a_redirected_group_is_still_a_log_line(tmp_path, run):
    write(tmp_path, REL, workflow(run))
    messages = [f["message"] for f in guard.audit(tmp_path, ())[0]]
    assert any(m.startswith("`VALUE` reaches a log line") for m in messages), messages
