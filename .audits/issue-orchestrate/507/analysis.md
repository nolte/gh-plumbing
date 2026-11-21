---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "507"
classification: "bug"
secondary-classes: ["security"]
route: "direct"
status: approved
created: "2026-11-21"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #507 — Masking guard: two gaps in the log and env-file rules (line-order reassignment, heredoc stdout into an env file)
- **URL**: https://github.com/nolte/gh-plumbing/issues/507
- **Labels**: cicd, security
- **Linked items**: follow-up of #506 (PR #508, merged as `8499e75`); rules from #505; origin #492
- **Prior art checked**: no open PR (`gh pr list --state open` empty, 2026-11-21); no linked PR on the issue; no `project/features/` or `project/roadmap.md` in this repository; `project/requirements/` holds only `release-archive-provenance.md`
- **Working copy**: `/home/nolte/repos/.worktrees/gh-plumbing/507-masking-guard-gaps`; branch `fix/507-masking-guard-gaps` off `origin/develop` @ `8499e75`; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: exit 1 (not ignored)
- **Author / trust**: issue written by `nolte` (repository owner, the operator); no comments
- **Requirements gate**: operator override, 2026-11-21 (`requirements-elicit` skipped; the issue carries its own acceptance list and two reproduced fixtures)

## Classification

- **Primary class**: bug
- **Secondary class(es)**: security
- **Rationale**: the guard passes two forms it's meant to refuse; no run body with either form is known today, so it's a defect of the guard, with a security-relevant class behind it.
- **Asserted cause verified**: confirmed on `origin/develop` @ `8499e75`, 2026-11-21. Both fixtures from the issue, each as the only step of `reusable-x.yaml` under a scratch root, give `python3 scripts/workflow_command_masking.py --root <fixture>` exit 0 ("… prints only masked or constrained values.").
  - Gap 1: `scripts/workflow_command_masking.py:1254-1259` (`clean_shell`) accepts a name when `before[-1]`, the last assignment by unit index before the print, matches `MASKED_ASSIGNMENT`. Nothing asks whether that assignment runs.
  - Gap 2: `scripts/workflow_command_masking.py:958-969` (`sink_units`) takes a Python or Node stdout print as a sink only when `unit.dest == "log"`; with `dest == "envfile"` the print is never read.

## Scope

- **In scope**
  - Gap 1, rule decided by the operator (2026-11-21): **block dominance**. A masked assignment covers a print only when the block that holds the assignment also encloses the print, and no raw assignment to the name stands between the two. The fixture (mask inside `if false`) becomes a finding; the straight-line form in `actions/setup-vale/setup-vale.sh:51-54` stays accepted, the script isn't changed.
  - Gap 2: the stdout prints of a Python or Node heredoc whose destination is an env file are read like its log prints.
  - A test per fixture and per rule edge; the "Not covered" entries at `scripts/workflow_command_masking.py:154-159` and `:178-179` removed or reworded to what remains.
  - A sweep with its own predicate over the reusable workflows and `actions/`, count recorded.
- **Out of scope**
  - A full control-flow reading (paths through `if`/`else`/`case`, loops); the operator chose the block rule instead.
  - A heredoc that opens the env file itself (`open(os.environ["GITHUB_OUTPUT"], "a")`, `fs.appendFileSync`): not this issue; if the guard doesn't read it, it's named under "Not covered" and reported as a finding of this run.
  - Every other "Not covered" entry.

## Route

- **Decision**: direct
- **Rationale**: one outcome (the guard refuses both forms), one PR strand, no roadmap item.

## Work packages

### P1 — Log rule: a masked reassignment counts only where it dominates the print

- **Problem statement**: `clean_shell` reads the last assignment by line. A masked assignment in a branch, loop body, function or subshell that doesn't enclose the print covers a raw assignment made before it.
- **Acceptance criteria**
  - The issue's fixture 1 is a finding (guard exit 1), with a test.
  - Accepted, with a test each: raw then masked at the same block level as the print; raw then masked in an outer block with the print in an inner block; `setup-vale.sh`'s `finish()` as shipped.
  - Refused, with a test each: mask inside `if`/`elif`/`else`, a `for`/`while` body, a `case` arm, a `( … )` or `{ …; }` group that doesn't enclose the print, and a function body when the print is outside that function; a raw assignment after the dominating mask and before the print; mask on a `cond && x=$(shown "$x")` or `|| ` line.
  - `python3 scripts/workflow_command_masking.py` exits 0 on the tree; the full suite passes; no existing test is weakened.
- **Touched files / artifacts**: `scripts/workflow_command_masking.py`, `scripts/tests/test_workflow_command_masking.py`
- **Specialist**: `nolte-engineering:fullstack-developer` (production Python plus matching tests; no catalog entry names guard or linter authoring)
- **Depends on**: none

### P2 — Env-file rule: read the stdout of a Python or Node heredoc redirected to an env file

- **Problem statement**: `sink_units` skips a heredoc's stdout prints unless they go to the log, so `node <<'X' >> "$GITHUB_OUTPUT"` writes an entry from a raw value unseen.
- **Acceptance criteria**
  - The issue's fixture 2 is a finding, and its Python twin (`python3 - <<'PY' >> "$GITHUB_OUTPUT"`), with a test each; `>`, `>>` and `>|`, and `$GITHUB_ENV`, `$GITHUB_PATH`, `$GITHUB_STATE` behave the same.
  - What makes such a print clean is decided against the existing env-file rule for shell (`:20-40` of the docstring) and stated in the docstring: a `shown(...)` call with the canonical definition in that heredoc removes line ends and is the expected mask; a test shows the masked form passing.
  - A heredoc inside a group redirected to an env file is read the same way, or named under "Not covered" with a test pinning the present behaviour.
  - A heredoc to an ordinary file (`reusable-release-publish.yml:367`, `> vbf.json`) stays no finding.
  - Guard exit 0 on the tree; full suite passes.
- **Touched files / artifacts**: `scripts/workflow_command_masking.py`, `scripts/tests/test_workflow_command_masking.py`
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: P1 (same two files; one specialist, in sequence)

### P3 — Sweep and docstring

- **Problem statement**: the old guard couldn't see either form, so whether a run body has one today is unmeasured.
- **Acceptance criteria**
  - A predicate that doesn't rest on the new rules alone is run over `.github/workflows/reusable-*` and `actions/` and its count recorded: (a) names with both a masked and an unmasked assignment in one run body or action script, each read by hand against the block rule; (b) Python or Node heredocs whose stdout goes to an env file.
  - Every hit is repaired or shown clean; the "Not covered" list says what remains (at least: a mask in a function called before the print, loops that run zero times, `eval`).
- **Touched files / artifacts**: `scripts/workflow_command_masking.py` (docstring); a workflow or action file only if the sweep finds a hit
- **Specialist**: `nolte-engineering:fullstack-developer`; the count is re-run by the orchestrator
- **Depends on**: P1, P2

## Existing installations / upgrade / rollback

- P1, P2, P3: not applicable — touches no persisted state, consumer configuration key, invocation name or artifact path. The guard runs in this repository's `required-check-triggers-tests` job only; consumers don't call it. If P3 has to change a reusable workflow or an action script, that file is consumed by ref and the change is listed here before dispatch continues.

## Dependency ordering

P1 → P2 → P3, one specialist dispatch per package or one dispatch carrying all three in order (same files, no parallel lane).

## Risks

- **A stricter log rule refuses a body that's fine today.** Mitigation: guard exit 0 on the tree is an acceptance criterion; consumers aren't affected because the guard reads only this repository.
- **The block reading rests on the guard's line-and-indent model** (`block_end`, `redirected_groups`), which isn't a shell parser: a block opened and closed on one line, or indentation that lies, can be misread. Mitigation: err towards a finding where the block can't be attributed, and name the rest under "Not covered".
- **Block dominance isn't path analysis**: a mask in a loop that runs zero times, or in a function defined but called after the print, still passes or is refused by structure only. Mitigation: named in the docstring; the operator declined full control flow.
- **Security-sensitive path**: `scripts/` holds the guard for a workflow-command injection class, and `actions/**/*.sh` is read by it. A read-only agent that didn't write the change reviews `git diff origin/develop...HEAD` with the security brief before the PR opens; it gets shell access to run fixtures (the `code-security-reviewer` agent has none).

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| B1 print or raw assignment in a function whose body isn't opened as `f() {` + newline passes | diff review @ 80e2194a7191fa055eba22619653cae5f80d80dc | fixed directly (6c46d8e) | fixtures A1, A2, A3: guard exit 0 at 80e2194, exit 1 at c5f19dd (re-run by orchestrator) | — |
| B2 loop opened after another statement on its line: raw value after the print passes | diff review @ 80e2194 | fixed directly (6c46d8e) | fixture B: 0 → 1 | — |
| B3 mask after a trailing `&&`, `\|\|` or `\|` on the line before counts as unconditional | diff review @ 80e2194 | fixed directly (6c46d8e) | fixture C: 0 → 1 | — |
| B4 raw assignments unseen (case arm, `a=1 x=`, `typeset`, `read` names, `select`, `for x;` …); exists on develop | diff review @ 80e2194 | fixed directly (6c46d8e, c5f19dd) | fixtures D1, D2: 0 → 1 | — |
| B5 regression: `(( N==1 ))`, `( N=lit )` make a name constant | diff review @ 80e2194 | fixed directly (6c46d8e) | fixtures R1, R2: develop 1, 80e2194 0, c5f19dd 1 | — |
| B6 env-file heredoc prints read laxly (concatenation, second print, continuation, `end=`) | diff review @ 80e2194 | fixed directly (6c46d8e): strict reader shared with the summary rule | fixtures E1–E4: 0 → 1 | — |
| N1 `"a"#` read as a comment; N2 `tee --append` / `dd of=`; N3 heredoc delimiters and interpreters | diff review @ 80e2194 | fixed directly (6c46d8e); rest named under "Not covered" | developer tests; not re-run one by one by the orchestrator | — |
| Log-line Python/Node prints: only the first call on a line, no continuation lines, no `end=`/`sep=`; exists on develop | diff review @ 80e2194 (B6, log side) | named under "Not covered"; follow-up issue pending operator decision | reviewer observed on develop and head | pending |

## Dispatch log

2026-11-21 P1 dispatched to nolte-engineering:fullstack-developer — committed 92a7d94; block reader `blocks_of` built new (orchestrator's assumption that the existing block model suffices: refuted)
2026-11-21 P2 dispatched to nolte-engineering:fullstack-developer — committed 4363789
2026-11-21 P3 dispatched to nolte-engineering:fullstack-developer — committed 80e2194; sweep: (a) 1 name with a masked and an unmasked assignment (`message`, actions/setup-vale/setup-vale.sh:51,54, accepted by the block rule), (b) 0 of 5 Python/Node heredocs write an env file; re-run by orchestrator
2026-11-21 diff review @ 80e2194 by an independent read-only agent, security brief — 5 blocking, 1 blocking by documentation, 5 non-blocking; all 13 fixtures re-run by orchestrator
2026-11-21 review findings dispatched to nolte-engineering:fullstack-developer — committed 6c46d8e, c5f19dd; orchestrator re-run at c5f19dd: 15 fixtures exit 1, tree exit 0, 717 passed
