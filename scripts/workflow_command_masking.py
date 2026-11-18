#!/usr/bin/env python3
"""Refuse a log line or env-file write that carries an unchecked value.

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
    -- and a print piped into another command;
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
  * `shell: python` steps and other non-bash `shell:` values;
  * Python string concatenation, `%` and `.format(...)`, and `+` in Node --
    only f-strings, template literals and bare arguments are read;
  * `: "${x:=$V}"`, `printf -v`, `eval`, `${!n}`, `declare -n`, an alias or a
    variable holding `$GITHUB_OUTPUT`, a command prefix held in a variable,
    `node -e` / `python -c` one-liners;
  * `actions/**/*.bash` and extension-less scripts;
  * `${{ ... }}` expressions in a `run:` body (a neighbouring class),
    `$GITHUB_STEP_SUMMARY` (Markdown, not a command channel), and the
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
ENV_FILE = re.compile(r"""(?:>>?|\btee\b(?:\s+-a)?)\s*["']?\$\{?GITHUB_(?:OUTPUT|ENV|STATE|PATH)\b\}?["']?""")
SUMMARY = re.compile(r"""\$\{?GITHUB_STEP_SUMMARY\b""")
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
    can't outlive the check.
    """

    path: str
    name: str
    reason: str
    step: str | None = None
    env: str | None = None
    after: str | None = None
    source: tuple[str, str] | None = None


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
    """Where a shell line's stdout goes: log, file, envfile or pipe."""
    bare = unquoted(text)
    if ENV_FILE.search(text):
        return "envfile"
    if re.search(r"(?<!\|)\|(?!\|)", bare):
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


def redirected_groups(units: list[Logical]) -> tuple[set[int], set[int]]:
    """Lines inside a `{ ... } > target` group: all of them, and those into an env file."""
    redirected: set[int] = set()
    envfile: set[int] = set()
    for k, unit in enumerate(units):
        if unit.lang == "sh" and re.match(r"^\s*\}", unit.text) and destination(unit.text) != "log":
            depth = 0
            for j in range(k, -1, -1):
                stripped = units[j].text.strip()
                if stripped.startswith("}"):
                    depth += 1
                if stripped == "{":
                    depth -= 1
                    if depth == 0:
                        redirected.update(range(j + 1, k))
                        if destination(unit.text) == "envfile":
                            envfile.update(range(j + 1, k))
                        break
    return redirected, envfile


def sink_units(units: list[Logical]) -> set[int]:
    """Indices of units that emit a command, write an env file or print to the log."""
    redirected, sinks = redirected_groups(units)
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
                  and text.strip() != SHELL_SHOWN):
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


def shell_refs(text: str) -> list[tuple[str, bool, bool]]:
    """(name, masked, numeric) for every expansion outside single quotes."""
    text = ENV_FILE.sub("", text)
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
            masked = SHELL_MASKED.match(text, i)
            if masked:
                refs.append((masked.group(1), True, False))
                i = masked.end()
                continue
            m = SHELL_REF.match(text, i)
            if m:
                if m.group(2):
                    refs.append((m.group(2), False, bool(m.group(1))))
                    # `${x:-$y}`, `${x//pat/$y}`: the modifier expands too.
                    refs += shell_refs(m.group(3))
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

    def heredoc_id(self, k: int) -> int:
        j = k
        while j > 0 and self.units[j - 1].lang == self.units[k].lang:
            j -= 1
        return j

    def allowed(self, name: str, k: int, shell: bool) -> bool:
        body = self.body
        found = []
        for entry in self.entries:
            if entry.path not in ("*", body.path) or entry.name != name:
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
    redirected, _ = redirected_groups(checker.units)
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
        print(f"Every log line and env-file write in {shown(str(args.root))} prints only masked or "
              "constrained values.")
    return 1 if findings or stale else 0


if __name__ == "__main__":
    sys.exit(main())
