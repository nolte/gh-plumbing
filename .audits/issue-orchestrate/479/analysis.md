---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "479"
classification: "bug"
secondary-classes: []
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #479 — Retitled pull requests keep a stale type label and render under two release-note categories
- **URL**: https://github.com/nolte/gh-plumbing/issues/479
- **Labels**: bug
- **Linked items**: #475 / PR #478 (merged; added `reusable-release-drafter-autolabel.yml`). No open PR references #479.
- **Prior art checked**: hand-off record from `issue-backlog-partition` run 2026-11-18-gh-plumbing, re-checked against the live issue (open, author `nolte`, 0 comments).
- **Working copy**: `~/repos/.worktrees/gh-plumbing/479-stale-type-label`, branch `fix/479-stale-type-label` off `origin/develop` @ 078116b; detect=200; created via fallback `git worktree add -b`; ignore check: ignored=1
- **Lane**: `lane: true` — returns `committed-locally`.
- **Gates**: scope, requirements override (issue states defect, options and acceptance), route, decomposition and the option choice below approved under the operator's standing authorisation of 2026-11-18 ("arbeite möglichst autonom"), recorded in `.resume/issue-backlog-partition/2026-11-18-gh-plumbing.yml`.

## Classification

- **Primary class**: bug
- **Rationale**: a pull request ends with two type labels and renders under two changelog categories.
- **Asserted cause verified**: confirmed on the repository side: `.github/workflows/release-drafter-autolabel.yml:11-13` triggers on `pull_request_target` types `[opened, reopened, edited]`; `.github/workflows/reusable-release-drafter-autolabel.yml:51-58` has one step, `release-drafter/release-drafter@6a93d82… # v6.4.0` with `disable-releaser: true`, and nothing removes a label; the file's own comment at `:37-38` says "Labels are only ever added". **Unestablished**: that release-drafter v6.4.0's autolabeler never removes a label — not read in its source here; the specialist confirms it against the pinned version's source before relying on it.

## Scope

- **In scope** (option 2 of the issue): after release-drafter ran, the autolabel reusable removes a type label the title no longer implies. Rule: when the current title implies a type label T, every other type label is removed; when the title implies none, nothing is removed, so a hand-applied label on a `refactor:` or `ci:` title survives. Type labels are the ones the commons autolabeler derives from a title: `feat`, `fix`, `chore`, `docs` (`.github/commons-release-drafter.yml:71-111`). Docs for the workflow in both languages.
- **Out of scope**: option 1 (a pr-lint rule) — it would only report the state, and the acceptance asks for the pull request to end up right. Area labels, `release` and `experimental` are never removed.

## Route

- **Decision**: direct — one outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Remove type labels the title no longer implies

- **Problem statement**: `feat: …` retitled to `fix: …` keeps `feat`; release notes list the pull request twice.
- **Acceptance criteria**:
  1. Retitle `feat: x` → `fix: x`: the pull request ends with `fix` and without `feat`; other labels (`cicd`, `automerge`, `documentation`, `release`, `experimental`) are untouched.
  2. A title implying no type label (`refactor: x`, `ci: x`, free text) removes nothing.
  3. Scoped and breaking forms (`fix(ci): x`, `feat(api)!: x`) are recognised exactly as the autolabeler regexes at `commons-release-drafter.yml:71-111` recognise them; `chore(release): x` keeps `chore` and `release`.
  4. A pull request with only the right label triggers no label write.
  5. No pull request code runs: no checkout; the title reaches the script through `env:`, never through `${{ }}` in a `run:` body; a title with quotes, backticks, `$(…)`, newlines is handled as data.
  6. The job's `permissions:` gain only what a label removal needs, and the caller `release-drafter-autolabel.yml` grants exactly the same set (a scope the caller doesn't grant is a `startup_failure`, #422). State which scope the REST call needs and how you know.
  7. The removal runs after release-drafter added the new label, and a failed removal fails the job visibly.
  8. Comments that say labels are only ever added (`reusable-release-drafter-autolabel.yml:37-38`, `:48`) are corrected; `docs/{en,de}/workflows/release.md` describe the behaviour.
  9. `actionlint` (CI flags) passes; the extracted script passes a stub-`gh` test matrix covering 1–5.
- **Touched files / artifacts**: `.github/workflows/reusable-release-drafter-autolabel.yml`, `.github/workflows/release-drafter-autolabel.yml` (only if scopes change), `docs/{en,de}/workflows/release.md`
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: none

## Existing installations / upgrade / rollback

Health gate: none (reusable workflow consumed by ref).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P1 | consumers calling the reusable get label removal on the next `opened`/`reopened`/`edited` event; a consumer whose caller grants fewer scopes than the reusable then declares would hit `startup_failure` | none; surfaces read: the caller's `permissions:` block (invocation contract) | a revert stops removals; labels already removed stay removed | AC 6: scopes unchanged, or the change is named as a consumer action in the PR's Risk notes |

## Dependency ordering

P1 (single package).

## Risks

- `pull_request_target` with a write token: any untrusted input reaching a shell is a privilege escalation. Mitigation: AC 5, and a security-briefed read-only diff review before the lane returns.
- A new job scope breaks every existing caller silently (`startup_failure`, no logs). Mitigation: AC 6 — prefer a call the existing `pull-requests: write` already covers.
- The type-label list is a second copy of what the commons autolabeler declares. Mitigation: the comment names the source; if a cheap way exists to keep one copy, the specialist says so.
- The live path can only be exercised by a real pull request against a branch that carries the change; `pull_request_target` runs the base branch's workflow, so the lane's own PR doesn't test it. Stated in the PR.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|

## Dispatch log
