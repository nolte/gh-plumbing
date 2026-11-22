---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "511"
classification: "bug"
secondary-classes: ["security"]
route: "direct"
status: approved
created: "2026-11-22"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #511 — Masking guard: read Python and Node heredoc log prints as strictly as env-file prints
- **URL**: https://github.com/nolte/gh-plumbing/issues/511
- **Labels**: cicd, security
- **Linked items**: #507 / PR #512 (merged `f5d7e4f`, mentions #511 as a follow-up only); #513 (adjacent gaps, out of scope)
- **Prior art checked**: no open PR references #511 (`gh pr list --state all --search "511 in:body"` → only #512, which leaves it open); no `project/requirements/` artifact for #511 (only `release-archive-provenance.md`)
- **Working copy**: /home/nolte/repos/.worktrees/gh-plumbing/511-strict-heredoc-log-prints; detect=no-taskfile (`task -l` lists no worktree task); created via fallback `git worktree add -b fix/511-strict-heredoc-log-prints … origin/develop` @ `f5d7e4f`; ignore check `git check-ignore -q` on this path: not ignored
- **Author trust**: issue author `nolte` (owner) — trusted.

## Classification

- **Primary class**: bug
- **Secondary class(es)**: security
- **Rationale**: a CI security guard accepts caller-controlled values on log lines that start workflow commands; the guard is wrong, the fix is to the guard.
- **Asserted cause verified**: confirmed. Fixtures were run against `scripts/workflow_command_masking.py` @ `f5d7e4f` as the only step of a `reusable-x.yaml` with `env: P: ${{ inputs.p }}` under a scratch root. Results:
  - `print("ok"); print("::error::" + p)` (issue fixture) → exit 0
  - continuation `print("ok",⏎ "::error::" + p)` → exit 0
  - `print("x", end="\n::error::"); print(p)` → exit 0
  - Node `console.log("ok"); console.log("::error::" + p);` → exit 0
  - a **single** `print("::error::" + p)` → exit 0
  - `print("ok", p, sep="\n::error::")` → exit 1 (already a finding)
  The docstring states the lax log reading at `scripts/workflow_command_masking.py:269-277` ("only the first print call on a line is read, and of it only f-strings, template literals and bare arguments on that line ...").

## Scope

- **In scope**:
  - The log rule for Python and Node heredoc prints (stderr prints, and stdout prints whose heredoc stdout isn't redirected) uses the same strict reader as the env-file and step-summary rules. That covers every print on a line, continuation lines, `end=`/`sep=`, concatenation, `%`, `.format(...)`, Node `+`, `print (` with a space, and every console method.
  - The log-specific rule that a value must not lead the line (the runner trims, `<leading value>`) stays in force on top.
  - One test per measured form above. Each must be a finding.
  - Sweep over the Python and Node heredocs whose prints reach the log. Every new hit is repaired, either by masking or by an ALLOWED entry with a reason.
  - The "Not covered" entry is removed or reworded to what remains. If the strict reader refuses harmless forms on the log side, a matching "Refused although harmless" entry is added.
- **Out of scope**: #513 (shell block structure, gaps of the env-file sink, `| tee`/`cat` destination reading). Stdout under an alias (`sys.__stdout__`) is already named under "Not covered" and is not part of #511.

## Route

- **Decision**: direct
- **Rationale**: one outcome (log rule = strict reader), one file plus its tests, one PR strand, no roadmap item.

## Work packages

### P1 — Strict reading of heredoc log prints

- **Problem statement**: The log path reads only the first print call of a line, and of that only f-strings, template literals and bare arguments. The strict reader of the env-file and summary paths reads every print. Route log-bound heredoc prints (stderr, and unredirected stdout) through the strict reader. Keep the `<leading value>` check.
- **Acceptance criteria**: all five measured forms (Python second print, continuation line, `end=`, Node second print, single concatenation) exit 1 with a test each; `sep=` stays a finding; a log print of `f"...{shown(p)}..."` and of literals stays clean; the full suite is green.
- **Touched files / artifacts**: `scripts/workflow_command_masking.py`, `scripts/tests/test_workflow_command_masking.py`
- **Specialist**: nolte-engineering:fullstack-developer (runtime catalog: no entry names guard/linter authoring; `guard-coverage-scanner` is read-only rule inventory; same choice as #507)
- **Depends on**: none

### P2 — Sweep, tree repair, docstring

- **Problem statement**: The stricter log rule may hit existing heredocs. Candidates are three log-bound heredocs, found by grepping the heredoc openers in `.github/workflows` and `actions`:
  - `.github/workflows/reusable-nodejs-coverage.yaml:129` prints `${threshold}` unmasked.
  - `.github/workflows/reusable-release-publish.yml:532`
  - `.github/workflows/reusable-release-publish.yml:673` prints `{tag}` and `len(...)`.

  The docstring must match the new behaviour.
- **Acceptance criteria**: `python3 scripts/workflow_command_masking.py` exits 0 on the tree; every new hit is repaired, by masking or by an ALLOWED entry with the reason the value is constrained, and listed with its count in the PR's class sweep; the "Not covered" entry at `:269-277` is removed or reworded; any harmless form now refused is listed under "Refused although harmless".
- **Touched files / artifacts**: `scripts/workflow_command_masking.py` (docstring, ALLOWED), possibly `.github/workflows/reusable-nodejs-coverage.yaml` and `.github/workflows/reusable-release-publish.yml`
- **Specialist**: nolte-engineering:fullstack-developer
- **Depends on**: P1

## Existing installations / upgrade / rollback

Not applicable. The repository ships no deployable artefact: it is a configuration repo of reusable workflows. The guard runs only on this repository (`required-check-triggers-tests / Python Coverage`). A workflow edit in P2 that only adds a mask changes what consumers print to their logs, not their inputs or outputs.

## Dependency ordering

P1 → P2

## Risks

- **New false positives on a log line that was clean, including in consumer-visible workflows.** Mitigation: the P2 sweep and repair; the tree must exit 0 before the PR opens.
- **Security-sensitive surface.** P2 may touch `.github/workflows/`, and the guard is a security control. Mitigation: a security-briefed read-only diff review before the PR, by an agent with shell access so it can run fixtures; `code-security-reviewer` has no shell. The review must also cover regressions against `develop`.
- **The strict reader carries env-file semantics, such as the end-of-entry rules.** Its refusals may not all fit a log line. Mitigation: P1 keeps the log-specific rules, such as `<leading value>`; any difference that remains is stated in the docstring.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| A line starting `def shown(` hid its prints | diff review @ `0b6babc` | fixed directly (`ea1bd4c`) | `def shown(v): print(f"x {p}", file=sys.stderr)`: develop 1 / HEAD 0 | — |
| Any `file=` not literally sys.stdout/stderr was treated as a file of its own (`sys.__stderr__`, `(sys.stderr)`, alias) | diff review @ `0b6babc` | fixed directly (`15e29c6`) | `print(f"x {p}", file=sys.__stderr__)`: 1/0 | — |
| `file=sys.stderr` on a continuation line wasn't read | diff review @ `0b6babc` | fixed directly (`86fc6ee`) | multi-line print with `> /tmp/o`: 0/0 | — |
| Own-file exception for `file=open(...)` bypassable (path forms, rebinding, nested prints; `//dev/stdout` into GITHUB_OUTPUT) | diff review @ `86fc6ee` | fixed directly by removing the exception (`51cb2ad`) | `print(f"x={p}", file=open("//dev/stdout","w"))` with `>> "$GITHUB_OUTPUT"`: 1/0 | — |
| Triple quotes broke the quote scan, `file=sys.stderr` lost | diff review @ `51cb2ad` | fixed directly (`4cf4d9d`, also unclosed / `**` → unknown) | `print(p, end='''it's''', file=sys.stderr)` with `> f.txt`: 1/0 | — |
| PEP 701 same-quote f-string field; `\`-continued `**kw` / `file=` | delta review @ `4cf4d9d` | fixed directly (`4bbb63e`) | `print(f"{d[")"]}", p, file=sys.stderr)`: 1/0 | — |
| `\{` in raw f-strings, t-strings, `}` in a field comment | delta review @ `4bbb63e` | fixed directly by the text backstop (`f7c11aa`) | `print(rf"\{d[")"]}", p, file=sys.stderr)`: 1/0 | — |
| A heredoc piped to a command (`\| cat`) wasn't read | matrix re-run @ `f7c11aa` | fixed directly (`e412bc2`, pipe = log) | `print(f"::warning::{p}")` with `\| cat`: 1/0 | — |
| `> f.txt` with a literal `::cmd::` line no longer flagged | matrix re-run @ `e412bc2` | dismissed: output goes to the file, not the log; develop's flag was a false positive | `print(f"::warning::{p}")` with `> f.txt`: 1/0 | — |
| Final review: no blocking findings | diff review @ `e412bc2` | no findings that block; ALLOWED-emptied sets develop = HEAD (107) | ~600 fixtures, 12 000 fuzz bodies | — |
| `)` in a `#` comment ends the call early; multi-line summary print not joined; stdout to `/dev/stderr` read as a file; `piped` not inherited through `{ … } \| cat`; further stderr paths (logging, raise, assert, os.write, throw) | diff review @ `e412bc2` | filed (all 0/0 on develop) | `print(p,  # )` ⏎ `file=sys.stderr)` with `> f.txt`: 0/0 | #513 |

## Dispatch log

- 2026-11-22 P1+P2 dispatched to nolte-engineering:fullstack-developer — strict log reader (`6b522fa`), docstring (`0b6babc`); sweep 5 heredocs / 17 log-print lines / 0 hits
- 2026-11-22 review fixes dispatched to nolte-engineering:fullstack-developer — `ea1bd4c`, `15e29c6`, `86fc6ee`, `51cb2ad`, `4cf4d9d`, `4bbb63e`, `f7c11aa`, `e412bc2`; 1111 tests, tree exit 0
