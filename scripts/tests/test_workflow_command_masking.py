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


# --- a masked assignment counts only where its block encloses the print (#507) ---

ISSUE_507_GAP_1 = f'{HELPER}\nx="$VALUE"\nif false; then\n  x=$(shown "$VALUE")\nfi\necho "::error::$x"'


def test_issue_507_a_mask_in_a_branch_that_does_not_run_is_a_finding(tmp_path):
    assert check(tmp_path, ISSUE_507_GAP_1) == ["x"]


@pytest.mark.parametrize("run", [
    # raw, then masked, at the print's own level
    f'{HELPER}\nx="$VALUE"\nx=$(shown "$x")\necho "::error::$x"\necho "v=$x" >> "$GITHUB_OUTPUT"',
    # raw, then masked in an outer block, the print in an inner one
    f'{HELPER}\nx="$VALUE"\nx=$(shown "$x")\nif true; then\n  for v in a; do\n    echo "::error::$x"\n  done\nfi',
    f'{HELPER}\nf() {{\n  local m="$1"\n  m=$(shown "$m")\n  if true; then\n    echo "x $m"\n  fi\n}}\nf "$VALUE"',
    # both inside the same branch, loop body, case arm, subshell, group
    f'{HELPER}\nif true; then\n  x=$(shown "$VALUE")\n  echo "::error::$x"\nfi',
    f'{HELPER}\nfor v in a; do\n  x=$(shown "$VALUE")\n  echo "::error::$x"\ndone',
    f'{HELPER}\ncase "$VALUE" in\n  a)\n    x=$(shown "$VALUE")\n    echo "::error::$x"\n    ;;\nesac',
    f'{HELPER}\n(\n  x=$(shown "$VALUE")\n  echo "::error::$x"\n)',
    # a later masked assignment that doesn't dominate is passed over
    f'{HELPER}\nx=$(shown "$VALUE")\nif true; then\n  x=$(shown "$OTHER")\nfi\necho "::error::$x"',
    # the mask may be followed by `&&` or `||`: it ran
    f'{HELPER}\nx=$(shown "$VALUE") || exit 1\necho "::error::$x"',
    # a heredoc into an env file, masked before it
    f'{HELPER}\nx=$(shown "$VALUE")\ncat >> "$GITHUB_OUTPUT" <<EOF\nv=$x\nEOF',
])
def test_a_dominating_mask_covers_the_print(tmp_path, run):
    assert check(tmp_path, run, env="          VALUE: ${{ inputs.value }}\n          OTHER: ${{ inputs.o }}\n") == []


@pytest.mark.parametrize("block", [
    'if true; then\n  x=$(shown "$x")\nfi',
    'if false; then\n  :\nelif true; then\n  x=$(shown "$x")\nfi',
    'if false; then\n  :\nelse\n  x=$(shown "$x")\nfi',
    'if false; then x=$(shown "$x"); fi',
    'for v in a; do\n  x=$(shown "$x")\ndone',
    'while false; do\n  x=$(shown "$x")\ndone',
    'case "$VALUE" in\n  a) x=$(shown "$x") ;;\nesac',
    '(\n  x=$(shown "$x")\n)',
    '( x=$(shown "$x") )',
    '{\n  x=$(shown "$x")\n}',
    '{ x=$(shown "$x"); }',
    'f() {\n  x=$(shown "$x")\n}\nf',
    'true && x=$(shown "$x")',
    'false || x=$(shown "$x")',
    'x=$(shown "$x") true',
    'x=$(shown "$x") | cat',
    'x=$(shown "$x") &',
])
def test_a_mask_whose_block_does_not_enclose_the_print_is_a_finding(tmp_path, block):
    assert check(tmp_path, f'{HELPER}\nx="$VALUE"\n{block}\necho "::error::$x"') == ["x"]


def test_a_mask_in_one_case_arm_does_not_cover_another(tmp_path):
    run = (f'{HELPER}\nx="$VALUE"\ncase "$VALUE" in\n  a)\n    x=$(shown "$x")\n    ;;\n'
           '  b)\n    echo "::error::$x"\n    ;;\nesac')
    assert check(tmp_path, run) == ["x"]


def test_a_mask_in_one_branch_does_not_cover_the_else_branch(tmp_path):
    run = f'{HELPER}\nx="$VALUE"\nif true; then\n  x=$(shown "$x")\nelse\n  echo "::error::$x"\nfi'
    assert check(tmp_path, run) == ["x"]


@pytest.mark.parametrize("run", [
    # a raw assignment after the dominating mask, before the print
    f'{HELPER}\nx=$(shown "$VALUE")\nif true; then\n  x="$VALUE"\nfi\necho "::error::$x"',
    f'{HELPER}\nx=$(shown "$VALUE")\nread -r x < f\necho "::error::$x"',
    # on the print's own line
    f'{HELPER}\nx=$(shown "$VALUE")\nx="$VALUE"; echo "::error::$x"',
    # on the mask's own line, after it
    f'{HELPER}\nx=$(shown "$VALUE"); x="$VALUE"\necho "::error::$x"',
    # after the print, inside a loop the mask is outside of: the next pass prints it
    f'{HELPER}\nx=$(shown "$VALUE")\nwhile true; do\n  echo "::error::$x"\n  x="$VALUE"\ndone',
    # a print in a function body, the mask outside: the body runs where it is called
    f'{HELPER}\nx=$(shown "$VALUE")\nf() {{\n  echo "::error::$x"\n}}\nx="$VALUE"\nf',
    # a raw assignment in a function body, called between the mask and the print
    f'{HELPER}\ng() {{ x="$VALUE"; }}\nx=$(shown "$VALUE")\ng\necho "::error::$x"',
    f'{HELPER}\ng() {{\n  x="$VALUE"\n}}\nx=$(shown "$VALUE")\ng\necho "::error::$x"',
])
def test_a_raw_value_that_can_reach_the_print_past_the_mask_is_a_finding(tmp_path, run):
    # A command line counts whole, so `x="$VALUE"; echo "::error::$x"` names VALUE too.
    found = check(tmp_path, run)
    assert "x" in found and set(found) <= {"x", "VALUE"}, found


@pytest.mark.parametrize("run", [
    'x=lit\n{ x="$VALUE"; }\necho "::error::$x"',
    'x=lit\nif true; then { x="$VALUE"; }; fi\necho "::error::$x"',
])
def test_an_assignment_after_a_group_brace_is_an_assignment(tmp_path, run):
    # Before #507 `{ x=...` read as no assignment, so x passed as a constant.
    assert check(tmp_path, run) == ["x"]


def test_a_mask_in_a_loop_re_applied_before_the_print_is_fine(tmp_path):
    run = f'{HELPER}\nwhile true; do\n  x=$(shown "$VALUE")\n  echo "::error::$x"\n  x="$VALUE"\ndone'
    assert check(tmp_path, run) == []


@pytest.mark.parametrize("run", [
    f'{HELPER}\nx="$VALUE"\nx[1]=$(shown "$VALUE")\necho "::error::$x"',
    f'{HELPER}\nx="$VALUE"\nx[1]=$(shown "$VALUE")\necho "v=$x" >> "$GITHUB_OUTPUT"',
    f'{HELPER}\nread -ra x <<< "$VALUE"\nx[0]=$(shown "$VALUE")\necho "::error::${{x[*]}}"',
    f'{HELPER}\nx=("$VALUE" "$VALUE")\nx[0]=$(shown "$VALUE")\necho "::error::${{x[@]}}"',
])
def test_a_masked_element_does_not_mask_the_array(tmp_path, run):
    # `x[1]=$(shown ...)` sets one element: `$x` is `x[0]`, `${x[*]}` all of
    # them, still raw. An indexed assignment is an unmasked one.
    assert check(tmp_path, run) == ["x"]


def test_a_background_job_on_the_line_before_does_not_make_the_mask_conditional(tmp_path):
    # Only `&&`, `||` and `|` continue a list onto the next line; `&` ends it.
    run = f'{HELPER}\nx="$VALUE"\nsleep 1 &\nx=$(shown "$VALUE")\necho "::error::$x"'
    assert check(tmp_path, run) == []
    for tail in ("&&", "||", "|"):
        shutil.rmtree(tmp_path / ".github")
        assert check(tmp_path, run.replace("sleep 1 &", f"true {tail}")) == ["x"]


@pytest.mark.parametrize("unbalanced", [
    'v="$(\n  cat f\n)"',        # a substitution over lines: its `)` reads as a closer
    "jq '\n  if . then 1 else 2 end\n' f",  # a quoted string over lines, its words read as keywords
    "fi",                        # a closer without an opener
    "if true; then",             # an opener without a closer
])
def test_a_body_whose_blocks_cannot_be_attributed_gets_no_mask(tmp_path, unbalanced):
    # Errs towards a finding: the straight-line form is refused there too.
    run = f'{HELPER}\n{unbalanced}\nx="$VALUE"\nx=$(shown "$x")\necho "::error::$x"'
    assert "x" in check(tmp_path, run)


def test_setup_vale_finish_is_covered_by_its_dominating_mask():
    # actions/setup-vale/setup-vale.sh as shipped: `local ... message="$3"`,
    # then `message=$(shown "$message")` at the function's own level, then the
    # prints in the if/else below it.
    rel = "actions/setup-vale/setup-vale.sh"
    [body] = guard.bodies_of(REPO_ROOT, REPO_ROOT / rel)
    checker = guard.Checker(body, [body], guard.ALLOWED, set())
    prints = [k for k, u in enumerate(checker.units)
              if u.lang == "sh" and not guard.is_comment(u.text) and "echo" in u.text and "message" in u.text]
    assert len(prints) == 2
    assert all(checker.masked_before("message", k) for k in prints)
    assert not any(f["message"].startswith("`message`") for f in guard.audit_body(body))


def test_undoing_setup_vale_s_mask_dominance_is_seen(tmp_path):
    rel = "actions/setup-vale/setup-vale.sh"
    root = copy_with(tmp_path, rel, '  message=$(shown "$message")\n',
                     '  if [[ -n "$message" ]]; then\n    message=$(shown "$message")\n  fi\n')
    findings, _ = guard.audit(root)
    assert {(f["path"], f["message"].split("`")[1]) for f in findings} == {(rel, "message")}


# --- #507 review: forms block dominance and the env-file reading missed ------------

@pytest.mark.parametrize("definition", [
    'f() { echo "::error::$x"; }',
    'f() { echo "::error::$x"\n}',
    'function f() { echo "::error::$x"; }',
    'function f { echo "::error::$x"; }',
    'f () {\n  echo "::error::$x"\n}',
    'f()\n{\n  echo "::error::$x"\n}',
    'function f\n{\n  echo "::error::$x"\n}',
    'f() ( echo "::error::$x" )',
    'f() if true; then echo "::error::$x"; fi',
    'f() for i in 1; do echo "::error::$x"; done',
    'f() while true; do echo "::error::$x"; break; done',
    'f() case a in a) echo "::error::$x";; esac',
])
def test_a_print_in_a_function_body_is_seen_wherever_the_body_opens(tmp_path, definition):
    # The print sits in the body, though the line's `f` doesn't; the body runs
    # at the call, after the raw assignment.
    run = f'{HELPER}\nx=$(shown "$VALUE")\n{definition}\nx="$VALUE"\nf'
    assert check(tmp_path, run) == ["x"]


@pytest.mark.parametrize("definition", [
    'g() { x="$VALUE"; }',
    'g()\n{\n  x="$VALUE"\n}',
    'function g\n{\n  x="$VALUE"\n}',
    'g() ( x="$VALUE" )',
    'g() if true; then x="$VALUE"; fi',
    'g() case a in a) x="$VALUE";; esac',
])
def test_a_raw_assignment_in_a_function_body_is_seen_wherever_the_body_opens(tmp_path, definition):
    run = f'{HELPER}\n{definition}\nx=$(shown "$VALUE")\ng\necho "::error::$x"'
    assert check(tmp_path, run) == ["x"]


@pytest.mark.parametrize("run", [
    # the mask and the print in the same body, however it opens
    f'{HELPER}\nf()\n{{\n  local m="$1"\n  m=$(shown "$m")\n  echo "x $m"\n}}\nf "$VALUE"',
    f'{HELPER}\nfunction f {{\n  local m="$1"\n  m=$(shown "$m")\n  echo "x $m"\n}}\nf "$VALUE"',
    # a mask before a one-line function that prints, nothing raw after it
    f'{HELPER}\nx="$VALUE"\nx=$(shown "$x")\nwhile :; do echo "::error::$x"; [[ -n $z ]] && break; z=1; done',
    f'{HELPER}\nx=$(shown "$VALUE")\ntrue; if true; then echo "::error::$x"; fi; true',
])
def test_a_dominating_mask_still_covers_a_print_deeper_on_its_line(tmp_path, run):
    assert check(tmp_path, run) == []


@pytest.mark.parametrize("loop", [
    'true; while [[ -z $d ]]; do echo "::error::$x"\n  x="$VALUE"\n  [[ -n $e ]] && d=1; e=1\ndone',
    ': ; for i in 1 2; do echo "::error::$x"\nx="$VALUE"; done',
    'f() { :; }; for i in 1 2; do echo "::error::$x"\nx="$VALUE"; done',
    'arr=(a b); while :; do echo "::error::$x"\nx="$VALUE"; [[ -n $z ]] && break; z=1; done',
    '[[ a ]] && { while :; do echo "::error::$x"\nx="$VALUE"; [[ -n $z ]] && break; z=1; done; }',
    'if true; then for i in 1 2; do\n  echo "::error::$x"\n  x="$VALUE"\ndone; fi',
])
def test_a_print_in_a_loop_opened_after_another_statement_is_in_the_loop(tmp_path, loop):
    # Before the review fix, the line's other statement put the print at body
    # level, so the raw assignment later in the loop body went unseen.
    assert check(tmp_path, f'{HELPER}\nx=$(shown "$VALUE")\n{loop}') == ["x"]


@pytest.mark.parametrize("condition", [
    '[[ -n "$Q" ]] &&', '[[ -n "$Q" ]] ||', 'echo hi |', 'false &&\n# a comment', 'false &&\n', 'true && # why\n',
])
def test_a_mask_continuing_a_list_from_the_line_before_is_conditional(tmp_path, condition):
    run = f'{HELPER}\nx="$VALUE"\n{condition}\n  x=$(shown "$x")\necho "::error::$x"'
    assert check(tmp_path, run) == ["x"]


def test_a_mask_after_a_line_that_ends_its_list_still_covers(tmp_path):
    run = f'{HELPER}\nx="$VALUE"\ntrue && true\nx=$(shown "$x")\necho "::error::$x"'
    assert check(tmp_path, run) == []


# --- #513: forms the block and assignment reading let through ---------------


def test_issue_513_a_mask_in_a_substitution_over_lines_in_a_case_arm_is_a_finding(tmp_path):
    # The substitution's lone `)` read as a case pattern, so the mask inside
    # `$( ... )` counted for the arm; bash prints the raw value. A pattern is
    # never empty: the `)` now leaves the body unattributed, as at top level.
    run = (f'{HELPER}\nx="$VALUE"\ncase a in\n  a)\n    y=$(\n      x=$(shown "$x")\n    )\n'
           '    echo "x $x"\n    ;;\nesac')
    assert check(tmp_path, run) == ["x"]
    shutil.rmtree(tmp_path / ".github")
    # A pattern on a line of its own still opens the arm the mask covers.
    run = f'{HELPER}\nx="$VALUE"\ncase a in\n  a)\n    x=$(shown "$x")\n    echo "x $x"\n    ;;\nesac'
    assert check(tmp_path, run) == []


def test_issue_513_a_print_right_after_a_case_pattern_is_a_log_print(tmp_path):
    assert check(tmp_path, f'{HELPER}\nx="$VALUE"\ncase "$1" in b) echo "x $x" ;; esac') == ["x"]


def test_issue_513_a_mask_after_a_line_ending_in_a_stderr_pipe_is_conditional(tmp_path):
    # `|&` is a pipe: the mask on the next line runs in the pipeline's subshell.
    run = f'{HELPER}\nx="$VALUE"\ntrue |&\nx=$(shown "$x")\necho "v: $x"'
    assert check(tmp_path, run) == ["x"]


@pytest.mark.parametrize("raw", ['declare x[0]="$VALUE"', 'typeset x[0]="$VALUE"'])
def test_issue_513_an_indexed_declare_assignment_voids_the_mask(tmp_path, raw):
    assert check(tmp_path, f'{HELPER}\nx=$(shown "$VALUE")\n{raw}\necho "v: $x"') == ["x"]


def test_issue_513_an_assignment_with_a_nested_subscript_voids_the_mask(tmp_path):
    # `\[[^\]\s]*\]` stopped at the inner `]`, so `x[${a[0]}]=` was no assignment.
    run = f'{HELPER}\nx=$(shown "$VALUE")\nx[${{a[0]}}]="$VALUE"\necho "v: $x"'
    assert check(tmp_path, run) == ["x"]


@pytest.mark.parametrize("raw", [
    'case a in\n  a) x="$VALUE" ;;\nesac',
    'case a in a) x="$VALUE";; esac',
    'case a in (a) x="$VALUE";; esac',
    'a=1 x="$VALUE"',
    'typeset x="$VALUE"',
    'time x="$VALUE"',
    '! x="$VALUE"',
    'x[0]="$VALUE"',
    'if false; then :; elif x="$VALUE"; then :; fi',
    'while x="$VALUE"; [[ -z $d ]]; do d=1; done',
    'read -r a x <<<"q $VALUE"',
    'read -d \'\' -r -a q x <<<"$VALUE" || true',
    'read -p "q" x <<<"$VALUE"',
    'IFS=, read -r x <<<"$VALUE"',
    'select x in "$VALUE"; do break; done',
    'readarray -t x <<<"$VALUE"',
    'mapfile -d \'\' x < f',
    'getopts ab x',
    'let x=1',
    'set -- "$VALUE"; for x; do :; done',
    'set -- "$VALUE"\nfor x do :; done',
])
def test_a_raw_assignment_the_reader_used_to_miss_voids_the_mask(tmp_path, raw):
    assert check(tmp_path, f'{HELPER}\nx=$(shown "$VALUE")\n{raw}\necho "::error::$x"') == ["x"]


@pytest.mark.parametrize("raw", [
    'case a in\n  a) x="$VALUE" ;;\nesac',
    'a=1 x="$VALUE"',
    'read -r a x < f',
])
def test_a_raw_assignment_the_reader_used_to_miss_voids_the_constant_rule(tmp_path, raw):
    # Before the review fix, `case a in a) x="$VALUE" ;; esac` left x constant
    # on develop as well.
    assert check(tmp_path, f'x=lit\n{raw}\necho "::error::$x"') == ["x"]


@pytest.mark.parametrize("pseudo", [
    'if (( GITHUB_HEAD_REF==1 )); then :; fi',
    '( GITHUB_HEAD_REF=lit )',
    '( GITHUB_HEAD_REF=lit; true )',
    '(\n  GITHUB_HEAD_REF=lit\n)',
    'case a in (GITHUB_HEAD_REF=lit) :;; esac',
    'GITHUB_HEAD_REF=lit true',
    'a=1 GITHUB_HEAD_REF=lit true',
])
def test_an_assignment_that_does_not_reach_the_print_makes_no_name_constant(tmp_path, pseudo):
    # Arithmetic, a subshell, a case pattern, a command's environment: the
    # runner's value is what the print shows. `origin/develop` reported the
    # first four; the change under review made them constant.
    assert check(tmp_path, f'{pseudo}\necho "::error::$GITHUB_HEAD_REF"', env="          X: y\n") == ["GITHUB_HEAD_REF"]


def test_a_subshell_literal_in_a_function_makes_no_name_constant(tmp_path):
    run = 'f() {\n  ( m=lit )\n  echo "::error::$m"\n}\nf "$VALUE"'
    assert check(tmp_path, run) == ["m"]


def test_a_raw_assignment_in_a_subshell_still_counts(tmp_path):
    # Harmless in bash (the subshell's x doesn't reach the print), refused all
    # the same: the guard errs towards a finding. A `{ ...; }` group's
    # assignment is real and refused too (see above).
    assert check(tmp_path, 'x=lit; ( x="$VALUE" ); echo "::error::$x"') == ["VALUE", "x"]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, 'x=lit\n( x="$VALUE" )\necho "::error::$x"') == ["x"]


def test_a_quoted_hash_right_after_a_quote_starts_no_comment(tmp_path):
    # `echo "a"#; fi; ...` prints `a#`; the rest of the line is code. Read as
    # a comment, the `fi` went unseen and the blocks shifted.
    run = (f'{HELPER}\nx="$VALUE"\nif false; then\n  x=$(shown "$x")\n  echo "a"#; fi; if true; then\n'
           '  echo "::error::$x"\nfi')
    assert check(tmp_path, run) == ["x"]


def test_a_hash_after_a_separator_starts_a_comment(tmp_path):
    run = f'{HELPER}\nx="$VALUE"\nx=$(shown "$x");# fi\necho "::error::$x"'
    assert check(tmp_path, run) == []


# --- #513 (P2): sinks and destinations the guard read as elsewhere ----------

# Stands for PY_HELPER, which is defined further down, in a parametrized run.
ISSUE_513_PY_HELPER = "@PY_HELPER@\n"


def issue_513_py(opener: str, line: str) -> str:
    """A Python heredoc opened with `opener` after its `<<'PY'`, printing `line`."""
    return (f"{HELPER}\npython3 - <<'PY'{opener}\nimport os, re, sys\n{ISSUE_513_PY_HELPER}"
            f"p = os.environ['VALUE']\n{line}\nPY")


def check_513(tmp_path, run: str) -> list[str]:
    return check(tmp_path, run.replace(ISSUE_513_PY_HELPER, PY_HELPER))


@pytest.mark.parametrize("pipe", ["| tee out.log", "| cat", "|& tee out.log", "| /usr/bin/tee -a out.log"])
def test_issue_513_a_shell_print_piped_into_tee_or_cat_is_a_log_print(tmp_path, pipe):
    # tee and cat print what they read: the `##[` reaches the log.
    assert check(tmp_path, f'{HELPER}\necho "##[warning]$VALUE" {pipe}') == ["VALUE"]


def test_issue_513_a_print_piped_into_another_command_stays_unread(tmp_path):
    # Not covered: the guard doesn't follow what `grep` prints.
    assert check(tmp_path, f'{HELPER}\necho "x $VALUE" | grep x') == []


def test_issue_513_the_file_tee_writes_is_not_charged_to_the_print(tmp_path):
    # The print's statement ends at the pipe: `$RUNNER_X` names tee's file.
    assert check(tmp_path, f'{HELPER}\necho "x $(shown "$VALUE")" | tee "$RUNNER_X"') == []


@pytest.mark.parametrize("opener", [
    " > /dev/stderr", " >> /dev/stderr", " > /dev/stdout", " >/dev/fd/2", " > /proc/self/fd/2", " > >(cat)",
    ' > "/dev/stderr"',
])
def test_issue_513_a_heredoc_redirected_to_a_standard_stream_prints_to_the_log(tmp_path, opener):
    assert check_513(tmp_path, issue_513_py(opener, 'print("x", p)')) == ["p"]


@pytest.mark.parametrize("redirect", ["> /dev/stderr", ">/dev/stdout", ">> /dev/fd/1", "> >(cat)"])
def test_issue_513_a_shell_print_redirected_to_a_standard_stream_is_a_log_print(tmp_path, redirect):
    assert check(tmp_path, f'{HELPER}\necho "x $VALUE" {redirect}') == ["VALUE"]


def test_issue_513_a_heredoc_in_a_group_teed_into_an_env_file_is_read_as_the_log_as_well(tmp_path):
    # The group's closer pipes its stdout into tee, which prints it: the
    # entry begins a log line, as for `python3 - <<'PY' | tee -a ...`.
    run = (f"{HELPER}\n{{ python3 - <<'PY'\nimport os, re, sys\n{PY_HELPER}p = os.environ['VALUE']\n"
           "print(f\"{shown(p)}=x\")\nPY\n} | tee -a \"$GITHUB_OUTPUT\"")
    assert check(tmp_path, run) == [guard.LEADING]


def test_issue_513_a_heredoc_writing_only_stderr_to_an_env_file_prints_stdout_to_the_log(tmp_path):
    # `2>>` sends stderr into the env file; stdout stays on the log, where
    # the masked value begins the line.
    assert check_513(tmp_path, issue_513_py(' 2>> "$GITHUB_OUTPUT"', "print(shown(p))")) == [guard.LEADING]


def test_issue_513_a_print_redirected_to_the_summary_with_greater_ampersand_is_a_summary_write(tmp_path):
    run = f'{HELPER}\necho "x $VALUE" >& "$GITHUB_STEP_SUMMARY"'
    write(tmp_path, ".github/workflows/reusable-w.yaml", workflow(run))
    findings, _ = guard.audit(tmp_path, ())
    assert [f["message"].split("`")[1] for f in findings] == ["VALUE"]
    assert "step-summary write" in findings[0]["message"]


def test_issue_513_a_script_whose_name_holds_python_is_no_interpreter(tmp_path):
    # Its unquoted heredoc is shell text, read as such -- not a Python
    # heredoc with a `$` in it (`<unquoted heredoc>`).
    assert check(tmp_path, f"{HELPER}\n./run-python-tests.sh <<EOT\n$VALUE\nEOT") == ["VALUE"]


@pytest.mark.parametrize("command", [
    "/usr/bin/python3 -", "python3.12 -", "uv run python3 -", "env node", "x=$(python3 -", "if ! node",
])
def test_issue_513_an_interpreter_named_as_a_word_still_reads_the_heredoc(tmp_path, command):
    assert check(tmp_path, f"{command} <<PY\nprint('$VALUE')\nPY") == [guard.UNQUOTED_NAME]


def test_issue_513_a_mask_in_a_substitution_closed_after_text_in_a_case_arm_is_a_finding(tmp_path):
    # `x=$(shown "$x"))` closes the `y=$(` of the line above; the trailing `)`
    # read as a case pattern, so the mask counted for the arm.
    run = (f'{HELPER}\nx="$VALUE"\ncase a in\n  a)\n    y=$(\n      x=$(shown "$x"))\n    echo "x $x"\n'
           '    ;;\nesac')
    assert check(tmp_path, run) == ["x"]


def test_issue_513_a_print_after_a_subshell_paren_is_a_log_print(tmp_path):
    assert check(tmp_path, f'{HELPER}\nx="$VALUE"\n( echo "x $x" )') == ["x"]


def test_issue_513_an_element_assignment_with_spaces_in_its_subscript_voids_the_mask(tmp_path):
    # `x[1 + 1]=...` sets x[2]; it is an assignment to x all the same.
    assert check(tmp_path, f'{HELPER}\nx=$(shown "$VALUE")\nx[1 + 1]="$VALUE"\necho "v: $x"') == ["x"]


@pytest.mark.parametrize("run, expected", [
    # Refused at f79d452 already: held here as regressions.
    (issue_513_py(' >> "$GITHUB_OUTPUT"', 'print("x=" + p, file=sys.stdout if p else sys.stderr)'), ['"x=" + p']),
    (f"{HELPER}\npython3 - <<'PY' |\nimport os, re, sys\n{ISSUE_513_PY_HELPER}p = os.environ['VALUE']\n"
     "print('x=' + p)\nPY\ntee -a \"$GITHUB_OUTPUT\"", ["'x=' + p"]),
    (issue_513_py(' | tee -a "$GITHUB_OUTPUT"', 'print(f"{shown(p)}=x")'), [guard.LEADING]),
    (f"{HELPER}\n{{ python3 - <<'PY'\nimport os, re, sys\n{ISSUE_513_PY_HELPER}p = os.environ['VALUE']\n"
     "print('x', p)\nPY\n} | cat", ["p"]),
])
def test_issue_513_forms_refused_before_stay_refused(tmp_path, run, expected):
    assert check_513(tmp_path, run) == expected


# --- #513 (P3): the heredoc reading and two shell sinks ---------------------


def issue_513_js(opener: str, line: str) -> str:
    """A Node heredoc opened with `opener` after its `<<'JS'`, defining `shown` and printing `line`."""
    return f"{HELPER}\nnode - <<'JS'{opener}\n{guard.JS_SHOWN}\nconst p = process.env.VALUE;\n{line}\nJS"


@pytest.mark.parametrize("run", [
    issue_513_py("", 'shown = str\nprint(f"x {shown(p)}")'),
    issue_513_py(' >> "$GITHUB_OUTPUT"', 'shown = str\nprint(f"x={shown(p)}")'),
    issue_513_py("", 'shown: object = str\nprint(f"x {shown(p)}")'),
    issue_513_py("", '(shown := str)\nprint(f"x {shown(p)}")'),
    issue_513_py("", 'def shown(value):\n    return value\nprint(f"x {shown(p)}")'),
    issue_513_py("", 'import builtins as shown\nprint(f"x {shown(p)}")'),
    issue_513_py("", 'from builtins import str as shown\nprint(f"x {shown(p)}")'),
    issue_513_py("", 'for shown in [str]:\n    pass\nprint(f"x {shown(p)}")'),
    issue_513_py("", 'with open("/dev/null") as shown:\n    pass\nprint(f"x {shown(p)}")'),
    issue_513_js("", "{ let shown = String; console.log(`x ${shown(p)}`); }"),
    issue_513_js("", "function shown(v) { return v; }\nconsole.log(`x ${shown(p)}`);"),
    issue_513_js(' >> "$GITHUB_OUTPUT"', "var shown = String;\nconsole.log(`x=${shown(p)}`);"),
])
def test_issue_513_a_heredoc_that_rebinds_shown_has_no_mask(tmp_path, run):
    # The canonical definition proves nothing once anything else in the
    # heredoc binds the name: the call is read as an unmasked value.
    assert check_513(tmp_path, run) == ["shown"]


def test_issue_513_a_python_shown_decorated_is_not_canonical(tmp_path):
    run = (f"{HELPER}\npython3 - <<'PY'\nimport os, re, sys\n@lambda f: str\n{ISSUE_513_PY_HELPER}"
           "p = os.environ['VALUE']\nprint(f\"x {shown(p)}\")\nPY")
    assert check_513(tmp_path, run) == ["shown"]


@pytest.mark.parametrize("rebind", ['shown() { echo "v$@"; }', "unset -f shown"])
def test_issue_513_a_shell_shown_redefined_after_the_canonical_one_has_no_mask(tmp_path, rebind):
    assert check(tmp_path, f'{HELPER}\n{rebind}\necho "x $(shown "$VALUE")"') == ["VALUE"]


def test_issue_513_a_python_shown_must_return_on_its_first_body_line(tmp_path):
    # `if value: return value` returns the raw value first.
    helper = f"def shown(value):\n    if value: return value\n    {guard.PY_SHOWN_RETURN}\n"
    run = issue_513_py("", 'print(f"x {shown(p)}")').replace(ISSUE_513_PY_HELPER, helper)
    assert check(tmp_path, run) == ["shown"]


def test_issue_513_comment_lines_before_the_canonical_return_keep_the_mask(tmp_path):
    helper = f"def shown(value):\n    # masks a value\n\n    {guard.PY_SHOWN_RETURN}\n"
    run = issue_513_py("", 'print(f"x {shown(p)}")').replace(ISSUE_513_PY_HELPER, helper)
    assert check(tmp_path, run) == []


@pytest.mark.parametrize("run", [
    issue_513_py(' >> "$GITHUB_OUTPUT"', "sys.stdout.writelines([p])"),
    issue_513_py(' >> "$GITHUB_OUTPUT"', "sys.stdout.buffer.write(p.encode())"),
    issue_513_py(' >> "$GITHUB_OUTPUT"', "import json\njson.dump(p, sys.stdout)"),
    f"{HELPER}\nnode - <<'JS' >> \"$GITHUB_OUTPUT\"\nconst p = process.env.VALUE;\nconsole['log'](p);\nJS",
    issue_513_py(" > f.txt", "import functools\nlog = functools.partial(print, file=sys.stderr)\nlog(p)"),
])
def test_issue_513_a_stream_writer_the_strict_reading_does_not_name_is_refused(tmp_path, run):
    assert check_513(tmp_path, run) == [guard.UNKNOWN_WRITER]


def test_issue_513_a_stdout_writer_into_a_plain_file_stays_unread(tmp_path):
    # The real tree's vbf.json step: stdout goes to a file, not a sink.
    assert check_513(tmp_path, issue_513_py(" > vbf.json", "import json\njson.dump(p, sys.stdout)")) == []


@pytest.mark.parametrize("run, expected", [
    # `# )` closed the call early: `file=sys.stderr` went unread, and the
    # masked value starts a stderr line on the log.
    (issue_513_py(" > f.txt", "print(shown(p),  # )\n      file=sys.stderr)"), [guard.LEADING]),
    (issue_513_py(" > f.txt", "print(p,  # )\n      file=sys.stderr)"), ["p", guard.LEADING]),
    (issue_513_js(" > f.txt", "console.error(shown(p), // )\n  p);"), ["p", guard.LEADING]),
    (issue_513_js(" > f.txt", "console.error(shown(p), /* ) */\n  p);"), ["p", guard.LEADING]),
])
def test_issue_513_a_comment_in_a_print_call_does_not_end_it(tmp_path, run, expected):
    assert check_513(tmp_path, run) == expected


def test_issue_513_a_comment_in_a_masked_multi_line_print_is_skipped(tmp_path):
    # Refused before as the argument `# label`.
    run = issue_513_py(' >> "$GITHUB_OUTPUT"', 'print(\n    "x=",  # label, )\n    shown(p),\n    sep="")')
    assert check_513(tmp_path, run) == []


def test_issue_513_a_hash_in_a_same_quote_field_hides_no_argument(tmp_path):
    # PEP 701: the scan misreads the field, so the `#` reads as a comment;
    # the call's arguments are read without comments as well.
    run = issue_513_py("", 'd = {"#": 1}\nprint(f"x {shown(d["#"])}", p)')
    assert "p" in check_513(tmp_path, run)


def test_issue_513_a_bare_name_on_a_summary_print_continuation_line_is_read(tmp_path):
    assert check_513(tmp_path, issue_513_py(' >> "$GITHUB_STEP_SUMMARY"', 'print("x",\n      p)')) == ["p"]


@pytest.mark.parametrize("run", [
    issue_513_py("", 'open(os.environ["GITHUB_ENV"], "a").write(f"K={p}\\n")'),
    issue_513_py("", 'with open(os.environ["GITHUB_ENV"], "a") as fh:\n    fh.write(f"K={p}\\n")'),
    issue_513_py("", 'open(os.getenv("GITHUB_STEP_SUMMARY"), "a").write(p)'),
    f"{HELPER}\nnode - <<'JS'\nconst fs = require('fs');\n"
    "fs.appendFileSync(process.env.GITHUB_OUTPUT, `k=${process.env.VALUE}\\n`);\nJS",
])
def test_issue_513_a_heredoc_that_names_an_env_file_is_refused(tmp_path, run):
    assert check_513(tmp_path, run) == [guard.ENV_FILE_OPENED]


def test_issue_513_a_heredoc_that_names_an_env_file_can_be_allowed(tmp_path):
    run = issue_513_py("", 'open(os.environ["GITHUB_ENV"], "a").write("K=1\\n")')
    write(tmp_path, REL, workflow(run.replace(ISSUE_513_PY_HELPER, PY_HELPER)))
    entry = guard.Allowed(REL, guard.ENV_FILE_OPENED, reason="writes a literal")
    assert names(tmp_path, [entry]) == []


def test_issue_513_a_field_in_a_format_spec_is_a_value(tmp_path):
    # `p` sets the fill (a line end is one) and the width.
    assert check_513(tmp_path, issue_513_py("", 'print(f"ok {len(p):{p}}")')) == ["p"]
    shutil.rmtree(tmp_path / ".github")
    assert check_513(tmp_path, issue_513_py("", 'print(f"ok {len(p):>{len(p)}}")')) == []


@pytest.mark.parametrize("run", [
    f"{HELPER}\ncat <<EOF | tee out.log\n##[warning]$VALUE\nEOF",
    f"{HELPER}\ncat <<EOF | tee out.log\nx ##[warning]$VALUE\nEOF",
    # A shell heredoc's line that starts with `#` is data, not a comment.
    f"{HELPER}\ncat <<EOF\n##[warning]$VALUE\nEOF",
    f"{HELPER}\ncat <<EOF >> \"$GITHUB_OUTPUT\"\n#x=$VALUE\nEOF",
    f"{HELPER}\ncat <<EOF >> \"$GITHUB_STEP_SUMMARY\"\n# $VALUE\nEOF",
])
def test_issue_513_a_shell_heredoc_piped_into_tee_or_starting_with_a_hash_is_read(tmp_path, run):
    assert check(tmp_path, run) == ["VALUE"]


def test_issue_513_a_shell_line_teed_into_an_env_file_keeps_the_line_start_rule(tmp_path):
    # tee writes the entry and the log both: the masked value begins a log line.
    run = f'{HELPER}\nx=$(shown "$VALUE")\necho "$x=1" | tee -a "$GITHUB_OUTPUT"'
    assert check(tmp_path, run) == [guard.LEADING]
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, f'{HELPER}\nx=$(shown "$VALUE")\necho "k=$x" | tee -a "$GITHUB_OUTPUT"') == []


PY_PRINTS = "python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os\np = os.environ['P']\n{}\nPY"


@pytest.mark.parametrize("print_", [
    'print("v=" + p)',
    'print("v=%s" % p)',
    'print("v={}".format(p))',
    'print("\\n".join([p]))',
    'print (p)',
    'print("a=1"); print(p)',
    'print("v=1", end=p)',
    'print("a", sep=p)',
    'print(\n    f"v={p}"\n)',
    'print(\n    p\n)',
    'print("v=", p, flush=True)',
])
def test_a_python_print_into_an_env_file_is_read_strictly(tmp_path, print_):
    found = check(tmp_path, PY_PRINTS.format(print_))
    assert found and all("p" in name for name in found), found


@pytest.mark.parametrize("print_", [
    'console.log("v=" + p);',
    'console.dir(p);',
    'console .log(p);',
    'console.log("a=1"); console.log(p);',
    'process.stdout.write(\n  `v=${p}\\n`);',
])
def test_a_node_print_into_an_env_file_is_read_strictly(tmp_path, print_):
    run = f"node <<'NODE' >> \"$GITHUB_OUTPUT\"\nconst p = process.env.P;\n{print_}\nNODE"
    found = check(tmp_path, run)
    assert found and all("p" in name for name in found), found


@pytest.mark.parametrize("print_", [
    'print(f"v={shown(p)}", end="\\n")',
    'print("a=1"); print(shown(p))',
    'print(\n    f"v={shown(p)}"\n)',
    'print("x", shown(p), file=sys.stderr)',
])
def test_a_masked_python_print_into_an_env_file_passes_the_strict_reading(tmp_path, print_):
    run = f"python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os, re, sys\n{PY_HELPER}p = os.environ['P']\n{print_}\nPY"
    assert check(tmp_path, run) == []


def test_the_strict_reading_refuses_shown_inside_a_concatenation(tmp_path):
    # Harmless, but not one literal and not the helper call: refused, as on a
    # summary line.
    run = (f"python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os, re\n{PY_HELPER}p = os.environ['P']\n"
           "print('v=' + shown(p))\nPY")
    assert check(tmp_path, run) == ["'v=' + shown(p)"]


def test_a_stderr_print_in_an_env_file_heredoc_stays_a_log_line(tmp_path):
    run = PY_PRINTS.format("import sys\nprint(p, file=sys.stderr)")
    assert check(tmp_path, run) == ["p", "<leading value>"]


def test_a_heredoc_inside_an_env_file_group_is_read_strictly(tmp_path):
    run = ("{\n  echo a=fixed\n  python3 - <<'PY'\nimport os\np = os.environ['P']\nprint(\"v=\" + p)\nPY\n"
           "} >> \"$GITHUB_OUTPUT\"")
    assert check(tmp_path, run) == ['"v=" + p']


@pytest.mark.parametrize("opener", [
    "python3 - <<'PY-END' >> \"$GITHUB_OUTPUT\"", "python3 - <<\\PY-END >> \"$GITHUB_OUTPUT\"",
    "python3 - <<\"PY.END\" >> \"$GITHUB_OUTPUT\"", "pypy3 - <<'PY-END' >> \"$GITHUB_OUTPUT\"",
])
def test_a_python_heredoc_with_another_delimiter_or_interpreter_is_read(tmp_path, opener):
    delimiter = "PY.END" if "PY.END" in opener else "PY-END"
    assert check(tmp_path, f"{opener}\nprint(f\"v={{p}}\")\n{delimiter}") == ["p"]


def test_a_deno_heredoc_is_read_as_javascript(tmp_path):
    assert check(tmp_path, "deno run - <<'JS' >> \"$GITHUB_OUTPUT\"\nconsole.log(`v=${p}`);\nJS") == ["p"]


@pytest.mark.parametrize("line", [
    'echo "v=$VALUE" | tee --append "$GITHUB_OUTPUT"',
    'echo "v=$VALUE" | tee -a /dev/null "$GITHUB_OUTPUT"',
    'echo "v=$VALUE" | dd of="$GITHUB_OUTPUT" oflag=append conv=notrunc',
])
def test_a_shell_line_teed_to_an_env_file_with_other_options_is_read(tmp_path, line):
    assert check(tmp_path, line) == ["VALUE"]


@pytest.mark.parametrize("line", [
    'echo "x $VALUE" | tee --append "$GITHUB_STEP_SUMMARY"',
    'echo "x $VALUE" | dd of="$GITHUB_STEP_SUMMARY" oflag=append conv=notrunc',
])
def test_a_shell_line_teed_to_the_summary_with_other_options_is_read(tmp_path, line):
    assert "VALUE" in check(tmp_path, line)


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


ISSUE_507_GAP_2 = "node <<'NODE' >> \"$GITHUB_OUTPUT\"\nconst p = process.env.P;\nconsole.log(`v=${p}`);\nNODE"
PY_ENV_FILE = "python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os\np = os.environ['P']\nprint(f\"v={p}\")\nPY"


def test_issue_507_node_stdout_into_an_env_file_is_read(tmp_path):
    assert check(tmp_path, ISSUE_507_GAP_2) == ["p"]


def test_python_stdout_into_an_env_file_is_read(tmp_path):
    assert check(tmp_path, PY_ENV_FILE) == ["p"]


@pytest.mark.parametrize("target", [
    '>> "$GITHUB_OUTPUT"', '> "$GITHUB_OUTPUT"', '>| "$GITHUB_OUTPUT"', ">> $GITHUB_OUTPUT",
    '>> "${GITHUB_ENV}"', '>> "$GITHUB_PATH"', '>> "$GITHUB_STATE"', '| tee -a "$GITHUB_OUTPUT"',
    # tee with other options or files before the env file, and dd (#507 review)
    '| tee --append "$GITHUB_OUTPUT"', '| tee -ai -- "$GITHUB_OUTPUT"', '| tee -a /dev/null "$GITHUB_OUTPUT"',
    '| dd of="$GITHUB_OUTPUT" oflag=append conv=notrunc',
])
@pytest.mark.parametrize("lang", ["node", "python"])
def test_heredoc_stdout_into_any_env_file_is_read(tmp_path, target, lang):
    run = (ISSUE_507_GAP_2 if lang == "node" else PY_ENV_FILE).replace('>> "$GITHUB_OUTPUT"', target)
    assert check(tmp_path, run) == ["p"]


@pytest.mark.parametrize("run", [
    (f"node <<'NODE' >> \"$GITHUB_OUTPUT\"\n{guard.JS_SHOWN}\nconst p = process.env.P;\n"
     "console.log(`v=${shown(p)}`);\nprocess.stdout.write(`w=${shown(p)}\\n`);\nconsole.log(shown(p));\nNODE"),
    (f"python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os, re\n{PY_HELPER}p = os.environ['P']\n"
     "print(f\"v={shown(p)}\")\nprint('w=x', len(p))\nprint(shown(p))\nPY"),
])
def test_a_masked_heredoc_print_into_an_env_file_is_fine(tmp_path, run):
    # shown() turns every line end into '?', so the value can't add an entry;
    # an env-file entry is not a log line, so a leading value is no finding
    # there (as for a shell write to an env file).
    assert check(tmp_path, run) == []


@pytest.mark.parametrize("method", ["log", "info", "debug"])
def test_every_stdout_console_method_into_an_env_file_is_an_env_file_entry(tmp_path, method):
    # All console methods but STDERR_PRINTS write to stdout, so a masked
    # `console.debug` into an env file is an entry there, not a log line.
    run = (f"node <<'JS' >> \"$GITHUB_OUTPUT\"\n{guard.JS_SHOWN}\nconst p = process.env.VALUE;\n"
           f"console.{method}(shown(p));\nJS")
    assert check(tmp_path, run) == []


def test_shown_into_an_env_file_needs_the_canonical_definition(tmp_path):
    run = ("node <<'NODE' >> \"$GITHUB_OUTPUT\"\nconst shown = (v) => v;\n"
           "console.log(`v=${shown(process.env.P)}`);\nNODE")
    assert check(tmp_path, run) == ["shown"]


def test_a_heredoc_inside_an_env_file_group_is_read_as_well(tmp_path):
    # Its stdout is the group's: read with the log rule's check, which is the
    # env-file write's check too.
    run = ("{\n  echo a=fixed\n  node <<'NODE'\nconst p = process.env.P;\nconsole.log(`v=${p}`);\nNODE\n"
           "} >> \"$GITHUB_OUTPUT\"")
    assert check(tmp_path, run) == ["p"]
    shutil.rmtree(tmp_path / ".github")
    masked = run.replace("const p", f"{guard.JS_SHOWN}\nconst p").replace("${p}", "${shown(p)}")
    assert check(tmp_path, masked) == []


@pytest.mark.parametrize("target", ["> vbf.json", ">> out.txt"])
def test_heredoc_stdout_into_a_plain_file_stays_unread(tmp_path, target):
    assert check(tmp_path, ISSUE_507_GAP_2.replace('>> "$GITHUB_OUTPUT"', target)) == []


def test_heredoc_stdout_into_a_pipe_is_read_as_the_log(tmp_path):
    # Fails closed (#511): the guard doesn't follow a pipeline's output, so
    # `| jq .` is read like `| cat`, which prints the heredoc's stdout to the log.
    assert check(tmp_path, ISSUE_507_GAP_2.replace('>> "$GITHUB_OUTPUT"', "| jq .")) == ["p"]


def test_quoted_data_heredoc_is_not_shell(tmp_path):
    assert check(tmp_path, "cat > f.py <<'PY'\nprint('::error::$VALUE')\nPY") == []


# --- #507 second review: function names, stderr into an env file, unquoted heredocs ---

@pytest.mark.parametrize("fname", ["x@y", "a/b", "f+", "f", "my-f"])
def test_a_print_in_a_function_with_any_name_is_seen_in_its_body(tmp_path, fname):
    # bash takes any word before an empty `()` as a function's name. Read as
    # a subshell and a group, `x@y() {` let the mask before it cover the print.
    run = f'{HELPER}\nx=$(shown "$VALUE")\n{fname}() {{\n  echo "::error::x $x"\n}}\nx="$VALUE"\n{fname}'
    assert check(tmp_path, run) == ["x"]


@pytest.mark.parametrize("fname", ["x@y", "a/b", "f+", "f", "my-f"])
def test_a_raw_assignment_in_a_function_with_any_name_voids_the_mask(tmp_path, fname):
    run = f'{HELPER}\n{fname}() {{ x="$VALUE"; }}\nx=$(shown "$VALUE")\n{fname}\necho "::error::x $x"'
    assert check(tmp_path, run) == ["x"]


STDERR_PY = "python3 - <<'PY' {}\nimport os, sys\np = os.environ['P']\n{}\nPY"


@pytest.mark.parametrize("redirect, print_, expected", [
    ('>> "$GITHUB_OUTPUT" 2>&1', 'print("v=" + p, file=sys.stderr)', '"v=" + p'),
    ('2>> "$GITHUB_OUTPUT"', 'sys.stderr.write("v=" + p + "\\n")', '"v=" + p + "\\n"'),
    ('&>> "$GITHUB_OUTPUT"', 'print("v=" + p, file=sys.stderr)', '"v=" + p'),
    ('&> "$GITHUB_ENV"', 'print("v=" + p, file=sys.stderr)', '"v=" + p'),
    ('> /dev/null 2>> "$GITHUB_OUTPUT"', 'print("v=" + p, file=sys.stderr)', '"v=" + p'),
    ('|& tee -a "$GITHUB_OUTPUT"', 'print("v=" + p, file=sys.stderr)', '"v=" + p'),
])
def test_stderr_routed_into_an_env_file_is_read_strictly(tmp_path, redirect, print_, expected):
    # Its stderr prints are entries of the env file too, read as strictly as
    # its stdout prints (and as a log line, #511).
    assert check(tmp_path, STDERR_PY.format(redirect, print_)) == [expected]


@pytest.mark.parametrize("redirect", ['>> "$GITHUB_OUTPUT" 2>&1', '2>> "$GITHUB_OUTPUT"'])
def test_node_stderr_routed_into_an_env_file_is_read_strictly(tmp_path, redirect):
    run = f"node <<'NODE' {redirect}\nconst p = process.env.P;\nconsole.error(\"v=\" + p);\nNODE"
    assert check(tmp_path, run) == ['"v=" + p']


@pytest.mark.parametrize("run", [
    (f"python3 - <<'PY' >> \"$GITHUB_OUTPUT\" 2>&1\nimport os, re, sys\n{PY_HELPER}p = os.environ['P']\n"
     "print(f\"v={shown(p)}\", file=sys.stderr)\nsys.stderr.write(f\"w={shown(p)}\\n\")\nPY"),
    (f"node <<'NODE' 2>> \"$GITHUB_OUTPUT\"\n{guard.JS_SHOWN}\nconst p = process.env.P;\n"
     "console.error(`v=${shown(p)}`);\nNODE"),
])
def test_masked_stderr_routed_into_an_env_file_is_fine(tmp_path, run):
    assert check(tmp_path, run) == []


@pytest.mark.parametrize("print_, expected", [
    # Read as a log line -- since #511 as strictly as an entry.
    ('print("v=" + p, file=sys.stderr)', ['"v=" + p']),
    ('print(f"v={shown(p)}", file=sys.stderr)', []),
    ('print(shown(p), file=sys.stderr)', ["<leading value>"]),
])
def test_stderr_kept_on_the_log_stays_a_log_line(tmp_path, print_, expected):
    # Without a stderr redirect into the env file, it is a log line only: the
    # line-start rule holds for it, not for the stdout entries.
    run = STDERR_PY.format('>> "$GITHUB_OUTPUT"', f"import re\n{PY_HELPER}{print_}\nprint(shown(p))")
    assert check(tmp_path, run) == expected


@pytest.mark.parametrize("run", [
    'python3 - <<PY >> "$GITHUB_OUTPUT"\nprint("v=$VALUE")\nPY',
    'node <<NODE >> "$GITHUB_OUTPUT"\nconsole.log("v=$VALUE");\nNODE',
    'python3 - <<PY\nprint("::error::x $VALUE")\nPY',
    'python3 - <<PY >> "$GITHUB_STEP_SUMMARY"\nprint("v=$VALUE")\nPY',
    'python3 - <<PY > out.json\nprint("v=${VALUE}")\nPY',
    'python3 - <<-PY\nprint("::error::x `cat f`")\nPY',
])
def test_an_unquoted_python_or_node_heredoc_with_an_expansion_is_refused(tmp_path, run):
    # The shell expands `$VALUE` before the interpreter runs, so the value
    # becomes code and text the Python or Node reading never sees.
    assert check(tmp_path, run) == [guard.UNQUOTED_NAME]


@pytest.mark.parametrize("run", [
    'python3 - <<PY\nprint("::error::x fixed")\nPY',
    "python3 - <<'PY'\nimport os\nprint(\"x\", os.environ['VALUE'].count('$'))\nPY",
    "node <<\\NODE\nconsole.log(`x $${1}`);\nNODE",
])
def test_a_quoted_or_expansion_free_python_heredoc_is_not_refused_as_unquoted(tmp_path, run):
    assert guard.UNQUOTED_NAME not in check(tmp_path, run)


# --- #507 third review: heredoc end lines, `>&` and stderr aliases ------------

@pytest.mark.parametrize("run, expected", [
    # An indented end line inside a Python string: bash reads on, so the
    # print after it is an env-file entry, not shell text.
    ('python3 - <<PY >> "$GITHUB_OUTPUT"\n_ = """\n  PY\n"""\nprint("v=" + """$VALUE""")\nPY',
     ['"v=" + """$VALUE"""', guard.UNQUOTED_NAME]),
    ("python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os\n_ = \"\"\"\n  PY\n\"\"\"\np = os.environ[\"VALUE\"]\n"
     "print(\"v=\" + p)\nPY", ['"v=" + p']),
    # A trailing space doesn't end it either.
    ("python3 - <<'PY' >> \"$GITHUB_OUTPUT\"\nimport os\n_ = \"\"\"\nPY \n\"\"\"\np = os.environ[\"VALUE\"]\n"
     "print(\"v=\" + p)\nPY", ['"v=" + p']),
    # A shell heredoc the same way: `k=$VALUE` is a line of it, not an assignment.
    ('cat >> "$GITHUB_OUTPUT" <<EOF\nk=fixed\n  EOF\nk=$VALUE\nEOF', ["VALUE"]),
    # `<<-` strips leading tabs only: an end line indented by spaces stays a heredoc line.
    ('cat >> "$GITHUB_OUTPUT" <<-EOF\nk=fixed\n  EOF\nk=$VALUE\nEOF', ["VALUE"]),
])
def test_a_heredoc_ends_only_on_its_exact_delimiter(tmp_path, run, expected):
    assert check(tmp_path, run) == expected


@pytest.mark.parametrize("run", [
    'cat > f <<-EOF\n\tk=fixed\n\tEOF\necho "v=$VALUE" >> "$GITHUB_OUTPUT"',
    "python3 - <<-'PY' >> \"$GITHUB_OUTPUT\"\n\tprint(\"v=fixed\")\n\tPY\necho \"v=$VALUE\" >> \"$GITHUB_OUTPUT\"",
])
def test_a_tab_indented_end_line_closes_a_dash_heredoc(tmp_path, run):
    # The heredoc closes, so the echo after it is read as shell.
    assert check(tmp_path, run) == ["VALUE"]


@pytest.mark.parametrize("redirect", [
    '>& "$GITHUB_OUTPUT"',
    '>&"$GITHUB_ENV"',
    '>> "$GITHUB_OUTPUT" 2>&01',
    '>> "$GITHUB_OUTPUT" 2>/dev/stdout',
    '>> "$GITHUB_OUTPUT" 2>/dev/fd/1',
    '>> "$GITHUB_OUTPUT" 2>/proc/self/fd/1',
])
def test_stderr_aliased_into_an_env_file_is_read_strictly(tmp_path, redirect):
    assert check(tmp_path, STDERR_PY.format(redirect, 'print("v=" + p, file=sys.stderr)')) == ['"v=" + p']


def test_heredoc_stdout_through_ampersand_redirect_is_an_env_file(tmp_path):
    # bash reads `>& word` as `&> word`: stdout goes there as well.
    assert check(tmp_path, STDERR_PY.format('>& "$GITHUB_OUTPUT"', 'print("v=" + p)')) == ['"v=" + p']


def test_a_shell_write_through_ampersand_redirect_is_an_env_file(tmp_path):
    assert check(tmp_path, 'echo "v=$VALUE" >& "$GITHUB_OUTPUT"') == ["VALUE"]
    assert check(tmp_path, f'{HELPER}\necho "v=$(shown "$VALUE")" >& "$GITHUB_OUTPUT"') == []


@pytest.mark.parametrize("redirect", ["2>&1", ">&2", "2>/dev/stdout", '>&2 2>> /tmp/log'])
def test_stderr_or_stdout_kept_on_the_log_is_no_env_file(tmp_path, redirect):
    # No env file on the line: the heredoc is a log heredoc, its prints log
    # lines -- read as strictly as an entry (#511), but under the line-start
    # rule, which an entry isn't.
    helper = f"import re\n{PY_HELPER}"
    assert check(tmp_path, STDERR_PY.format(redirect, 'print("v=" + p, file=sys.stderr)')) == ['"v=" + p']
    assert check(tmp_path, STDERR_PY.format(redirect, f'{helper}print(f"v={{shown(p)}}", file=sys.stderr)')) == []
    if "/tmp/log" not in redirect:
        # (With `>&2 2>> /tmp/log` bash sends stdout to the log, but the guard
        # reads the heredoc's stdout as a file: a known gap, not #511's.)
        assert check(tmp_path, STDERR_PY.format(redirect, f'{helper}print(shown(p))')) == ["<leading value>"]


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


def test_this_repository_s_masked_assignments_hold_by_block_dominance():
    # The #507 sweep: every print of a name assigned from $(shown ...) in a
    # reusable workflow or an action script is covered by a dominating mask --
    # none passes through another rule -- so a misreading of these bodies'
    # blocks fails here by name, not only as a finding somewhere.
    covered = set()
    for path in guard.candidate_files(REPO_ROOT):
        bodies = guard.bodies_of(REPO_ROOT, path)
        for body in bodies:
            checker = guard.Checker(body, bodies, guard.ALLOWED, set())
            masked = {n for n, events in checker.assigned.items() if any(checker._is_mask(r) for _, r in events)}
            for k in guard.sink_units(checker.units):
                if checker.units[k].lang not in ("sh", "sh-heredoc"):
                    continue
                for name, _, _ in guard.shell_refs(checker.printed_segment(checker.units[k])):
                    if name in masked:
                        assert checker.masked_before(name, k), (body.path, body.first_line + checker.units[k].index)
                        covered.add((body.path, name))
    assert covered == {
        (PUBLISH, "shown_target"), (PUBLISH, "shown_domain"), (PUBLISH, "shown_hacs_filename"),
        (PUBLISH, "shown_filename"), ("actions/setup-vale/setup-vale.sh", "message"),
    }


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
    # `rows` twice: the write's line reads its call joined over the
    # continuation line (#513), which is read on its own as well.
    assert summary_names(tmp_path, raw) == ["shown", "k", "p", "rows", "rows", "p", "'x' + p"]
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


# --- a closer anywhere on a line ends its group (#506 re-review) ------------------

@pytest.mark.parametrize("run", [
    # the 2b49da4-era form: the closer on the line of the last statement
    f'{{\n  echo "### t"\n  echo "$VALUE"; }} {SUMMARY}',
    f'for v in a; do\n  echo "x $VALUE"; done {SUMMARY}',
    f'if true; then\n  echo "x $VALUE"; fi {SUMMARY}',
    f'{{ for v in a; do\n  echo "x $VALUE"\ndone; }} {SUMMARY}',
    f'{{ for v in a; do\n  echo "x $VALUE"; done; }} {SUMMARY}',
    f'f() {{\n  echo "x $VALUE"\n}} {SUMMARY}\nf',
    f'function f {{\n  echo "x $VALUE"\n}} {SUMMARY}\nf',
    'for v in a; do\n  echo "x $VALUE"\ndone |\n  tee -a "$GITHUB_STEP_SUMMARY"',
])
def test_a_closer_after_a_statement_still_ends_the_group(tmp_path, run):
    write(tmp_path, REL, workflow(run))
    messages = [f["message"] for f in guard.audit(tmp_path, ())[0]]
    assert any(m.startswith("`VALUE` reaches a step-summary write") for m in messages), messages


def test_an_env_file_group_closed_after_a_statement_is_read_as_env_file(tmp_path):
    write(tmp_path, REL, workflow('{\n  echo "a=fixed"\n  echo "b=$VALUE"; } >> "$GITHUB_OUTPUT"'))
    findings = guard.audit(tmp_path, ())[0]
    assert findings and {f["line"] for f in findings} == {14}, "only the line that writes b=$VALUE"
    assert all(f["message"].startswith("`VALUE` reaches a log line or env-file write") for f in findings)


def test_a_summary_closer_without_an_opener_fails_closed(tmp_path):
    run = f"cat > g.sh <<'EOF'\n{{\nEOF\n  echo \"fixed\"; }} {SUMMARY}"
    assert summary_names(tmp_path, run) == [guard.GROUP_NAME]


def test_a_statement_before_a_group_on_its_line_stays_a_log_line(tmp_path):
    write(tmp_path, REL, workflow(f'echo "x $VALUE"; {{ echo a\n  echo b\n}} {SUMMARY}'))
    messages = [f["message"] for f in guard.audit(tmp_path, ())[0]]
    assert any(m.startswith("`VALUE` reaches a log line") for m in messages), messages


# --- a heredoc inside a redirected group, an array of keywords (#506, third pass) ---

def summary_messages(tmp_path, run: str) -> list[str]:
    write(tmp_path, REL, workflow(run))
    return [f["message"] for f in guard.audit(tmp_path, ())[0]]


@pytest.mark.parametrize("run", [
    f'{HELPER}\n{{\n  cat <<EOF\nx $(shown "$VALUE")\nEOF\n}} {SUMMARY}',
    f'{HELPER}\nfor v in a; do\n  cat <<EOF\nx $(shown "$VALUE")\nEOF\ndone {SUMMARY}',
    (f"{{\n  node <<'NODE'\n{guard.JS_SHOWN}\nconst p = process.env.P;\nconsole.log(`x ${{shown(p)}}`);\nNODE\n}} "
     f"{SUMMARY}"),
])
def test_a_heredoc_inside_a_summary_group_is_read_by_the_summary_rule(tmp_path, run):
    messages = summary_messages(tmp_path, run)
    assert messages and all("step-summary write" in m for m in messages), messages


def test_a_raw_heredoc_value_inside_a_summary_group_gets_the_summary_message(tmp_path):
    messages = summary_messages(tmp_path, f'{{\n  cat <<EOF\nx $VALUE\nEOF\n}} {SUMMARY}')
    assert [m.split("`")[1] for m in messages] == ["VALUE"]
    assert messages[0].startswith("`VALUE` reaches a step-summary write unencoded")


def test_an_encoded_python_heredoc_inside_a_summary_group_is_fine(tmp_path):
    run = ("{\n  python3 - <<'PY'\nimport os, re\n" + guard.PY_MD
           + f"k = os.environ['K']\nprint(md_code(k))\nPY\n}} {SUMMARY}")
    assert summary_messages(tmp_path, run) == []


def test_a_heredoc_inside_an_env_file_group_stays_an_env_file_write(tmp_path):
    messages = summary_messages(tmp_path, '{\n  cat <<EOF\nv=$VALUE\nEOF\n} >> "$GITHUB_OUTPUT"')
    assert [m.split("`")[1] for m in messages] == ["VALUE"]
    assert messages[0].startswith("`VALUE` reaches a log line or env-file write unmasked")


def test_a_heredoc_redirected_elsewhere_inside_a_summary_group_is_not_summary(tmp_path):
    run = f"{{\n  echo fixed\n  python3 - <<'PY' >&2\nimport os\nprint(os.environ['V'])\nPY\n}} {SUMMARY}"
    messages = summary_messages(tmp_path, run)
    assert messages and all("log line" in m for m in messages), messages


def test_an_array_of_keywords_opens_nothing(tmp_path):
    run = (f'{HELPER}\nfor x in 1; do\n  echo "x $(shown "$VALUE")"\n  kw=(if for while)\n  local -a k2=(do {{ case)\n'
           f'done {SUMMARY}')
    assert summary_names(tmp_path, run) == ["VALUE"]


# --- #511: Python and Node log prints, read as strictly as an env-file entry ---

P_ENV = "          P: ${{ inputs.p }}\n"
LOG_PY = "python3 - <<'PY'\nimport os, re, sys\np = os.environ[\"P\"]\n{}\nPY"
LOG_PY_SHOWN = f"python3 - <<'PY'\nimport os, re, sys\n{PY_HELPER}p = os.environ[\"P\"]\n{{}}\nPY"
LOG_JS = "node <<'JS'\nconst p = process.env.P;\n{}\nJS"
LOG_JS_SHOWN = f"node <<'JS'\n{guard.JS_SHOWN}\nconst p = process.env.P;\n{{}}\nJS"


@pytest.mark.parametrize("run, expected", [
    # A second print call on the line (the issue's fixture).
    (LOG_PY.format('print("ok"); print("::error::" + p)'), ['"::error::" + p']),
    # The continuation line of a call.
    (LOG_PY.format('print("ok",\n      "::error::" + p)'), ['"::error::" + p']),
    # `end=` ends the line in a command; the next print fills it.
    (LOG_PY.format('print("x", end="\\n::error::"); print(p)'), ["p", guard.LEADING]),
    # A second Node print call on the line.
    (LOG_JS.format('console.log("ok"); console.log("::error::" + p);'), ['"::error::" + p']),
    # A single print, built by concatenation.
    (LOG_PY.format('print("::error::" + p)'), ['"::error::" + p']),
    # `sep=` was a finding already and stays one.
    (LOG_PY.format('print("ok", p, sep="\\n::error::")'), ["p"]),
])
def test_the_measured_log_print_forms_are_findings(tmp_path, run, expected):
    # Each exited 0 on develop before #511, as the only step of a reusable
    # workflow reading a caller's input.
    assert check(tmp_path, run, env=P_ENV) == expected
    assert guard.main(["--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("print_", [
    'print("x %s" % p)',
    'print("x {}".format(p))',
    'print("x", "y" + p)',
    'print("x", file=sys.stderr); print("::error::" + p, file=sys.stderr)',
    'sys.stderr.write("x " + p + "\\n")',
    'raise SystemExit("::error::" + p)',
    'print (f"x {p}")',
    'print("x",\n      f"y {p}",\n      file=sys.stderr)',
    'print("x", end=p)',
])
def test_python_log_prints_are_read_strictly(tmp_path, print_):
    assert check(tmp_path, LOG_PY.format(print_), env=P_ENV) != []


@pytest.mark.parametrize("print_", [
    'console.error("::error::" + p);',
    'console.log("ok"); console.error(`x ${p}`);',
    'console.table(`x ${p}`);',
    'console.dir("x " + p);',
    'console . log("x " + p);',
    'process.stderr.write("x " + p + "\\n");',
    'console.log("ok",\n  "x " + p);',
])
def test_node_log_prints_are_read_strictly(tmp_path, print_):
    assert check(tmp_path, LOG_JS.format(print_), env=P_ENV) != []


@pytest.mark.parametrize("run", [
    LOG_PY_SHOWN.format('print(f"::error::{shown(p)}")'),
    LOG_PY_SHOWN.format('print("ok"); print(f"::error::x {shown(p)}", file=sys.stderr)'),
    LOG_PY_SHOWN.format('print("ok",\n      f"x {shown(p)}", sep=" - ", end="\\n")'),
    LOG_PY_SHOWN.format('print(f"n={len(p)}"); sys.stderr.write(f"x {shown(p)}\\n")'),
    LOG_PY.format('print("ok"); print("::error::fixed", file=sys.stderr)'),
    LOG_JS_SHOWN.format('console.log("ok"); console.error(`::error::${shown(p)}`);'),
    LOG_JS.format('console.log("ok"); console.table("fixed");'),
])
def test_masked_or_literal_log_prints_stay_clean(tmp_path, run):
    assert check(tmp_path, run, env=P_ENV) == []


def test_only_the_log_prints_of_a_heredoc_redirected_elsewhere_are_read(tmp_path):
    # Its stdout goes to a file: those prints aren't log lines; its stderr
    # prints are, read strictly.
    run = 'python3 - <<\'PY\' > out.txt\nimport os, sys\np = os.environ["P"]\nprint("x " + p)\nPY'
    assert check(tmp_path, run, env=P_ENV) == []
    shutil.rmtree(tmp_path / ".github")
    run = ('python3 - <<\'PY\' > out.txt\nimport os, sys\np = os.environ["P"]\n'
           'print("x " + p); print("y " + p, file=sys.stderr)\nPY')
    assert check(tmp_path, run, env=P_ENV) == ['"y " + p']


TOTAL_PY = ("python3 - <<'PY'\nimport os, re, sys\ntotal = len(os.environ[\"P\"])\np = os.environ[\"P\"]\n"
            "{}\nPY")


@pytest.mark.parametrize("line, expected", [
    ('print("x", total, file=sys.stderr)', []),
    ('print("x", total[0], int(total), file=sys.stderr)', ["int"]),
    # A dotted name is named as written, as it always was.
    ('print("x", total.real, file=sys.stderr)', ["total.real"]),
    ('print(f"x {total}", file=sys.stderr)', []),
    ('print("x", total + p, file=sys.stderr)', ["total + p"]),
    ('print("x", total % p, file=sys.stderr)', ["total % p"]),
    ('print("x", total or p, file=sys.stderr)', ["total or p"]),
    ('print("x", total if p else 0, file=sys.stderr)', ["total if p else 0"]),
    ('print("x", total == p, file=sys.stderr)', ["total == p"]),
    ('print("x", total[0] | p, file=sys.stderr)', ["total[0] | p"]),
    ('print(f"x {total + p}", file=sys.stderr)', ["total + p"]),
    # A string prefix is no name: the f-string and what follows it are named whole.
    ('print("x", f"{total}" + p, file=sys.stderr)', ['f"{total}" + p']),
])
def test_an_operator_expression_is_named_whole_not_by_its_first_name(tmp_path, line, expected):
    # An entry for `total` covers `total` and accesses of it, not an
    # expression it merely starts: `total + p` prints the unmasked `p` (#511 review).
    entry = guard.Allowed(REL, "total", step="Step", reason="a number")
    write(tmp_path, REL, workflow(TOTAL_PY.format(line), env=P_ENV))
    assert [n for _, n in names(tmp_path, [entry])] == expected


@pytest.mark.parametrize("expr, name", [
    ("x", "x"),
    ("a.b", "a.b"),
    ("x[0]", "x"),
    ("f(x)", "f"),
    ("a.b(c)[1].d", "a.b"),
    ("x + p", "x + p"),
    ("x.y - p", "x.y - p"),
    ('f"v" + x', 'f"v" + x'),
    ('"{}".format(x)', '"{}".format(x)'),
    ("not x", "not x"),
    ("x(", "x("),
])
def test_expr_name(expr, name):
    assert guard.expr_name(expr) == name


def test_a_log_entry_names_a_bare_value_on_a_strict_line(tmp_path):
    entry = guard.Allowed(REL, "p", reason="test")
    run = LOG_PY.format('print("ok"); print("x", p)')
    write(tmp_path, REL, workflow(run, env=P_ENV))
    assert names(tmp_path, [entry]) == []
    assert names(tmp_path) == [(15, "p")]


@pytest.mark.parametrize("text, lang, leads", [
    ('print(shown(p))', "py", True),
    ('print(f"{shown(p)}")', "py", True),
    ('print(f"  {shown(p)}")', "py", True),
    ('print(f"ok\\n{shown(p)}")', "py", True),
    ('print(f"ok\\x0a {shown(p)}")', "py", True),
    ('print("ok\\n" + shown(p))', "py", True),
    ('print("" + shown(p))', "py", True),
    ('print("%s x" % shown(p))', "py", True),
    ('print("{} x".format(shown(p)))', "py", True),
    ('print("", shown(p))', "py", True),
    ('print("ok", shown(p), sep="\\n")', "py", True),
    ('sys.stderr.write(shown(p))', "py", True),
    ('raise SystemExit(f"{shown(p)}")', "py", True),
    ('console.log(shown(p))', "js", True),
    ('console.log(`ok\\n${shown(p)}`)', "js", True),
    ('console.log("%s", shown(p))', "js", True),
    ('console.log("ok\\n" + shown(p))', "js", True),
    ('print(f"x {shown(p)}")', "py", False),
    ('print("x", shown(p))', "py", False),
    ('print("x " + shown(p))', "py", False),
    ('print("x %s" % shown(p))', "py", False),
    ('print("x {}".format(shown(p)))', "py", False),
    ('print(f"{{literal}} {shown(p)}")', "py", False),
    ('print(r"x\\n" + shown(p))', "py", False),
    ('print("ok", shown(p), sep=" - ")', "py", False),
    ('print(f"ok\\n  - {shown(p)}")', "py", False),
    ('print()', "py", False),
    ('console.log(`x ${shown(p)}`)', "js", False),
    ('console.log("x", shown(p))', "js", False),
    ('console.log("x %s", shown(p))', "js", False),
])
def test_the_line_start_rule_reads_every_line_a_print_writes(text, lang, leads):
    calls = guard.print_calls(text, lang)
    assert len(calls) == 1
    assert guard.leading_print(calls[0], lang) is leads


@pytest.mark.parametrize("text, lang, leads", [
    ('print(f"v\\U0000000D{shown(p)}")', "py", True),
    ('print(f"v\\U0000000a{shown(p)}")', "py", True),
    ('print("v\\N{line feed}", shown(p))', "py", True),
    ('print("v\\N{Carriage Return}", shown(p))', "py", True),
    ('print("v\\N{cr}" + shown(p))', "py", True),
    ('print(f"v\\N{LINE FEED}{shown(p)}")', "py", True),
    ('print("v\\N{BULLET}", shown(p))', "py", False),
    ('print(f"v\\N{BULLET} {shown(p)}")', "py", False),
    ('print("v\\N{NO SUCH NAME}", shown(p))', "py", False),
    ('print(r"v\\N{LINE FEED}", shown(p))', "py", False),
    ('print(r"v\\U0000000A", shown(p))', "py", False),
    # Not escapes of JavaScript: `"\U0000000A"` is `U0000000A`.
    ('console.log("v\\U0000000A", shown(p))', "js", False),
    ('console.log("v\\N{LINE FEED}", shown(p))', "js", False),
])
def test_the_line_start_rule_reads_python_s_long_and_named_line_ends(text, lang, leads):
    # Python resolves `\N{...}` in any case and by an alias; `\U0000000a`
    # writes a line end as `\u000a` does (#511 review).
    calls = guard.print_calls(text, lang)
    assert len(calls) == 1
    assert guard.leading_print(calls[0], lang) is leads


@pytest.mark.parametrize("line", [
    'print(f"v\\U0000000D{shown(p)}", file=sys.stderr)',
    'print("v\\N{line feed}", shown(p))',
    'print("v\\N{NEW LINE}", shown(p))',
    'print("v\\N{EOL}", shown(p))',
    'print("v\\N{END OF LINE}", shown(p))',
    'print("v\\N{nl}", shown(p))',
    'print("v\\N{carriage return}", shown(p))',
    # The braces of a named character are no field: not a value `LINE`.
    'print(f"v\\N{LINE FEED}{shown(p)}")',
])
def test_a_long_or_named_line_end_escape_starts_a_line(tmp_path, line):
    assert check(tmp_path, LOG_PY_SHOWN.format(line), env=P_ENV) == [guard.LEADING]


@pytest.mark.parametrize("line, expected", [
    ('print(f"v {shown(p)}")', []),
    ('print(f"v\\N{BULLET} {shown(p)}")', []),
    ('print("v\\N{BULLET}", shown(p))', []),
    # A literal built by concatenation is refused as before, whole.
    ('print("v\\N{BULLET} " + "x")', ['"v\\N{BULLET} " + "x"']),
    # A raw f-string's `\N{p}` is a field `p`, as is one after an escaped backslash.
    ('print(rf"v \\N{p}")', ["p"]),
    ('print(f"v \\\\N{p}")', ["p"]),
])
def test_a_named_character_that_is_no_line_end_is_no_finding(tmp_path, line, expected):
    assert check(tmp_path, LOG_PY_SHOWN.format(line), env=P_ENV) == expected


@pytest.mark.parametrize("text, exprs", [
    ('f"v\\N{LINE FEED}{x}"', ["x"]),
    ('f"v\\N{bullet} {x}"', ["x"]),
    ('rf"v\\N{x}"', ["x"]),
    ('f"v\\\\N{x}"', ["x"]),
    ('"a\\N{LF}" + f"{x}"', ["x"]),
])
def test_template_exprs_skip_a_named_character(text, exprs):
    assert guard.template_exprs(text, "py") == exprs


@pytest.mark.parametrize("line", [
    'print(b"\\N{", f"{p}")',
    'print(b"\\N{", f"{p}", "}")',
    'print(b"\\N{", f"x{p}x}")',
    'print(B"\\N{", f"{p}")',
    'print(rb"\\N{", f"{p}")',
    'print(Rb"\\N{", f"{p}")',
    # A quote before the `}` ends the literal: no named character.
    'print("\\N{", f"{p}")',
])
def test_a_bytes_literal_s_backslash_n_brace_hides_no_field(tmp_path, line):
    # `b"\N{"` is a backslash, an `N` and a `{` (bytes have no named
    # characters), so the f-string after it is read; at runtime it prints p.
    assert check(tmp_path, LOG_PY.format(line), env=P_ENV) != []


@pytest.mark.parametrize("text, spans", [
    ('b"\\N{" + f"{x}"', {}),
    ('B"\\N{" + f"{x}"', {}),
    ('rb"\\N{" + f"{x}"', {}),
    ('br"\\N{" + f"{x}"', {}),
    ('"\\N{" + f"{x}"', {}),
    ('f"\\N{A\\"}{x}"', {}),
    ('f"\\N{LINE FEED}" + f"{x}"', {4: 15}),
])
def test_a_named_character_ends_within_its_literal_and_not_in_bytes(text, spans):
    # Where it is no escape its `{` is read as a field, so `x` is read.
    assert guard.named_escapes(text) == spans
    assert any("x" in e for e in guard.template_exprs(text, "py"))


@pytest.mark.parametrize("field, expr", [
    ("x=", "x"),
    ("x = ", "x"),
    ("x=!r", "x"),
    ("x = !r", "x"),
    ("x=:>8", "x"),
    ("d['k']=", "d['k']"),
    ("a == b", "a == b"),
    ("a <= b", "a <= b"),
    ("a >= b", "a >= b"),
    ("a != b", "a != b"),
    ("x!r", "x"),
    ("x:>8", "x"),
])
def test_a_self_documenting_field_is_named_by_its_expression(field, expr):
    assert guard.field_expr(field) == expr


def test_an_allowed_name_covers_its_self_documenting_field(tmp_path):
    run = LOG_PY.format('x = os.environ["X"]\nprint(f"{x=}", file=sys.stderr)')
    write(tmp_path, REL, workflow(run, env=P_ENV))
    entry = guard.Allowed(REL, "x", reason="a number")
    # `{x=}` prints `x=` before the value: the line starts with text.
    assert names(tmp_path, [entry]) == []
    run = LOG_PY.format('x = os.environ["X"]\nprint(f"{x=}{p}")')
    write(tmp_path, REL, workflow(run, env=P_ENV))
    assert [n for _, n in names(tmp_path, [entry])] == ["p"]


@pytest.mark.parametrize("text, lang, leads", [
    ('print(p, b"ok\\N{LINE FEED}")', "py", True),
    ('print(b"ok\\N{LINE FEED}", shown(p))', "py", False),
    ('print(b"ok\\N{LINE FEED}" + shown(p))', "py", False),
    ('print(B"ok\\N{CARRIAGE RETURN}", shown(p))', "py", False),
    ('print("ok\\N{LINE FEED}", shown(p))', "py", True),
    ('print(b"ok\\n", shown(p))', "py", True),
])
def test_a_bytes_literal_s_backslash_n_is_no_line_end(text, lang, leads):
    # Bytes have no named characters: `b"\N{LINE FEED}"` is that text. A
    # first value starts the line as ever (`print(p, ...)`).
    calls = guard.print_calls(text, lang)
    assert len(calls) == 1
    assert guard.leading_print(calls[0], lang) is leads


def test_a_bytes_named_character_starts_no_line_in_a_workflow(tmp_path):
    assert check(tmp_path, LOG_PY_SHOWN.format('print(b"ok\\N{LINE FEED}", shown(p))'), env=P_ENV) == []
    shutil.rmtree(tmp_path / ".github")
    assert check(tmp_path, LOG_PY_SHOWN.format('print("ok\\N{LINE FEED}", shown(p))'), env=P_ENV) == [guard.LEADING]


def test_the_line_start_rule_holds_for_every_print_on_a_line(tmp_path):
    run = LOG_PY_SHOWN.format('print("ok"); print(shown(p))')
    assert check(tmp_path, run, env=P_ENV) == [guard.LEADING]
    shutil.rmtree(tmp_path / ".github")
    run = LOG_JS_SHOWN.format('console.log("ok"); console.error(`${shown(p)}`);')
    assert check(tmp_path, run, env=P_ENV) == [guard.LEADING]


SHOWN_PY = f"python3 - <<'PY'{{}}\nimport os, re, sys\n{PY_HELPER}p = os.environ[\"P\"]\n{{}}\nPY"


@pytest.mark.parametrize("opener", ["", " > /tmp/o", ' >> "$GITHUB_OUTPUT"'])
@pytest.mark.parametrize("line", [
    'def shown(v): print(f"x {p}", file=sys.stderr)',
    'def shown(v): raise SystemExit(f"x {p}")',
])
def test_a_line_that_only_starts_like_the_helper_hides_no_print(tmp_path, opener, line):
    # A line starting `def shown(` is not the helper's definition: the log
    # prints on it are read (develop read them; #511's first cut skipped them).
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == ["p"]


@pytest.mark.parametrize("opener", ["", ' >> "$GITHUB_OUTPUT"'])
def test_a_stdout_print_on_a_helper_like_line_is_read(tmp_path, opener):
    assert check(tmp_path, SHOWN_PY.format(opener, 'def shown(v): print(f"x {p}")'), env=P_ENV) == ["p"]


@pytest.mark.parametrize("opener", ["", " > /tmp/o", ' >> "$GITHUB_OUTPUT"', ' >> "$GITHUB_STEP_SUMMARY"'])
def test_the_canonical_helper_definition_is_no_finding(tmp_path, opener):
    assert check(tmp_path, SHOWN_PY.format(opener, "pass"), env=P_ENV) == []
    shutil.rmtree(tmp_path / ".github")
    # A definition other than the canonical one doesn't define the mask.
    run = SHOWN_PY.format(opener, 'print(f"x {shown(p)}", file=sys.stderr)').replace(
        "def shown(value):", "def shown(value):  # masked")
    assert check(tmp_path, run, env=P_ENV) == ["shown"]


UNKNOWN_FILES = [
    "file=sys.stderr if p else sys.stdout",
    "file=stderr",
    "file=err",
    "file=open(2, 'w')",
    'file=open("/dev/stderr", "w")',
    "file=open(os.environ['GITHUB_OUTPUT'], 'a')",
]
STREAM_PRELUDE = "from sys import stderr\nerr = sys.stderr\n"


def opened(file_: str) -> list[str]:
    """A heredoc that names an env file is refused on its own as well (#513)."""
    return [guard.ENV_FILE_OPENED] if "GITHUB_OUTPUT" in file_ else []


@pytest.mark.parametrize("opener", ["", ' >> "$GITHUB_OUTPUT"'])
@pytest.mark.parametrize("file_", ["file=sys.__stderr__", "file=sys.__stdout__", "file=(sys.stderr)",
                                   "file=( sys.stdout )", *UNKNOWN_FILES])
def test_a_print_to_a_stream_the_guard_cant_rule_out_is_read(tmp_path, opener, file_):
    # Fails closed (#511): no `file=` escapes the reading. Develop read every
    # `file=` but sys.stderr as stdout; the first cut of #511 dropped every
    # one but sys.stdout/sys.stderr.
    line = f'{STREAM_PRELUDE}print(f"x {{p}}", {file_})'
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == ["p", *opened(file_)]


@pytest.mark.parametrize("file_", UNKNOWN_FILES)
def test_an_unknown_stream_of_an_env_file_heredoc_is_read_both_ways(tmp_path, file_):
    # It may be the entry's stdout or the log's stderr: both readings take it.
    run = SHOWN_PY.format(' >> "$GITHUB_OUTPUT"', f'{STREAM_PRELUDE}print(p, {file_})')
    write(tmp_path, REL, workflow(run, env=P_ENV))
    [body] = guard.bodies_of(tmp_path, tmp_path / REL)
    checker = guard.Checker(body, [body], (), set())
    [k] = [k for k, u in enumerate(checker.units) if u.text.startswith("print(")]
    assert checker.envfile_template(k) == ["p"]
    assert checker.log_template(k) == ["p"]
    assert checker.leading_print(k)
    assert [n for _, n in names(tmp_path)] == ["p", guard.LEADING, *opened(file_)]


def test_an_unknown_stream_of_a_summary_heredoc_is_read_both_ways(tmp_path):
    run = SHOWN_PY.format(' >> "$GITHUB_STEP_SUMMARY"', f'{STREAM_PRELUDE}print(f"x {{p}}", file=err)')
    write(tmp_path, REL, workflow(run, env=P_ENV))
    messages = [f["message"] for f in guard.audit(tmp_path, ())[0]]
    assert len(messages) == 2
    assert any("log line" in m for m in messages) and any("step-summary" in m for m in messages)


OWN_FILE = 'open("/tmp/o", "w")'


@pytest.mark.parametrize("opener", ["", " > /tmp/o", ' >> "$GITHUB_OUTPUT"'])
@pytest.mark.parametrize("line", [
    'print(f"x {p}", file=open("/tmp/f", "w"))',
    'print(f"x {p}", file=io.open("/tmp/f", "w"))',
    'f = open("/tmp/f", "w")\nprint(f"x {p}", file=f)',
    'with open("/tmp/f", "w") as out:\n    print(f"x {p}", file=out)',
    'with open("/tmp/a") as src, open("/tmp/f", "w") as out:\n    print(f"x {p}", file=out)',
])
def test_a_print_to_a_file_the_heredoc_opens_is_read(tmp_path, opener, line):
    # Refused although harmless (#511): the guard can't tell a file of the
    # heredoc's own from a standard stream, so it reads the print as both.
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == ["p"]


def test_a_print_to_a_file_the_heredoc_opens_is_a_summary_line_too(tmp_path):
    line = f'print(f"x {{p}}", file={OWN_FILE})'
    write(tmp_path, REL, workflow(SHOWN_PY.format(' >> "$GITHUB_STEP_SUMMARY"', line), env=P_ENV))
    messages = [f["message"] for f in guard.audit(tmp_path, ())[0]]
    assert len(messages) == 2
    assert any("log line" in m for m in messages) and any("step-summary" in m for m in messages)


@pytest.mark.parametrize("opener", ["", ' >> "$GITHUB_OUTPUT"'])
@pytest.mark.parametrize("line", [
    f'print(f"x {{shown(p)}}", file={OWN_FILE})',
    f'f = {OWN_FILE}\nprint(f"x={{shown(p)}}", file=f)',
    f'f = {OWN_FILE}\nf.write(shown(p))',
])
def test_a_masked_value_into_a_file_the_heredoc_opens_is_clean(tmp_path, opener, line):
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == []


@pytest.mark.parametrize("opener", ["", " > /tmp/o", ' >> "$GITHUB_OUTPUT"', ' >> "$GITHUB_STEP_SUMMARY"'])
def test_a_write_to_a_file_the_heredoc_opens_is_not_read(tmp_path, opener):
    # Not covered, as on develop: a write that isn't a named print isn't read.
    assert check(tmp_path, SHOWN_PY.format(opener, f'f = {OWN_FILE}\nf.write(p)'), env=P_ENV) == []


@pytest.mark.parametrize("line", [
    # A path that names a standard stream after all.
    'print(f"x {p}", file=open("//dev/stdout", "w"))',
    'print(f"x {p}", file=open("/./dev/stderr", "w"))',
    'print(f"x {p}", file=open("../../../../dev/stderr", "w"))',
    'os.chdir("/")\nprint(f"x {p}", file=open("dev/stderr", "w"))',
    'print(f"x {p}", file=open(rb"/dev/stderr", "w"))',
    'print(f"x {p}", file=open("/\\x64ev/stderr", "w"))',
    'print(f"x {p}", file=open("/tmp/o", "w", opener=lambda a, b: 2))',
    # A name bound to a file, rebound to a stream.
    f'f = {OWN_FILE}\nx = 1; f = sys.stderr\nprint(f"x {{p}}", file=f)',
    f'f = {OWN_FILE}\ng = lambda f=sys.stderr: print(f"x {{p}}", file=f)\ng()',
    f'f = {OWN_FILE}\nmatch sys.stderr:\n    case f:\n        print(f"x {{p}}", file=f)',
    f'f = {OWN_FILE}\ndef g(\n    f,\n):\n    print(f"x {{p}}", file=f)\ng(sys.stderr)',
    f'f = {OWN_FILE}\ndef g(\n    f=sys.stderr,\n):\n    print(f"x {{p}}", file=f)\ng()',
    f'f = {OWN_FILE}\nexec("f = sys.stderr")\nprint(f"x {{p}}", file=f)',
    f'f = {OWN_FILE}\nglobals().update(f=sys.stderr)\nprint(f"x {{p}}", file=f)',
    f'f = {OWN_FILE}\nsetattr(sys.modules[__name__], "f", sys.stderr)\nprint(f"x {{p}}", file=f)',
    # Names bound otherwise, as the first cut of #511 already refused.
    f'f = {OWN_FILE}\nf = sys.stderr\nprint(f"x {{p}}", file=f)',
    f'f = {OWN_FILE}\nif p:\n    f, g = sys.stderr, 1\nprint(f"x {{p}}", file=f)',
    'from sys import stderr as out\nwith open("/tmp/f", "w") as out:\n    print(f"x {p}", file=out)',
    'f = open(f"/dev/{p}", "w")\nprint(f"x {p}", file=f)',
    'f = open("/proc/self/fd/2", "w")\nprint(f"x {p}", file=f)',
])
def test_a_file_that_may_be_a_stream_is_read(tmp_path, line):
    # The bypasses of an "own file" exception (#511): every one reaches the log.
    assert check(tmp_path, SHOWN_PY.format("", line), env=P_ENV) == ["p"]


@pytest.mark.parametrize("line, name", [
    (f'print(print("x", p), file={OWN_FILE})', "print"),
    (f'print(sys.stderr.write(p), file={OWN_FILE})', "sys.stderr.write"),
    (f'print(f"{{print(p)}}", file={OWN_FILE})', "print"),
])
def test_a_print_nested_in_a_print_to_a_file_is_read(tmp_path, line, name):
    # The inner print reaches the log whatever the outer one's file is.
    assert check(tmp_path, SHOWN_PY.format("", line), env=P_ENV) == [name, guard.LEADING]


def test_a_print_to_a_stream_path_reaches_an_env_file_unmasked(tmp_path):
    # `//dev/stdout` is the heredoc's stdout: the env file.
    run = SHOWN_PY.format(' >> "$GITHUB_OUTPUT"', 'print(f"x={p}", file=open("//dev/stdout", "w"))')
    assert check(tmp_path, run, env=P_ENV) == ["p"]


@pytest.mark.parametrize("value, stream", [
    ("sys.stdout", "stdout"), ("sys.__stdout__", "stdout"), ("( sys.stdout )", "stdout"),
    ("sys.stderr", "stderr"), ("sys.__stderr__", "stderr"), ("((sys.stderr))", "stderr"),
    ('open("out.txt", "w")', "unknown"), ("io.open('out.txt')", "unknown"), ("out", "unknown"),
    ("err", "unknown"), ("stderr", "unknown"), ("sys.stderr if c else sys.stdout", "unknown"),
    ("open(2, 'w')", "unknown"), ('open("/dev/stdout", "w")', "unknown"), ('open(path, "w")', "unknown"),
    ('open("a").buffer', "unknown"), ("(sys.stderr).buffer", "unknown"),
])
def test_file_stream(value, stream):
    assert guard.file_stream(value) == stream


@pytest.mark.parametrize("opener", [" > /tmp/o", ' >> "$GITHUB_OUTPUT"', ' >> "$GITHUB_STEP_SUMMARY"'])
@pytest.mark.parametrize("call", [
    'print(\n    f"x {p}",\n    file=sys.stderr)',
    'print("x",\n      p,\n      file=sys.stderr)',
    'print("x", p,\n      end="\\n", file=sys.stderr)',
    'print("x",\n      p,\n      file=sys.__stderr__)',
    'print("x",\n      p,\n      file=err)',
])
def test_a_stderr_file_on_a_continuation_line_makes_the_call_a_log_line(tmp_path, opener, call):
    # The stream is read from the joined call, not from its first line (#511):
    # the call is a log line whatever the heredoc's stdout does.
    run = SHOWN_PY.format(opener, f"err = sys.stderr\n{call}")
    write(tmp_path, REL, workflow(run, env=P_ENV))
    log = [f for f in guard.audit(tmp_path, ())[0] if "log line or env-file" in f["message"]]
    [body] = guard.bodies_of(tmp_path, tmp_path / REL)
    first = body.first_line + next(u.index for u in guard.Checker(body, [body], (), set()).units
                                   if u.text.startswith("print("))
    assert [(f["line"], f["message"].split("`")[1]) for f in log if f["line"] == first] == [(first, "p")]


@pytest.mark.parametrize("opener", [" > /tmp/o", ' >> "$GITHUB_OUTPUT"'])
def test_a_masked_stderr_call_over_lines_stays_clean(tmp_path, opener):
    call = 'print("x",\n      shown(p),\n      file=sys.stderr)'
    assert check(tmp_path, SHOWN_PY.format(opener, call), env=P_ENV) == []
    shutil.rmtree(tmp_path / ".github")
    # Its stdout twin into a file is no log line.
    call = 'print("x",\n      p,\n      file=sys.stdout)'
    assert check(tmp_path, SHOWN_PY.format(" > /tmp/o", call), env=P_ENV) == []


def test_a_print_inside_a_string_literal_is_refused_although_harmless(tmp_path):
    # Documented under "Refused although harmless": calls are found by name.
    assert check(tmp_path, SHOWN_PY.format("", 'msg = "use print(p)"'), env=P_ENV) == ["p", guard.LEADING]


TRIPLE_QUOTED_STDERR = [
    "print(p, end='''it's''', file=sys.stderr)",
    'print(p, end="""it"s""", file=sys.stderr)',
    "print(p, sep='''it's''', file=sys.stderr)",
    "print(p, end=f'''it's''', file=sys.stderr)",
    "print(p, end=rb'''it's''', file=sys.stderr)",
    "print(p, end='''it's\n''', file=sys.stderr)",
]


@pytest.mark.parametrize("opener", [" > f.txt", " | cat"])
@pytest.mark.parametrize("line", TRIPLE_QUOTED_STDERR)
def test_a_triple_quoted_argument_does_not_hide_a_stderr_file(tmp_path, opener, line):
    # A quote inside a Python triple quote left the scan in an open quote
    # (#511): the call read as unclosed, `file=sys.stderr` as part of `end=`,
    # and the print as a stdout one into the heredoc's file. Develop read it.
    assert check(tmp_path, LOG_PY.replace("<<'PY'", "<<'PY'" + opener).format(line), env=P_ENV)[0] == "p"


@pytest.mark.parametrize("line, expected", [
    ("print(f\"x {p}\", '''it's''', file=sys.stderr)", ["p"]),
    ("print(shown(p), end='''it's''', file=sys.stderr)", [guard.LEADING]),
])
def test_a_triple_quoted_argument_keeps_its_call_a_stderr_print(tmp_path, line, expected):
    assert check(tmp_path, SHOWN_PY.format(" > f.txt", line), env=P_ENV) == expected


@pytest.mark.parametrize("opener", ["", " > f.txt", ' >> "$GITHUB_OUTPUT"'])
@pytest.mark.parametrize("line", [
    "print(f\"x {shown(p)}\", end='''it's''', file=sys.stderr)",
    "print('''it's a \"quote\"''', file=sys.stderr)",
    "print(f'''it's {shown(p)}''', file=sys.stderr)",
    "print(\"x\", '''it's''', sep=\"\"\" \"\"\", file=sys.stderr)",
])
def test_a_masked_or_literal_triple_quoted_stderr_print_is_clean(tmp_path, opener, line):
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == []


def test_a_pure_triple_quoted_literal_log_print_is_clean(tmp_path):
    assert check(tmp_path, LOG_PY.format("print(f'''it's''')"), env=P_ENV) == []


@pytest.mark.parametrize("text, close", [
    ("print(p, end='''it's''', file=sys.stderr) # x", 41),
    ('print(p, end="""a"b""")', 23),
    ("print(p, end='''it's", None),
    ("print('''a)''')", 15),
])
def test_call_close_reads_triple_quotes(text, close):
    assert guard.call_close(text, len("print(")) == close


def test_call_args_reads_triple_quotes():
    text = "print(p, end='''it's, (''', file=sys.stderr)"
    assert guard.call_args(text, len("print(")) == ["p", "end='''it's, ('''", "file=sys.stderr"]
    assert guard.bracket_state("print('''a\n", len("print(")) == (1, "'''")
    # Carried over a continuation line: a lone `'` doesn't end it, `'''` does.
    assert guard.bracket_state("it's\nb'''), x", 0, 1, "'''") == (0, None)


UNCLOSED = "print(p,\n" + '      "x",\n' * (guard.JOINED_LINES + 1) + "      file=sys.stderr)"


@pytest.mark.parametrize("opener", [" > f.txt", " | cat"])
def test_a_print_not_closed_in_the_joined_text_reaches_the_log(tmp_path, opener):
    # Fails closed (#511): its `file=` may sit past the lines joined, so it is
    # read as both streams, never as a stdout print into the heredoc's file.
    assert check(tmp_path, LOG_PY.replace("<<'PY'", "<<'PY'" + opener).format(UNCLOSED), env=P_ENV) == [
        "p", guard.LEADING]


def test_a_print_not_closed_in_the_joined_text_is_read_both_ways_in_an_env_file_heredoc(tmp_path):
    run = SHOWN_PY.format(' >> "$GITHUB_OUTPUT"', UNCLOSED)
    write(tmp_path, REL, workflow(run, env=P_ENV))
    [body] = guard.bodies_of(tmp_path, tmp_path / REL)
    checker = guard.Checker(body, [body], (), set())
    k = next(k for k, u in enumerate(checker.units) if u.text.startswith("print("))
    [call] = guard.print_calls(checker.joined(k), "py")
    assert call.unknown and call.read_by(True, False) and call.read_by(False, True)
    assert checker.envfile_template(k) == ["p"]
    assert checker.log_template(k) == ["p"]


@pytest.mark.parametrize("opener", [" > f.txt", " | cat", ' >> "$GITHUB_OUTPUT"'])
@pytest.mark.parametrize("line", [
    'print(p, **{"file": sys.stderr})',
    'kw = {"file": sys.stderr}\nprint(p, **kw)',
    'print(p,\n      **kw)',
])
def test_a_spread_keyword_argument_makes_the_stream_unknown(tmp_path, opener, line):
    # Fails closed (#511): `**` may carry any `file=`, so the call reaches the
    # log whatever the heredoc's stdout does.
    run = LOG_PY.replace("<<'PY'", "<<'PY'" + opener).format(line)
    write(tmp_path, REL, workflow(run, env=P_ENV))
    [body] = guard.bodies_of(tmp_path, tmp_path / REL)
    checker = guard.Checker(body, [body], (), set())
    k = next(k for k, u in enumerate(checker.units) if u.text.startswith("print("))
    [call] = guard.print_calls(checker.joined(k), "py")
    assert call.unknown
    assert "p" in checker.log_template(k)
    assert guard.main(["--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("opener, line", [
    (" > f.txt", 'print(f"{d[")"]}", p, file=sys.stderr)'),
    (" > f.txt", "print(\"x\", f\"{'''\")'''}\", p, file=sys.stderr)"),
    (" | cat", 'print("x", f"{")"}", p, file=sys.stderr)'),
    (" > f.txt", 'print("x", f"{shown(")")}", p, file=sys.stderr)'),
])
def test_a_same_quote_f_string_field_makes_the_stream_unknown(tmp_path, opener, line):
    # Fails closed (#511): since Python 3.12 (PEP 701) a replacement field may
    # hold the f-string's own quote; the scan ends the f-string there, closes
    # the call early and loses `file=sys.stderr`. Such a call reaches the log.
    run = SHOWN_PY.format(opener, line)
    write(tmp_path, REL, workflow(run, env=P_ENV))
    [body] = guard.bodies_of(tmp_path, tmp_path / REL)
    checker = guard.Checker(body, [body], (), set())
    k = next(k for k, u in enumerate(checker.units) if u.text.startswith("print("))
    [call] = guard.print_calls(checker.joined(k), "py")
    assert call.unknown and call.read_by(True, False) and call.read_by(False, True)
    assert checker.log_template(k)
    assert guard.main(["--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("text, found", [
    ('print(f"{d[")"]}", p)', True),
    ("print(f'{d[')']}')", True),
    ("print(f\"{'''\")'''}\")", True),
    ("print(F\"{x}\", rf\"{d[\"k\"]}\")", True),
    ('print(f"""{d[""\"k""\"]}""")', True),
    ("print(f\"{d['k']}\")", False),
    ('print(f"""{"a"}""")', False),
    ('print(f"{{")', False),
    ('print(f"{{)}}", p)', False),
    ('print(f"x {shown(p)!r:>{9}}")', False),
    ("print(f'x {shown(p)} \"q\"')", False),
    ('print("{" + p + "}")', False),
    ('print(b"{\\"}")', False),
])
def test_same_quote_field_finds_only_the_pep_701_form(text, found):
    assert guard.same_quote_field(text, len("print("), len(text)) is found


@pytest.mark.parametrize("text, found", [
    ('print(t"{d[")"]}", p)', True),
    ('print(rt"{d[")"]}", p)', True),
    ('print(rf"\\{d[")"]}", p)', True),
    ('print(Rf"\\{d[")"]}", p)', True),
    ('print(f"\\{d[")"]}", p)', True),
    ("print(t\"{d['k']}\")", False),
    ('print(f"\\N{LINE FEED}", p)', False),
    ('print(rb"\\{")', False),
])
def test_same_quote_field_reads_t_strings_and_a_backslash_before_a_field(text, found):
    # PEP 750 t-strings take fields as f-strings do, and a `\{` opens one
    # all the same, in a raw f-string too; `\N{...}` is a named escape.
    assert guard.same_quote_field(text, len("print("), len(text)) is found


@pytest.mark.parametrize("lines", [
    ['d = {")": 1}', 'print(rf"\\{d[")"]}", p, file=sys.stderr)'],
    ['d = {")": 1}', 'print(fr"x\\{d[")"]}", p, file=sys.stderr)'],
    ['d = {")": 1}', 'print(Rf"\\{d[")"]}", p, file=sys.stderr)'],
    ["d = {')': 1}", "print(rf'\\{d[')']}', p, file=sys.stderr)"],
    ['d = {")": 1}', 'print(f"\\{d[")"]}", p, file=sys.stderr)'],
    ['d = {")": 1}', 'print(t"{d[")"]}", p, file=sys.stderr)'],
    ['d = {")": 1}', 'print(rt"{d[")"]}", p, file=sys.stderr)'],
    ['d = {")": 1}', 'print(f"{1 # }', ' + d[")"]}", p, file=sys.stderr)'],
    ['print("see stderr:", p)'],
    ['print(p)  # file=sys.stderr'],
    ['print(p, "stderr", file=sys.stdout)'],
])
def test_a_print_whose_text_names_stderr_or_file_reaches_the_log(tmp_path, lines):
    # The text backstop (#511): where the parse loses `file=sys.stderr` -- a
    # `\{` in a raw f-string, a t-string, a `}` in a comment inside a field
    # -- or the text names `stderr` or `file=` beside a stdout call, the
    # call is read as reaching the log, whatever the heredoc's stdout does.
    # `print("see stderr:", p)` into a file is harmless, refused fail-closed.
    run = SHOWN_PY.format(" > f.txt", "\n".join(lines))
    assert check(tmp_path, run, env=P_ENV) != []
    assert guard.main(["--root", str(tmp_path)]) == 1


@pytest.mark.parametrize("line", [
    'print(f"x {shown(p)}", file=sys.stderr)',
    'print(t"x {shown(p)}", file=sys.stderr)',
    'print("x", file=sys.stderr)',
    'print(p)',
    'print("no stderr here", end="")',
    'print("see stderr")',
    'print("a", p, file=sys.stdout)',
    'print(p); print("x", file=sys.stderr)',
    'stderr_note = 1\nprint(p, stderr_note)',
])
def test_the_text_backstop_leaves_clean_prints_clean(tmp_path, line):
    # A stdout print into a file is not a log line; the backstop only reads
    # text up to the next print after a `;`, and a literal stays clean.
    assert check(tmp_path, SHOWN_PY.format(" > f.txt", line), env=P_ENV) == []


def test_the_text_backstop_takes_the_text_past_a_misread_close_as_a_value():
    text = 'print(f"{1 # }\n + d[")"]}", p, file=sys.stderr)'
    [call] = guard.print_calls(text, "py")
    assert call.unknown and call.end == len(text)
    assert call.args[-1] == '"]}", p, file=sys.stderr)'


@pytest.mark.parametrize("line", [
    'kw = {"file": sys.stderr}\nprint(p, \\\n      **kw)',
    "print(p, \\\n  file=sys.stderr)",
])
def test_a_keyword_on_a_continued_line_is_read(tmp_path, line):
    # A backslash continuation left `\` and the line end in front of the
    # argument (#511), so neither `**kw` nor `file=` was seen as such and the
    # stderr print counted as a stdout one into the heredoc's file.
    assert "p" in check(tmp_path, LOG_PY.replace("<<'PY'", "<<'PY' > f.txt").format(line), env=P_ENV)


def test_call_args_reads_a_line_continuation_as_a_space():
    text = 'print(p, \\\n  file=sys.stderr, \\\n  **kw, end="\\\n")'
    assert guard.call_args(text, len("print(")) == ["p", "file=sys.stderr", "**kw", 'end="\\\n"']


@pytest.mark.parametrize("opener", ["", " > f.txt"])
@pytest.mark.parametrize("line", [
    'print(f"x {shown(p)}", \\\n  file=sys.stderr)',
    'print("a", \\\n  "b", file=sys.stderr)',
    "print(f'x {shown(p)} \"q\"', file=sys.stderr)",
    'print(f"{{)}}", file=sys.stderr)',
])
def test_a_masked_or_literal_continued_or_quoted_stderr_print_is_clean(tmp_path, opener, line):
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == []


def test_a_different_quote_f_string_field_keeps_its_reading(tmp_path):
    line = 'd = {"k": 1}\nprint(f"{d[\'k\']}")'
    assert check(tmp_path, LOG_PY.format(line), env=P_ENV) == ["d", guard.LEADING]
    [call] = guard.print_calls("print(f\"{d['k']}\")", "py")
    assert not call.unknown and not call.to_stderr


# --- #511: a heredoc whose stdout is piped into a command -------------------

PIPED = [" | cat", " |& cat", " | tee out.log", " | jq . > out.json"]


@pytest.mark.parametrize("opener", PIPED)
@pytest.mark.parametrize("line, expected", [
    ('print(f"::warning::{p}")', ["p"]),
    ('print(f"x {p}")', ["p"]),
    ("print(p)", ["p", guard.LEADING]),
    ('sys.stdout.write(f"x {p}\\n")', ["p"]),
])
def test_a_python_heredoc_piped_into_a_command_reads_its_stdout_as_the_log(tmp_path, opener, line, expected):
    # Develop flagged `::warning::` through the literal command on the line;
    # with the strict reading the pipe hid every stdout print. `cat` prints it
    # to the log at runtime, so a pipe is read as the log, failing closed.
    run = LOG_PY.replace("<<'PY'", "<<'PY'" + opener).format(line)
    assert check(tmp_path, run, env=P_ENV) == expected


@pytest.mark.parametrize("opener", [" | cat", " |& cat"])
@pytest.mark.parametrize("line", ["console.log(`::warning::${p}`);", "console.log(`x ${p}`);",
                                  "process.stdout.write(`x ${p}\\n`);"])
def test_a_node_heredoc_piped_into_a_command_reads_its_stdout_as_the_log(tmp_path, opener, line):
    run = LOG_JS.replace("<<'JS'", "<<'JS'" + opener).format(line)
    assert check(tmp_path, run, env=P_ENV) == ["p"]


@pytest.mark.parametrize("opener", PIPED)
@pytest.mark.parametrize("line", [
    'print(f"x {shown(p)}")',
    'print("fixed")',
    'print("::notice::fixed", end="")',
    'sys.stdout.write("x\\n")',
])
def test_a_masked_or_literal_print_piped_into_a_command_is_clean(tmp_path, opener, line):
    assert check(tmp_path, SHOWN_PY.format(opener, line), env=P_ENV) == []


@pytest.mark.parametrize("opener", [" | cat", " |& cat"])
@pytest.mark.parametrize("line", ["console.log(`x ${shown(p)}`);", "console.log('fixed');"])
def test_a_masked_or_literal_node_print_piped_into_a_command_is_clean(tmp_path, opener, line):
    run = LOG_JS_SHOWN.replace("<<'JS'", "<<'JS'" + opener).format(line)
    assert check(tmp_path, run, env=P_ENV) == []


TEE_ENV = ' | tee -a "$GITHUB_OUTPUT"'


def test_a_heredoc_teed_into_an_env_file_is_read_as_the_log_as_well(tmp_path):
    # `tee` writes the env file and its stdout, the log: the entry is read as
    # one (`shown(p)` is clean there) and as a log line, which it begins.
    run = SHOWN_PY.format(TEE_ENV, "print(shown(p))")
    assert check(tmp_path, run, env=P_ENV) == [guard.LEADING]
    write(tmp_path, REL, workflow(run, env=P_ENV))
    [body] = guard.bodies_of(tmp_path, tmp_path / REL)
    checker = guard.Checker(body, [body], (), set())
    k = next(k for k, u in enumerate(checker.units) if u.text.startswith("print("))
    unit = checker.units[k]
    assert unit.dest == "envfile" and unit.piped and unit.stdout_logged()


@pytest.mark.parametrize("line, expected", [
    ('print(f"v={p}")', ["p"]),
    ('print(f"v={shown(p)}")', []),
])
def test_a_raw_entry_teed_into_an_env_file_is_a_finding(tmp_path, line, expected):
    assert check(tmp_path, SHOWN_PY.format(TEE_ENV, line), env=P_ENV) == expected


def test_a_redirected_env_file_heredoc_does_not_read_stdout_as_the_log(tmp_path):
    # The env-file reading alone: no pipe, so stdout isn't the log and a
    # masked entry doesn't begin a log line.
    assert check(tmp_path, SHOWN_PY.format(' >> "$GITHUB_OUTPUT"', "print(shown(p))"), env=P_ENV) == []


def test_a_heredoc_teed_into_the_summary_is_read_as_the_log_as_well(tmp_path):
    run = SHOWN_PY.format(' | tee -a "$GITHUB_STEP_SUMMARY"', 'print(f"x {p}")')
    # Read by the summary rule and by the log rule both.
    assert sorted(check(tmp_path, run, env=P_ENV)) == ["p", "p"]
