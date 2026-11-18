---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "484"
classification: "bug"
secondary-classes: []
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #484 — reusable-release-publish: Resolve draft emits a branch name instead of a commit SHA for bare-branch targets
- **URL**: https://github.com/nolte/gh-plumbing/issues/484
- **Labels**: bug
- **Linked items**: #456 / PR #485 (merged, introduced `resolve_commit`); no open PR references #484 (`gh pr list --state open --search 484` → `[]`)
- **Prior art checked**: hand-off record from `issue-backlog-partition` run 2026-11-18-gh-plumbing, re-checked against the live issue (open, author `nolte`, 0 comments, 0 closing PRs). No roadmap item or feature covers it.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/484-resolve-draft-sha`, branch `fix/484-resolve-draft-sha` off `origin/develop` @ 1c33b7b; detect=200; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: ignored=1
- **Lane**: `lane: true` — the run returns `committed-locally`; nothing is pushed.
- **Requirements gate**: operator override, 2026-11-18 — the issue text states the defect and the fix unambiguously; no `project/requirements/` artefact is written.

## Classification

- **Primary class**: bug
- **Secondary class(es)**: none
- **Rationale**: an existing step emits a wrong output value (a branch name where a commit SHA is promised).
- **Asserted cause verified**: confirmed: `.github/workflows/reusable-release-publish.yml:219-223` resolves only `refs/heads/*` via `origin/…` and otherwise sets `sha="$target"`; `:230` writes it to `target_sha` unvalidated. The checkout at `:160-163` uses `ref: develop`, which is why `git merge-base --is-ancestor develop origin/develop` at `:225` passes for exactly that branch name. Consumers of `steps.draft.outputs.target_sha`: `:245`, `:560`, `:632` (summary `:653`), `:684` (`git show` `:703`, `git archive` `:725`), `:991`.

## Scope

- **In scope**: "Resolve draft" resolves every draft target to a commit read from origin and emits only a 40-character lowercase SHA; it refuses a target that resolves to no commit. Follow-up in the same file: the "Check the draft target against the expected commit" step compares the already-resolved SHA, and its comment at `:259-263`, which describes the old pass-through, is corrected.
- **Out of scope**: the flip step's own re-resolution (`:894-909`) stays; it reads the live `targetCommitish` again on purpose (#456). No new input, no interface change. #488 (same file, Vale install step) is a separate lane after this one.

## Route

- **Decision**: direct
- **Rationale**: one coherent outcome, one PR strand, no roadmap item. Confirmed by the operator 2026-11-18.

## Work packages

### P1 — Resolve draft emits a commit SHA for every target form

- **Problem statement**: a bare branch name (`develop`, any other branch) passes through as `target_sha`; later steps then read a local branch or fail.
- **Acceptance criteria**:
  1. For targets `refs/heads/develop`, `develop`, a full SHA (upper or lower case), the step writes `target_sha=<40 lowercase hex>` equal to the commit on origin.
  2. A bare branch that exists on origin but not locally resolves from origin; a local branch of the same name that differs from origin is not read.
  3. A target that resolves to no commit fails the step with an `::error::` naming tag and target, and writes no `target_sha`.
  4. A resolved commit not reachable from `origin/develop` still fails with the existing message.
  5. The step never emits a value that isn't `^[0-9a-f]{40}$` (class guard, checked right before the output is written).
  6. With `expected-target-sha` set, match and mismatch behave as before for all three target forms.
  7. `actionlint` passes on the file; the extracted step scripts run against a stub `gh` and a real bare origin/clone, as for #456.
- **Touched files / artifacts**: `.github/workflows/reusable-release-publish.yml`; `docs/{en,de}/workflows/release.md` only if a sentence there describes the old behaviour (grep found none in `en`).
- **Specialist**: `nolte-engineering:fullstack-developer` (bug fix with runnable code and matching tests; no agent names workflow-YAML authoring)
- **Depends on**: none

## Existing installations / upgrade / rollback

Health gate: none (reusable workflow consumed by ref).

- P1: touches no persisted state, consumer configuration key, invocation name or artifact path. Inputs, outputs and secrets of the reusable are unchanged. The only behavioural change for a consumer: a hand-edited draft with a bare branch target that used to publish from a local `develop` branch now publishes from the origin commit, and any other bare branch name now resolves instead of failing. Rollback is a revert of the commit.

## Dependency ordering

P1 (single package).

## Risks

- The step sits on the release path of every consumer. Mitigation: release-drafter's `refs/heads/develop` form is a tested case and must keep its result; the reachability check stays.
- No live run can exercise this before a release. Mitigation: the stub-`gh` harness covers the scripts; the limit is stated in the PR's Testing section.
- Security surface: none added — values still reach the script through `env:`, no permission or action change. The diff review is briefed to confirm that.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| Comment claimed a local ref is "never" read; the fallback reads local refs when origin has no such name | diff review @ ffb061d | fixed directly (ddef5b0: comment states the order and the reachability backstop) | targets `HEAD`, `heads/develop`, `refs/heads/localbr` resolved locally, then rejected as not reachable | — |
| An origin branch wins over a tag of the same name | diff review @ ffb061d | fixed directly as documentation (ddef5b0); behaviour fails safe, unchanged | origin branch `v0.1` beat tag `v0.1` | — |
| Editable draft target printed raw in `::error::` lines | diff review @ ffb061d | fixed directly (ddef5b0: control characters masked, Resolve draft and flip step) | target `nope\n::warning::injected` prints as one line `nope?::warning::injected`, rc=1, no `target_sha` | — |
| A 40-hex SHA naming no commit passed resolution and was caught only by the reachability check | specialist result (P1) | fixed directly (ffb061d: `git cat-file -e`) | harness case "valid hex without commit": rc=1, no `target_sha` | — |
| Other pre-existing `::error::` lines print caller- or draft-controlled text raw (`inputs.tag` at `:203`, `expected-target-sha` at `:282`, draft tag names) | diff review @ ddef5b0 | not fixed here: outside #484, inferred not reproduced; named in Risk / rollout notes as a follow-up to file | none run against a runner | to file |
| no blocking findings | diff review @ ddef5b09dda61ffe3316e961146af680b88ecd88 (lane b, security-briefed; files: `.audits/issue-orchestrate/484/analysis.md`, `.github/workflows/reusable-release-publish.yml`) | — | — | — |

## Dispatch log

- 2026-11-18 P1 dispatched to `nolte-engineering:fullstack-developer` — ffb061d; harness 29/29, actionlint 1.7.12 (CI flag) rc=0, pre-commit green; no refutation of the analysis.
- 2026-11-18 review fixes by the orchestrator (comment wording, masked print) — ddef5b0; harness re-run 29/29 on the re-extracted scripts, actionlint rc=0, pre-commit green.

## Class sweep

- Predicate: `echo "<name>sha=…" >> "$GITHUB_OUTPUT"` in `.github/workflows/*.y{a}ml` whose value isn't derived from `git rev-parse`, the commits API, or checked against `^[0-9a-f]{40}$`
- Hits: 1 (of 4 writers: `reusable-release-publish.yml` Resolve draft; the align step's two writers use `git rev-parse HEAD`, `reusable-release-archive.yml:136` uses the commits API)
- Repaired: 1
- Guard: the `^[0-9a-f]{40}$` check right before Resolve draft writes `target_sha`

