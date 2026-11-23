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
    `$GITHUB_PATH` (`>`, `>>`, `>|`, `>&`, `&>`, `tee`, `dd of=`) -- a `{
    ...; } >> "$GITHUB_OUTPUT"` group and a heredoc written there count line
    by line; a heredoc ends only on a line that is exactly its delimiter
    (after stripping leading tabs for `<<-`), as in bash, so `  PY` or `PY `
    is a line of it -- or
  * prints to the log: a shell `echo`/`printf` statement whose output is not
    redirected to a file nor piped into a command other than `tee` or `cat`
    (`| tee out.log`, `|& cat` print it to the log, #513) -- every such
    statement of the line, not only the first, each read by its own
    pipeline's redirects and those of a group, compound or subshell the line
    closes around it (`echo x > f; echo "$V"`, `echo x | tee f && echo
    "$V"`; `{ echo "$V"; } > f` is a file's, #513) --, the words of the
    commands it pipes into counting with it, but for a `tee`'s, which name
    files, up to a process substitution among them, whose commands print
    (`| tee >(echo "$V")`, #513) (`| cat - <(printf "%s" "$V")`; in a group
    redirected to an env file `echo a | sed "s/a/$V/"` too), also in a `{`
    ... `}` group whose
    closer pipes it into `tee` or `cat`, opened on a line of its own or not
    -- likewise a line
    of a shell heredoc (`cat <<EOF | tee out.log`; a line of one that starts
    with `#` is data, not a comment, #513) --, a Python
    `print(...)`, `raise SystemExit(...)` or `sys.stdout/stderr.write(...)`, a
    Node `console.*(...)` or `process.stdout/stderr.write(...)` -- stdout
    counting when the heredoc's own stdout is not redirected or is piped into
    a command (`| cat`, `|& cat`, `| tee out.log`, also `| tee -a
    "$GITHUB_OUTPUT"` or the summary, which tee writes and the log both),
    also where the heredoc is opened inside a group whose closer pipes it
    (`} | tee -a "$GITHUB_OUTPUT"`; the `{` on the heredoc's line or a line
    of its own), or where its opener writes only another
    file descriptor into an env file (`2>> "$GITHUB_OUTPUT"`, #513); a stdout
    print into a plain file is not read. A redirect to `/dev/stdout`,
    `/dev/stderr`, `/dev/fd/1` or `2`, `/proc/self/fd/1` or `2`, or into a
    process substitution (`> >(cat)`) is the log, not a file (#513), in
    shell and on a heredoc's opener alike. Such a print is read as strictly as an env-file line
    (below, #511): every print call on the line, every argument that is not
    one plain string literal, `end=`, `sep=` and the continuation lines of
    the call, which tell its stream as well (`file=sys.stderr` on one makes
    the call a log print, whatever the heredoc's stdout does; a comment in
    the call -- Python's `#`, Node's `//` and `/* */` -- is skipped, so a `)`
    in it doesn't end the call, #513) --
  * is a line of a Python or Node heredoc whose stdout goes to one of the
    env files above (#507): redirected there (`>`, `>>`, `>|`, `>&`), piped into
    `tee` with the file among its arguments (`tee -a`, `tee --append`, `tee
    -ai --`, `tee -a /dev/null "$GITHUB_OUTPUT"`) or into `dd ... of=`, or
    opened without a stdout redirect of its own inside a group or compound
    redirected there -- every line of it,
    read as strictly as a step-summary line (below): every print call on
    the line (`print (` and every `console` method included), every
    argument of a stdout print that is not one plain string literal,
    Python's `end=` and `sep=`, the continuation lines of a call not closed
    on its line (up to JOINED_LINES of them), and every f-string or template-literal part outside a
    stderr print -- a field nested in a format spec too (`{len(p):{p}}`: `p`
    sets the fill, a line end included, and the width; #513) -- must be
    `shown(...)` -- with the canonical definition in
    that heredoc -- or `len(...)`, or a name on ALLOWED. So `"v=" + p`,
    `"v=%s" % p` and `.format(p)` are findings there; its stderr prints are
    log lines, read as above, unless the line that opens the heredoc sends
    stderr into an env file as well (`2>>`, `&>`/`&>>` or `>&` there, or
    `2>&1`, `2>&01`, `2>/dev/stdout`, `2>/dev/fd/1`, `2>/proc/self/fd/1` or
    `|&` with stdout going there): then they are read as strictly as its
    stdout prints --

and interpolates a value. Each interpolated name must be one of the list
below -- the same list for a log line and an env-file write, in shell and in
a Python or Node heredoc alike, since what an env file must not get from a
value is a line end, and the mask turns every one into `?`:

  * masked at the print by the canonical helper, which turns control
    characters into `?` and every `##[` into `#?[`: `$(shown "$name")` in
    shell, `shown(...)` in a Python or Node heredoc -- and only where the body
    or heredoc defines `shown` exactly that way (SHELL_SHOWN, PY_SHOWN and
    PY_SHOWN_RETURN, JS_SHOWN) -- in Python with PY_SHOWN_RETURN as the
    first line of the body that isn't blank or a comment, and no decorator
    above the `def` (one continued over bracketed or backslash-joined lines
    too: `@(lambda f:`, `    str)`, its brackets counted outside strings and
    comments: `    "(" and str)`, `    str)  # (`, and none proven through a
    line with a quote: `    f"{"("}" and str)`) -- and nothing else there binds the
    name (#513): in shell no other definition (wherever `shown()` or
    `function shown` stands after a blank or an operator: `a) shown() {`,
    `then shown() {`, `! shown() {`, `time shown() {`), `unset`, `alias` or `declare -f`/`export -f` of
    `shown`; in a Python or Node heredoc no mention of `shown` other than a
    call of it (`shown = str`, `shown: T = ...`, `shown := ...`, `import ...
    as shown`, `from ... import shown`, `for shown in`, `with ... as shown`,
    a second `def shown`, `let`/`var shown`, `function shown`, a parameter).
    Only those exact lines are the helper's own: a line that merely starts
    `def shown(` is read like any other, prints and all;
  * assigned from such a masked expansion (`x=$(shown "$x")`) by a
    statement that dominates the print (#507): the block holding the
    assignment -- an `if` branch, a loop body, a `case` arm, a `{ ...; }`
    group, a `( ... )` subshell, a function body, or the body itself --
    also encloses the print, and walking back from the print to it meets no
    assignment to the name that isn't masked (one on the print's own line
    counts as met). "The print" is the statement that expands the name --
    each one, where several on the line do -- not the line: in `true; while
    ...; do echo "$x"` the echo sits in the loop, in `f() { echo "$x"; }` in
    the function body; a heredoc's lines belong to every statement of the
    line that opens it. A masked assignment in a block that doesn't enclose
    the print is passed over, not counted. The assignment must be a
    statement of its own, run unconditionally where it stands: not after
    `&&` or `||` -- also not at the start of a line after one that ends in
    `&&`, `||`, `|` or `|&` --, not in a pipeline or in the background, not a
    prefix of a command (`x=$(shown "$x") cmd` sets x for cmd only), not
    after a `(` on the same line (see the constant rule), not to an element
    (`x[1]=$(shown "$x")` sets one element, `$x` is `x[0]`: it is an
    unmasked assignment -- also through `declare`/`typeset x[0]=...`, and
    with a nested subscript, `x[${a[0]}]=...`), and the last assignment
    to the name on its line. Since a function body runs where
    the function is called, not where it stands, a print inside one the
    mask is outside of is not covered, and an unmasked assignment to the
    name inside a function body the print is outside of voids every mask of
    the name for that print (a `local` one included). Nor is a print covered
    that an unmasked assignment follows inside a loop enclosing the print
    but not the mask (the next pass prints it). Blocks are read statement by
    statement from their keywords (`if`/`then`/`elif`/`else`/`fi`, `for`/`while`/`until`/`select`
    ... `done`, `case`/`;;`/`esac`, `{`/`}`, `(`/`)`); in a `case` a `)`
    ends a pattern only where something stands before it on its segment --
    a pattern is never empty, so a `)` alone closes what the guard didn't
    see open, as at top level (see below); and a line that leaves a `$(`,
    `<(` or `>(` open -- a substitution over lines -- leaves the body
    unattributed wherever its `)` stands (`x=$(shown "$x"))` closing it
    reads like a pattern, #513). A function body is
    the compound command after `f()`, `f ()` or `function f` [`()`] --
    before an empty `()` any single word is a function's name (`x@y()`,
    `a/b()`, `f+()`), since bash takes it as one --
    wherever it opens (same line or a later one) and whatever it is (`{
    ...; }`, `( ... )`, `if`, a loop, `case`). Where a closer has no
    matching opener, a block stays open -- a quoted string over several
    lines can read that way -- or a function definition has a
    body the guard doesn't read, no block is attributed in that body and no
    masked assignment covers anything there (errs towards a finding);
  * refused earlier in the same body by the canonical check
    `if [[ "$name" == *[[:cntrl:]]* || "$name" == *'##['* ]]; then`, whose
    then-branch holds an `exit` statement at its own level (not in a comment,
    a string, a subshell, a nested block or an else-branch), and with no
    assignment to the name anywhere after the check (a loop could reach one
    before the print);
  * constant by construction: every assignment in the body, or the step's
    `env:` value, is a literal -- or a string built only from literals and
    names that pass this list themselves (a message assembled from a refused
    tag); a command substitution never is, nor a target of `read` (every
    name-shaped word after it, an option's argument too), `mapfile`,
    `readarray`, `getopts`, `let`, `for` or `select`, nor an assignment in a
    `( ... )` subshell (it doesn't reach a print outside it; one after a
    `(` on the same line -- inside a case arm's `(pattern)` too, as in
    `case a in (x=lit) ...` -- is never read as a literal, while one after
    the pattern's closing `)`, as in `(a) mode=fast ;;`, is a statement of
    the arm and is), nor assignment words before a command (`a=1 x=lit cmd`
    sets x for cmd only); `x+=...`, `x[0]=...` and `x[${a[0]}]=...` count as
    assignments (after `declare` or `typeset` too), and
    so does a second assignment word (`a=1 x="$v"`), one after `typeset`,
    `time`, `elif`, `while`, `until` or a case pattern's `)` (`a) x="$v"
    ;;`); `(( x==1 ))` is arithmetic, not one;
  * numeric by construction: `${#name}`, `${#name[@]}`, `len(...)`;
  * on ALLOWED below, whose every entry states why the value is constrained.

Two rules hold per line, whatever its names:

  * a log line must not BEGIN with an interpolated value: the runner trims
    leading whitespace before it looks for `::`, and no mask touches `::`. A
    literal with a non-space character must come first (`echo "x $v"`,
    `printf 'gh: %s'`, `print(f"  - {v}")`); the few lines that start with a
    value are on ALLOWED under the name `<leading value>`, with the reason.
    In a Python or Node heredoc this holds for every log print call on the
    line (#511), each taken to start a line, and after every line end the
    printed text holds: a line-end escape in a literal (`f"ok\\n{v}"`;
    Python's `\\U0000000a` too, and a `\\N{...}` whose name Python resolves
    to a line end, in any case or by an alias: `\\N{nl}`, `\\N{cr}`), a
    `sep=` that holds one, a value joined by `+` to a literal that ends in
    one; the parts formatted in by `%`, `.format(...)` or a Node `console`
    `%s` count as values;
  * `$(shown "...")` must not sit directly next to a literal `#` or `[` or
    another `$(shown "...")`, quotes in between included -- `'#'` followed by
    a masked `#[x` re-forms `##[` (`<mask seam>`).

A line of a Python or Node heredoc whose delimiter is unquoted (`<<PY`, not
`<<'PY'`, `<<"PY"` or `<<\\PY`) must not hold `$` or a backtick, wherever the
heredoc's output goes (`<unquoted heredoc>`): the shell expands both before
the interpreter reads the line, so a value lands in the code itself, which
the Python or Node reading doesn't see.

The step summary is a third sink with its own rule (#506). GitHub renders
`$GITHUB_STEP_SUMMARY` as Markdown, so a controlled value there can add a
link, an image, a heading, a mention or a table cell. Every line whose output
reaches it -- a statement redirected (`>`, `>>`, `>|`, `>&`) or `tee`d there,
also through `> >(tee ...)` and whatever else the line holds; a statement of
a `{ ...; } >> "$GITHUB_STEP_SUMMARY"` group, a function body (`f() {`,
`function f {`) or a `for`/`while`/`until`/`if` compound redirected or piped
into `tee` there as a whole, its opening line included, unless it sends its
own stdout elsewhere -- openers and closers count anywhere at statement level
(`echo "$v"; } >> ...` ends its group), and a closer redirected there whose
opener the guard can't find is itself a finding (`<summary group>`); a line
of a heredoc written there by a bare `cat`, or a Python or Node heredoc whose
stdout goes there (their stderr prints are read as log lines, though `2>&1`
on the opener sends them into the summary too; that isn't read) -- also one opened
inside such a group without a stdout redirect of its own -- may interpolate
only names that are:

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
heredoc, every print call on a line counts (`print (` with a space, and every
`console` method -- all but `error`, `warn`, `trace` and `assert` write to
stdout), with the continuation lines of a call not closed on its line (up
to JOINED_LINES, #513): every argument of a stdout print that is not one
plain string literal, Python's `end=` and `sep=`, and every f-string or template-literal
part on the line outside a stderr print must be a call of the helper. Whether
a print goes to stderr is read from its name or its `file=` argument, never
from other text on the line. An env-file heredoc is read the same way, with
`shown(...)` as the helper, and so are the log prints of any heredoc (#511).

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
    -- and a print piped into a command other than `tee` or `cat`, on a log
    line (on a summary line both are refused as `<command output>`); nor a
    print at the end of a pipeline (`true | echo "##[warning]$V"`, #513):
    a print's sink is read per pipeline, and a pipeline with a `|` reads as
    piped into the command after it, so a print that is that command is
    passed over -- reading it needs the pipeline's members told apart;
  * a summary write inside a command substitution: the body of `$(...)` is
    blanked before sinks are read, so `out=$(echo "$V" | tee -a
    "$GITHUB_STEP_SUMMARY")` and `x=$(echo "$V" >> "$GITHUB_STEP_SUMMARY")`
    pass with a raw value; likewise an env-file write inside a `$(...)` in
    the body of an unquoted heredoc whose own destination is a plain file or
    the log (`cat > f <<EOF` then `$(echo "v=$V" >> "$GITHUB_OUTPUT")`):
    bash runs it, but a heredoc line is a sink only by the heredoc's own
    destination, and redirects inside its `$(...)` aren't read;
  * a leading value the line-start rule can't see: an `echo` whose first word
    is built by a command substitution or a variable holding the whole
    message, and a call site of a helper such as fork-guard's or setup-vale's
    `finish` (both on ALLOWED, read by hand); nor is the rule applied to a
    line of a shell heredoc whose destination is the log (`cat <<EOF`, then
    `$(shown "$V") x`, then `EOF`; #513): a shell heredoc often feeds a
    command's stdin (`while read`, `grep`), where a line-start rule would
    refuse harmless input, and telling the two apart needs knowing what the
    command prints;
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
  * prints the selector doesn't see: `cat <<<"$V"`, `tee` or `cat` reading a
    file, `set -x` tracing, an EXIT trap or a function that prints and is
    called elsewhere, `logger`;
  * a canonical `shown` that is defined only after its first use (the guard
    checks that the body or heredoc defines it, not where), and one rebound
    in a way that doesn't name it: through `eval` or `source` (shell),
    `globals()`, `exec` or `setattr` (Python), `globalThis[...]` or `eval`
    (Node) -- nor a rebinding of a helper the canonical `shown` calls
    (`re.sub = lambda a, b, c: c`, `String.prototype.replace = ...`): the
    guard reads the definition's text, not what its calls resolve to;
  * on a log line, what block dominance doesn't read (#507): an assignment
    the guard doesn't see as one -- through `eval`, `source`, a `trap`,
    `printf -v`, `wait -p`, `coproc NAME`, `exec {fd}>...`, `: "${x:=$V}"`
    or a nameref (`declare -n`) -- doesn't stop
    the walk back from the print, and a command run between the mask and
    the print that reassigns the name some other way (a script `source`d
    from a file) isn't read. A loop that runs zero times, a branch that
    doesn't run or a function that is never called needs no path reading:
    a mask in one covers only prints in the same block, which then don't
    run either; but a mask that an `exit`, `return`, `break` or `continue`
    skips is still read as run, which is harmless only because the same
    jump skips every print it covers. Blocks are told by keywords at the
    start of a statement, not by a parser: a keyword at the start of a
    line inside a quoted string over lines can open or close one (a body
    left unbalanced by it refuses, see above; one that happens to balance is
    read with the wrong blocks), and so can one inside a backtick
    substitution over lines; a `$(...)` over lines refuses (see above). The summary rule reads every
    assignment instead;
  * `shell: python` steps and other non-bash `shell:` values;
  * in the step summary: a heredoc that opens the summary file by a path
    it doesn't get by naming `GITHUB_STEP_SUMMARY` (see the env-file entry
    below), and a summary written by a script run from a file --
    scripts/docs_freshness.py, scripts/branch_protection_audit.py and
    scripts/required_check_triggers.py encode theirs with PY_MD's helpers,
    held by their own tests, not by this guard; a helper redefined through
    `eval` or `source` (shell), `exec` or an import machinery call (Python)
    or `require`/`eval` (Node); and a `case` compound redirected there (its
    arms read as commands, so that one errs towards a finding);
  * on a log line, a Python or Node heredoc whose stdout the guard reads as
    going to a file though bash sends it to the log: `>&2 2>> f` sends stdout
    to the log's stderr and only then stderr to f, but the `>>` reads as a
    stdout redirect, so its stdout prints are not read (#511 found it);
  * a heredoc fed to an interpreter the guard doesn't name -- only the
    simple command that carries the `<<` (the text before it after the last
    unquoted `|`, `|&`, `;`, `&&`, `||` or `&`, or after the `$(`, `(` or
    backtick it stands in), its leading assignments skipped, is searched,
    for `python` or `pypy` with a version, `node`, `nodejs`, `deno` or `bun`
    as a word, a path, a suffix or an expansion around it allowed
    (`/usr/bin/python3`, `${PY:-python3}`, `python.exe`, `python3-dbg`,
    `python3.13t`, `python3.12m`, `sudo python3`), but not in a word that
    ends in `.sh`, `.bash` or `.zsh` (`./run-python-tests.sh`, #513); the
    first name in it decides (`node - python3` is read as Node), a value
    assigned (`env X=node python3`) only where no other word names one; a
    name in an earlier command of the line decides nothing (`node
    --version; python3 -` is read as Python, #513), unless the command is
    run from a parameter or by a function or alias the line defines
    (`PY=python3; $PY -`) -- (`ruby`, `perl`, `php`, `uv run -` without the
    word `python`, a name inside a longer word: `mypython`, `pythonw`, or one
    set on an earlier line: `PY=python3`, then `$PY -`): with a quoted delimiter
    its lines are data, with an unquoted one shell text; nor a delimiter
    that starts with a digit or holds a character other than a letter, a
    digit, `_`, `-` or `.`;
  * in an env-file or summary heredoc or a log print, a bare name on a
    continuation line of a print call more than JOINED_LINES lines below
    its start; in an
    env-file heredoc, a stderr print in
    a heredoc whose stderr reaches the env file other than through a
    redirect on the line that opens it -- through a redirect of an enclosing
    group or compound (`{ ...; } >> "$GITHUB_OUTPUT" 2>&1`), an earlier
    `exec 2>> "$GITHUB_OUTPUT"`, another file descriptor (`3>>"$GITHUB_OUTPUT"
    2>&3`) or a process substitution (`2> >(tee -a "$GITHUB_OUTPUT")`): read
    as a log line only;
  * stderr written other than by a named print, which is read neither as a
    log line nor, in a heredoc whose stderr goes to an env file, as an entry
    (#513): in Python `logging.warning(p)`, `warnings.warn(p)`, an uncaught
    `raise ValueError(p)` (its traceback), `assert False, p`, `sys.exit(p)`,
    `os.write(2, ...)`, a print or stderr writer under another name (`w =
    sys.stderr.write`, `say = vars(builtins)["pr" + "int"]`), and every print
    after `sys.stderr = sys.stdout`; in Node `throw new Error(p)`,
    `process.emitWarning(p)`, `fs.writeSync(2, ...)` and a stderr writer
    under another name (`process.stderr.write.bind(process.stderr)`). The
    set is open-ended: telling it apart needs a Python and a JavaScript
    parser. An alias that names `print` or `console` is refused as
    `<unknown writer>` instead (`say = print`, `functools.partial(print,
    file=sys.stderr)`, `console["error"]`, `const e = console.error`, see
    below);
  * an interpreter fed by a pipe (`cat <<PY | python3 -`): the heredoc is
    `cat`'s, read as data or shell text, and the interpreter's own stdout is
    not followed; nor a redirect written before the command (`<<'PY' python3
    - >> "$GITHUB_OUTPUT"`), since the interpreter is named only before the
    `<<`;
  * an env file or the summary written by a command other than a
    redirect, `tee` or `dd of=` (`cp /dev/stdin "$GITHUB_OUTPUT"`,
    `sponge`, `install`), or by a `tee` whose arguments before the file
    hold a quoted word with a space;
  * an assignment on a later line of a `( ... )` subshell, in a body whose
    blocks the guard can't attribute: read as an ordinary one, so a literal
    there can make the name constant (one on the line of its `(` never
    does);
  * `: "${x:=$V}"`, `printf -v`, `eval`, `${!n}`, `declare -n`, an alias or a
    variable holding `$GITHUB_OUTPUT` or `$GITHUB_STEP_SUMMARY`, a command
    prefix held in a variable, `node -e` / `python -c` one-liners, and
    `${!m[@]}`: the keys of an associative array (`m["$V"]=1`) aren't read
    as a reference to anything (#513);
  * in a Node heredoc, a regex literal holding `'` or `[ /*]`: print calls
    are read by quote and comment tracking, not a parser, so the literal
    opens a string or a comment and the names after it on the call are
    lost -- the line stays refused, named by the text from the literal on,
    not by those names (#513);
  * a Python or Node heredoc that opens an env file or the summary itself
    by a path it gets other than by naming the variable: a line that names
    `GITHUB_ENV`, `GITHUB_OUTPUT`, `GITHUB_STATE`, `GITHUB_PATH` or
    `GITHUB_STEP_SUMMARY` is refused (`<env file opened>`, #513), but a
    name built at run time (`os.environ["GITHUB_" + k]`), a path passed in
    from shell under another name, or one into the runner's file-commands
    directory isn't seen, and what such a heredoc writes is not read;
  * an env-file entry in the multi-line form (`name<<DELIM`, value lines,
    `DELIM`): a masked value has no line end, but a value line that equals
    the delimiter ends the entry early, so the lines after it become entries
    of their own. The guard doesn't check that the delimiter is one a value
    can't guess (the one step that writes such an entry today, in
    reusable-release-archive.yml, ends it with a kernel UUID), in shell or
    in a heredoc;
  * an array literal that spans lines (`kw=(` ... `)`): its words on the
    later lines read as statements, so a keyword there opens or closes a
    group (one closed on its own line is blanked);
  * a write to a standard stream the Python or Node reading doesn't see by
    name. A line that names `print` or `console` outside a print call the
    strict reading names (`console['log'](p)`, `out = print`, `const log =
    console.log`) is refused on every heredoc, and one that names
    `sys.stdout`, `sys.__stdout__` or `process.stdout` outside one
    (`sys.stdout.writelines([p])`, `sys.stdout.buffer.write(...)`,
    `json.dump(p, sys.stdout)`, `out = sys.stdout`) where the heredoc's
    stdout reaches the log, an env file or the summary (`<unknown writer>`,
    #513); not covered: a stream reached without naming those
    (`from sys import stdout`, `getattr(sys, "stdout")`, `os.write(1,
    ...)`, `pprint.pprint`, `input(prompt)`, a child process that inherits
    stdout, `globalThis["console"]`). A print's `file=` is read (#511): `sys.stdout` and
    `sys.__stdout__` are stdout, `sys.stderr` and `sys.__stderr__` stderr (in
    parentheses too); any other `file=` is read as stdout and as stderr both,
    so it reaches the log and, in an env-file or summary heredoc, that sink
    as well -- and so is a call whose `)` isn't found in its joined lines,
    one with a `**` argument, or one with an f-string or t-string (PEP 750,
    read like an f-string) whose replacement field holds its own quote
    (`f"{d[")"]}"`, legal since Python 3.12), whose `file=` the guard can't
    see (the `**` argument itself is read as a value, as it may carry `end=`
    or `sep=`). A text backstop fails closed where that reading and the
    text disagree: a print whose text -- from its name to its parsed `)`,
    or on to the end of its joined lines where anything but a `;` and the
    next print follows that `)` -- names `stderr` or a `file=` its parse
    doesn't read as `file=sys.stderr` is read as stdout and as stderr both
    (`sys.stderr.write` and `SystemExit` are stderr by name), and text past
    the `)` is read as one more argument, a value. An
    argument after a backslash line continuation is read as written, so
    `file=` or `**` there counts. Not covered there: `sys.stderr` rebound
    (`sys.stderr = open(...)`; a rebinding of `sys.stdout` names it, and is
    refused where the heredoc's stdout reaches a sink, see above), and a
    write to a file the heredoc opens that isn't a named print
    (`f = open(...)` then `f.write(p)`), which isn't read at all;
  * a mask line that isn't a statement: `x=$(shown "$x")` on a line inside a
    quoted string over several lines or inside a backtick command
    substitution is read as a statement of its own, as a keyword there is
    (see block dominance above), so it can cover a print it never reaches
    -- `x="$V"`, `msg="`, `x=$(shown "$x")`, `"`, `echo "x $x"` (or the
    same with `msg='` ... `'`) prints the raw value and passes (#513):
    `assignments()` reads line by line, and telling a string line from a
    statement needs quote tracking across lines;
  * for the constant rule, whether an assignment runs where it stands: a
    literal assignment in a pipeline (`true | N=1`), in the background
    (`N=1 &`), in a function that is never called or under `if false` still
    makes an otherwise unset name constant, though the print sees the name
    unset (or as the runner set it);
  * `actions/**/*.bash` and extension-less scripts;
  * `${{ ... }}` expressions in a `run:` body (a neighbouring class), and the
    non-reusable workflows.

Refused although harmless (the log rule's block dominance and the env-file
heredoc reading err towards a finding, #507):

  * a mask that runs before the print without enclosing it: in a function
    called before the print, in a `{ ...; }` group, in an `if` or `while`
    condition with the print after the compound, on the print's own line
    (`x=$(shown "$V"); echo "x $x"`) or on the line that opens a heredoc
    the value is printed in -- mask on a line of its own, in a block that
    encloses the print, instead;
  * every masked assignment in a body whose blocks the guard can't attribute
    -- also one with a `$(`, `<(` or `>(` left open on a line, a substitution
    over lines (#513): any `y=$(` or `done < <(` whose `)` stands on a later
    line voids every mask in the body, even one outside the substitution
    (`x=$(shown "$V")` on a line of its own, then `y=$(`, `date`, `)`, then
    `echo "x $x"`) -- keep a substitution on one line;
  * a mask after a subshell's `(` on the same line (`( x=$(shown "$V");
    echo "x $x" )`): an assignment after a `(` on the same line is read as
    unknown -- open the subshell on a line of its own instead -- and a raw
    assignment in a subshell the print is outside of (`x=lit; ( x="$V" );
    echo "x $x"`) still stops the walk back and voids the constant rule,
    though it can't reach the print;
  * in an env-file heredoc, and in a log print of any heredoc (#511), a
    print argument built from literals or from `shown(...)` by
    concatenation, `%` or `.format(...)` (`"v=" + shown(p)`,
    `"n=" + str(len(p))`) -- put `shown(...)` in an f-string or template
    literal instead; the finding names the whole expression, not a value
    an ALLOWED entry would name (`expr_name`: an operator expression such
    as `total + p` is named whole, also in an f-string field, so an entry
    for `total` doesn't cover the `p` in it) -- and an f-string or template part
    outside any print on such a line (`msg = f"v={p}"`), as on a summary
    line; in an env-file heredoc so is a value encoded for the entry,
    `print(f"matrix={json.dumps(m)}")` or ``console.log(`matrix=${JSON.stringify(m)}`)``,
    though JSON escapes every line end -- mask it as well, or add the name to ALLOWED;
  * a print into a file the heredoc opens itself (#511): `file=` an
    `open(...)` of any path, or a name bound to one (`f = open("out.txt",
    "w")`, `with open(...) as f`), is read as stdout and stderr both -- as a
    log line, and in an env-file or summary heredoc as an entry or summary
    line as well, since its path, its opener or a rebinding of the name can
    make it a standard stream (`open("//dev/stdout", "w")`) -- write to the
    file with `f.write(...)` of a masked value, or mask the printed value;
  * a print call's text inside a string literal (`msg = "use print(p)"`):
    print calls are found by name, not by a parser, so it reads as a print
    of `p` -- on a log line, and in an env-file or summary heredoc;
  * a log print that follows one on its line ending without a line end
    (`print("x", end=""); print(shown(p))`): every print call is taken to
    start a line, so a value first in it is a `<leading value>`;
  * a stdout print whose text names `stderr` or a second `file=` without
    a `file=sys.stderr` argument (#511, the text backstop): `print("see
    stderr:", p)` or `print(p)  # file=sys.stderr` with the heredoc's stdout
    into a file reads as a log print of `p`, and a print with anything but
    `;` and the next print after its `)` on the line takes that text as a
    value as well -- keep the word out of the call's line, or mask the value;
  * a mention of `print`, `console` or a stdout object outside a print
    call the strict reading names that writes nothing (`sys.stdout.flush()`,
    `"print"` in a string, an inline comment naming one), a heredoc line
    that names an env-file variable only in text (`print("set
    GITHUB_OUTPUT")`), and a mention of `shown` other than a call in a
    Python or Node heredoc (`"shown"` in a string, `f(shown=1)`) or an
    `export -f shown` in shell (#513) -- reword, or add `<unknown writer>`
    or `<env file opened>` to ALLOWED with the reason;
  * a stderr print of a heredoc whose opener names `2>&1` or `|&` anywhere,
    also where stderr stays on the log (`2>&1 >> "$GITHUB_OUTPUT"`): read as
    an env-file entry and as a log line both;
  * a `$` or backtick the shell leaves alone in an unquoted Python or Node
    heredoc (`\\$`, a `$` before a space or a quote): every one is refused --
    quote the delimiter;
  * a delimiter quoted in part (`<<P"Y"`): bash takes it as the quoted
    delimiter `PY`, the guard as the unquoted delimiter `P`, so a harmless
    body with `$1` is refused as `<unquoted heredoc>` -- quote the whole
    delimiter;
  * a stdout print of a Python or Node heredoc piped into a command that
    doesn't print it (#511): `| jq . > out.json`, `| sort >> "$GITHUB_OUTPUT"`,
    `| wc -l`, a pipe later on the opener's line (`python3 - <<'PY' && a |
    b`): the guard doesn't follow a pipeline's output, so every pipe is read
    as reaching the log -- mask the value, or redirect the heredoc's own
    stdout (`python3 - <<'PY' > out.json`); likewise a shell print piped into
    `cat` or `tee` that writes elsewhere after all (`| cat > f`, `| cat >
    g`, `| tee f > g`, `| tee f | sort > g`) or among whose `tee` words a
    quoted `">("` stands (`| tee ">(" f`: read as a process substitution),
    a print after an `exec` that sends stdout to a file (`exec > f; echo
    "$V"`: read as a log print), and a line with a redirect to a standard
    stream or a process substitution beside one to a file (`> /dev/stderr > f`, `> >(cat > f)`,
    #513), and a name in the words of a command a print pipes into, other
    than a `tee`'s, that it doesn't print (`| tee f | grep -q "$p"`), or in
    the redirect target of a `tee` or `cat` it pipes into (`echo x | cat >
    "$p"`: charged to the print, #513), or among a `tee`'s words after a
    process substitution (`| tee >(cat) "$p"`);
  * `shown()` or `function shown` named inside quoted text in a shell body
    (`echo "call shown() first"`): read as another definition of `shown`,
    so it voids the mask of the whole body (#513) -- reword the text;
  * a decorator walk over foreign lines: walking up from a canonical `def
    shown`, lines are read one by one and the walk stops only at a line at
    most as indented as the `def` where the brackets of the lines walked
    balance and none of them holds a quote (#513), so a string literal or a
    bracket left open on any line between the `def` and an `@` at the start
    of an earlier line -- a decorator of another function (`@staticmethod`,
    `def f():`, `    return 'a'`), a line of a triple-quoted string --
    voids the definition -- define `shown` above every decorator, or put a
    plain statement without quotes or brackets right above the `def`.

Refused although harmless (the summary rule errs towards a finding):

  * a heredoc in an inner group with a target of its own, inside a group
    redirected to the summary (`{ { cat <<EOF ... EOF } > /tmp/f; } >>
    "$GITHUB_STEP_SUMMARY"`, or an inner `>> "$GITHUB_OUTPUT"`): its lines
    are read as summary lines, because the heredoc takes its destination
    from its own start line and the outer group, not from the inner group;
  * an array assignment inside a group or compound redirected to the summary
    (`for n in a; do kw=(if for); echo "- $(md_code "$n")"; done >> ...`):
    the statement reads as a command and is refused as `<command output>`.

Reads only. Exits non-zero on any finding, and on any file it can't read or
parse.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

# `::error::`, `::error title=x::`, `::add-mask::`, `::<token>::` (resume).
COMMAND = re.compile(r"::[A-Za-z0-9][A-Za-z0-9_-]*(?:\s[^:\n]*)?::")
# `>`, `>>`, the clobbering `>|` and `>&` (bash reads `>&word` with a word
# that isn't a number or `-` as `&>word`: stdout and stderr) into the file;
# `tee` with any options or other files before it (`tee -a`, `tee --append`,
# `tee -ai --`, `tee -a /dev/null "$GITHUB_OUTPUT"`); `dd ... of=`.
TEE_TO = r"""\btee\b(?:\s+[^\s|;&<>]+)*?\s+|\btee\s*"""
ENV_FILE = re.compile(
    r"""(?:(?:>>|>&|>\|?)\s*|""" + TEE_TO + r"""|\bdd\b[^|;&\n]*?\bof=)"""
    r"""["']?\$\{?GITHUB_(?:OUTPUT|ENV|STATE|PATH)\b\}?["']?""")
# The same for the step summary (`>&` too: stdout and stderr, as above).
SUMMARY_FILE = re.compile(
    r"""(?:(?:>>|>&|>\|?)\s*|""" + TEE_TO + r"""|\bdd\b[^|;&\n]*?\bof=)["']?\$\{?GITHUB_STEP_SUMMARY\b\}?["']?""")
# A pipe, not `||` and not the `|` of `>|`.
PIPE = re.compile(r"(?<![|>])\|(?!\|)")
# A stdout redirect elsewhere: `> f`, `>> f`, `>| f`, `>&2`, `&> f`.
STDOUT_ELSEWHERE = re.compile(r"(?<![0-9<])>>?\|?|(?<![0-9])>&\s*2|&>")
SUMMARY_TEE = re.compile(r"""(?:""" + TEE_TO + r"""|\bdd\b[^|;&\n]*?\bof=)["']?\$\{?GITHUB_STEP_SUMMARY\b""")
# `<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"`, `<<\EOF`; a delimiter may hold `-` and `.`.
# Groups: 1 a backslash, 2 a quote, 3 the delimiter; quoted when 1 or 2 is set.
HEREDOC = re.compile(r"""(?<!<)<<-?\s*(\\?)(['"]?)([A-Za-z_][A-Za-z0-9_.-]*)\2""")
# The interpreters whose heredoc is read as Python or as JavaScript, searched
# for as a word (`python3.12`, `python3.13t`, `python.exe`, `${PY:-python3}`,
# `/usr/bin/env python3`) in the heredoc's own simple command only -- see
# `interpreter_of`.
PY_INTERPRETER = re.compile(r"\b(?:python|pypy)[0-9.]*\b")
JS_INTERPRETER = re.compile(r"\b(?:node(?:js)?|deno|bun)\b")
# The leading assignment words of a simple command (`NAME=value`, `NAME+=value`).
LEADING_ASSIGNMENTS = re.compile(
    r"""^\s*(?:[A-Za-z_][A-Za-z0-9_]*\+?=(?:"(?:[^"\\]|\\.)*"|'[^']*'|\\.|[^\s"'\\])*\s+)*""")
# The shell word around a name, and the two kinds `interpreter_of` reads apart:
# a shell script (`./run-python-tests.sh`, #513) and an assignment (`X=node`).
SHELL_WORD = r"""[^\s;&|<>()]"""
SCRIPT_WORD = re.compile(r"""\.(?:sh|bash|zsh)["']*$""")
ASSIGNMENT_WORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
# `$name`, `${name...}`, `$1`; `${{` is an expression, `${#` a length.
SHELL_REF = re.compile(r"\$(?:\{(?!\{)(#?)([A-Za-z_][A-Za-z0-9_]*|[0-9])([^}]*)\}|([A-Za-z_][A-Za-z0-9_]*|[0-9]))")
# `$(shown "$x")`, `$(shown "${x}")`, `$(shown "$1")`.
SHELL_MASKED = re.compile(r"""\$\(shown "\$\{?([A-Za-z_][A-Za-z0-9_]*|[0-9])\}?"\)""")
MASKED_ASSIGNMENT = re.compile(r"""^"?\$\(shown "\$\{?([A-Za-z_][A-Za-z0-9_]*|[0-9])\}?"\)"?$""")
SHELL_SHOWN = """shown() { local v="${1//[[:cntrl:]]/?}"; printf '%s' "${v//\\#\\#\\[/#?[}"; }"""
# The canonical definition line itself, nothing on it after the colon: a line that
# only starts `def shown(` can hold a print of its own (`def shown(v): print(...)`).
PY_SHOWN = re.compile(r"^\s*def shown\(value\):\s*$")
# Any mention of `shown` in a Python or Node heredoc that is not a call of it
# -- an assignment, an annotation, a walrus, an import, a loop or `with`
# target, a parameter, a second definition -- outside the canonical lines:
# the heredoc's canonical definition then proves nothing (#513).
PY_SHOWN_NAME = re.compile(r"\bshown\b(?!\s*\()|\b(?:def|class)\s+shown\b")
JS_SHOWN_NAME = re.compile(r"\bshown\b(?!\s*\()|\bfunction\b\s*\*?\s*shown\b")
PY_SHOWN_RETURN = """return re.sub(r"[\\x00-\\x1f\\x7f-\\x9f]", "?", str(value)).replace("##[", "#?[")"""
JS_SHOWN = ("const shown = (value) => String(value).replace(/[\\u0000-\\u001f\\u007f-\\u009f]/g, '?')"
            ".replace(/##\\[/g, '#?[');")
REFUSAL = re.compile(
    r"""^\s*if\s+\[\[\s+"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?"\s+==\s+\*\[\[:cntrl:\]\]\*\s+\|\|\s+"""
    r""""\$\{?\1\}?"\s+==\s+\*'##\['\*\s+\]\];\s*then\s*$""")
EXIT_STATEMENT = re.compile(r"^exit(?:\s+[0-9]+)?\s*$")
# Also after a group's `{ `, a subshell's `(` (`{ x="$v"; }` assigns x) or a
# case pattern's `)` (`a) x="$v" ;;`) -- each only where it stands outside
# quotes, see `assignments` -- and after `time`. Not after `((`: `(( x==1 ))`
# is arithmetic, not an assignment.
STATEMENT_START = (r"(?:^|[;&|]\s*|\b(?:then|do|else|elif|if|while|until|time)\s+|!\s+|(?<!\$)\{\s+"
                   r"|(?<![$<>(])\((?!\()\s*|\)\s*)")
RHS = r"""("(?:[^"\\]|\\.)*"|'[^']*'|\$\((?:[^()]|\([^()]*\))*\)|[^\s;]*)"""
# An element's subscript: brackets nested one deep, so a nested one
# (`x[${a[0]}]=`) is read whole, not cut at its inner `]`; spaces inside count
# (`x[1 + 1]=`, #513).
SUBSCRIPT = r"\[(?:[^\[\]]|\[[^\[\]]*\])*\]"
# `x=`, `x+=`, `x[0]=`, `x[${a[0]}]=`.
TARGET = r"([A-Za-z_][A-Za-z0-9_]*)(?:" + SUBSCRIPT + r")?(\+?)="
ASSIGNMENT = re.compile(
    STATEMENT_START + r"(?:(?:local|readonly|export|declare|typeset)(?:\s+-\w+)*\s+)?" + TARGET + RHS)
# A further assignment word after one (`a=1 x="$v"`).
CHAINED = re.compile(r"\s+" + TARGET + RHS)
DECLARE_LIST = re.compile(r"""^\s*(?:local|readonly|declare|export|typeset)\b""")
# `declare x=...`, `typeset x+=...`, `declare x[0]=...` (group 2: the subscript).
DECLARED = re.compile(r"""\s([A-Za-z_][A-Za-z0-9_]*)(""" + SUBSCRIPT + r""")?(\+?)=("(?:[^"\\]|\\.)*"|'[^']*'|[^\s;]*)""")
# Commands whose words name variables they set: every name-shaped word after
# them is taken as a target (an option's argument too -- `read -p prompt`).
READERS = ("read", "mapfile", "readarray", "getopts", "let")
LOOP_OR_READ = re.compile(r"""\b(?:(?:for|select)\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b|read\s+(?:-[A-Za-z]+\s+(?:''\s+)?)*([A-Za-z_][A-Za-z0-9_]*)|mapfile\s+(?:-\w+\s+)*([A-Za-z_][A-Za-z0-9_]*))""")
# An `echo`/`printf` that starts a statement -- after a case pattern's `)` too
# (`b) echo "x $x" ;;`), and after a subshell's `(` (`( echo "x $x" )`, #513).
SHELL_PRINT = re.compile(r"(?:^\s*|[;&|()]\s*|\b(?:then|do|else|if|!)\s+|\{\s+)(echo|printf)\b(?!\s+-v\b)")
# Where a print's statement ends. Not at a pipe: what the commands after it
# print reaches the same sink (`{ echo a | sed "s/a/$V/"; } >> "$GITHUB_OUTPUT"`).
STATEMENT_END = re.compile(r";|&&|\|\||\bthen\b|\bdo\b")
# A pipe into `tee` and tee's words up to the next pipe: they name the files
# tee writes, which it doesn't print (`| tee "$f"`, #513) -- up to a process
# substitution, whose commands print to the log (`| tee >(cat; echo "$V")`),
# so it and the words after it count (read on the text: `unquoted` blanks it).
TEE_SEGMENT = re.compile(r"(?<![|>])\|(?!\|)&?\s*(?:[^\s|;&<>]*/)?tee(?![\w.-])[^|]*")
PROCESS_SUBSTITUTION = re.compile(r"[<>]\(")
# How a Python or Node print is read, on every sink (step summary, env file,
# log -- #511): a space before the call's `(` too, and every `console` method
# -- all but STDERR_PRINTS write to stdout.
PY_STRICT_PRINT = re.compile(r"\b(print|SystemExit|sys\.stdout\.write|sys\.stderr\.write)\s*\(")
JS_STRICT_PRINT = re.compile(r"\b(console\s*\.\s*[A-Za-z]+|process\.stdout\.write|process\.stderr\.write)\s*\(")
STDERR_PRINTS = {"SystemExit", "sys.stderr.write", "console.error", "console.warn", "console.trace", "console.assert",
                 "process.stderr.write"}
# A heredoc command that sends its stderr into an env file as well: `2>>`,
# `&>`/`&>>` or `>&` there, or -- its stdout going there -- `2>&1` (`2>&01`
# too: bash reads a file descriptor as a number), `2>/dev/stdout`,
# `2>/dev/fd/1`, `2>/proc/self/fd/1` or `|&` (read wherever it stands, so
# `2>&1 >> "$GITHUB_OUTPUT"`, which keeps stderr on the log, errs towards a
# finding). `2>&1` or `>&2` alone, with no env file on the line, never
# reaches this: the heredoc's stdout isn't an env file then.
STDERR_TO_ENV_FILE = re.compile(
    r"""(?:(?<![0-9])0*2>>?\|?|&>>?|(?<![0-9])>&)\s*["']?\$\{?GITHUB_(?:OUTPUT|ENV|STATE|PATH)\b"""
    r"""|(?<![0-9])0*2>&\s*0*1\b"""
    r"""|(?<![0-9])0*2>>?\|?\s*["']?/(?:dev/stdout\b|dev/fd/0*1\b|proc/self/fd/0*1\b)"""
    r"""|\|&""")
# The most continuation lines an env-file heredoc's print call is joined over.
JOINED_LINES = 50
# The depth `canonical_shown` reads a line above a `def` from, so a closing
# bracket never ends `bracket_state` early: what is left is the line's net count.
WALK_DEPTH = 1 << 20
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
# bash's substitution slows with the number of matches. It walks the
# punctuation codes by brace expansion (`{33..47} ...`), so it needs brace
# expansion on: under `set +B` it aborts (`printf: {91..96}: invalid number`).
# No step sets +B today.
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
# The log mask the same way: `shown` defined, aliased, unset or rebound
# anywhere but on its canonical line (#513) -- a definition wherever the word
# stands after a blank or an operator, not only at a statement's start (`a)
# shown() {`, `then shown() {`, `! shown() {`, `time shown() {`), failing closed.
SHELL_SHOWN_REBIND = re.compile(
    r"""\bfunction\s+shown\b|(?<![^\s;&|{}()!`])shown\s*\(\s*\)"""
    r"""|\b(?:unset|alias|unalias|declare\s+-f|readonly\s+-f|export\s+-f)\b[^;&|]*\bshown\b""")
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
    dest: str = "log"  # where a heredoc's stdout goes: log, file, envfile, summary, pipe
    origin: int = -1  # a heredoc line: the unit of the command that opened it
    expands: bool = False  # a heredoc line the shell expands: its delimiter is unquoted
    piped: bool = False  # a heredoc line whose opener has a pipe: its stdout may reach the log
    # An env-file heredoc line whose opener writes only another file
    # descriptor there (`2>> "$GITHUB_OUTPUT"`): its stdout is the log (#513).
    fd_logged: bool = False

    def stdout_logged(self) -> bool:
        """A Python or Node heredoc line's stdout prints are read as log lines (#511).

        Where the heredoc's stdout is the log, and -- failing closed -- where
        its opener pipes it into a command, whatever that command does with
        it: `| cat` and `| tee` print it to the log, and the guard doesn't
        follow a pipeline's output (`| tee -a "$GITHUB_OUTPUT"` is read as an
        env-file heredoc as well, `| jq . > out.json` as the log all the same).
        So does one whose opener writes only stderr or another file descriptor
        into an env file (`2>> "$GITHUB_OUTPUT"`), its stdout left on the log
        (#513).
        """
        return self.dest == "log" or self.piped or self.fd_logged


def unquoted(text: str, fill: str = " ") -> str:
    """The text with quoted strings and `$(...)` blanked, for finding `|` and `>`.

    `fill` is the character they are blanked with: a space by default, a
    word character where word boundaries must survive (`"a"#` is one word).
    """
    return _unquoted(text, fill)[0]


def opens_substitution(text: str) -> bool:
    """The line leaves a `$(`, `<(` or `>(` open: the substitution goes on over lines (#513)."""
    return _unquoted(text, " ")[1] > 0


def _unquoted(text: str, fill: str) -> tuple[str, int]:
    """`unquoted`, and the depth of `$(...)` left open at the end of the text."""
    out = []
    i, quote, depth = 0, None, 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            out.append(fill * len(text[i:i + 2]))
            i += 2
            continue
        if quote == "'":
            quote = None if c == "'" else quote
            out.append(fill)
        elif depth:
            depth += {"(": 1, ")": -1}.get(c, 0)
            out.append(fill)
        elif text.startswith(("$(", "<(", ">("), i):
            depth = 1
            out.append(fill * 2)
            i += 2
            continue
        elif quote == '"':
            quote = None if c == '"' else quote
            out.append(fill)
        elif c in "'\"":
            quote = c
            out.append(fill)
        else:
            out.append(c)
        i += 1
    return "".join(out), depth


# A stdout redirect whose target is the log after all: a standard stream by
# its path, or a process substitution (`> >(cat)`), whose output the guard
# doesn't follow (#513).
LOG_TARGET = re.compile(r"""\s*(?:["']?(?:/dev/std(?:out|err)|/dev/fd/0*[12]|/proc/self/fd/0*[12])\b|>\()""")


def destination(text: str) -> str:
    """Where a shell line's stdout goes: log, file, envfile, summary or pipe.

    A redirect to `/dev/stdout`, `/dev/stderr`, `/dev/fd/1` or `2`,
    `/proc/self/fd/1` or `2`, or into a process substitution `>(...)` is the
    log (#513), failing closed: one such redirect makes the line a log line,
    whatever other redirect it holds.
    """
    bare = unquoted(text)
    if ENV_FILE.search(text):
        return "envfile"
    if SUMMARY_TEE.search(text):
        return "summary"
    # A pipeline into the summary still ends there.
    if any(SUMMARY_FILE.match(text, m.start()) for m in re.finditer(r"(?<![0-9<])>", bare)):
        return "summary"
    if PIPE.search(bare):
        return "pipe"
    redirects = [m for m in re.finditer(r"(?<![0-9&<])(>>?)(?!&)\s*", bare)]
    if any(LOG_TARGET.match(text, m.end(1)) for m in redirects):
        return "log"
    for m in redirects:
        if ENV_FILE.search(text[m.start():]):
            return "envfile"
        return "file"
    return "log"


def pipes_to_log(text: str) -> bool:
    """A shell line pipes into `tee` or `cat`, which print what they read to the log (#513).

    Failing closed: wherever `tee` writes besides, and whatever follows `cat`
    (`| cat > f` is read as the log too).
    """
    segments = statements_of(text)
    for i, (_, _, separator) in enumerate(segments[:-1]):
        if separator != "|":
            continue
        j = i + 1
        if j + 1 < len(segments) and not segments[j][1].strip() and segments[j][2] == "&":
            j += 1  # `|&`, which `statements_of` splits into `|` and `&`
        words = segments[j][1].split()
        if words and words[0].rsplit("/", 1)[-1] in ("tee", "cat"):
            return True
    return False


def own_command(command: str) -> str:
    """The simple command a heredoc's `<<` belongs to: the text before the `<<`
    after its last unquoted `|`, `|&`, `;`, `&&`, `||` or `&`, or after the
    `$(`, `<(`, `(` or backtick it stands in, its leading assignment words
    dropped (#513).
    """
    # The stack holds, per open substitution or subshell, the start and quote
    # outside it and what closes it.
    start, quote, stack, i = 0, None, [], 0
    while i < len(command):
        c = command[i]
        if c == "\\" and quote != "'":
            i += 2
            continue
        if quote is None and command.startswith(("&&", "||", "|&"), i):
            start = i = i + 2
            continue
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "`" and stack and stack[-1][2] == "`":
            start, quote, _ = stack.pop()
        elif c == "`" or command.startswith("$(", i) or (quote is None and command.startswith(("<(", ">(", "("), i)):
            opener = "`" if c == "`" else ")"
            stack.append((start, quote, opener))
            width = 2 if c in "$<>" else 1
            start, quote, i = i + width, None, i + width
            continue
        elif quote == '"':
            quote = None if c == '"' else quote
        elif c in "'\"":
            quote = c
        elif c == ")":
            # Unopened on the line: a `case` pattern's, after which a command starts.
            start, quote = stack.pop()[:2] if stack and stack[-1][2] == ")" else (i + 1, None)
        elif c in ";\n" or (c == "&" and command[i - 1:i] != ">" and command[i + 1:i + 2] != ">"):
            start = i + 1
        elif c == "|" and command[i - 1:i] != ">":
            start = i + 1
        i += 1
    return LEADING_ASSIGNMENTS.sub("", command[start:], count=1)


def interpreter_of(command: str) -> str | None:
    """`py` or `js` if the simple command of a heredoc's `<<` names an interpreter.

    `command` is the text before the `<<`. Only its own simple command is
    searched (`own_command`): a name in an earlier command of the line
    (`node --version; python3 -`, `jq . nodes.json | python3 -`) or in a
    leading assignment (`node_version=20 python3 -`) decides nothing (#513).
    In it, `python`/`pypy` (with a version) and `node`/`nodejs`/`deno`/`bun`
    are searched for as words -- a path, a suffix or an expansion around
    them allowed (`python3.13t`, `python.exe`, `python3-dbg`,
    `${PY:-python3}`, `sudo python3`) -- but not in a word ending in a shell
    script's extension (`./run-python-tests.sh`). The first name decides
    (`node - python3` is Node); one in an assignment word only where no
    other word names one (`env X=node python3` is Python). A command run
    from a parameter (`$PY -`), or named by a function or alias the text
    defines (`f() { python3 "$@"; }; f -`), whose own words name none is
    searched over the whole text before the `<<` (`PY=python3; $PY -`),
    failing closed.
    """
    own = own_command(command)

    def search(text: str) -> str | None:
        found: dict[bool, tuple[int, str]] = {}
        for regex, lang in ((PY_INTERPRETER, "py"), (JS_INTERPRETER, "js")):
            for m in regex.finditer(text):
                left = re.search(SHELL_WORD + "*$", text[:m.start()]).group()
                word = left + re.match(SHELL_WORD + "*", text[m.start():]).group()
                if SCRIPT_WORD.search(word):
                    continue
                assigned = ASSIGNMENT_WORD.match(word) is not None and "=" in left
                if assigned not in found or m.start() < found[assigned][0]:
                    found[assigned] = (m.start(), lang)
        best = found.get(False) or found.get(True)
        return best[1] if best else None

    lang = search(own)
    word = (own.split() or [""])[0]
    name = re.escape(word)
    defined = rf"(?:^|[\s;&|(){{}}])(?:function\s+{name}\b|{name}\s*\(\s*\)|alias\s+{name}=)"
    if lang is None and (re.match(r"""["']?\$""", word) or (word and re.search(defined, command))):
        lang = search(command)
    return lang


# A stdout redirect into an env file of a file descriptor other than stdout
# (`2>> "$GITHUB_OUTPUT"`): stdout stays where the rest of the line sends it.
OTHER_FD_TO_ENV_FILE = re.compile(
    r"""(?<![0-9&>])0*(?:[02-9]|[1-9][0-9]+)>>?\|?\s*["']?\$\{?GITHUB_(?:OUTPUT|ENV|STATE|PATH)\b\}?["']?""")


def logical_lines(lines: list[str]) -> list[Logical]:
    out: list[Logical] = []
    i = 0
    # The delimiter, the heredoc's lang and destination, its opener's unit,
    # whether the shell expands it, whether it strips leading tabs (`<<-`),
    # whether its opener pipes its stdout into a command and whether only
    # another file descriptor than stdout goes to an env file.
    heredoc: tuple[str, str, str, int, bool, bool, bool, bool] | None = None
    while i < len(lines):
        if heredoc is not None:
            delimiter, lang, dest, origin, expands, tabs, piped, fd_logged = heredoc
            # bash ends a heredoc only on a line that IS the delimiter -- no
            # leading or trailing space -- after stripping leading tabs for
            # `<<-` (and only tabs). `  PY` or `PY ` is a line of the heredoc.
            if (lines[i].lstrip("\t") if tabs else lines[i]) == delimiter:
                heredoc = None
            else:
                out.append(Logical(i, lines[i], lang, dest, origin, expands, piped, fd_logged))
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
            rest = text[:match.start()] + text[match.end():]
            dest = destination(rest)
            piped = PIPE.search(unquoted(text[:match.start()] + " " + text[match.end():])) is not None
            fd_logged = dest == "envfile" and destination(OTHER_FD_TO_ENV_FILE.sub(" ", rest)) == "log"
            # Quoted delimiter: text the shell leaves alone. Unquoted: the
            # shell expands it -- in a Python or Node heredoc too, before the
            # interpreter reads it (see UNQUOTED_NAME).
            expands = not (match.group(1) or match.group(2))
            # An unquoted one that no interpreter reads is like any other shell line.
            lang = interpreter_of(command) or ("sh-heredoc" if expands else "data")
            heredoc = (match.group(3), lang, dest, len(out) - 1, expands, match.group(0).startswith("<<-"), piped,
                       fd_logged)
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
    plain assignment and an appended raw value keeps the name unclean. So is
    an indexed one (`x[1]=...`, `declare x[1]=...`, `x[${a[0]}]=...`): it
    sets one element, and `$x` is `x[0]`, so `x[1]=$(shown "$x")` masks
    nothing; it still counts for the constant rule.
    """
    if unit.lang != "sh" or unit.text.lstrip().startswith("#"):
        return []
    found: list[tuple[str, str | None]] = []
    text = unit.text.strip()
    if DECLARE_LIST.match(text):
        for m in DECLARED.finditer(" " + text):
            found.append((m.group(1), ("+" if m.group(2) or m.group(3) else "") + m.group(4)))
    else:
        bare = unquoted(text, "x")
        for m in ASSIGNMENT.finditer(text):
            opener = m.group(0)[0]
            if opener in "({)!" and bare[m.start()] != opener:
                continue  # inside quotes or a `$(...)`: no statement starts there
            if opener == "!" and not re.search(r"(?:^|[;&|(){]|\b(?:then|do|else|elif|if|while|until|time))\s*$",
                                               bare[:m.start()]):
                continue  # `[[ ! x=1 ]]` tests a string
            chain = [m]
            while (more := CHAINED.match(text, chain[-1].end())) is not None:
                chain.append(more)
            # An assignment in a one-line subshell (or a `(pattern)` of a case
            # arm) is unknown: it doesn't reach the shell outside the
            # subshell, so it neither masks nor makes the name constant.
            # Assignment words before a command set its environment only
            # (`a=1 x="$v" cmd`): unknown too.
            rest = bare[chain[-1].end():]
            prefix = re.match(r"\s*(?![0-9]*[<>]|#)[^\s;&|()]", rest) is not None
            for c in chain:
                indexed = text[c.end(1)] == "["
                rhs = ("+" if c.group(2) or indexed else "") + c.group(3)
                found.append((c.group(1), None if opener == "(" or prefix else rhs))
    for m in LOOP_OR_READ.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3)
        found.append((name, None))
    for statement, _, _ in statements_of(text):
        words = shell_words(statement)
        while words and (words[0] in KEYWORDS or words[0] == "time" or re.match(TARGET, words[0])):
            words.pop(0)
        if len(words) > 1 and words[0] in ("for", "select") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", words[1]):
            found.append((words[1], None))  # `for x; do` and `for x do` too: x runs through "$@"
        if words and words[0] in READERS:
            for word in words[1:]:
                target = re.match(r"""^["']?([A-Za-z_][A-Za-z0-9_]*)\b""", word)
                if target and (words[0] == "let" or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", word)):
                    found.append((target.group(1), None))
    return found


def shell_words(text: str) -> list[str]:
    """The words of a shell statement, quoted strings kept whole."""
    bare = unquoted(text, "x")
    return [text[m.start():m.end()] for m in re.finditer(r"\S+", bare)]


def is_literal(rhs: str | None) -> bool:
    if rhs is None:
        return False
    return "$" not in rhs and not re.search(r"(?<!\\)`", rhs)


def is_comment(text: str) -> bool:
    return text.lstrip().startswith(("#", "//"))


def is_comment_unit(unit: Logical) -> bool:
    """A comment line: a shell heredoc's line is data the shell expands, `#` and all (#513)."""
    return unit.lang != "sh-heredoc" and is_comment(unit.text)


TO_STDERR = re.compile(r"(?<![0-9])>&\s*2|&>|/dev/std(?:err|out)")
OPENERS = {"{", "for", "while", "until", "select", "if", "case"}
CLOSERS = {"}", "done", "fi", "esac"}


# Statement boundaries in unquoted text: `;`, `&&`, `||`, a pipe (not the `|`
# of `>|`), a background `&` (not `2>&1` or `&>`), and `(` / `)`.
STATEMENT_SPLIT = re.compile(r";|&&|\|\||(?<!>)\|(?!\|)|(?<![>&])&(?![>&])|[()]")
GROUP_NAME = "<summary group>"
# A line of a Python or Node heredoc with an unquoted delimiter that holds `$`
# or a backtick: the shell expands it before the interpreter reads the line,
# and the Python or Node reading doesn't see that expansion.
UNQUOTED_NAME = "<unquoted heredoc>"
# A Python or Node heredoc line that writes to a standard stream other than
# through a named print (#513): `sys.stdout.writelines(...)`,
# `json.dump(x, sys.stdout)`, `console['log'](...)`, `print` passed as a value.
UNKNOWN_WRITER = "<unknown writer>"
# What such a line names: stdout objects (read where the heredoc's stdout
# reaches a sink), and a print or `console` (either stream: read on every
# heredoc). A reference inside a print call the strict reading names is that
# call's own.
PY_STDOUT_REF = re.compile(r"\bsys\s*\.\s*(?:__)?stdout\b")
JS_STDOUT_REF = re.compile(r"\bprocess\s*\.\s*stdout\b")
PY_PRINT_REF = re.compile(r"\bprint\b")
JS_PRINT_REF = re.compile(r"\bconsole\b")
# A Python or Node heredoc line that names an env file or the step summary
# (#513): it can open the file itself (`open(os.environ["GITHUB_ENV"], "a")`,
# `fs.appendFileSync(process.env.GITHUB_OUTPUT, ...)`), and what it writes
# there is no print the guard reads.
ENV_FILE_OPENED = "<env file opened>"
ENV_FILE_NAMED = re.compile(r"\bGITHUB_(?:ENV|OUTPUT|STATE|PATH|STEP_SUMMARY)\b")


# `name=(...)`, `name+=(...)`: an array literal, whose words are data.
ARRAY_LITERAL = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\+?=\([^()]*\)")


def statements_of(text: str) -> list[tuple[str, str, str]]:
    """(text, unquoted text, separator after it) for every statement-level segment.

    An array literal closed on the same line is blanked first, so `kw=(if fi)`
    neither splits a statement nor opens or closes a group.
    """
    bare = ARRAY_LITERAL.sub(lambda m: " " * len(m.group()), unquoted(text))
    out, start = [], 0
    for m in STATEMENT_SPLIT.finditer(bare):
        out.append((text[start:m.start()], bare[start:m.start()], m.group()))
        start = m.end()
    out.append((text[start:], bare[start:], ""))
    return out


def segment_role(bare: str) -> tuple[int, int]:
    """(groups opened, groups closed) by a statement-level segment: `{ for x` opens two."""
    words = bare.split()
    opens = closes = 0
    while words:
        if words[0] in ("then", "else", "elif", "do", "!"):
            words.pop(0)
        elif words[0] in OPENERS:
            opens += 1
            words.pop(0)
        elif words[0] == "function" and "{" in words[1:3]:
            opens += 1
            words = words[words.index("{", 1) + 1:]
        elif words[0] in CLOSERS and not opens:
            closes += 1
            words.pop(0)
        else:
            break
    return opens, closes


# Where a shell line splits into pipelines: `;`, `&&`, `||`, a background
# `&` (not the `&` of `|&`, `2>&1` or `&>`) and a subshell's `(` / `)`.
PIPELINE_SPLIT = re.compile(r";|&&|\|\||(?<![>&|])&(?![>&])|[()]")


def reaches_log(text: str) -> bool:
    """A shell pipeline's stdout reaches the log: not redirected, or piped into `tee` or `cat`."""
    dest = destination(text)
    return dest == "log" or (dest == "pipe" and pipes_to_log(text))


def logged_prints(text: str) -> list[tuple[re.Match, int]]:
    """(match, end) of every `echo`/`printf` statement of a shell line whose output reaches the log (#513).

    Every print of the line counts, not only the first (`echo x > f; echo
    "$V"`), each read with its own pipeline's destination -- the line split
    at `;`, `&&`, `||`, `&`, `(` and `)` -- and with the redirect of every
    group, compound or subshell on the line that encloses it (`{ echo "$V";
    } > f` is a file's). Failing closed: a print whose enclosing group the
    line doesn't close is read by its own pipeline alone. `end` is where its
    statement ends (SHELL_PRINT's `match.start(1)` is where it starts).
    """
    bare = ARRAY_LITERAL.sub(lambda m: " " * len(m.group()), unquoted(text))
    pieces, start = [], 0
    for m in PIPELINE_SPLIT.finditer(bare):
        pieces.append((start, m.start(), m.group()))
        start = m.end()
    pieces.append((start, len(bare), ""))
    prints = list(SHELL_PRINT.finditer(bare))
    logged: dict[int, tuple[re.Match, int]] = {}
    top: list[int] = []
    stack: list[tuple[bool, list[int]]] = []  # (a subshell's `(`, the logged prints inside)

    def close(ids: list[int], closer: str) -> None:
        if reaches_log(closer):
            (stack[-1][1] if stack else top).extend(ids)
        else:
            for i in ids:
                logged.pop(i, None)

    for n, (a, b, sep) in enumerate(pieces):
        opens, closes = segment_role(bare[a:b])
        for c in range(closes):
            if not stack or stack[-1][0]:
                break  # opened on an earlier line, or not a group the line opened
            # Only the last closer of `} }` carries the segment's redirect.
            close(stack.pop()[1], text[a:b] if c == closes - 1 else "")
        stack += [(False, []) for _ in range(opens)]
        m = next((p for p in prints if a <= p.start(1) < b), None)
        if m and reaches_log(text[a:b]):
            end = STATEMENT_END.search(bare, m.end(), b)
            logged[m.start(1)] = (m, end.start() if end else b)
            (stack[-1][1] if stack else top).append(m.start(1))
        if sep == "(":
            stack.append((True, []))
        elif sep == ")" and stack and stack[-1][0]:
            after = pieces[n + 1] if n + 1 < len(pieces) else (b, b, "")
            close(stack.pop()[1], text[after[0]:after[1]])
    return [logged[i] for i in sorted(logged)]


def segment_dest(segments: list[tuple[str, str, str]], i: int, units: list[Logical], k: int) -> str:
    """Where the closer segment i of unit k sends its group's output."""
    text = segments[i][0]
    if SUMMARY_FILE.search(text) or SUMMARY_TEE.search(text):
        return "summary"
    if ENV_FILE.search(text):
        return "envfile"
    if segments[i][2] == "|":
        # A pipeline: where its tee writes, on this line or -- after a
        # trailing `|` -- on the next shell line.
        rest = "".join(seg[0] + seg[2] for seg in segments[i + 1:])
        if not rest.strip():
            rest = next((u.text for u in units[k + 1:] if u.lang == "sh" and u.text.strip()), "")
        if SUMMARY_TEE.search(rest):
            return "summary"
        if ENV_FILE.search(rest):
            return "envfile"
        return "pipe"
    if STDOUT_ELSEWHERE.search(segments[i][1]):
        return "file"
    return "log"


def redirected_groups(units: list[Logical]) -> tuple[set[int], set[int], set[int], set[int]]:
    """Lines whose output a redirect on a later line sends to a file.

    Returns all lines inside a `{ ... } > target` group, the lines of a group
    or compound command (`{`, `f() {`, `function f {`, `for`/`while`/`until`/
    `select`, `if`, `case`) into an env file, those into the summary, and
    those of one whose closer pipes its output into a command (`} | tee -a
    "$GITHUB_OUTPUT"`, `} | cat`), which may reach the log (#513).

    Openers and closers are read per statement, anywhere on a line, through a
    stack across lines, so `echo "$v"; } >> "$GITHUB_STEP_SUMMARY"` closes the
    group it ends. For an env file or the summary every line from the opener's
    to the closer's counts; a line is only taken out of the log rule if its
    opener starts it and its closer ends it, and never when it sends stdout to
    stderr. Into a plain file only the old `{`-alone form is taken out of the
    log rule.
    """
    redirected: set[int] = set()
    envfile: set[int] = set()
    summary: set[int] = set()
    piped: set[int] = set()
    for k, unit in enumerate(units):
        if unit.lang != "sh" or is_comment(unit.text):
            continue
        head = unquoted(unit.text).split()
        if not head or head[0] != "}" or destination(unit.text) == "log":
            continue
        # A closer that pipes the group into `tee` or `cat` prints it to the
        # log: its lines stay log lines (#513). Into another command, a
        # shell line's print is unread, as on a line of its own; a Python
        # or Node line's stdout is read as reaching the log all the same.
        piped_closer = PIPE.search(unquoted(unit.text)) is not None
        logged = pipes_to_log(unit.text)
        depth = 0
        for j in range(k, -1, -1):
            stripped = units[j].text.strip()
            if stripped.startswith("}"):
                depth += 1
            if stripped == "{":
                depth -= 1
                if depth == 0:
                    redirected.update(m for m in range(j + 1, k)
                                      if not piped_closer or (units[m].lang == "sh" and not logged))
                    if destination(unit.text) == "envfile":
                        envfile.update(range(j + 1, k))
                    if destination(unit.text) == "summary":
                        summary.update(range(j + 1, k))
                    break
    stack: list[tuple[int, bool]] = []
    for k, unit in enumerate(units):
        if unit.lang != "sh" or is_comment(unit.text):
            continue
        segments = statements_of(unit.text)
        for i, (_, bare, _) in enumerate(segments):
            opens, closes = segment_role(bare)
            first = not any(seg[1].strip() for seg in segments[:i])
            stack += [(k, first)] * opens
            for c in range(closes):
                # Only the last closer of `} }` carries the segment's redirect.
                dest = segment_dest(segments, i, units, k) if c == closes - 1 else "log"
                if not stack:
                    break  # unattributed; a summary closer is reported by audit_body
                opened, first = stack.pop()
                members = [m for m in range(opened, k + 1) if units[m].lang == "sh"]
                if c == closes - 1 and segments[i][2] == "|":
                    piped.update(members)
                if dest not in ("envfile", "summary"):
                    continue
                if dest == "envfile":
                    envfile.update(members)
                    continue
                summary.update(members)
                last = not any(seg[1].strip() for seg in segments[i + 1:])
                redirected.update(m for m in members if (m != opened or first) and (m != k or last))
    # A line inside such a group that sends its own stdout to stderr prints to
    # the log after all: the log rule keeps reading it.
    redirected = {i for i in redirected if not TO_STDERR.search(unquoted(units[i].text))}
    return redirected, envfile, summary, piped


def inherit_group_dest(units: list[Logical]) -> None:
    """A heredoc opened inside a redirected group writes where the group does.

    Its own line decides first: a heredoc whose command redirects stdout
    (`> f`, `>> "$GITHUB_OUTPUT"`, `>&2`, a pipe) keeps that. Otherwise, in
    a group redirected to the summary, its lines take the summary as their
    target, so the summary rule reads them; in a group into an env file they
    take the env file, so they are read as an env-file heredoc's (#507).
    In a group whose closer pipes its output into a command, its stdout may
    reach the log as well, as a heredoc piped on its own line does (#513).
    """
    _, envfile, summary, piped = redirected_groups(units)
    for unit in units:
        if unit.lang == "sh" or unit.origin < 0 or unit.dest != "log":
            continue
        opener = units[unit.origin]
        command = HEREDOC.sub(" ", opener.text)
        if STDOUT_ELSEWHERE.search(unquoted(command)) or PIPE.search(unquoted(command)):
            continue
        if unit.origin in summary:
            unit.dest = "summary"
        elif unit.origin in envfile:
            unit.dest = "envfile"
        if unit.origin in piped:
            unit.piped = True


def unattributed_summary_closers(units: list[Logical]) -> list[int]:
    """Lines whose closer is redirected to the summary but whose opener the guard can't find."""
    out, depth = [], 0
    for k, unit in enumerate(units):
        if unit.lang != "sh" or is_comment(unit.text):
            continue
        segments = statements_of(unit.text)
        for i, (_, bare, _) in enumerate(segments):
            opens, closes = segment_role(bare)
            depth += opens
            if closes > depth and segment_dest(segments, i, units, k) == "summary":
                out.append(k)
            depth = max(depth - closes, 0)
    return out


# A function's name after `function` (`function f ...`). Before an empty `()`
# any single word is one (`x@y() ...`, `a/b() ...`, `f+() ...`): outside a
# definition, a word followed by `()` is a syntax error, so it can't be a
# subshell.
FUNCTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_:.-]*")
# The words that open the compound command a function definition takes as its body.
BODY_OPENERS = ("{", "if", "for", "while", "until", "select", "case")
# `#` at the start of a word, outside quotes: the rest of the line is a comment.
# Read on text whose quotes are filled, not blanked, so `"a"#` stays one word.
LINE_COMMENT = re.compile(r"(?:^|(?<=[\s;&|()]))#")


@dataclass
class Blocks:
    """Which blocks enclose each shell statement of a body (#507).

    A block is an `if` compound, one of its branches (`then`, `elif ...
    then`, `else`), a loop (`for`/`while`/`until`/`select` to `done`), a
    `case` compound, one of its arms, a `{ ... }` group or a `( ... )`
    subshell. `segments[k]` holds the statements of shell unit k, as
    `statements_of` splits them, and `paths[k]` the blocks open at each -- a
    closer's statement counts inside the block it closes. `functions` holds
    the blocks that are a function's body: the compound command after `f()`
    or `function f`, wherever it opens (same line, next line; `{ ... }`,
    `( ... )`, `if`, a loop, `case`). `ok` is False when a closer has no
    matching opener, a block stays open or a function definition has a body
    the guard doesn't read: then no block is attributed, and nothing may rest
    on one.
    """

    segments: dict[int, list[tuple[str, str, str]]]
    paths: dict[int, list[tuple[int, ...]]]
    kinds: dict[int, str]
    spans: dict[int, tuple[int, int]]
    functions: set[int]
    ok: bool


def code_of(text: str) -> str:
    """A shell line without its trailing comment."""
    m = LINE_COMMENT.search(unquoted(text, "x"))
    return text[:m.start()] if m else text


def blocks_of(units: list[Logical]) -> Blocks:
    """Read the block structure of a body's shell lines, statement by statement."""
    kinds: dict[int, str] = {}
    starts: dict[int, int] = {}
    spans: dict[int, tuple[int, int]] = {}
    functions: set[int] = set()
    stack: list[int] = []
    segments_by: dict[int, list[tuple[str, str, str]]] = {}
    paths_by: dict[int, list[tuple[int, ...]]] = {}
    ok = True
    k = 0
    # `header`: a function's name was read, its body is the next compound
    # command; `body`: the next block pushed is that body.
    header = body = False

    def push(kind: str) -> None:
        nonlocal body
        rid = len(kinds)
        kinds[rid] = kind
        starts[rid] = k
        stack.append(rid)
        if body:
            functions.add(rid)
            body = False

    def pop(*expected: str) -> None:
        nonlocal ok
        if stack and kinds[stack[-1]] in expected:
            rid = stack.pop()
            spans[rid] = (starts[rid], k)
        else:
            ok = False

    def parens_follow(segments: list[tuple[str, str, str]], i: int) -> bool:
        """Segment i ends in `(` and the next one is an empty `)`: the `()` of `f()`."""
        return segments[i][2] == "(" and i + 1 < len(segments) and not segments[i + 1][1].strip() \
            and segments[i + 1][2] == ")"

    for k, unit in enumerate(units):
        if unit.lang != "sh" or is_comment(unit.text):
            continue
        if opens_substitution(code_of(unit.text)):
            # Its lines up to the closing `)` read as statements, and that `)`
            # -- after text on its line, in a case arm -- as a pattern's: no
            # block is attributed (#513).
            ok = False
        segments = statements_of(code_of(unit.text))
        paths: list[tuple[int, ...]] = []
        parens = -1  # the segment whose `(` is a definition's `()`
        for i, (text, bare, separator) in enumerate(segments):
            words = bare.split()
            path: tuple[int, ...] | None = None
            if i == parens + 1 and parens >= 0:
                words = []  # the inside of `()`
            elif len(words) == 1 and parens_follow(segments, i):
                header, words, parens = True, [], i
            while words:
                word = words.pop(0)
                if header:
                    header = False
                    if word in BODY_OPENERS:
                        body = True
                    elif word == "[[":
                        break  # a `[[ ... ]]` body: no block, nothing it can assign or print
                    else:
                        ok = False
                        break
                if word in ("!", "do"):
                    continue
                if word == "function":
                    if not words or not FUNCTION_NAME.fullmatch(words[0]):
                        ok = False
                        break
                    words.pop(0)
                    header = True
                    if not words and parens_follow(segments, i):
                        parens = i
                    continue
                if word == "if":
                    push("if")
                elif word == "then":
                    push("branch")
                elif word == "elif":
                    pop("branch")
                elif word == "else":
                    pop("branch")
                    push("branch")
                elif word in ("for", "while", "until", "select"):
                    push("loop")
                elif word == "case":
                    push("case")
                    push("arm")
                elif word == "{":
                    push("group")
                elif word in ("fi", "done", "esac", "}"):
                    # A closer's statement belongs to the block it closes.
                    path = tuple(stack) if path is None else path
                    if word == "fi":
                        pop("branch")
                        pop("if")
                    elif word == "done":
                        pop("loop")
                    elif word == "esac":
                        pop("arm")
                        pop("case")
                    else:
                        pop("group")
                else:
                    break
            paths.append(tuple(stack) if path is None else path)
            if i == parens or (i == parens + 1 and parens >= 0):
                continue  # the `(` and `)` of `f()`
            if header and separator not in ("", "("):
                header, ok = False, False  # `f() ;`: no body the guard can read
            if separator == "(":
                if header:
                    header, body = False, True
                push("subshell")
            elif separator == ")":
                # Outside a subshell, `)` ends a case pattern -- unless nothing
                # stands before it: a pattern is never empty, so a `)` alone
                # closes something the guard didn't see open (a `$(` over
                # lines) and leaves the body unattributed, as at top level.
                if not (stack and kinds[stack[-1]] in ("arm", "case") and text.strip()):
                    pop("subshell")
            elif separator == ";" and i + 1 < len(segments) and not segments[i + 1][1].strip() \
                    and segments[i + 1][2] in (";", "&"):
                # `;;`, `;&`, `;;&`: the arm ends, the next one starts.
                pop("arm")
                push("arm")
        segments_by[k] = segments
        paths_by[k] = paths
    if stack or header or body:
        ok = False
    return Blocks(segments_by, paths_by, kinds, spans, functions, ok)


def joined_text(units: list[Logical], k: int) -> str:
    """A Python or Node line, with the continuation lines of a print call it leaves open.

    Up to JOINED_LINES of them, of the same heredoc. Every reading of a print
    call -- which sink it reaches, which stream it writes, what it prints --
    takes the joined call, so `file=sys.stderr` on a continuation line counts.
    """
    unit = units[k]
    text = unit.text
    opener = open_print(text, unit.lang)
    if opener is not None:
        depth, _ = bracket_state(text, opener, lang=unit.lang)
        end = k + 1
        while depth and end < len(units) and end - k <= JOINED_LINES \
                and units[end].origin == unit.origin and units[end].lang == unit.lang:
            text += "\n" + units[end].text
            # Read again from the call's `(`: a `/* ... */` can span the lines.
            depth, _ = bracket_state(text, opener, lang=unit.lang)
            end += 1
    return text


def sink_units(units: list[Logical]) -> set[int]:
    """Indices of units that emit a command, write an env file or print to the log."""
    redirected, sinks, _, _ = redirected_groups(units)
    for k, unit in enumerate(units):
        if unit.lang == "data" or is_comment_unit(unit):
            continue
        text = unit.text
        if COMMAND.search(text):
            sinks.add(k)
        if unit.lang == "sh":
            dest = destination(text)
            if dest == "envfile":
                sinks.add(k)
            elif (logged_prints(text)
                  and k not in redirected
                  and text.strip() != SHELL_SHOWN and text.strip() not in SHELL_MD):
                sinks.add(k)
        elif unit.lang == "sh-heredoc":
            # Piped into `tee` or `cat`, its lines are printed to the log (#513).
            if unit.dest in ("envfile", "log") or (
                    unit.dest == "pipe" and pipes_to_log(HEREDOC.sub(" ", units[unit.origin].text))):
                sinks.add(k)
        elif unit.lang in ("py", "js") and unit.dest == "envfile":
            # Every line of a heredoc whose stdout goes to an env file (#507),
            # read strictly, as for the step summary.
            if unit.text.strip():
                sinks.add(k)
        elif unit.lang in ("py", "js") and any(call.reaches_log(unit.stdout_logged())
                                                for call in print_calls(joined_text(units, k), unit.lang)):
            # stderr is the log; stdout counts where the heredoc sends it to
            # it. Every print call on the line, read strictly (#511), each
            # with its continuation lines: `file=sys.stderr` can sit on one.
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
    """Interpolated expressions of a Python f-string or t-string (PEP 750), or a JS template literal."""
    exprs = []
    opener = "${" if lang == "js" else "{"
    if lang == "py" and not re.search(r"\b[rR]?[fFtT][rR]?['\"]", text):
        return []
    if lang == "js" and "`" not in text:
        return []
    named = named_escapes(text) if lang == "py" else {}
    i = 0
    while True:
        i = text.find(opener, i)
        if i < 0:
            return exprs
        if i in named:
            i = named[i]  # `\N{...}`, a named character, not a field
            continue
        if lang == "py" and text.startswith("{{", i):
            i += 2
            continue
        start = i + len(opener)
        depth, j = 1, start
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        expr = text[start:j - 1].strip()
        exprs.append(field_expr(expr) if lang == "py" else expr)
        if lang == "py":
            exprs += spec_fields(expr)
        i = j


FIELD_TAIL = re.compile(r"![rsa]\s*$|:(?![^\[]*\])")
SELF_DOCUMENTING = re.compile(r"(?<![=<>!:])=\s*$")
NAMED_CHARACTER = re.compile(r"\\N\{[A-Za-z0-9 -]+\}")


def field_expr(field: str) -> str:
    """The expression of a Python replacement field, as an ALLOWED entry names it.

    A format spec or conversion is dropped (`{x!r}`, `{x:>8}`), and so is the
    `=` of a self-documenting field (`{x=}`, `{x = !r}`), which prints the
    expression's text before its value; `==`, `<=`, `>=`, `!=` and `:=` stay.
    """
    expr = FIELD_TAIL.split(field.strip())[0]
    return SELF_DOCUMENTING.sub("", expr).strip()


def spec_fields(field: str) -> list[str]:
    """The expressions of the replacement fields nested in a Python field's format spec (#513).

    `{len(p):{p}}` formats with `p` as its spec: `p` sets the fill -- any
    character, a line end too -- and the width, so it is a value printed
    like any other. Node template literals have no spec.
    """
    tail = FIELD_TAIL.search(field.strip())
    if not tail:
        return []
    spec = field.strip()[tail.start():]
    out, i = [], 0
    while (i := spec.find("{", i)) >= 0:
        depth, j = 1, i + 1
        while j < len(spec) and depth:
            depth += {"{": 1, "}": -1}.get(spec[j], 0)
            j += 1
        out.append(field_expr(spec[i + 1:j - 1]))
        i = j
    return out


def named_escapes(text: str) -> dict[int, int]:
    """The `{` of every `\\N{...}` escape in a Python string literal that isn't raw, mapped to the index past its `}`.

    In an f-string or t-string that isn't raw `f"v\\N{LINE FEED}{x}"` has one
    field, `x`: the braces of a named character are no field (#511). A raw
    one's `\\N{x}` is a backslash, an `N` and the field `x`, as is a
    non-raw `\\\\N{x}` (an escaped backslash). A bytes literal has no
    named characters: `b"\\N{"` is a backslash, an `N` and a `{`, so its `{`
    is no escape and a field after the literal stays a field. An escape is
    a name of letters, digits, spaces and hyphens closed by `}` (Python's
    names and aliases); anything else -- a quote or the literal's end before
    the `}` -- is no escape, so its `{` is read as a field. A literal is read
    to its first closing quote, as `_literal_end` does.
    """
    spans: dict[int, int] = {}
    i = 0
    while i < len(text):
        quote = quote_open(text, i)
        if not quote or quote == "`":
            i += 1
            continue
        k = i
        while k > 0 and (text[k - 1].isalnum() or text[k - 1] == "_"):
            k -= 1
        prefix = text[k:i].lower()
        named = "r" not in prefix and "b" not in prefix
        i += len(quote)
        while i < len(text) and not text.startswith(quote, i):
            escape = NAMED_CHARACTER.match(text, i) if named else None
            if escape:
                spans[i + 2] = escape.end()
                i = escape.end()
                continue
            i += 2 if text[i] == "\\" else 1
        i += len(quote)
    return spans


def quote_open(text: str, i: int) -> str | None:
    """The quote a string literal opening at i ends at -- a Python triple quote, `'`, `"` or `` ` `` -- or None.

    A Python triple quote (three `'` or three `"`) is read as one, so a
    quote of the other kind or a lone one inside it doesn't end it (#511);
    a string prefix before it (`f`, `rb`, ...) is plain text to the scan.
    """
    if text.startswith(("'''", '"""'), i):
        return text[i:i + 3]
    return text[i] if text[i] in "'\"`" else None


def same_quote_field(text: str, start: int, end: int) -> bool:
    """A Python f-string or t-string in text[start:end] has a replacement field holding its own quote.

    Legal since Python 3.12 (PEP 701): `f"{d[")"]}"`, `f"{'''")'''}"`, and
    in a t-string (PEP 750, `t"{d[")"]}"`). The call scans end the f-string
    at that inner quote, so they misread where its call closes (#511). A
    `{{`/`}}` escape is text, and a field quoting with the other kind
    (`f"{d['k']}"`) is a form older Pythons know too. A backslash before a
    `{` doesn't escape it (`rf"\\{d[")"]}"`, `f"\\{x}"`): the field opens
    there all the same; only `\\N{...}` of a string that isn't raw is an
    escape (a named character), not a field.
    """
    i = start
    while i < end:
        quote = quote_open(text, i)
        if not quote or quote == "`":
            i += 1
            continue
        k = i
        while k > start and (text[k - 1].isalnum() or text[k - 1] == "_"):
            k -= 1
        prefix = text[k:i].lower()
        i += len(quote)
        if not (len(prefix) <= 2 and set(prefix) <= set("rbftu") and ("f" in prefix or "t" in prefix)):
            i = _literal_end(text, i, quote)
            continue
        depth = 0
        while i < end:
            if text[i] == "\\" and not depth and text.startswith("{", i + 1):
                i += 1  # the `{` opens a field all the same
                continue
            if text[i] == "\\" and not depth and "r" not in prefix and text.startswith("N{", i + 1):
                close = text.find("}", i)
                i = close + 1 if close >= 0 else end
                continue
            if text[i] == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                if depth:
                    return True
                i += len(quote)
                break
            if not depth and text.startswith(("{{", "}}"), i):
                i += 2
                continue
            inner = quote_open(text, i) if depth else None
            if inner:
                inner_end = _literal_end(text, i + len(inner), inner)
                if quote in text[i + len(inner):inner_end]:
                    return True
                i = inner_end
                continue
            depth = max(depth + {"{": 1, "}": -1}.get(text[i], 0), 0)
            i += 1
    return False


def comment_end(text: str, i: int, lang: str | None) -> int | None:
    """Index just past the comment that starts at i, outside a string; None if none starts there (#513).

    Python's `#` and Node's `//` run to the line end (which stays text),
    Node's `/* ... */` to its `*/` (or the end of the text). A Node `//` or
    `/*` counts only after a blank, a bracket or a separator, so
    one inside a regex literal (`/\\//`, `/[//]/`) is no comment. `lang` None
    reads no comments.
    """
    if lang == "py" and text[i] == "#":
        end = text.find("\n", i)
        return len(text) if end < 0 else end
    if lang == "js" and text.startswith(("//", "/*"), i) and (i == 0 or text[i - 1] in " \t\n,;(){}"):
        if text.startswith("//", i):
            end = text.find("\n", i)
            return len(text) if end < 0 else end
        end = text.find("*/", i + 2)
        return len(text) if end < 0 else end + 2
    return None


def call_args(text: str, opener_end: int, lang: str | None = None) -> list[str]:
    """Top-level arguments of the call whose `(` ends at opener_end.

    A line continuation (a backslash and its line end) outside a quote reads
    as a space, so an argument on a continued line is read as written:
    `file=sys.stderr`, `**kw` (#511). A comment (`comment_end`, read where
    `lang` is given) is dropped: a `)` or `,` in it ends nothing (#513).
    """
    args, depth, current, quote = [], 1, [], None
    i = opener_end
    while i < len(text) and depth:
        c = text[i]
        if not quote and text.startswith("\\\n", i):
            current.append(" ")
            i += 2
            continue
        if not quote and (skip := comment_end(text, i, lang)) is not None:
            i = skip
            continue
        if quote:
            if c == "\\":
                current.append(text[i:i + 2])
                i += 2
                continue
            if text.startswith(quote, i):
                current.append(quote)
                i += len(quote)
                quote = None
                continue
        elif quote_open(text, i):
            quote = quote_open(text, i)
            current.append(quote)
            i += len(quote)
            continue
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
    close = call_close(text, opener_end)
    return len(text) if close is None else close


def call_close(text: str, opener_end: int, lang: str | None = None) -> int | None:
    """Index just past the `)` closing the call whose `(` ends at opener_end; None if the text doesn't close it.

    A comment (`comment_end`, read where `lang` is given) is skipped: a `)` in
    it closes nothing (#513).
    """
    depth, quote, i = 1, None, opener_end
    while i < len(text):
        c = text[i]
        if not quote and (skip := comment_end(text, i, lang)) is not None:
            i = skip
            continue
        if quote:
            if c == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif quote_open(text, i):
            quote = quote_open(text, i)
            i += len(quote)
            continue
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if not depth:
                return i + 1
        i += 1
    return None


def open_print(text: str, lang: str) -> int | None:
    """Where the arguments start of the print call on the text whose `)` isn't on it; None if all close."""
    last = 0
    for m in (PY_STRICT_PRINT if lang == "py" else JS_STRICT_PRINT).finditer(text):
        if m.start() < last:
            continue  # inside an earlier call
        close = call_close(text, m.end(), lang)
        if close is None:
            return m.end()
        last = close
    return None


def bracket_state(text: str, start: int, depth: int = 1, quote: str | None = None,
                  lang: str | None = None) -> tuple[int, str | None]:
    """Bracket depth and open quote after reading text[start:], from the given state; comments skipped (`lang`)."""
    i = start
    while i < len(text) and depth:
        c = text[i]
        if not quote and (skip := comment_end(text, i, lang)) is not None:
            i = skip
            continue
        if quote:
            if c == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif quote_open(text, i):
            quote = quote_open(text, i)
            i += len(quote)
            continue
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return depth, quote


@dataclass
class PrintCall:
    """One print call of a Python or Node line, as the strict reading takes it."""

    start: int  # where the call's name starts
    opener_end: int  # just past its `(`
    end: int  # just past its `)`, or the end of the text if it isn't closed there
    name: str  # `print`, `console.log`, ... with any space dropped
    args: list[str]
    keyword: dict[str, str]  # Python's keyword arguments: `file`, `end`, `sep`, `flush`
    to_stderr: bool  # by its name or a `file=` naming stderr
    # A `file=` the guard can't tell (or can't see: unclosed, `**`, a PEP 701
    # same-quote f-string field, text naming `stderr` or `file=` the parse
    # missed): stdout, stderr or a file.
    unknown: bool = False

    def reaches_log(self, stdout: bool) -> bool:
        """It prints to the log: to stderr, to a heredoc stdout read as the log (`stdout`), or -- unknown -- either."""
        return self.to_stderr or self.unknown or stdout

    def read_by(self, stdout: bool, stderr: bool) -> bool:
        """A reading of the stdout prints, the stderr prints or both takes this call.

        A call to an unknown stream is taken by either: it fails closed.
        """
        if self.unknown:
            return stdout or stderr
        return stderr if self.to_stderr else stdout


def file_stream(value: str) -> str:
    """Where a Python `file=` argument writes: `stdout`, `stderr` or `unknown`.

    Fails closed (#511): only `sys.stdout`/`sys.__stdout__` and `sys.stderr`/
    `sys.__stderr__` (in parentheses too) are told; anything else -- a file
    the heredoc opens (`open("out.txt", "w")`, or a name bound to one),
    `from sys import stderr`, `err = sys.stderr`, `sys.stderr if c else
    sys.stdout` -- is unknown, and read as stdout and as stderr both.
    """
    text = value.strip()
    while text.startswith("(") and call_close(text, 1) == len(text):
        text = text[1:-1].strip()
    bare = re.sub(r"\s+", "", text)
    if bare in ("sys.stdout", "sys.__stdout__"):
        return "stdout"
    if bare in ("sys.stderr", "sys.__stderr__"):
        return "stderr"
    return "unknown"


# A `file=` in the text of a Python print call, as its text backstop reads it (#511).
FILE_KEYWORD = re.compile(r"\bfile\s*=")


def call_region(text: str, lang: str, close: int | None) -> int:
    """Where the text a print call may span ends, for the text backstop (#511).

    Just before the next print call when only a `;` or space stands between
    the parsed close and it (`print(p); print("x", file=sys.stderr)`);
    anything else after the close -- an argument the scan misread as past it,
    a comment, an operator -- may be the call's own, so the region runs to
    the end of the joined text, as it does for a call not closed there.
    """
    if close is None:
        return len(text)
    following = (PY_STRICT_PRINT if lang == "py" else JS_STRICT_PRINT).search(text, close)
    stop = following.start() if following else len(text)
    return stop if text[close:stop].strip() in ("", ";") else len(text)


def print_calls(text: str, lang: str) -> list[PrintCall]:
    """Every print call on the text, outermost only (`print (` and every `console` method included).

    A Python print call is read fail-closed (#511) where the parse and the
    text can disagree: a call not closed in the joined text, one spreading
    `**` keyword arguments, or one whose close the scan can't trust -- an
    f-string or t-string field holding its own quote (PEP 701) -- may name
    any `file=`, so its stream is unknown. So is one whose text -- from its
    name to the end of `call_region` -- names `stderr` or a `file=` the
    parsed call doesn't read as `file=sys.stderr`: a stdout call (by
    default, or by `file=sys.stdout` where that text names `stderr` or a
    second `file=`) whose text says otherwise is read as reaching the log.
    Where that text runs past the parsed close, the call is taken to run to
    the end of it, the part past the close read as one more argument, a value.
    `sys.stderr.write` and `SystemExit` are stderr by their name.
    """
    calls: list[PrintCall] = []
    last = 0
    for m in (PY_STRICT_PRINT if lang == "py" else JS_STRICT_PRINT).finditer(text):
        if m.start() < last:
            continue  # inside an earlier call
        args = call_args(text, m.end(), lang)
        name = re.sub(r"\s+", "", m.group(1))
        close = call_close(text, m.end(), lang)
        same_quote = lang == "py" and same_quote_field(text, m.end(), len(text) if close is None else close)
        if same_quote:
            # The quote scan misreads such a field, so a `#` in it may read as
            # a comment and hide arguments: read them without comments too,
            # and end the call where that reading does (#513).
            args += [a for a in call_args(text, m.end()) if a not in args]
            close = call_close(text, m.end())
        keyword = {a.split("=", 1)[0].strip(): a.split("=", 1)[1].strip()
                   for a in args if lang == "py" and KEYWORD_ARG.match(a)}
        end = len(text) if close is None else close
        if lang == "py" and (close is None or any(a.startswith("**") for a in args) or same_quote):
            stream = "unknown"
        else:
            stream = file_stream(keyword["file"]) if "file" in keyword else "stdout"
        if lang == "py" and name not in STDERR_PRINTS and stream != "stderr":
            # The text backstop: any disagreement between the parse and the
            # text reads the call as reaching the log.
            region = call_region(text, lang, close)
            told = stream == "stdout" and "file" in keyword  # a recognised `file=sys.stdout`
            spoken = text[m.start():region]
            if re.search(r"\bstderr\b", spoken) or len(FILE_KEYWORD.findall(spoken)) > told:
                stream = "unknown"
                if region > end:
                    args = args + [text[end:region].strip()]
                    end = region
        calls.append(PrintCall(
            m.start(), m.end(), end, name, args, keyword,
            name in STDERR_PRINTS or stream == "stderr", stream == "unknown"))
        last = calls[-1].end
    return calls


# A Python keyword argument (`file=`, `end=`, `sep=`, `flush=`), not `==`.
KEYWORD_ARG = re.compile(r"^[A-Za-z_]+\s*=(?!=)")
# The mark an interpolated value leaves in the text a print call writes, and
# the escapes that write a line end (`\n`, `\x0a`, `\u000a`, `\012`, ...);
# Python's `\U0000000a` and `\N{...}` too, read by `line_ends`.
VALUE = "\x00"
LINE_END_ESCAPE = re.compile(
    r"\\(?:[nr]|x0[aAdD]|u000[aAdD]|u\{0*[aAdD]\}|0?1[25](?![0-7])|(U0000000[aAdD])|N\{([^{}]*)\})")


def line_ends(content: str, lang: str, data: bool = False) -> str:
    """A literal's content with every escape that writes a line end as a line end.

    Python's `\\U0000000a` and `\\N{...}` are escapes of Python only; a
    `\\N{...}` is one where its name resolves to a line feed or a carriage
    return as Python resolves it (#511): in any case and by an alias, so
    `\\N{line feed}`, `\\N{NEW LINE}`, `\\N{EOL}`, `\\N{END OF LINE}`, `\\N{nl}`
    and `\\N{cr}` are, `\\N{BULLET}` isn't. A bytes literal's (`data`)
    `\\N{...}` is no escape: `b"\\N{LINE FEED}"` writes it as written.
    """
    def end(m: re.Match[str]) -> str:
        if m.group(1) is None and m.group(2) is None:
            return "\n"
        if lang != "py":
            return m.group(0)
        if m.group(1) is not None:
            return "\n"
        if data:
            return m.group(0)
        try:
            char = unicodedata.lookup(m.group(2))
        except KeyError:
            return m.group(0)
        return "\n" if char in ("\n", "\r") else m.group(0)
    return LINE_END_ESCAPE.sub(end, content)
LITERAL_OPEN = re.compile("([rRbBfFtTuU]{0,2})('''|\"\"\"|['\"`])")
PERCENT_CONVERSION = re.compile(r"%(?:\([^)]*\))?[-#0 +]*(?:\*|[0-9]+)?(?:\.(?:\*|[0-9]+))?[diouxXeEfFgGcrsa]")
CONSOLE_CONVERSION = re.compile(r"%[sdifjoOc]")


def _literal_end(text: str, i: int, quote: str) -> int:
    """Index just past the literal whose content starts at i and ends at `quote`."""
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text.startswith(quote, i):
            return i + len(quote)
        if quote == "`" and text.startswith("${", i):
            depth, i = 1, i + 2
            while i < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            continue
        i += 1
    return len(text)


def _interpolated(content: str, lang: str, raw: bool = False) -> str:
    """An f-string's or template literal's content with every interpolation as VALUE.

    A `\\N{...}` of a Python f-string that isn't raw is a named character,
    kept as written, not a field (`named_escapes`). A self-documenting field
    (`{x=}`) prints its expression's text, then the value: `x=` and VALUE.
    """
    out, i = [], 0
    opener = "${" if lang == "js" else "{"
    while i < len(content):
        if content[i] == "\\" and lang == "js":
            out.append(content[i:i + 2])
            i += 2
            continue
        if content[i] == "\\" and lang == "py" and not raw:
            escape = NAMED_CHARACTER.match(content, i)
            stop = escape.end() if escape else i + 2 if content.startswith("\\", i + 1) else None
            if stop is not None:
                out.append(content[i:stop])
                i = stop
                continue
        if lang == "py" and content.startswith(("{{", "}}"), i):
            out.append(content[i])
            i += 2
            continue
        if content.startswith(opener, i):
            depth, start, i = 1, i + len(opener), i + len(opener)
            while i < len(content) and depth:
                depth += {"{": 1, "}": -1}.get(content[i], 0)
                i += 1
            head = FIELD_TAIL.split(content[start:i - 1])[0] if lang == "py" else ""
            out.append((head if SELF_DOCUMENTING.search(head) else "") + VALUE)
            continue
        out.append(content[i])
        i += 1
    return "".join(out)


def _top_level(text: str, i: int, stops: str) -> int:
    """Index of the first character of `stops` at bracket depth 0 from i, outside quotes; len(text) if none."""
    depth, quote = 0, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif quote_open(text, i):
            quote = quote_open(text, i)
            i += len(quote)
            continue
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c in stops and depth == 0:
            return i
        i += 1
    return len(text)


def printed_skeleton(expr: str, lang: str, console_format: bool = False) -> str:
    """The text an expression prints, literal parts as written and every value as VALUE.

    Read for the log's line-start rule: string literals (f-strings and
    template literals with their parts as VALUE), joined by `+`; a literal
    formatted by `%` or `.format(...)` -- or, as the first argument of a Node
    `console` call, by its own `%s`-style conversions -- has each conversion
    as VALUE; anything else is one VALUE. Line-end escapes become line ends.
    """
    out: list[str] = []
    text, i = expr.strip(), 0
    while i < len(text):
        if text[i].isspace() or text[i] == "+":
            i += 1
            continue
        lit = LITERAL_OPEN.match(text, i)
        if lit and (lang == "py" or not lit.group(1)) and (lang == "js" or lit.group(2) != "`"):
            prefix, quote = lit.group(1).lower(), lit.group(2)
            end = _literal_end(text, lit.end(), quote)
            closed = text.startswith(quote, end - len(quote)) and end - len(quote) >= lit.end()
            content = text[lit.end():end - len(quote)] if closed else text[lit.end():end]
            formatted = "f" in prefix or "t" in prefix or quote == "`"
            if formatted:
                content = _interpolated(content, lang, "r" in prefix)
            if "r" not in prefix:
                content = line_ends(content, lang, "b" in prefix)
            content = content.replace("\r", "\n")
            i = end
            rest = text[i:].lstrip()
            if not formatted and lang == "py" and rest.startswith(".format("):
                content = re.sub(r"(?<!\{)\{[^{}]*\}", VALUE, content)
                i = call_end(text, text.index(".format(", i) + len(".format("))
            elif not formatted and lang == "py" and rest.startswith("%") and not rest.startswith("%="):
                content = PERCENT_CONVERSION.sub(VALUE, content).replace("%%", "%")
                i = _top_level(text, text.index("%", i) + 1, "+")
            elif not formatted and console_format and not out:
                content = CONSOLE_CONVERSION.sub(VALUE, content)
            out.append(content)
            continue
        # Anything else -- a name, a call, an operator expression -- is a value.
        out.append(VALUE)
        i = max(_top_level(text, i, "+"), i + 1)
    return "".join(out)


def leading_print(call: PrintCall, lang: str) -> bool:
    """A log print call whose text begins a line with an interpolated value.

    The call's positional arguments are joined by its separator (a space, or
    Python's `sep=`); the line-start rule holds at the start of the text and
    after every line end in it. The call itself is taken to start a line.
    """
    positional = [a for a in call.args if not (lang == "py" and KEYWORD_ARG.match(a))]
    console = call.name.startswith("console")
    if lang == "py" and call.name == "print":
        sep = printed_skeleton(call.keyword["sep"], lang) if "sep" in call.keyword else " "
    else:
        sep = " " if console else ""
    printed = sep.join(printed_skeleton(arg, lang, console and n == 0) for n, arg in enumerate(positional))
    return any(line.lstrip().startswith(VALUE) for line in printed.split("\n"))


def single_literal(arg: str, lang: str) -> bool:
    """One string literal and nothing else; a template's or f-string's parts are read on their own."""
    prefix = r"[rRbBfFtTuU]{0,2}" if lang == "py" else ""
    quotes = ("'", '"') if lang == "py" else ("'", '"', "`")
    if lang == "py" and any(re.fullmatch(prefix + q * 3 + r"(?:(?!" + q * 3 + r")[^\\]|\\.)*" + q * 3, arg.strip(),
                                         re.DOTALL) for q in quotes):
        return True  # a triple-quoted one
    return any(re.fullmatch(prefix + q + r"(?:[^" + q + r"\\]|\\.)*" + q, arg.strip()) for q in quotes)


ATTRIBUTE = re.compile(r"\.[A-Za-z_][A-Za-z0-9_]*")


def expr_name(expr: str) -> str:
    """The name a finding gives a printed expression: its root name, or the whole expression.

    A name, or one followed only by attribute accesses, subscripts and calls
    (`x`, `a.b`, `x[0]`, `f(x)`), is named by its leading dotted name (`x`,
    `a.b`, `x`, `f`), the name an ALLOWED entry gives it. Anything else -- an
    operator expression (`total + p`, `x % p`, `p or ""`, `a if c else b`),
    a literal followed by more (`f"v" + p`, `"{}".format(p)`) -- is named
    whole (#511), so an ALLOWED entry for its first name doesn't cover it.
    """
    text = expr.strip()
    root = re.match(r"[A-Za-z_][A-Za-z0-9_.]*", text)
    if not root:
        return text
    i = root.end()
    while i < len(text):
        if text[i] in "([":
            close = call_close(text, i + 1)
            if close is None:
                return text
            i = close
        elif attr := ATTRIBUTE.match(text, i):
            i = attr.end()
        else:
            return text
    return root.group(0)


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
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif quote_open(text, i):
            quote = quote_open(text, i)
            i += len(quote)
            continue
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
        inherit_group_dest(self.units)
        self._consumed: dict[int, list[tuple[int, int]]] | None = None
        self._heredoc_ids = list(range(len(self.units)))
        for j in range(1, len(self.units)):
            if self.units[j - 1].lang == self.units[j].lang:
                self._heredoc_ids[j] = self._heredoc_ids[j - 1]
        self.assigned: dict[str, list[tuple[int, str | None]]] = {}
        for j, unit in enumerate(self.units):
            for name, rhs in assignments(unit):
                self.assigned.setdefault(name, []).append((j, rhs))
        self.shell_shown = any(u.lang == "sh" and u.text.strip() == SHELL_SHOWN for u in self.units) \
            and not any(u.lang == "sh" and u.text.strip() != SHELL_SHOWN and not is_comment(u.text)
                        and SHELL_SHOWN_REBIND.search(u.text) for u in self.units)
        self.blocks = blocks_of(self.units)
        self._mask_paths: dict[tuple[str, int], tuple[int, ...] | None] = {}
        self._events: dict[str, tuple[list[tuple[int, bool]], set[int]]] = {}
        # The function bodies each unit stands in, by their spans.
        self.function_lines: dict[int, set[int]] = {}
        for b in self.blocks.functions:
            start, end = self.blocks.spans.get(b, (0, -1))
            for j in range(start, end + 1):
                self.function_lines.setdefault(j, set()).add(b)
        # Which Python/Node heredoc defines `shown` the canonical way -- and
        # nothing else in it binds the name (#513).
        self.shown: dict[int, bool] = {}
        rebound: set[int] = set()
        for k, unit in enumerate(self.units):
            key = self.heredoc_id(k)
            if unit.lang not in ("py", "js"):
                continue
            ok = self.canonical_shown(k)
            if not ok and not is_comment(unit.text) and unit.text.strip() != PY_SHOWN_RETURN \
                    and (PY_SHOWN_NAME if unit.lang == "py" else JS_SHOWN_NAME).search(unit.text):
                rebound.add(key)
            self.shown[key] = self.shown.get(key, False) or ok
        for key in rebound:
            self.shown[key] = False
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

    def canonical_shown(self, k: int) -> bool:
        """Unit k defines `shown` the canonical way.

        Node: the line is JS_SHOWN. Python: the line is PY_SHOWN, the first
        line of its body that isn't blank or a comment is PY_SHOWN_RETURN --
        not one further down, below a statement that can return first
        (#513) -- and no decorator stands above it (`@d` rebinds the name),
        also not one continued over bracketed or backslash-joined lines
        (`@(lambda f:`, `    str)`). Failing closed: walking up from the
        `def`, every code line is taken until one at most as indented as the
        `def`, where the lines walked are bracket-balanced -- counted outside
        strings and comments, so `"("` and `# (` don't balance a line (#513)
        -- none of them holds a quote (a PEP 701 f-string nests them,
        `f"{"("}"`, so no count through one is proven) and the line above
        doesn't end in a backslash; an `@` at the start of any line taken
        voids it, up to the heredoc's start.
        """
        unit = self.units[k]
        if unit.lang == "js":
            return unit.text.strip() == JS_SHOWN
        if unit.lang != "py" or PY_SHOWN.match(unit.text) is None:
            return False
        key = self.heredoc_id(k)
        code = [j for j, u in enumerate(self.units)
                if self.heredoc_id(j) == key and u.text.strip() and not is_comment(u.text)]
        at = code.index(k)
        body = self.units[code[at + 1]].text.strip() if at + 1 < len(code) else ""
        if body != PY_SHOWN_RETURN:
            return False
        depth, quoted, indent = 0, False, indent_of(unit.text)
        for j in range(at - 1, -1, -1):
            line = self.units[code[j]].text
            above = line.strip()
            if above.startswith("@"):
                return False
            # Brackets outside strings and comments (`    "(" and str)`,
            # `    str)  # (`). A quote on any line walked makes the count
            # unproven -- a PEP 701 f-string nests quotes (`f"{"("}"`) -- so
            # the walk goes on to the heredoc's start (#513).
            left, _ = bracket_state(above, 0, depth=WALK_DEPTH, lang="py")
            depth += WALK_DEPTH - left
            quoted = quoted or "'" in above or '"' in above
            if not depth and not quoted and indent_of(line) <= indent \
                    and not (j and self.units[code[j - 1]].text.rstrip().endswith("\\")):
                break
        return True

    def helper_line(self, k: int) -> bool:
        """A line of a canonical helper's own definition, exactly as the canonical text has it.

        Its prints aren't read, so it must be one of those lines and nothing
        else: `def shown(v): print(f"x {p}")` is not one.
        """
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

    def consumed(self) -> dict[int, list[tuple[int, int]]]:
        """For each Python or Node unit, the column spans that print calls the strict reading names cover.

        A call goes on over its continuation lines (`joined_text`), so its
        span covers part of each.
        """
        if self._consumed is None:
            self._consumed = {}
            for k, unit in enumerate(self.units):
                if unit.lang not in ("py", "js"):
                    continue
                text = self.joined(k)
                start = 0
                spans = []
                for n, part in enumerate(text.split("\n")):
                    spans.append((k + n, start, start + len(part)))
                    start += len(part) + 1
                for call in print_calls(text, unit.lang):
                    for j, first, last in spans:
                        if call.start < last and call.end > first:
                            self._consumed.setdefault(j, []).append(
                                (max(call.start, first) - first, min(call.end, last) - first))
        return self._consumed

    def unknown_writer(self, k: int) -> bool:
        """A Python or Node line names a stream writer that no print call it is part of accounts for (#513).

        A stdout object (`sys.stdout`, `sys.__stdout__`, `process.stdout`)
        counts where the heredoc's stdout reaches a sink -- an env file, the
        summary or the log --, a print or `console` everywhere: passed on or
        reached by a subscript, it writes to a stream the guard can't tell.
        """
        unit = self.units[k]
        if unit.lang not in ("py", "js") or is_comment(unit.text) or self.helper_line(k):
            return False
        refs = [PY_PRINT_REF if unit.lang == "py" else JS_PRINT_REF]
        if unit.dest in ("envfile", "summary") or unit.stdout_logged():
            refs.append(PY_STDOUT_REF if unit.lang == "py" else JS_STDOUT_REF)
        covered = self.consumed().get(k, [])
        return any(not any(a <= m.start() < b for a, b in covered)
                   for ref in refs for m in ref.finditer(unit.text))

    def heredoc_id(self, k: int) -> int:
        """The first unit of the run of units in unit k's language that holds k."""
        return self._heredoc_ids[k]

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

    @staticmethod
    def _is_mask(rhs: str | None) -> bool:
        return MASKED_ASSIGNMENT.match((rhs or "").strip()) is not None

    def mask_statement(self, name: str, j: int) -> tuple[int, ...] | None:
        """`_mask_statement`, read once per name and unit: every print walks back over the same masks."""
        key = (name, j)
        if key not in self._mask_paths:
            self._mask_paths[key] = self._mask_statement(name, j)
        return self._mask_paths[key]

    def _mask_statement(self, name: str, j: int) -> tuple[int, ...] | None:
        """The blocks around the masked assignment to `name` on unit j, if it always runs there.

        The assignment must be a statement of its own -- not a `cond && x=...`,
        `cond || x=...`, a pipeline element, a background job or a prefix of a
        command (`x=$(shown "$x") cmd` sets x for cmd only) -- and the last
        assignment to the name on its line. A line that ends in `&&`, `||`,
        `|` or `|&` continues its list on the next line, so a mask that starts
        a line after one is conditional too (after a pipe it runs in a
        subshell); one ending in `&` doesn't.
        """
        segments = self.blocks.segments.get(j)
        if segments is None:
            return None
        carried = ""
        for p in range(j - 1, -1, -1):
            previous = self.blocks.segments.get(p)
            if previous is None or not any(seg[1].strip() or seg[2] for seg in previous):
                continue  # not a shell statement line (heredoc text, comment, blank)
            if len(previous) > 1 and not previous[-1][1].strip() and previous[-2][2] in ("&&", "||", "|"):
                carried = previous[-2][2]  # `cmd &` ends its list: the next line runs anyway
            elif (len(previous) > 2 and not previous[-1][1].strip() and previous[-2][2] == "&"
                  and not previous[-2][0].strip() and previous[-3][2] == "|"):
                carried = "|"  # `cmd |&`, which `statements_of` splits into `|` and `&`: a pipe
            break
        found: tuple[int, ...] | None = None
        for i, (text, _, separator) in enumerate(segments):
            statement = text.strip()
            while True:
                words = statement.split(None, 1)
                if not words or words[0] not in ("then", "else", "elif", "do", "if", "while", "until", "!", "{"):
                    break
                statement = words[1] if len(words) > 1 else ""
            own = [rhs for n, rhs in assignments(Logical(j, statement, "sh")) if n == name]
            if not own:
                continue
            found = None
            whole = ASSIGNMENT.match(statement)
            before = segments[i - 1][2] if i else carried
            if (len(own) == 1 and self._is_mask(own[0]) and whole and whole.group(1) == name
                    and whole.end() == len(statement) and before not in ("&&", "||", "|", "&")
                    and separator not in ("|", "&")):
                found = self.blocks.paths[j][i]
        return found

    def masked_before(self, name: str, k: int) -> bool:
        """A masked assignment to `name` dominates the print on unit k (#507).

        Walking back from the print, every assignment to the name must be
        masked, and the first one met whose block encloses the print -- so it
        runs whenever the print does -- covers it. A masked assignment in a
        block that doesn't enclose the print (a branch, a loop body, a case
        arm, a group, a subshell, a function body) is passed over, a raw one
        stops the walk. Beyond that the print must not sit in a function body
        the mask is outside of (the body runs when it is called, not where it
        stands), no unmasked assignment to the name may stand in a function
        body the print is outside of (a call can run it between the two), and
        no unmasked assignment may follow the print inside a loop that
        encloses the print but not the mask (the next pass would print it).
        When the guard can't attribute the body's blocks, nothing covers.
        """
        if not self.shell_shown or not self.blocks.ok:
            return False
        unit = self.units[k]
        at = unit.origin if unit.lang == "sh-heredoc" else k
        segments = self.blocks.segments.get(at)
        if segments is None:
            return False
        events, raw = self.events_of(name)
        if at in raw:
            return False  # an assignment on the print's own line: order unknown
        # The print is the statement that expands the name, each one if there
        # are several -- not the blocks every statement of the line shares:
        # in `f() { echo "$x"; }` the echo sits in the function body, though
        # `f` doesn't. A heredoc's lines belong to every statement of its
        # opening line.
        statements = [i for i, seg in enumerate(segments)
                      if unit.lang == "sh" and any(ref == name for ref, _, _ in shell_refs(seg[0]))]
        paths = [self.blocks.paths[at][i] for i in statements or range(len(segments))]
        return all(self.dominated(name, at, set(path), events, raw) for path in paths)

    def events_of(self, name: str) -> tuple[list[tuple[int, bool]], set[int]]:
        """(unit, masked) for every assignment to `name`, and the units of the unmasked ones."""
        if name not in self._events:
            events = [(j, self._is_mask(rhs)) for j, rhs in self.assigned.get(name, [])]
            self._events[name] = (events, {j for j, masked in events if not masked})
        return self._events[name]

    def dominated(self, name: str, at: int, here: set[int], events: list[tuple[int, bool]], raw: set[int]) -> bool:
        """A masked assignment to `name` dominates a print on unit `at` whose statement sits in `here`."""
        if any(self.function_lines.get(j, set()) - here for j in raw):
            # A function body runs where it is called, so a raw assignment in
            # one the print is outside of can run between the mask and it.
            return False
        for j, masked in reversed([event for event in events if event[0] < at]):
            if not masked:
                return False
            path = self.mask_statement(name, j)
            if path is None or not set(path) <= here:
                continue
            outside = here - set(path)
            if outside & self.blocks.functions:
                return False
            for b in outside:
                if self.blocks.kinds[b] != "loop":
                    continue
                end = self.blocks.spans[b][1]
                if any(at <= a <= end for a in raw):
                    return False
            return True
        return False

    def in_subshell(self, name: str, j: int) -> bool:
        """An assignment to `name` on unit j may stand in a `( ... )` subshell (#507).

        Read from the blocks. Where they can't be attributed this says no: an
        assignment after a `(` on the same line is unknown anyway
        (`assignments`), one on a later line of the subshell is read as an
        ordinary one.
        """
        segments = self.blocks.segments.get(j)
        if segments is None or not self.blocks.ok:
            return False
        for i, (text, _, _) in enumerate(segments):
            if any(n == name for n, _ in assignments(Logical(j, text, "sh"))) \
                    and any(self.blocks.kinds[b] == "subshell" for b in self.blocks.paths[j][i]):
                return True
        return False

    def clean_shell(self, name: str, k: int, depth: int = 0) -> bool:
        before = [(j, rhs) for j, rhs in self.assigned.get(name, []) if j < k]
        if self.refused_before(name, k):
            return True
        if before and self.masked_before(name, k):
            return True
        if self.allowed(name, k, shell=True):
            return True
        everywhere = self.assigned.get(name, [])
        if name in self.body.env:
            return not everywhere and "$" not in self.body.env[name]
        if not everywhere or depth > 5:
            return False
        # Constant, or built only from clean names: every assignment is a
        # literal or a string whose expansions are all clean where it stands,
        # and none is made in a subshell (it doesn't reach the print).
        for j, rhs in everywhere:
            if rhs is None or "$(" in rhs or re.search(r"(?<!\\)`", rhs) or self.in_subshell(name, j):
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
            if rhs is None or self.in_subshell(name, j):
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
        _, _, grouped, _ = redirected_groups(self.units)
        out = []
        for k, unit in enumerate(self.units):
            if is_comment_unit(unit) or not unit.text.strip() or self.helper_line(k):
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
        _, _, grouped, _ = redirected_groups(self.units)
        heredoc = HEREDOC.search(text)
        if heredoc:
            # The heredoc's own lines are read where they stand; a bare `cat`
            # prints them unchanged, anything else prints its own output.
            command = SUMMARY_FILE.sub("", text[:heredoc.start()] + text[heredoc.end():]).strip()
            if interpreter_of(text[:heredoc.start()]) or re.fullmatch(r"cat(?:\s+-)?", command):
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

        Read strictly (`strict_prints`), with the summary helpers as the mask,
        and -- as on an env-file line -- a print call with its continuation
        lines joined to it, so a bare name on one is read (#513).
        """
        unit = self.units[k]
        calls = JS_MD_CALL if unit.lang == "js" else PY_MD_CALL
        return self.strict_prints(k, calls, self.md.get(self.heredoc_id(k), False), self.joined(k))

    def envfile_template(self, k: int) -> list[str]:
        """Unclean values on a line of a Python or Node heredoc whose stdout goes to an env file (#507).

        Read like a summary line (`strict_prints`), with `shown(...)` -- defined
        the canonical way in that heredoc -- as the mask, and ALLOWED for the log
        sink. A stdout print whose call goes on past the line is read with its
        continuation lines joined to it.
        """
        unit = self.units[k]
        opener = self.units[unit.origin] if unit.origin >= 0 else None
        stderr = opener is not None and STDERR_TO_ENV_FILE.search(HEREDOC.sub(" ", opener.text)) is not None
        names = self.strict_prints(k, ("shown",), self.shown.get(self.heredoc_id(k), False), self.joined(k),
                                   stderr=stderr)
        return [name for name in names if not self.allowed(name, k, shell=False)]

    def log_template(self, k: int) -> list[str]:
        """Unclean values in the log prints of a Python or Node line (#511).

        Read as strictly as an env-file line (`strict_prints`), with
        `shown(...)` -- defined the canonical way in that heredoc -- as the
        mask, and ALLOWED for the log sink: every stderr print, and every
        stdout print where the heredoc's stdout is the log.
        """
        unit = self.units[k]
        names = self.strict_prints(k, ("shown",), self.shown.get(self.heredoc_id(k), False), self.joined(k),
                                   stdout=unit.stdout_logged(), stderr=True)
        return [name for name in names if not self.allowed(name, k, shell=False)]

    def joined(self, k: int) -> str:
        """`joined_text` of unit k."""
        return joined_text(self.units, k)

    def strict_prints(self, k: int, calls: tuple[str, ...], defined: bool, text: str,
                      stdout: bool = True, stderr: bool = False) -> list[str]:
        """Unclean values in the print calls of a Python or Node line that reach a sink.

        Every print call on the line counts. Which ones this reads: stdout
        calls where `stdout` is set (the summary, an env file, or the log when
        the heredoc's stdout goes there); calls to stderr -- by their name, or
        a `file=sys.stderr` argument (that text in a comment makes a stdout
        call one to either stream, not a stderr call) -- where
        `stderr` is set (the log, or an env file the heredoc sends its stderr
        into as well); calls to a `file=` the guard can't name as a stream
        (`file_stream`), calls not closed in the joined text, calls with a
        `**` argument, calls with a same-quote f-string field
        (`same_quote_field`) and calls whose text names `stderr` or `file=`
        where the parse saw no `file=sys.stderr` (`print_calls`) where
        either is set. In a call read, every argument,
        and Python's `end=` and `sep=`, must be one plain literal or a call of
        the helper (`calls`, which counts only where `defined`). Template and f-string parts anywhere else on the
        line, outside the calls not read, must be helper calls too.
        """
        unit = self.units[k]
        exprs: list[str] = []
        outside, last = [], 0
        for call in print_calls(text, unit.lang):
            outside.append(text[last:call.start])
            last = call.end
            if not call.read_by(stdout, stderr):
                continue  # another sink's line (its rules read it)
            exprs += template_exprs(text[call.opener_end:call.end], unit.lang)
            for arg in call.args:
                if unit.lang == "py" and KEYWORD_ARG.match(arg):
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
            names.append(expr_name(expr))
        return names

    @staticmethod
    def printed_segment(unit: Logical) -> str:
        """The part of a shell line whose expansions reach the sink.

        A command or env-file line counts whole. A plain print counts from its
        `echo`/`printf` to the end of that statement, so `gh api "$x" || echo ''`
        doesn't charge `$x` to the echo -- every print of the line whose
        output reaches the log, each with its own statement (`echo x > f;
        echo "$x"`, `logged_prints`, #513). The commands it pipes into count
        with it -- what they print goes where the echo's output goes, as in a
        group redirected to an env file -- except for a `tee` and its words,
        which name the files it writes (`| tee "$f"`, #513), up to a process
        substitution, whose commands print (`| tee >(echo "$x")`).
        """
        text = unit.text
        if unit.lang != "sh" or COMMAND.search(text) or destination(text) == "envfile":
            return text
        prints = logged_prints(text)
        if not prints:
            return text
        bare = unquoted(text)
        segment = []
        for m, stop in prints:
            at = m.start(1)
            for tee in TEE_SEGMENT.finditer(bare, at, stop):
                segment.append(text[at:tee.start()])
                sub = PROCESS_SUBSTITUTION.search(text, tee.start(), tee.end())
                at = sub.start() if sub else tee.end()
            segment.append(text[at:stop])
        return " ; ".join(segment)

    def names_on(self, k: int) -> list[str]:
        unit = self.units[k]
        names = []
        if unit.lang in ("sh", "sh-heredoc"):
            for name, masked, numeric in shell_refs(self.printed_segment(unit)):
                if not ((masked and self.shell_shown) or numeric or self.clean_shell(name, k)):
                    names.append(name)
            return names
        if self.helper_line(k):
            return names
        if unit.dest == "envfile":
            # Its stdout prints are entries, read strictly; its stderr prints
            # are log lines, read below as on any other heredoc line.
            names += self.envfile_template(k)
            if not any(call.reaches_log(unit.stdout_logged()) for call in print_calls(self.joined(k), unit.lang)):
                return names
        # Its log prints, read as strictly (#511).
        return names + self.log_template(k)

    def leading_print(self, k: int) -> bool:
        """A log print call of a Python or Node line begins a line with a value (`leading_print`)."""
        unit = self.units[k]
        return any(call.reaches_log(unit.stdout_logged()) and leading_print(call, unit.lang)
                   for call in print_calls(self.joined(k), unit.lang))


def _literal_head(quoted: str) -> str | None:
    """Text before the first expansion of a shell word, or None if it isn't quoted."""
    if quoted.startswith("'"):
        return quoted[1:quoted.find("'", 1)] if "'" in quoted[1:] else quoted[1:]
    if quoted.startswith('"'):
        head = re.split(r'(?<!\\)[$"]', quoted[1:], maxsplit=1)[0]
        return head
    return None


def leading_value(unit: Logical) -> bool:
    """A shell log line whose printed text begins with an interpolated value.

    The runner trims leading whitespace before it looks for `::`, and no mask
    touches `::`, so such a value can start a command of its own. A literal
    with at least one non-space character must come first. A line piped
    into `tee` or `cat` is printed to the log, wherever else tee writes it
    (`echo "$x=1" | tee -a "$GITHUB_OUTPUT"`, #513). Every print of the line
    whose output reaches the log is read, each from its own start (`echo x >
    f; echo "$x"`, `logged_prints`, #513), and so is every print whose own
    pipeline pipes into `tee` or `cat` (`echo a; echo "$x" | tee -a
    "$GITHUB_ENV"`, #513).
    """
    text = unit.text
    if unit.lang != "sh" or COMMAND.search(text):
        return False
    prints = [m for m, _ in logged_prints(text)]
    bare = ARRAY_LITERAL.sub(lambda m: " " * len(m.group()), unquoted(text))
    if pipes_to_log(text) and (first := SHELL_PRINT.search(bare)):
        prints.append(first)  # tee prints an env-file or summary write as well
    # And the print of every pipeline that itself pipes into `tee` or `cat`
    # (`echo a; echo "$x" | tee -a "$GITHUB_ENV"`, #513).
    starts = [0] + [m.end() for m in PIPELINE_SPLIT.finditer(bare)]
    ends = [m.start() for m in PIPELINE_SPLIT.finditer(bare)] + [len(bare)]
    found = list(SHELL_PRINT.finditer(bare))
    for a, b in zip(starts, ends):
        m = next((p for p in found if a <= p.start(1) < b), None)
        if m and pipes_to_log(text[a:b]):
            prints.append(m)
    return any(_leads(text, m) for m in prints)


def _leads(text: str, m: re.Match) -> bool:
    """The print SHELL_PRINT matched as `m` begins its printed text with a value."""
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


def audit_body(body: Body, siblings: list[Body] | None = None, entries: tuple[Allowed, ...] = ALLOWED,
               used: set[Allowed] | None = None) -> list[dict]:
    checker = Checker(body, siblings if siblings is not None else [body], entries,
                      used if used is not None else set())
    findings = []
    redirected, _, _, _ = redirected_groups(checker.units)
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
        lang = checker.units[k].lang
        leads = checker.leading_print(k) if lang in ("py", "js") else leading_value(checker.units[k])
        if k not in redirected and leads and not checker.allowed(LEADING, k, shell=lang == "sh"):
            findings.append(finding(
                body.path, line, body.step,
                f"`{LEADING}`: this log line begins with an interpolated value. No mask touches a "
                "leading '::', so put a literal in front of it."))
    for unit in checker.units:
        if unit.lang in ("py", "js") and unit.expands and re.search(r"[$`]", unit.text):
            findings.append(finding(
                body.path, body.first_line + unit.index, body.step,
                f"`{UNQUOTED_NAME}`: this line of a Python or Node heredoc holds '$' or a backtick, and the "
                "heredoc's delimiter is unquoted, so the shell expands it before the interpreter reads the "
                "line. Quote the delimiter (<<'PY') and read a value from the environment instead."))
    for k, unit in enumerate(checker.units):
        if unit.lang not in ("py", "js") or is_comment(unit.text):
            continue
        line = body.first_line + unit.index
        if checker.unknown_writer(k) and not checker.allowed(UNKNOWN_WRITER, k, shell=False):
            findings.append(finding(
                body.path, line, body.step,
                f"`{UNKNOWN_WRITER}`: this line of a Python or Node heredoc names a print, console or stdout "
                "outside a print call the guard reads (print, sys.stdout.write, sys.stderr.write, "
                "console.<method>, process.stdout.write, process.stderr.write), so it can't read what reaches "
                "the log, an env file or the summary. Print through one of those calls."))
        if ENV_FILE_NAMED.search(unit.text) and not checker.allowed(ENV_FILE_OPENED, k, shell=False):
            findings.append(finding(
                body.path, line, body.step,
                f"`{ENV_FILE_OPENED}`: this line of a Python or Node heredoc names an env file or the step "
                "summary, so it can write there itself, which the guard doesn't read. Print to stdout and redirect "
                "the heredoc there instead, or add it to ALLOWED with the reason it is constrained."))
    for k in unattributed_summary_closers(checker.units):
        findings.append(finding(
            body.path, body.first_line + checker.units[k].index, body.step,
            f"`{GROUP_NAME}`: this line closes a group or compound redirected to the step summary, but the "
            "guard finds no opener for it, so it can't tell which lines print there. Write the opener as a "
            "statement of its own (`{`, `for ...; do`, `if ...; then`)."))
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
