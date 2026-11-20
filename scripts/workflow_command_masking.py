#!/usr/bin/env python3
"""Refuse a log line, env-file or step-summary write that carries an unchecked value.

The runner reads every line a step prints as a possible workflow command, in
two syntaxes (actions/runner, src/Runner.Common/ActionCommand.cs, read from
source, not measured on a runner):

  * `::<command> <props>::<data>` -- only when the line, after leading
    whitespace, STARTS with `::` (TryParseV2);
  * `##[<command> <props>]<data>` -- ANYWHERE in the line (TryParse, which
    runs when the first one does not match).

So a value that a caller (`inputs.*`), a draft or API response, or repository
content controls starts a command of its own if it carries a line end followed
by `::warning::...`, or `##[warning]...` without any line end at all. Written
as `name=$value` to `$GITHUB_OUTPUT`, a line end adds an output entry. #491
masked one such line in reusable-release-publish.yml; #492 found the rest of
the class in it and in its siblings. This script refuses the class.

Predicate: EVERY line of a `run:` body that

  * emits a workflow command (it carries `::<command>::` or
    `::<command> <params>::`),
  * writes to `$GITHUB_OUTPUT`, `$GITHUB_ENV`, `$GITHUB_STATE` or
    `$GITHUB_PATH` -- a `{ ...; } >> "$GITHUB_OUTPUT"` group and a heredoc
    written there count line by line -- or
  * prints to the log: a shell `echo`/`printf` statement whose output is not
    piped or redirected to a file, a Python `print(...)`, `raise SystemExit(...)`
    or `sys.stdout/stderr.write(...)`, a Node `console.*(...)` or
    `process.stdout/stderr.write(...)` -- stdout counting only when the
    heredoc's own stdout is not redirected --

and interpolates a value. Each interpolated name must be one of:

  * masked at the print by the canonical helper, which turns control
    characters into `?` and every `##[` into `#?[`: `$(shown "$name")` in
    shell, `shown(...)` in a Python or Node heredoc -- and only where the body
    or heredoc defines `shown` exactly that way (SHELL_SHOWN, PY_SHOWN_RETURN,
    JS_SHOWN);
  * assigned, last before the print, from such a masked expansion;
  * refused earlier in the same body by the canonical check
    `if [[ "$name" == *[[:cntrl:]]* || "$name" == *'##['* ]]; then`, whose
    then-branch holds an `exit` statement at its own level (not in a comment,
    a string, a subshell, a nested block or an else-branch), and with no
    assignment to the name anywhere after the check (a loop could reach one
    before the print);
  * constant by construction: every assignment in the body, or the step's
    `env:` value, is a literal -- or a string built only from literals and
    names that pass this list themselves (a message assembled from a refused
    tag); a command substitution or a `read`/`for`/`mapfile` target never is,
    and `x+=...` counts as an assignment;
  * numeric by construction: `${#name}`, `${#name[@]}`, `len(...)`;
  * on ALLOWED below, whose every entry states why the value is constrained.

Two rules hold per line, whatever its names:

  * a log line must not BEGIN with an interpolated value: the runner trims
    leading whitespace before it looks for `::`, and no mask touches `::`. A
    literal with a non-space character must come first (`echo "x $v"`,
    `printf 'gh: %s'`, `print(f"  - {v}")`); the few lines that start with a
    value are on ALLOWED under the name `<leading value>`, with the reason;
  * `$(shown "...")` must not sit directly next to a literal `#` or `[` or
    another `$(shown "...")`, quotes in between included -- `'#'` followed by
    a masked `#[x` re-forms `##[` (`<mask seam>`).

The step summary is a third sink with its own rule (#506). GitHub renders
`$GITHUB_STEP_SUMMARY` as Markdown, so a controlled value there can add a
link, an image, a heading, a mention or a table cell. Every line whose output
reaches it -- a statement redirected (`>`, `>>`, `>|`) or `tee`d there,
also through `> >(tee ...)` and whatever else the line holds; a statement of
a `{ ...; } >> "$GITHUB_STEP_SUMMARY"` group or of a `for`/`while`/`until`/
`if` compound redirected there as a whole, its opening line included, unless
it sends its own stdout elsewhere; a line of a heredoc written there by a bare
`cat`, or a Python or Node heredoc whose stdout goes there (their stderr
prints stay log lines) -- may interpolate only names that are:

  * encoded and wrapped at the print by the canonical helper, which turns a
    control character into a question mark and every ASCII punctuation
    character into its numeric HTML entity -- `@` followed by an empty HTML
    comment -- inside `<code>` or `<pre>`: `$(md_code "$name")`,
    or `md_code "$name"` / `md_pre "$name"` as a statement of their own, in
    shell; `md_code(...)` / `md_pre(...)` in Python, `mdCode(...)` /
    `mdPre(...)` in Node -- and only where the body or heredoc defines all of
    the helper's lines exactly that way (SHELL_MD, PY_MD, JS_MD), and nothing
    else in it defines, unsets, aliases or rebinds a helper's name;
  * assigned from `$(md_code "$name")`, a constant or such names at EVERY
    assignment in the body -- the last one by line can sit in a branch that
    doesn't run;
  * constant or numeric by construction, as above;
  * on ALLOWED with `sink="summary"`.

`$(shown ...)`, a refusal and a log-sink ALLOWED entry don't count there: none
of them touches Markdown. Nor does the bare encoder `md_enc`: unwrapped,
`@name` and `#1` still link. A statement on such a line must be `echo`,
`printf`, `md_code`/`md_pre` or one that prints nothing (`for`, `[[`, an
assignment, ...); any other command, a pipeline, and a command substitution
other than the helper are a finding named `<command output>`, since what a
command prints is controlled text the guard can't read. In a Python or Node
heredoc, every print call on a line counts: every argument of a stdout print
that is not one plain string literal, Python's `end=` and `sep=`, and every
f-string or template-literal part on the line outside a stderr print must be
a call of the helper. Whether a print goes to stderr is read from its name or
its `file=` argument, never from other text on the line.

A name with no assignment in the body and no `env:` entry -- a runner
variable, a positional parameter -- is a finding unless ALLOWED names it. An
ALLOWED entry that no line needs is reported too, and an entry bound to a check
(`after`, `source`) only holds while that check is a non-comment line, so the
list can't keep a reason after its check is gone.

Selector: every `run:` step of every `.github/workflows/reusable-*.y*ml` and
of every composite action under `actions/` (its `action.y*ml` and the `*.sh`
scripts beside it; files under a directory named exactly `test` are fixtures
and skipped -- `tests/` is scanned), found by walking the files, not from a
list -- a message added to any of them is checked without anyone opting it in.

Not covered (each would need a parser this script doesn't have):

  * what another command prints -- `jq`, `git`, `gh`, `vale`, a script run
    from a file, the output of a `$(...)` substitution (its variables are
    checked, its output is not; #492 found `du` echoing a file name that way)
    -- and a print piped into another command, on a log line (on a summary
    line both are refused as `<command output>`);
  * a leading value the line-start rule can't see: an `echo` whose first word
    is built by a command substitution or a variable holding the whole
    message, and a call site of a helper such as fork-guard's or setup-vale's
    `finish` (both on ALLOWED, read by hand);
  * a refusal that isn't at body level: the canonical `if` inside a function
    that is never called or only called through `$(...)`, inside `( ... )`,
    or inside `if false; then` -- the guard reads it as if it always ran;
    likewise a `break` (or `continue`, `return`) before its `exit`;
  * `##[` re-forming across a seam the seam rule doesn't see: a value masked
    into a variable first (`$shown_x`) and printed next to `#`, `[` or another
    masked value, or a seam built across two `printf` arguments
    (`printf '%s#' ...`);
  * line ends produced after masking: `printf "$(shown "$V")\n"` or
    `printf '%b'` with the masked value in the format, and `echo -e`, turn
    backslash escapes in the value back into control characters;
  * prints the selector doesn't see: `cat <<<"$V"`, `tee` to the log,
    `echo ... > /dev/stderr` or `>/dev/stdout`, `set -x` tracing, an EXIT
    trap or a function that prints and is called elsewhere, `logger`;
  * `unset -f shown` or a later weak redefinition of `shown` after the
    canonical one, and a canonical `shown` that is defined only after its
    first use (the guard checks that the body defines it, not where);
  * on a log line, a masked assignment in a branch that doesn't run: the
    last assignment by line counts there (`x="$V"`, then `x=$(shown "$x")`
    inside `if false`), because reading control flow is out of proportion and
    the straight-line form -- raw, then masked -- is in use
    (actions/setup-vale/setup-vale.sh, finish()); the summary rule reads
    every assignment instead;
  * `shell: python` steps and other non-bash `shell:` values;
  * in the step summary: a bare name passed to a Node or Python print on a
    continuation line of the call (an f-string or template part there is
    read), a heredoc that opens the summary file itself (`fs.appendFileSync`,
    `open(os.environ["GITHUB_STEP_SUMMARY"], "a")`) instead of printing to a
    redirected stdout, and a summary written by a script run from a file --
    scripts/docs_freshness.py, scripts/branch_protection_audit.py and
    scripts/required_check_triggers.py encode theirs with PY_MD's helpers,
    held by their own tests, not by this guard; a helper redefined through
    `eval` or `source` (shell), `exec` or an import machinery call (Python)
    or `require`/`eval` (Node); and a `case` compound redirected there (its
    arms read as commands, so that one errs towards a finding);
  * on a log line, Python string concatenation, `%` and `.format(...)`, and
    `+` in Node -- only f-strings, template literals and bare arguments are
    read (on a summary line each is refused);
  * `: "${x:=$V}"`, `printf -v`, `eval`, `${!n}`, `declare -n`, an alias or a
    variable holding `$GITHUB_OUTPUT`, a command prefix held in a variable,
    `node -e` / `python -c` one-liners;
  * `actions/**/*.bash` and extension-less scripts;
  * `${{ ... }}` expressions in a `run:` body (a neighbouring class), and the
    non-reusable workflows.

Reads only. Exits non-zero on any finding, and on any file it can't read or
parse.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# `::error::`, `::error title=x::`, `::add-mask::`, `::<token>::` (resume).
COMMAND = re.compile(r"::[A-Za-z0-9][A-Za-z0-9_-]*(?:\s[^:\n]*)?::")
# `>`, `>>` and the clobbering `>|`, or `tee [-a]`, into the file.
ENV_FILE = re.compile(r"""(?:>>|>\|?|\btee\b(?:\s+-a)?)\s*["']?\$\{?GITHUB_(?:OUTPUT|ENV|STATE|PATH)\b\}?["']?""")
SUMMARY_FILE = re.compile(r"""(?:>>|>\|?|\btee\b(?:\s+-a)?)\s*["']?\$\{?GITHUB_STEP_SUMMARY\b\}?["']?""")
# A pipe, not `||` and not the `|` of `>|`.
PIPE = re.compile(r"(?<![|>])\|(?!\|)")
# A stdout redirect elsewhere: `> f`, `>> f`, `>| f`, `>&2`, `&> f`.
STDOUT_ELSEWHERE = re.compile(r"(?<![0-9<])>>?\|?|(?<![0-9])>&\s*2|&>")
SUMMARY_TEE = re.compile(r"""\btee\b(?:\s+-a)?\s*["']?\$\{?GITHUB_STEP_SUMMARY\b""")
HEREDOC = re.compile(r"""(?<!<)<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1""")
# `$name`, `${name...}`, `$1`; `${{` is an expression, `${#` a length.
SHELL_REF = re.compile(r"\$(?:\{(?!\{)(#?)([A-Za-z_][A-Za-z0-9_]*|[0-9])([^}]*)\}|([A-Za-z_][A-Za-z0-9_]*|[0-9]))")
# `$(shown "$x")`, `$(shown "${x}")`, `$(shown "$1")`.
SHELL_MASKED = re.compile(r"""\$\(shown "\$\{?([A-Za-z_][A-Za-z0-9_]*|[0-9])\}?"\)""")
MASKED_ASSIGNMENT = re.compile(r"""^"?\$\(shown "\$\{?([A-Za-z_][A-Za-z0-9_]*|[0-9])\}?"\)"?$""")
SHELL_SHOWN = """shown() { local v="${1//[[:cntrl:]]/?}"; printf '%s' "${v//\\#\\#\\[/#?[}"; }"""
PY_SHOWN = re.compile(r"^\s*def shown\(")
PY_SHOWN_RETURN = """return re.sub(r"[\\x00-\\x1f\\x7f-\\x9f]", "?", str(value)).replace("##[", "#?[")"""
JS_SHOWN = ("const shown = (value) => String(value).replace(/[\\u0000-\\u001f\\u007f-\\u009f]/g, '?')"
            ".replace(/##\\[/g, '#?[');")
REFUSAL = re.compile(
    r"""^\s*if\s+\[\[\s+"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?"\s+==\s+\*\[\[:cntrl:\]\]\*\s+\|\|\s+"""
    r""""\$\{?\1\}?"\s+==\s+\*'##\['\*\s+\]\];\s*then\s*$""")
EXIT_STATEMENT = re.compile(r"^exit(?:\s+[0-9]+)?\s*$")
STATEMENT_START = r"(?:^|[;&|]\s*|\b(?:then|do|else|if|!)\s+)"
ASSIGNMENT = re.compile(
    STATEMENT_START
    + r"""(?:(?:local|readonly|export|declare)(?:\s+-\w+)*\s+)?([A-Za-z_][A-Za-z0-9_]*)(\+?)=("(?:[^"\\]|\\.)*"|'[^']*'|\$\((?:[^()]|\([^()]*\))*\)|[^\s;]*)"""
)
DECLARE_LIST = re.compile(r"""^\s*(?:local|readonly|declare|export)\b""")
DECLARED = re.compile(r"""\s([A-Za-z_][A-Za-z0-9_]*)(\+?)=("(?:[^"\\]|\\.)*"|'[^']*'|[^\s;]*)""")
LOOP_OR_READ = re.compile(r"""\b(?:for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b|read\s+(?:-[A-Za-z]+\s+(?:''\s+)?)*([A-Za-z_][A-Za-z0-9_]*)|mapfile\s+(?:-\w+\s+)*([A-Za-z_][A-Za-z0-9_]*))""")
SHELL_PRINT = re.compile(r"(?:^\s*|[;&|]\s*|\b(?:then|do|else|if|!)\s+|\{\s+)(echo|printf)\b(?!\s+-v\b)")
STATEMENT_END = re.compile(r";|&&|\|\||\bthen\b|\bdo\b")
PY_PRINT = re.compile(r"\b(print|SystemExit|sys\.stdout\.write|sys\.stderr\.write)\(")
JS_PRINT = re.compile(r"\b(console\.(?:log|info|warn|error|debug)|process\.stdout\.write|process\.stderr\.write)\(")
CAP = 200
LEADING = "<leading value>"
SEAM_NAME = "<mask seam>"
# A masked value next to a literal '#' or '[' -- or next to another masked
# value -- can re-form '##[' across the seam: '#' + shown('#[x'), shown('##')
# + '[', shown('x#') + shown('#[y').
SEAM = re.compile(r"""#["']*\$\(shown "|\$\(shown "[^"]*"\)["']*(?:[#\[]|\$\(shown ")""")

# The step summary is Markdown, rendered by GitHub (#506). Its canonical
# helpers encode, then wrap. A control character -- C0, DEL, C1, U+2028 or
# U+2029, matched as bytes in bash so the runner's locale doesn't matter --
# becomes a question mark, which is punctuation and so written `&#63;`. Every
# ASCII punctuation character becomes its numeric HTML entity (`&#NN;`); `@`
# becomes `&#64;<!-- -->`, because GitHub autolinks an e-mail address inside
# <code> even with its `@` and `.` as entities, and the empty comment splits
# it. The result sits inside <code>...</code> (one line) or <pre>...</pre>
# (line ends kept, a CR before one dropped). Encoded text holds no character
# Markdown, HTML or an autolink reads, and inside <code>/<pre> GitHub links no
# `@name` or `#1` either; measured on the /markdown endpoint (gfm), not on a
# rendered summary. md_enc alone is not a mask: unwrapped, `@name` and `#1`
# still link. What passes all three helpers unchanged: bidi controls and
# zero-width characters (they can make a value inside <code> read differently,
# not add Markdown), and, in bash only, bytes that are not valid UTF-8 (Node
# and Python see decoded strings). Bash encodes with one pattern substitution
# per punctuation character over the whole value (each match becomes control
# markers around its code, the markers then `&#`, `;` and the comment), not
# with a per-character loop: measured with bash 5.3.9 on a loaded machine,
# 40 000 characters of code-like text take 0.27 s (the loop took 15.5 s);
# 40 000 characters of nothing but punctuation still take about 3 s, since
# bash's substitution slows with the number of matches.
SHELL_MD = (
    """md_enc() { local LC_ALL=C; local s="${1//[[:cntrl:]]/?}" c n x; """
    """s="${s//$'\\xc2'[$'\\x80'-$'\\x9f']/?}"; s="${s//$'\\xe2\\x80'[$'\\xa8\\xa9']/?}"; """
    """for n in {33..47} {58..64} {91..96} {123..126}; do printf -v x '%x' "$n"; printf -v c '%b' "\\\\x$x"; """
    """s=${s//"$c"/$'\\x01'$n$'\\x02'}; done; s=${s//$'\\x01'64$'\\x02'/$'\\x01'64$'\\x02\\x03'}; """
    """s=${s//$'\\x01'/'&#'}; s=${s//$'\\x02'/';'}; s=${s//$'\\x03'/'<!-- -->'}; printf '%s' "$s"; }""",
    """md_code() { printf '<code>%s</code>' "$(md_enc "$1")"; }""",
    """md_pre() { local line; printf '<pre>'; while IFS= read -r line; do md_enc "${line%$'\\r'}"; printf '\\n'; """
    """done <<< "$1"; printf '</pre>\\n'; }""",
)
JS_MD = (
    "const mdEnc = (value) => String(value).replace(/[\\u0000-\\u001f\\u007f-\\u009f\\u2028\\u2029]/g, '?')"
    ".replace(/[\\x21-\\x2f\\x3a-\\x40\\x5b-\\x60\\x7b-\\x7e]/g, "
    "(c) => (c === '@' ? '&#64;<!-- -->' : `&#${c.charCodeAt(0)};`));",
    "const mdCode = (value) => `<code>${mdEnc(value)}</code>`;",
    "const mdPre = (value) => `<pre>${String(value).replace(/\\r\\n/g, '\\n').split('\\n').map(mdEnc).join('\\n')}"
    "\\n</pre>`;",
)
PY_MD = '''def md_enc(value):
    return re.sub(r"[\\x21-\\x2f\\x3a-\\x40\\x5b-\\x60\\x7b-\\x7e]",
                  lambda m: "&#64;<!-- -->" if m.group() == "@" else f"&#{ord(m.group())};",
                  re.sub(r"[\\x00-\\x1f\\x7f-\\x9f\\u2028\\u2029]", "?", str(value)))


def md_code(value):
    return f"<code>{md_enc(value)}</code>"


def md_pre(value):
    lines = str(value).replace("\\r\\n", "\\n").split("\\n")
    return "<pre>" + "\\n".join(md_enc(line) for line in lines) + "\\n</pre>"
'''
NAME = r"([A-Za-z_][A-Za-z0-9_]*|[0-9])"
# `$(md_code "$x")`, `$(md_code "${x}")` inside a printed string.
SHELL_MD_CODE = re.compile(r"""\$\(md_code "\$\{?""" + NAME + r"""\}?"\)""")
# `md_code "$x"` or `md_pre "$x"` as a statement of its own.
MD_STATEMENT = re.compile(r"""^md_(?:code|pre) "\$\{?""" + NAME + r"""\}?"$""")
# Substitutions whose names are reported on their own: a log mask, the bare
# encoder or a non-canonical md_code is not a summary mask, and saying so names
# the value.
NAMED_SUBSTITUTION = re.compile(r"""\$\((?:shown|md_enc|md_code) "\$\{?""" + NAME + r"""\}?"\)""")
# A helper defined, aliased, unset or rebound anywhere but in its canonical
# lines: the body's canonical definition then proves nothing.
SHELL_MD_REBIND = re.compile(
    r"""(?:^|[;&|{(]\s*)(?:function\s+md_(?:enc|code|pre)\b|md_(?:enc|code|pre)\s*\(\s*\))"""
    r"""|\b(?:unset|alias|unalias|declare\s+-f|readonly\s+-f|export\s+-f)\b[^;&|]*\bmd_(?:enc|code|pre)\b""")
# Python and Node: any mention of a helper's name that is not a call of it.
PY_MD_NAME = re.compile(r"\bmd_(?:enc|code|pre)\b(?!\s*\()|\bdef\s+md_(?:enc|code|pre)\b")
JS_MD_NAME = re.compile(r"\bmd(?:Enc|Code|Pre)\b(?!\s*\()")
# Statements that write nothing to stdout, or only start a block.
SILENT = {"fi", "done", "esac", "}", "{", "[[", "[", "test", "true", "false", ":", "exit", "return", "break",
          "continue", "local", "declare", "readonly", "export", "set", "shift", "unset", "read", "mapfile", "cd"}
KEYWORDS = ("then", "else", "elif", "do", "if", "while", "until", "!", "{", "}")
OUTPUT_NAME = "<command output>"
JS_MD_CALL = ("mdCode", "mdPre")
PY_MD_CALL = ("md_code", "md_pre")


@dataclass(frozen=True)
class Allowed:
    """A value the guard cannot see is constrained, and why it is.

    `step` is the step's `name:` (None: every step of the file). `env` limits
    the entry to steps whose `env:` maps the name to exactly that expression.
    `after` limits it to lines below the `if` block whose `if` line contains
    that text -- the check that constrains the value. `source` names the
    (step, line) of the file that constrains the value at its origin, another
    step that writes the output this one reads. Both must match a non-comment
    line; either makes the entry stale when its line is gone, so the reason
    can't outlive the check. `sink` is the channel the reason holds for:
    "log" (log lines and env files) or "summary" (`$GITHUB_STEP_SUMMARY`) --
    a value safe on a command channel is not safe in Markdown, so an entry
    never covers both.
    """

    path: str
    name: str
    reason: str
    step: str | None = None
    env: str | None = None
    after: str | None = None
    source: tuple[str, str] | None = None
    sink: str = "log"


PUBLISH = ".github/workflows/reusable-release-publish.yml"
ARCHIVE = ".github/workflows/reusable-release-archive.yml"
DRAFTER = ".github/workflows/reusable-release-drafter.yml"
REFRESH = ".github/workflows/reusable-release-cd-refresh-master.yml"
TAG_REFUSAL = """if [[ "$TAG" == *[[:cntrl:]]* || "$TAG" == *'##['* ]]; then"""
SHA_CHECK = 'if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then'
DRAFT_TAG = "${{ steps.draft.outputs.tag }}"
TARGET_SHA = "${{ steps.align.outputs.target_sha || steps.draft.outputs.target_sha }}"
EXPECTED_CHECK = 'if [[ ! "$expected" =~ ^[0-9a-f]{40}$ ]]; then'

ALLOWED: tuple[Allowed, ...] = (
    # reusable-release-publish.yml
    Allowed(PUBLISH, "TAG", env=DRAFT_TAG, source=("Resolve draft", TAG_REFUSAL),
            reason="Resolve draft refuses a tag with a control character or '##[' before it writes this output (#492)"),
    Allowed(PUBLISH, "tag", env=DRAFT_TAG, source=("Resolve draft", TAG_REFUSAL),
            reason="Python reads TAG, the same refused output (#492)"),
    Allowed(PUBLISH, "expected_prefix", step="Verify version-bearing-file alignment", env=DRAFT_TAG,
            source=("Resolve draft", TAG_REFUSAL), reason="a literal prefix plus the refused tag"),
    Allowed(PUBLISH, "TARGET_SHA", env=TARGET_SHA, source=("Resolve draft", SHA_CHECK),
            reason="the draft's target_sha passes ^[0-9a-f]{40}$ before it is written; align's is `git rev-parse HEAD`"),
    Allowed(PUBLISH, "sha", step="Verify version-bearing-file alignment", env=TARGET_SHA,
            source=("Resolve draft", SHA_CHECK), reason="Python reads TARGET_SHA, constrained as above"),
    Allowed(PUBLISH, "DRAFT_TARGET", env="${{ steps.draft.outputs.target_sha }}", source=("Resolve draft", SHA_CHECK),
            reason="passes ^[0-9a-f]{40}$ in Resolve draft before it is written"),
    Allowed(PUBLISH, "expected", step="Check the draft target against the expected commit",
            after=EXPECTED_CHECK, reason="refused above unless it is a 40-hex SHA"),
    Allowed(PUBLISH, "expected", step="Publish (flip draft=false)",
            source=("Check the draft target against the expected commit", EXPECTED_CHECK),
            reason="the same input, lowercased; the check step refuses it unless 40-hex and runs earlier in this job "
                   "whenever it is set"),
    Allowed(PUBLISH, "actual", step="Publish (flip draft=false)",
            reason="resolve_commit output: a lowercased 40-hex string or `git rev-parse --verify` output"),
    Allowed(PUBLISH, "total", step="Resolve draft", reason="`jq 'length'`, a number"),
    Allowed(PUBLISH, "sha", step="Resolve draft",
            reason="resolve_commit output, confirmed a commit by `git cat-file -e`; checked against "
                   "^[0-9a-f]{40}$ before the output write"),
    Allowed(PUBLISH, "new_sha", step="Align version-bearing files (primary path)", reason="`git rev-parse HEAD`"),
    Allowed(PUBLISH, "published_at", step="Publish (flip draft=false)", reason="`date -Is`"),
    Allowed(PUBLISH, "is_draft", step="Post-publish sanity", reason="`--jq .isDraft`, a JSON boolean"),
    Allowed(PUBLISH, "count", step="Detect project type and load version-bearing files",
            reason="`jq '.entries | length'`, a number"),
    Allowed(PUBLISH, "source", step="Detect project type and load version-bearing files",
            reason="`.source` of vbf.json, which the Python above sets to one of five literals"),
    Allowed(PUBLISH, "VALE_RESULT", step="Check the release notes with Vale", env="${{ steps.vale.outputs.result }}",
            reason="actions/setup-vale writes one of its fixed result words"),
    *(Allowed(PUBLISH, "ref", step=step,
              reason="resolve_commit's `echo \"${ref,,}\"`: runs only after ref matched ^[0-9a-fA-F]{40}$, and the "
                     "function is only called inside $(...)")
      for step in ("Resolve draft", "Publish (flip draft=false)")),
    Allowed(PUBLISH, "out", step="Attach HACS zip-release asset",
            reason="only passed to du; the line keeps the size field of du's first line"),
    # reusable-release-archive.yml
    Allowed(ARCHIVE, "TAG", env="${{ needs.resolve.outputs.tag }}", source=("Resolve draft", TAG_REFUSAL),
            reason="the resolve job refuses a tag with a control character or '##[' before it writes this output (#492)"),
    Allowed(ARCHIVE, "sha", step="Resolve draft", after='if [[ "$sha" != "$GITHUB_SHA" ]]; then',
            reason="equal to GITHUB_SHA below this check"),
    Allowed(ARCHIVE, "total", step="Resolve draft", reason="`jq 'length'`, a number"),
    Allowed(ARCHIVE, "artifact", step="Resolve draft", reason="a literal prefix plus a kernel UUID"),
    Allowed(ARCHIVE, "BUILT_SHA", env="${{ needs.resolve.outputs.target_sha }}",
            reason="equal to GITHUB_SHA, checked in the resolve job before it is written"),
    Allowed(ARCHIVE, "delimiter", step="Attach to the draft", reason="a literal prefix plus a kernel UUID"),
    Allowed(ARCHIVE, "files", step="Attach to the draft",
            reason="asset names the build job refused unless they match ^[A-Za-z0-9_+-][A-Za-z0-9._+-]*$"),
    Allowed(ARCHIVE, "dupes", step="Match assets", after='if [[ -n "$bad" ]]; then',
            reason="names that passed the ^[A-Za-z0-9_+-][A-Za-z0-9._+-]*$ check above"),
    # reusable-release-drafter.yml
    Allowed(DRAFTER, "CAPTURED_TAG", env="${{ steps.capture.outputs.captured_tag }}",
            source=("Capture project-context block",
                    """if [[ "$captured_tag" == *[[:cntrl:]]* || "$captured_tag" == *'##['* ]]; then"""),
            reason="the capture step skips a tag with a control character or '##[' before it writes this output (#492)"),
    Allowed(DRAFTER, "new_tag", step="Restore project-context block",
            after='if [[ "$new_tag" != "$CAPTURED_TAG" ]]; then', reason="equal to CAPTURED_TAG below this check"),
    # reusable-release-cd-refresh-master.yml
    Allowed(REFRESH, "rule_types", step="Determine the write strategy from the target's protection",
            reason="ruleset rule types, GitHub's own enum words joined by `jq join(\",\")`"),
    Allowed(REFRESH, "classic", step="Determine the write strategy from the target's protection",
            reason="only tested with `[ -n ]`; the substitution prints yes or no"),
    Allowed(REFRESH, "SOURCE_SHA", step="Refresh the presentation branch",
            reason="`git rev-parse --verify` output, a commit SHA"),
    # reusable-nodejs-coverage.yaml
    Allowed(".github/workflows/reusable-nodejs-coverage.yaml", "threshold", step="Enforce coverage threshold",
            reason="`Number(process.env.FAIL_UNDER)`, a number"),
    # reusable-release-drafter-autolabel.yml
    Allowed(".github/workflows/reusable-release-drafter-autolabel.yml", "label",
            reason="iterates the literal array type_labels"),
    Allowed(".github/workflows/reusable-release-drafter-autolabel.yml", "PR_NUMBER",
            after='if [[ ! "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]]; then', reason="refused unless numeric"),
    # reusable-fork-guard.yaml
    Allowed(".github/workflows/reusable-fork-guard.yaml", "EVENT_NAME", env="${{ github.event_name }}",
            reason="an event name GitHub sets"),
    Allowed(".github/workflows/reusable-fork-guard.yaml", "2", step="Refuse protected-path changes from a fork",
            reason="finish()'s description; its call sites pass literals and counts (read by hand, NOT checked by "
                   "this guard)"),
    Allowed(".github/workflows/reusable-fork-guard.yaml", "resume", step="Refuse protected-path changes from a fork",
            reason="`openssl rand -hex 16`"),
    Allowed(".github/workflows/reusable-fork-guard.yaml", "path", step="Refuse protected-path changes from a fork",
            reason="printed with `printf %q` between ::stop-commands:: and its resume token, so no command is "
                   "processed"),
    # reusable-pr-lint.yaml
    Allowed(".github/workflows/reusable-pr-lint.yaml", "count", reason="`wc -l`, a number"),
    Allowed(".github/workflows/reusable-pr-lint.yaml", "n", after='if ! [[ "${n}" =~ ^[0-9]{1,9}$ ]]; then',
            reason="refused unless 1-9 digits"),
    Allowed(".github/workflows/reusable-pr-lint.yaml", "unreadable",
            reason="built only from n, refused unless 1-9 digits"),
    # reusable-pre-commit.yaml
    Allowed(".github/workflows/reusable-pre-commit.yaml", "key", step="Compute the hook-environment cache key",
            reason="no caller input: os-release, the installed pre-commit version, setup-python's path, a hashFiles digest"),
    # actions/setup-vale
    Allowed("actions/setup-vale/setup-vale.sh", "result",
            reason="finish()'s first argument; a literal result word at every call site (read by hand, NOT checked "
                   "by this guard)"),
    Allowed("actions/setup-vale/setup-vale.sh", "version", reason="refused unless it matches VERSION_RE, ^[0-9]+\\.[0-9]+\\.[0-9]+$"),
    Allowed("actions/setup-vale/setup-vale.sh", "install_dir",
            reason="RUNNER_TEMP plus the validated version plus a mktemp basename"),
    # Log lines that begin with a value (the leading-value rule).
    *(Allowed(PUBLISH, LEADING, step=step,
              reason="resolve_commit's `echo \"${ref,,}\"`, only ever called inside $(...), never printed")
      for step in ("Resolve draft", "Publish (flip draft=false)")),
    Allowed(".github/workflows/reusable-fork-guard.yaml", LEADING, step="Refuse protected-path changes from a fork",
            reason="finish()'s `echo \"$2\"`: every success description starts with a literal (read by hand, NOT "
                   "checked by this guard)"),
    Allowed("actions/setup-vale/setup-vale.sh", LEADING,
            reason="finish()'s `echo \"$message\"`: the one exit-0 message starts with a literal (read by hand, "
                   "NOT checked by this guard)"),
    # Set by the runner, the same for every caller.
    *(Allowed("*", name, reason="set by the runner") for name in (
        "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_SERVER_URL",
        "RUNNER_OS", "RUNNER_ARCH", "RUNNER_TEMP", "GITHUB_ACTION_PATH",
    )),
    # Step-summary Markdown (#506): values left as Markdown on purpose.
    *(Allowed(PUBLISH, name, step="Disclose target state in job summary", sink="summary",
              reason="the login of the user who triggered the run, set by the runner; written after '@' so the "
                     "summary links the triggerer on purpose")
      for name in ("GITHUB_TRIGGERING_ACTOR", "GITHUB_ACTOR")),
    *(Allowed(PUBLISH, name, step="Disclose target state in job summary", sink="summary",
              reason="set by the runner; the run URL is built from them so that it autolinks")
      for name in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")),
    Allowed(REFRESH, "REASON", step="Refuse: no permitted write path", env="${{ steps.strategy.outputs.reason }}",
            source=("Determine the write strategy from the target's protection", 'echo "reason=$reason"'),
            sink="summary",
            reason="the strategy step assigns reason only from literals, one with intended backticks (read by hand, "
                   "NOT checked by this guard)"),
)


@dataclass
class Body:
    path: str
    step: str
    env: dict[str, str]
    lines: list[str]
    first_line: int


def finding(path: str, line: int, step: str, message: str) -> dict:
    return {"path": path, "line": line, "step": step, "message": message}


# --- reading the files -------------------------------------------------------


def mapping_get(node: yaml.Node, key: str) -> yaml.Node | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return value_node
    return None


def scalar(node: yaml.Node | None) -> str | None:
    return node.value if isinstance(node, yaml.ScalarNode) else None


def step_bodies(rel: str, text: str) -> list[Body]:
    root = yaml.compose(text)
    if root is None:
        return []
    step_lists = []
    jobs = mapping_get(root, "jobs")
    if isinstance(jobs, yaml.MappingNode):
        step_lists += [mapping_get(job, "steps") for _, job in jobs.value]
    runs = mapping_get(root, "runs")
    if runs is not None:
        step_lists.append(mapping_get(runs, "steps"))
    bodies = []
    for steps in step_lists:
        if not isinstance(steps, yaml.SequenceNode):
            continue
        for index, step in enumerate(steps.value):
            run = mapping_get(step, "run")
            if scalar(run) is None:
                continue
            env_node = mapping_get(step, "env")
            env = {}
            if isinstance(env_node, yaml.MappingNode):
                env = {k.value: (scalar(v) or "") for k, v in env_node.value if isinstance(k, yaml.ScalarNode)}
            name = scalar(mapping_get(step, "name")) or scalar(mapping_get(step, "id")) or f"step {index + 1}"
            # A block scalar's content starts on the line after `run: |`.
            first = run.start_mark.line + (2 if run.style in ("|", ">") else 1)
            bodies.append(Body(rel, name, env, run.value.split("\n"), first))
    return bodies


def candidate_files(root: Path) -> list[Path]:
    files = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        files += [p for p in workflows.glob("reusable-*") if p.suffix in (".yml", ".yaml")]
    actions = root / "actions"
    if actions.is_dir():
        files += [p for p in actions.rglob("action.y*ml") if p.suffix in (".yml", ".yaml")]
        # A composite action keeps its shell beside action.yml; that is where
        # its messages are. A directory named exactly `test` holds fixtures.
        files += [p for p in actions.rglob("*.sh") if "test" not in p.relative_to(actions).parts]
    return sorted(files)


def bodies_of(root: Path, path: Path) -> list[Body]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".sh":
        return [Body(rel, path.name, {}, text.split("\n"), 1)]
    return step_bodies(rel, text)


# --- one run body --------------------------------------------------------------


@dataclass
class Logical:
    """A statement-ish unit: physical lines joined at a trailing backslash."""

    index: int  # first physical line, 0-based within the body
    text: str
    lang: str  # sh, py, js, data
    dest: str = "log"  # where a heredoc's stdout goes: log, file, envfile, pipe


def unquoted(text: str) -> str:
    """The text with quoted strings and `$(...)` blanked, for finding `|` and `>`."""
    out = []
    i, quote, depth = 0, None, 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            out.append("  ")
            i += 2
            continue
        if quote == "'":
            quote = None if c == "'" else quote
            out.append(" ")
        elif depth:
            depth += {"(": 1, ")": -1}.get(c, 0)
            out.append(" ")
        elif text.startswith(("$(", "<(", ">("), i):
            depth = 1
            out.append("  ")
            i += 2
            continue
        elif quote == '"':
            quote = None if c == '"' else quote
            out.append(" ")
        elif c in "'\"":
            quote = c
            out.append(" ")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def destination(text: str) -> str:
    """Where a shell line's stdout goes: log, file, envfile, summary or pipe."""
    bare = unquoted(text)
    if ENV_FILE.search(text):
        return "envfile"
    if SUMMARY_TEE.search(text):
        return "summary"
    # A pipeline into the summary still ends there.
    if any(SUMMARY_FILE.match(text, m.start()) for m in re.finditer(r"(?<![0-9&<])>>?(?!&)", bare)):
        return "summary"
    if PIPE.search(bare):
        return "pipe"
    for m in re.finditer(r"(?<![0-9&<])(>>?)(?!&)\s*", bare):
        if ENV_FILE.search(text[m.start():]):
            return "envfile"
        return "file"
    return "log"


def logical_lines(lines: list[str]) -> list[Logical]:
    out: list[Logical] = []
    i = 0
    heredoc: tuple[str, str, str] | None = None
    while i < len(lines):
        if heredoc is not None:
            delimiter, lang, dest = heredoc
            if lines[i].strip() == delimiter:
                heredoc = None
            else:
                out.append(Logical(i, lines[i], lang, dest))
            i += 1
            continue
        start, text = i, lines[i]
        while text.rstrip().endswith("\\") and i + 1 < len(lines) and not text.lstrip().startswith("#"):
            i += 1
            text = text.rstrip()[:-1] + " " + lines[i].strip()
        out.append(Logical(start, text, "sh"))
        match = HEREDOC.search(text)
        if match and not text.lstrip().startswith("#"):
            command = text[:match.start()]
            dest = destination(text[:match.start()] + text[match.end():])
            if re.search(r"\bpython[0-9.]*\b", command):
                lang = "py"
            elif re.search(r"\bnode\b", command):
                lang = "js"
            else:
                # Quoted delimiter: text the shell leaves alone. Unquoted: the
                # shell expands it, so it reads like any other shell line.
                lang = "data" if match.group(1) else "sh-heredoc"
            heredoc = (match.group(2), lang, dest)
        i += 1
    return out


def indent_of(text: str) -> int:
    return len(text) - len(text.lstrip())


def block_end(lines: list[Logical], at: int) -> int:
    """Index of the `fi` closing the `if` at lines[at], or `at` itself."""
    if not re.match(r"^\s*if\b", lines[at].text):
        return at
    indent = indent_of(lines[at].text)
    for j in range(at + 1, len(lines)):
        text = lines[j].text
        if text.strip() == "fi" and indent_of(text) == indent:
            return j
    return at


def refuses(lines: list[Logical], at: int) -> bool:
    """The then-branch of the `if` at lines[at] holds an `exit` at its own level."""
    indent = indent_of(lines[at].text)
    branch = []
    for j in range(at + 1, len(lines)):
        text = lines[j].text
        if text.strip() and indent_of(text) <= indent:
            break
        if text.strip():
            branch.append(text)
    if not branch:
        return False
    level = indent_of(branch[0])
    return any(indent_of(t) == level and EXIT_STATEMENT.match(t.strip()) for t in branch)


def assignments(unit: Logical) -> list[tuple[str, str | None]]:
    """(name, right-hand side or None when unknown) assigned on a shell line.

    `x+=...` is reported with a leading `+`, so it is never a mask or a
    plain assignment and an appended raw value keeps the name unclean.
    """
    if unit.lang != "sh" or unit.text.lstrip().startswith("#"):
        return []
    found: list[tuple[str, str | None]] = []
    text = unit.text.strip()
    pattern = DECLARED if DECLARE_LIST.match(text) else ASSIGNMENT
    source = " " + text if pattern is DECLARED else text
    for m in pattern.finditer(source):
        found.append((m.group(1), ("+" if m.group(2) else "") + m.group(3)))
    for m in LOOP_OR_READ.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3)
        found.append((name, None))
    return found


def is_literal(rhs: str | None) -> bool:
    if rhs is None:
        return False
    return "$" not in rhs and not re.search(r"(?<!\\)`", rhs)


def is_comment(text: str) -> bool:
    return text.lstrip().startswith(("#", "//"))


TO_STDERR = re.compile(r"(?<![0-9])>&\s*2|&>|/dev/std(?:err|out)")
OPENERS = {"{", "for", "while", "until", "select", "if", "case"}
CLOSERS = {"}", "done", "fi", "esac"}


def depth_change(unit: Logical) -> int:
    """How many compound commands a shell line opens minus how many it closes."""
    if unit.lang != "sh" or is_comment(unit.text):
        return 0
    change = 0
    for segment in re.split(r"[;&|()]", unquoted(unit.text)):
        words = segment.split()
        while words and words[0] in ("then", "else", "elif", "do", "!"):
            words.pop(0)
        if words and words[0] in OPENERS:
            change += 1
        elif words and words[0] in CLOSERS:
            change -= 1
    return change


def redirected_groups(units: list[Logical]) -> tuple[set[int], set[int], set[int]]:
    """Lines whose output a redirect on a later line sends to a file.

    Returns all lines inside a `{ ... } > target` group, the lines of a group
    or compound command (`{`, `for`/`while`/`until`, `if`, `case`) into an env
    file, and those into the summary. A group whose `{` is alone on its line is
    read as before for every target; for an env file or the summary the opener
    may also carry a statement (`{ echo a`) and a loop or `if` counts too, its
    opening line included -- that is where `{ echo "$v"` or `do echo "$v"`
    prints. Into a plain file only the old `{`-alone form is taken out of the
    log rule.
    """
    redirected: set[int] = set()
    envfile: set[int] = set()
    summary: set[int] = set()
    for k, unit in enumerate(units):
        if unit.lang != "sh" or is_comment(unit.text):
            continue
        head = unquoted(unit.text).split()
        if not head or head[0] not in CLOSERS:
            continue
        dest = destination(unit.text)
        if dest == "log":
            continue
        if head[0] == "}":
            depth = 0
            for j in range(k, -1, -1):
                stripped = units[j].text.strip()
                if stripped.startswith("}"):
                    depth += 1
                if stripped == "{":
                    depth -= 1
                    if depth == 0:
                        redirected.update(range(j + 1, k))
                        if dest == "envfile":
                            envfile.update(range(j + 1, k))
                        if dest == "summary":
                            summary.update(range(j + 1, k))
                        break
        if dest not in ("envfile", "summary"):
            continue
        total = 0
        for j in range(k, -1, -1):
            total += depth_change(units[j])
            if total == 0 and j < k:
                members = [i for i in range(j, k) if units[i].lang == "sh"]
                if dest == "envfile":
                    envfile.update(members)
                else:
                    summary.update(members)
                    redirected.update(members)
                break
            if total == 0:
                break  # a compound command that opens and closes on this line
    # A line inside such a group that sends its own stdout to stderr prints to
    # the log after all: the log rule keeps reading it.
    redirected = {i for i in redirected if not TO_STDERR.search(unquoted(units[i].text))}
    return redirected, envfile, summary


def sink_units(units: list[Logical]) -> set[int]:
    """Indices of units that emit a command, write an env file or print to the log."""
    redirected, sinks, _ = redirected_groups(units)
    for k, unit in enumerate(units):
        if unit.lang == "data" or is_comment(unit.text):
            continue
        text = unit.text
        if COMMAND.search(text):
            sinks.add(k)
        if unit.lang == "sh":
            dest = destination(text)
            if dest == "envfile":
                sinks.add(k)
            elif (SHELL_PRINT.search(unquoted(text)) and dest == "log" and k not in redirected
                  and text.strip() != SHELL_SHOWN and text.strip() not in SHELL_MD):
                sinks.add(k)
        elif unit.lang == "sh-heredoc":
            if unit.dest in ("envfile", "log"):
                sinks.add(k)
        elif unit.lang == "py":
            m = PY_PRINT.search(text)
            if m:
                to_stdout = m.group(1) in ("print", "sys.stdout.write") and "file=sys.stderr" not in text
                if not to_stdout or unit.dest == "log":
                    sinks.add(k)
        elif unit.lang == "js":
            m = JS_PRINT.search(text)
            if m:
                to_stdout = m.group(1) in ("console.log", "console.info", "process.stdout.write")
                if not to_stdout or unit.dest == "log":
                    sinks.add(k)
    return sinks


def shell_refs(text: str, mask: re.Pattern = SHELL_MASKED) -> list[tuple[str, bool, bool]]:
    """(name, masked, numeric) for every expansion outside single quotes.

    `mask` is the masked form of the sink: `$(shown "$x")` for a log line,
    `$(md_code "$x")` for the step summary.
    """
    text = SUMMARY_FILE.sub("", ENV_FILE.sub("", text))
    refs = []
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            i += 2
            continue
        if c == "'" and quote is None:
            end = text.find("'", i + 1)
            i = len(text) if end < 0 else end + 1
            continue
        if c == '"':
            quote = None if quote == '"' else '"'
        if c == "$":
            masked = mask.match(text, i)
            if masked:
                refs.append((masked.group(1), True, False))
                i = masked.end()
                continue
            m = SHELL_REF.match(text, i)
            if m:
                if m.group(2):
                    refs.append((m.group(2), False, bool(m.group(1))))
                    # `${x:-$y}`, `${x//pat/$y}`: the modifier expands too.
                    refs += shell_refs(m.group(3), mask)
                else:
                    refs.append((m.group(4), False, False))
                i = m.end()
                continue
        i += 1
    return refs


def template_exprs(text: str, lang: str) -> list[str]:
    """Interpolated expressions of a Python f-string or a JS template literal."""
    exprs = []
    opener = "${" if lang == "js" else "{"
    if lang == "py" and not re.search(r"\b[rR]?[fF][rR]?['\"]", text):
        return []
    if lang == "js" and "`" not in text:
        return []
    i = 0
    while True:
        i = text.find(opener, i)
        if i < 0:
            return exprs
        if lang == "py" and text.startswith("{{", i):
            i += 2
            continue
        start = i + len(opener)
        depth, j = 1, start
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        expr = text[start:j - 1].strip()
        # Drop a format spec or conversion: {x!r}, {x:>8}.
        expr = re.split(r"![rsa]$|:(?![^\[]*\])", expr)[0].strip() if lang == "py" else expr
        exprs.append(expr)
        i = j


def call_args(text: str, opener_end: int) -> list[str]:
    """Top-level arguments of the call whose `(` ends at opener_end."""
    args, depth, current, quote = [], 1, [], None
    i = opener_end
    while i < len(text) and depth:
        c = text[i]
        if quote:
            if c == "\\":
                current.append(text[i:i + 2])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if not depth:
                break
        elif c == "," and depth == 1:
            args.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    args.append("".join(current).strip())
    return [a for a in args if a]


def call_end(text: str, opener_end: int) -> int:
    """Index just past the `)` closing the call whose `(` ends at opener_end."""
    depth, quote, i = 1, None, opener_end
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if not depth:
                return i + 1
        i += 1
    return len(text)


def printed_exprs(unit: Logical) -> list[str]:
    """Expressions a Python or Node line prints."""
    text = unit.text
    exprs = list(template_exprs(text, unit.lang))
    m = (PY_PRINT if unit.lang == "py" else JS_PRINT).search(text)
    if m:
        for arg in call_args(text, m.end()):
            if unit.lang == "py" and re.match(r"^[A-Za-z_]+\s*=", arg):
                continue  # file=, end=, sep=, flush=
            if re.match(r"""^(?:[rRbBfF]{0,2})?['"`]""", arg):
                continue  # a literal; f-strings and templates are read above
            exprs.append(arg)
    return exprs


def single_literal(arg: str, lang: str) -> bool:
    """One string literal and nothing else; a template's or f-string's parts are read on their own."""
    prefix = r"[rRbBfFuU]{0,2}" if lang == "py" else ""
    quotes = ("'", '"') if lang == "py" else ("'", '"', "`")
    return any(re.fullmatch(prefix + q + r"(?:[^" + q + r"\\]|\\.)*" + q, arg.strip()) for q in quotes)


def whole_call(expr: str, names: tuple[str, ...]) -> bool:
    """The expression is one call of one of `names`, closed at its very end."""
    text = expr.strip()
    m = re.match(r"^(?:" + "|".join(map(re.escape, names)) + r")\(", text)
    if not m:
        return False
    depth, quote, i = 0, None, m.end() - 1
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i == len(text) - 1
        i += 1
    return False


class Checker:
    """Decides, for one run body, whether a name on a sink line is clean."""

    def __init__(self, body: Body, siblings: list[Body], entries: tuple[Allowed, ...], used: set[Allowed]):
        self.body = body
        self.siblings = siblings
        self.entries = entries
        self.used = used
        self.units = logical_lines(body.lines)
        self.assigned: dict[str, list[tuple[int, str | None]]] = {}
        for j, unit in enumerate(self.units):
            for name, rhs in assignments(unit):
                self.assigned.setdefault(name, []).append((j, rhs))
        self.shell_shown = any(u.lang == "sh" and u.text.strip() == SHELL_SHOWN for u in self.units)
        # Which Python/Node heredoc defines `shown` the canonical way.
        self.shown: dict[int, bool] = {}
        for k, unit in enumerate(self.units):
            key = self.heredoc_id(k)
            if unit.lang == "py":
                ok = PY_SHOWN.match(unit.text) is not None and any(
                    u.text.strip() == PY_SHOWN_RETURN for u in self.units[k + 1:k + 6] if u.lang == "py")
            elif unit.lang == "js":
                ok = unit.text.strip() == JS_SHOWN
            else:
                continue
            self.shown[key] = self.shown.get(key, False) or ok
        # The summary helpers: every line of the canonical block, in the body
        # (shell) or in the same heredoc (Python, Node).
        self.shell_md = all(any(u.lang == "sh" and u.text.strip() == line for u in self.units) for line in SHELL_MD) \
            and not any(u.lang == "sh" and u.text.strip() not in SHELL_MD and not is_comment(u.text)
                        and SHELL_MD_REBIND.search(u.text) for u in self.units)
        self.md: dict[int, bool] = {}
        heredocs: dict[int, list[str]] = {}
        for k, unit in enumerate(self.units):
            if unit.lang in ("py", "js") and unit.text.strip():
                heredocs.setdefault(self.heredoc_id(k), []).append(unit.text.strip())
        py_block = [line.strip() for line in PY_MD.split("\n") if line.strip()]
        for key, lines in heredocs.items():
            if self.units[key].lang == "js":
                own = [line for line in lines if line not in JS_MD and not line.startswith("//")]
                self.md[key] = all(line in lines for line in JS_MD) and not any(JS_MD_NAME.search(line) for line in own)
            else:
                at = [i for i in range(len(lines)) if lines[i:i + len(py_block)] == py_block]
                own = lines[:at[0]] + lines[at[0] + len(py_block):] if at else lines
                own = [line for line in own if not line.startswith("#")]
                self.md[key] = bool(at) and not any(PY_MD_NAME.search(line) for line in own)

    def helper_line(self, k: int) -> bool:
        """A line of a canonical helper's own definition."""
        unit = self.units[k]
        text = unit.text.strip()
        if unit.lang == "sh":
            return text in SHELL_MD or text == SHELL_SHOWN
        if unit.lang == "js":
            return text in JS_MD or text == JS_SHOWN
        if unit.lang == "py":
            return text in [line.strip() for line in PY_MD.split("\n")] or text == PY_SHOWN_RETURN \
                or PY_SHOWN.match(unit.text) is not None
        return False

    def heredoc_id(self, k: int) -> int:
        j = k
        while j > 0 and self.units[j - 1].lang == self.units[k].lang:
            j -= 1
        return j

    def allowed(self, name: str, k: int, shell: bool, sink: str = "log") -> bool:
        body = self.body
        found = []
        for entry in self.entries:
            if entry.path not in ("*", body.path) or entry.name != name or entry.sink != sink:
                continue
            if entry.step is not None and entry.step != body.step:
                continue
            if entry.env is not None:
                # A shell variable must BE that env value and never be
                # reassigned; a Python or Node name reads it, so the step must
                # at least pass it.
                if shell and (body.env.get(name) != entry.env or name in self.assigned):
                    continue
                if not shell and entry.env not in body.env.values():
                    continue
            if entry.after is not None:
                anchors = [j for j, u in enumerate(self.units) if entry.after in u.text and not is_comment(u.text)]
                if not anchors or block_end(self.units, anchors[0]) >= k:
                    continue
            if entry.source is not None:
                step, text = entry.source
                if not any(b.step == step and any(text in line and not is_comment(line) for line in b.lines)
                           for b in self.siblings):
                    continue
            found.append(entry)
        self.used.update(found)
        return bool(found)

    def refused_before(self, name: str, k: int) -> bool:
        for j in range(k):
            m = REFUSAL.match(self.units[j].text)
            if not (m and m.group(1) == name and self.units[j].lang == "sh"):
                continue
            end = block_end(self.units, j)
            # Any later assignment counts, not just one before k: inside a
            # loop it can run before the print on the next pass.
            if end < k and refuses(self.units, j) and not any(a > j for a, _ in self.assigned.get(name, [])):
                return True
        return False

    def clean_shell(self, name: str, k: int, depth: int = 0) -> bool:
        before = [(j, rhs) for j, rhs in self.assigned.get(name, []) if j < k]
        if self.refused_before(name, k):
            return True
        if before and self.shell_shown and MASKED_ASSIGNMENT.match((before[-1][1] or "").strip()):
            return True
        if self.allowed(name, k, shell=True):
            return True
        everywhere = self.assigned.get(name, [])
        if name in self.body.env:
            return not everywhere and "$" not in self.body.env[name]
        if not everywhere or depth > 5:
            return False
        # Constant, or built only from clean names: every assignment is a
        # literal or a string whose expansions are all clean where it stands.
        for j, rhs in everywhere:
            if rhs is None or "$(" in rhs or re.search(r"(?<!\\)`", rhs):
                return False
            for ref, masked, numeric in shell_refs(rhs):
                if not ((masked and self.shell_shown) or numeric
                        or (ref != name and self.clean_shell(ref, j, depth + 1))):
                    return False
        return True

    def clean_summary(self, name: str, k: int, depth: int = 0) -> bool:
        """A shell name is safe in the step summary's Markdown where it stands.

        Every assignment of it in the body -- not just the last one by line,
        which control flow can skip -- is `$(md_code "$x")`, a constant or
        built only from such names; or it is on ALLOWED for the summary. No
        refusal and no log mask counts: neither touches Markdown.
        """
        if self.allowed(name, k, shell=True, sink="summary"):
            return True
        everywhere = self.assigned.get(name, [])
        if name in self.body.env:
            return not everywhere and "$" not in self.body.env[name]
        if not everywhere or depth > 5:
            return False
        for j, rhs in everywhere:
            if rhs is None:
                return False
            rest = SHELL_MD_CODE.sub("", rhs) if self.shell_md else rhs
            if "$(" in rest or re.search(r"(?<!\\)`", rest):
                return False
            for ref, masked, numeric in shell_refs(rhs, SHELL_MD_CODE):
                if not ((masked and self.shell_md) or numeric
                        or (ref != name and self.clean_summary(ref, j, depth + 1))):
                    return False
        return True

    def summary_units(self) -> list[int]:
        """Units whose output reaches `$GITHUB_STEP_SUMMARY`."""
        _, _, grouped = redirected_groups(self.units)
        out = []
        for k, unit in enumerate(self.units):
            if is_comment(unit.text) or not unit.text.strip() or self.helper_line(k):
                continue
            if unit.lang == "sh" and (k in grouped or destination(unit.text) == "summary"):
                out.append(k)
            elif unit.lang in ("sh-heredoc", "py", "js") and unit.dest == "summary":
                out.append(k)
        return out

    def summary_shell(self, k: int) -> list[str]:
        """Unclean names on a shell line whose output reaches the summary.

        Read statement by statement: one reaches the summary if it redirects
        or `tee`s there itself, or -- inside a group or compound redirected
        there -- if it doesn't send its stdout elsewhere.
        """
        unit = self.units[k]
        if unit.lang == "sh-heredoc":
            # Text the shell expands: a single quote is literal, `$x` after it
            # expands.
            return self.summary_statements([("echo", SUMMARY_FILE.sub("", unit.text).replace("'", " "))], k)
        text = unit.text
        _, _, grouped = redirected_groups(self.units)
        heredoc = HEREDOC.search(text)
        if heredoc:
            # The heredoc's own lines are read where they stand; a bare `cat`
            # prints them unchanged, anything else prints its own output.
            command = SUMMARY_FILE.sub("", text[:heredoc.start()] + text[heredoc.end():]).strip()
            if re.search(r"\b(?:python[0-9.]*|node)\b", command) or re.fullmatch(r"cat(?:\s+-)?", command):
                return []
            return [OUTPUT_NAME]
        bare = unquoted(text)
        names: list[str] = []
        statements, start = [], 0
        for m in [*re.finditer(r";|&&|\|\|", bare), None]:
            end = m.start() if m else len(text)
            statements.append((text[start:end], bare[start:end]))
            start = m.end() if m else len(text)
        # A group or compound opened and closed on this line, its closer
        # redirected to the summary: every statement in between prints there.
        inline: set[int] = set()
        stack: list[int] = []
        for i, (_, statement_bare) in enumerate(statements):
            words = statement_bare.split()
            while words and words[0] in ("then", "else", "elif", "do", "!"):
                words.pop(0)
            if words and words[0] in OPENERS:
                stack.append(i)
            elif words and words[0] in CLOSERS and stack:
                opened = stack.pop()
                if SUMMARY_FILE.search(statements[i][0]) or SUMMARY_TEE.search(statements[i][0]):
                    inline.update(range(opened, i + 1))
        for i, (statement, statement_bare) in enumerate(statements):
            if not statement.strip():
                continue
            here = SUMMARY_FILE.search(statement) or SUMMARY_TEE.search(statement)
            grouped_here = k in grouped or i in inline
            if not here and (not grouped_here or STDOUT_ELSEWHERE.search(statement_bare)):
                continue
            # A pipeline: the summary gets the last command's output; every
            # part is still read for the names it prints.
            pieces, offset = [], 0
            for pipe in PIPE.finditer(statement_bare):
                pieces.append(statement[offset:pipe.start()])
                offset = pipe.end()
            pieces.append(statement[offset:])
            if len(pieces) > 1:
                names.append(OUTPUT_NAME)
            for piece in pieces:
                piece = SUMMARY_FILE.sub("", re.sub(r">\(\s*tee\b[^)]*\)", "", piece))
                names += self.summary_statements([(self.statement_head(piece), piece)], k)
        return names

    @staticmethod
    def statement_head(statement: str) -> str:
        """The command word: after keywords and `NAME=value` prefixes."""
        words = statement.split()
        while words and (words[0] in KEYWORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words.pop(0)
        return words[0] if words else ""

    def summary_statements(self, statements: list[tuple[str, str]], k: int) -> list[str]:
        names: list[str] = []
        for head, statement in statements:
            body = statement.strip()
            while True:
                words = body.split(None, 1)
                if not words or words[0] not in KEYWORDS:
                    break
                body = words[1] if len(words) > 1 else ""
            body = re.sub(r"\s*\}$", "", body).strip()
            assignment = ASSIGNMENT.match(body)
            if assignment and assignment.end() == len(body):
                continue  # prints nothing; a command substitution in it is captured
            if head in ("md_code", "md_pre"):
                if not (self.shell_md and MD_STATEMENT.match(body)):
                    names.append(OUTPUT_NAME)
                continue
            if head in ("echo", "printf"):
                # A command substitution prints a command's output, unless it
                # is the summary mask; names in `$(shown "$x")` and
                # `$(md_enc "$x")` are reported by name below.
                visible = self._outside_single_quotes(body)
                if self.shell_md:
                    visible = SHELL_MD_CODE.sub(lambda m: " " * len(m.group()), visible)
                visible = NAMED_SUBSTITUTION.sub(lambda m: " " * len(m.group()), visible)
                if re.search(r"\$\((?!\()", visible) or re.search(r"(?<!\\)`", visible):
                    names.append(OUTPUT_NAME)
                for name, masked, numeric in shell_refs(body, SHELL_MD_CODE):
                    if not ((masked and self.shell_md) or numeric or self.clean_summary(name, k)):
                        names.append(name)
                continue
            if not head or head in SILENT or head == "for":
                continue
            names.append(OUTPUT_NAME)
        return names

    @staticmethod
    def _outside_single_quotes(text: str) -> str:
        """The text with single-quoted strings blanked; double quotes kept."""
        out, quote, i = [], None, 0
        while i < len(text):
            c = text[i]
            if c == "\\" and quote is None and i + 1 < len(text):
                out.append(text[i:i + 2])
                i += 2
                continue
            if quote == "'":
                quote = None if c == "'" else quote
                out.append(" ")
            elif c == "'" and quote is None:
                quote = "'"
                out.append(" ")
            else:
                if c == '"':
                    quote = None if quote == '"' else ('"' if quote is None else quote)
                out.append(c)
            i += 1
        return "".join(out)

    def summary_template(self, k: int) -> list[str]:
        """Unclean values on a Python or Node line whose stdout reaches the summary.

        Every print call on the line counts. A call to stderr (by its name, or
        a `file=sys.stderr` argument -- not that text in a comment) is a log
        line and left to the log rules; in a stdout call every argument, and
        Python's `end=` and `sep=`, must be one plain literal or a call of the
        helper. Template and f-string parts anywhere else on the line must be
        helper calls too.
        """
        unit = self.units[k]
        text = unit.text
        calls = JS_MD_CALL if unit.lang == "js" else PY_MD_CALL
        defined = self.md.get(self.heredoc_id(k), False)
        exprs: list[str] = []
        outside, last = [], 0
        for m in (PY_PRINT if unit.lang == "py" else JS_PRINT).finditer(text):
            if m.start() < last:
                continue
            args = call_args(text, m.end())
            end = call_end(text, m.end())
            outside.append(text[last:m.start()])
            last = end
            keyword = {a.split("=", 1)[0].strip(): a.split("=", 1)[1].strip()
                       for a in args if unit.lang == "py" and re.match(r"^[A-Za-z_]+\s*=(?!=)", a)}
            to_stderr = (m.group(1) not in ("print", "sys.stdout.write", "console.log", "console.info",
                                            "console.debug", "process.stdout.write")
                         or keyword.get("file") == "sys.stderr")
            if to_stderr or ("file" in keyword and keyword["file"] != "sys.stdout"):
                continue  # a log line (the log rules read it), or a file of its own
            call_text = text[m.end():end]
            exprs += template_exprs(call_text, unit.lang)
            for arg in args:
                if unit.lang == "py" and re.match(r"^[A-Za-z_]+\s*=(?!=)", arg):
                    name, value = (part.strip() for part in arg.split("=", 1))
                    if name in ("end", "sep") and not single_literal(value, "py"):
                        exprs.append(value)
                    continue
                if single_literal(arg, unit.lang):
                    continue  # a literal, or a template whose parts are read above
                exprs.append(arg)
        outside.append(text[last:])
        rest = " ".join(outside)
        exprs = template_exprs(rest, unit.lang) + exprs
        names = []
        for expr in exprs:
            if defined and whole_call(expr, calls):
                continue
            if unit.lang == "py" and whole_call(expr, ("len",)):
                continue
            root = re.match(r"^[A-Za-z_][A-Za-z0-9_.]*", expr)
            names.append(root.group(0) if root else expr)
        return names

    @staticmethod
    def printed_segment(unit: Logical) -> str:
        """The part of a shell line whose expansions reach the sink.

        A command or env-file line counts whole. A plain print counts from its
        `echo`/`printf` to the end of that statement, so `gh api "$x" || echo ''`
        doesn't charge `$x` to the echo.
        """
        text = unit.text
        if unit.lang != "sh" or COMMAND.search(text) or destination(text) == "envfile":
            return text
        bare = unquoted(text)
        m = SHELL_PRINT.search(bare)
        if not m:
            return text
        end = STATEMENT_END.search(bare, m.end())
        return text[m.start(1):end.start() if end else len(text)]

    def names_on(self, k: int) -> list[str]:
        unit = self.units[k]
        names = []
        if unit.lang in ("sh", "sh-heredoc"):
            for name, masked, numeric in shell_refs(self.printed_segment(unit)):
                if not ((masked and self.shell_shown) or numeric or self.clean_shell(name, k)):
                    names.append(name)
            return names
        for expr in printed_exprs(unit):
            if re.match(r"^shown\(.*\)$", expr) and self.shown.get(self.heredoc_id(k)):
                continue
            if re.match(r"^len\(.*\)$", expr):
                continue
            root = re.match(r"^[A-Za-z_][A-Za-z0-9_]*", expr)
            name = root.group(0) if root else expr
            if not self.allowed(name, k, shell=False):
                names.append(name)
        return names


def _literal_head(quoted: str) -> str | None:
    """Text before the first expansion of a shell word, or None if it isn't quoted."""
    if quoted.startswith("'"):
        return quoted[1:quoted.find("'", 1)] if "'" in quoted[1:] else quoted[1:]
    if quoted.startswith('"'):
        head = re.split(r'(?<!\\)[$"]', quoted[1:], maxsplit=1)[0]
        return head
    return None


def leading_value(unit: Logical) -> bool:
    """A log line whose printed text begins with an interpolated value.

    The runner trims leading whitespace before it looks for `::`, and no mask
    touches `::`, so such a value can start a command of its own. A literal
    with at least one non-space character must come first.
    """
    text = unit.text
    if unit.lang == "sh":
        if COMMAND.search(text) or destination(text) != "log":
            return False
        bare = unquoted(text)
        m = SHELL_PRINT.search(bare)
        if not m:
            return False
        rest = text[m.end():].lstrip()
        if m.group(1) == "echo":
            while re.match(r"-[neE]+\s", rest):
                rest = rest.split(None, 1)[1] if " " in rest else ""
            if not rest or rest[0] in ";&|>":
                return False
            head = _literal_head(rest)
            return rest.startswith("$") or (head is not None and not head.strip() and "$" in rest.split(";")[0])
        # printf FORMAT ARGS: the format is quoted text; a value leads when
        # the format starts with a conversion.
        head = _literal_head(rest)
        if head is None:
            return rest.startswith("$")
        lead = head.split("%", 1)[0]
        return "%" in head and not lead.strip()
    if unit.lang in ("py", "js"):
        m = (PY_PRINT if unit.lang == "py" else JS_PRINT).search(text)
        if not m or COMMAND.search(text):
            return False
        args = call_args(text, m.end())
        if not args:
            return False
        first = args[0]
        lit = re.match(r"""^([rRbBfF]{0,2})(['"`])(.*)""", first)
        if not lit:
            return True
        prefix, quote, body = lit.groups()
        if quote == "`":
            head = body.split("${", 1)[0]
            return "${" in body and not head.strip()
        if "f" in prefix.lower():
            head = re.split(r"(?<!\{)\{(?!\{)", body, maxsplit=1)[0]
            return head != body and not head.strip()
        return False
    return False


def audit_body(body: Body, siblings: list[Body] | None = None, entries: tuple[Allowed, ...] = ALLOWED,
               used: set[Allowed] | None = None) -> list[dict]:
    checker = Checker(body, siblings if siblings is not None else [body], entries,
                      used if used is not None else set())
    findings = []
    redirected, _, _ = redirected_groups(checker.units)
    for k in sorted(sink_units(checker.units)):
        line = body.first_line + checker.units[k].index
        for name in dict.fromkeys(checker.names_on(k)):
            findings.append(finding(
                body.path, line, body.step,
                f"`{capped(name)}` reaches a log line or env-file write unmasked. Print it through the canonical "
                "shown() helper, refuse a control character and '##[' before it, or add it to ALLOWED with "
                "the reason it is constrained."))
        if checker.units[k].lang in ("sh", "sh-heredoc") and SEAM.search(checker.units[k].text):
            findings.append(finding(
                body.path, line, body.step,
                f"`{SEAM_NAME}`: a masked value sits next to a literal '#' or '[' or another masked value, so "
                "'##[' can re-form across the seam. Put a space or another character between them."))
        if k not in redirected and leading_value(checker.units[k]) \
                and not checker.allowed(LEADING, k, shell=checker.units[k].lang == "sh"):
            findings.append(finding(
                body.path, line, body.step,
                f"`{LEADING}`: this log line begins with an interpolated value. No mask touches a "
                "leading '::', so put a literal in front of it."))
    for k in checker.summary_units():
        unit = checker.units[k]
        line = body.first_line + unit.index
        names = checker.summary_shell(k) if unit.lang in ("sh", "sh-heredoc") else checker.summary_template(k)
        for name in dict.fromkeys(names):
            if name == OUTPUT_NAME:
                message = (f"`{OUTPUT_NAME}`: a command's output reaches a step-summary write as Markdown. Capture "
                           "it and write it through the canonical md_pre helper (md_code for one line).")
            else:
                message = (f"`{capped(name)}` reaches a step-summary write unencoded. Write it through the "
                           "canonical md_code/md_pre helper (mdCode/mdPre in Node, md_code/md_pre in Python), or "
                           "add it to ALLOWED with sink='summary' and the reason it is constrained.")
            findings.append(finding(body.path, line, body.step, message))
    return findings


# --- the repository --------------------------------------------------------------


def audit(root: Path, entries: tuple[Allowed, ...] = ALLOWED) -> tuple[list[dict], list[Allowed]]:
    """Findings, and the ALLOWED entries no line used (stale)."""
    findings: list[dict] = []
    used: set[Allowed] = set()
    audited = set()
    for path in candidate_files(root):
        rel = path.relative_to(root).as_posix()
        audited.add(rel)
        try:
            bodies = bodies_of(root, path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            # Fail closed, without echoing the file: a parser's message can
            # quote a line of it.
            findings.append(finding(rel, 0, "-", f"could not be read or parsed ({type(exc).__name__}); "
                                                 "nothing in it was checked."))
            continue
        for body in bodies:
            findings += audit_body(body, bodies, entries, used)
    # Stale: an entry for an audited file that no line needed.
    stale = [e for e in entries if e.path in audited and e not in used]
    return findings, stale


# --- output in the runner's command format -----------------------------------------


def capped(value: str) -> str:
    return value if len(value) <= CAP else value[:CAP] + "..."


def escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    return escape_data(capped(value)).replace(":", "%3A").replace(",", "%2C")


def shown(value: str) -> str:
    """For a plain log line: control characters as '?', '##[' as '#?['."""
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "?", capped(value)).replace("##[", "#?[")


def annotation(path: str, line: int, message: str) -> str:
    location = f"file={escape_property(path)}" + (f",line={line}" if line else "")
    return f"::error {location}::{escape_data(message)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: this script's repository)")
    args = parser.parse_args(argv)
    findings, stale = audit(args.root)
    for f in findings:
        print(annotation(f["path"], f["line"], f"step '{capped(f['step'])}': {f['message']}"))
    for e in stale:
        print(annotation(e.path, 0, f"ALLOWED entry for `{e.name}` matches no line; remove it or fix its scope."))
    if not findings and not stale:
        print(f"Every log line, env-file and step-summary write in {shown(str(args.root))} prints only masked "
              "or constrained values.")
    return 1 if findings or stale else 0


if __name__ == "__main__":
    sys.exit(main())
