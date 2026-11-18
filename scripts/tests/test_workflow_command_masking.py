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
    'echo "x=$VALUE" >> "$GITHUB_STEP_SUMMARY"',
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
    assert check(tmp_path, '{\n  echo "### $VALUE"\n} >> "$GITHUB_STEP_SUMMARY"') == []


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
    run = "node <<'NODE' >> \"$GITHUB_STEP_SUMMARY\"\nconst p = process.env.P;\nconsole.log(`${p}`);\nNODE"
    assert check(tmp_path, run) == []


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
