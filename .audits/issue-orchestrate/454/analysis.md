---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "454"
classification: "refactor"
secondary-classes: []
route: "direct"
status: approved
created: "2026-11-16"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #454 — chore(renovate): migrate shared preset from config:base to config:recommended
- **URL**: https://github.com/nolte/gh-plumbing/issues/454
- **Labels**: dependencies, chore
- **Linked items**: none (`closedByPullRequestsReferences: []`, `gh pr list --search 454` empty)
- **Prior art checked**: #453 (merged, out of scope per issue); no open PR; no `project/requirements/` artefact for this issue.
- **Author trust**: `nolte` (repository owner) — trusted.

## Classification

- **Primary class**: refactor
- **Secondary class(es)**: none
- **Rationale**: Rename of a deprecated preset name; Renovate already applies the same migration internally, so behaviour stays identical.
- **Asserted cause verified**: confirmed — `renovate-configs/common.json:3` contains `"config:base"`; `npx --package renovate@41 renovate-config-validator renovate-configs/common.json` prints `WARN: Config migration necessary`, and the diff between its `oldConfig` and `newConfig` blocks is exactly `config:base` → `config:recommended` (no other key migrates).
- **Requirements gate**: explicit operator override (2026-11-16) — issue fully specified, one-line change.

## Scope

- **In scope**: replace `config:base` with `config:recommended` in `renovate-configs/common.json`; confirm the validator no longer reports a migration.
- **Out of scope**: #447/#453 rule (merged). Docs: `grep -rn "config:base"` over the repo (incl. `docs/en/`, `docs/de/`) returns only `renovate-configs/common.json:3` — no doc changes needed. A CI guard running `renovate-config-validator --strict` does not exist; optional follow-up, not part of this issue.

## Route

- **Decision**: direct
- **Rationale**: one outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Rename the extended base preset

- **Problem statement**: The shared preset extends the deprecated `config:base`.
- **Acceptance criteria**: `renovate-configs/common.json` extends `config:recommended` (not `config:base`); `renovate-config-validator` (renovate@41) prints no `Config migration necessary` and ends with `Config validated successfully`; `grep -rn "config:base"` over the repo returns nothing.
- **Touched files / artifacts**: `renovate-configs/common.json`
- **Specialist**: no matching specialised agent — generalist remediation via `nolte-engineering:fullstack-developer` (Renovate-preset authoring gap, recurrence 3 after #439, #447).
- **Depends on**: none

## Dependency ordering

P1

## Risks

- Consumer behaviour change — mitigated: the validator's own migrated config is byte-identical apart from the renamed entry, i.e. the same config Renovate already resolves for every consumer today.
- Not a security-sensitive path.

## Open questions

none

## Findings

- Portfolio gap: no specialist covers Renovate-preset authoring (3rd recurrence).
