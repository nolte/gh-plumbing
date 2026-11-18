---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "481"
classification: "bug"
secondary-classes: []
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #481 — commons-settings: master entry's restrictions.apps fails with 422 on every user-owned consumer
- **URL**: https://github.com/nolte/gh-plumbing/issues/481
- **Labels**: bug, project-config
- **Linked items**: #442 / PR #482 (merged; removed the commons `develop` entry, ADR-005), #387 (closed with ADR-005). No open PR references #481.
- **Prior art checked**: hand-off record from `issue-backlog-partition` run 2026-11-18-gh-plumbing, re-checked against the live issue (open, author `nolte`, 0 comments). ADR-005 states at `docs/en/decisions/adr-005-consumer-owned-develop-protection.md:46` and `:102` that `master` is out of scope and left for a follow-up — this issue is that follow-up.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/481-commons-master-entry`, branch `fix/481-commons-master-entry` off `origin/develop` @ 078116b; detect=200; fallback `git worktree add -b`; ignore check: ignored=1
- **Lane**: `lane: true` — returns `committed-locally`.
- **Gates**: fix variant decided by the operator on 2026-11-18: "master eintrag entfernen". Scope, requirements override, route and decomposition approved under the standing authorisation of the same day, recorded in `.resume/issue-backlog-partition/2026-11-18-gh-plumbing.yml`.

## Classification

- **Primary class**: bug
- **Rationale**: a shared configuration entry produces a payload GitHub rejects, so it applies nothing while the docs say it protects `master`.
- **Asserted cause verified**: the configuration is confirmed: `.github/commons-settings.yml:170` `- name: master`, `restrictions.apps: [nolte-portfolio-app]` at `:190-194`, and the file's own comment at `:183-189` describes the 422 on personal-account consumers. **Unestablished in this run**: the 422 itself — no PUT was sent; it rests on GitHub's documented limit (push restrictions only on organisation-owned repositories) and on #416/#442, where the same field aborted the `develop` update. The fix doesn't depend on re-observing it: removing the entry is correct under either reading.
- **Measured for this repository**: `gh api repos/nolte/gh-plumbing/branches/master/protection` → `enforce_admins: true`, `required_status_checks: null`, `required_pull_request_reviews: null`, `restrictions: null`, `allow_force_pushes: false`, `allow_deletions: false`, `required_linear_history: false`. `.github/settings.yml` declares only `develop` (`:106`), so today this live state is declared nowhere that applies.

## Scope

- **In scope**:
  - Remove the `master` entry from `.github/commons-settings.yml`; the commons then declare no branch entry at all. The comment block explains why, pointing at the ADR.
  - `.github/settings.yml` of this repository declares its own complete `master` entry that reproduces the measured live state exactly (`required_pull_request_reviews: null`, `required_status_checks: null`, `enforce_admins: true`, `restrictions: null`), so the merge changes nothing on this repository's `master` and the state is declared.
  - The decision record: ADR-005 is revised (the precedent is ADR-001's "Revised" header with a "what this revision changes" box) to cover `master`, or a new ADR is added if the specialist finds the revision would distort ADR-005 — say which and why. Index updated.
  - Docs in both languages: `docs/{en,de}/portfolio-app/setup.md` (the "push-restricted after phase 2" claim near `:196-197`, the `restrictions.apps` snippet near `:259-279`, the warning near `:282-289`), `docs/{en,de}/probot/settings.md:11` ("Branch protection for `master`" in the list of what the commons provide), and any other sentence the corpus grep finds claiming the commons protect `master`.
  - Check, and state the result of, the effect on `reusable-release-cd-refresh-master.yml` and ADR-001 (the issue asks for it): the workflow reads the target's protection and picks its strategy; removing an entry that never applied changes no live protection.
- **Out of scope**: changing any consumer repository; changing live protection anywhere; the `restrictions: null` variant (rejected by the operator).

## Route

- **Decision**: direct — one outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Remove the commons `master` entry and declare this repository's own

- **Acceptance criteria**:
  1. `.github/commons-settings.yml` has no `branches:` entry for `master`; what remains under `branches:` is valid for the Settings App (an empty list, or the key removed — check what the App and this repository's own tooling expect, including `scripts/branch_protection_audit.py` and its tests, and say which).
  2. `.github/settings.yml` declares `master` with exactly the four measured values; the comment says the values mirror the live state and why the commons no longer carry it.
  3. The existing self-test `test_this_repository_branch_entries_apply_and_do_not_race` (in `scripts/tests/test_branch_protection_audit.py`) passes, and it — or a small addition — would fail if a commons branch entry carrying `restrictions` came back (the class guard). Show the guard failing against `origin/develop`'s commons file.
  4. `pytest` for `scripts/tests/` passes the way CI runs it; `pre-commit run --all-files` passes (it includes label-description and category checks on these files).
- **Touched files**: `.github/commons-settings.yml`, `.github/settings.yml`, `scripts/tests/test_branch_protection_audit.py` (and `scripts/branch_protection_audit.py` only if the guard needs it)
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: none

### P2 — Decision record and documentation

- **Acceptance criteria**:
  1. The ADR states the decision for `master` (consumers own it, as for `develop`), the alternative rejected (`restrictions: null` in the commons: it would start enforcing `enforce_admins` on every consumer's `master`, a behaviour change nobody asked for), and what a consumer has to do to protect `master`.
  2. No sentence in `docs/`, `README.md` or the commons comments still says the commons protect or push-restrict `master`; the corpus grep and its (empty) result for the false wording are shown, EN and DE.
  3. The setup docs say what is actually enforced on `master` and where it is declared.
  4. `mkdocs build --strict` passes if it can be run here; `python scripts/docs_freshness.py` as CI runs it reports nothing new; Vale on added English lines: no errors, new alerts well under ten (`vale --minAlertLevel=suggestion`).
- **Touched files**: `docs/{en,de}/decisions/…`, `docs/{en,de}/portfolio-app/setup.md`, `docs/{en,de}/probot/settings.md`
- **Specialist**: `nolte-engineering:fullstack-developer` (the docs change is the consequence of a config change and has to stay consistent with it; `audience-doc-author` needs an audience artefact this small correction doesn't justify)
- **Depends on**: P1

## Existing installations / upgrade / rollback

Health gate: none (Probot configuration consumed through `_extends`).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P1 | user-owned consumers: no change — the entry never applied. An organisation-owned consumer (none known today) would stop getting `master` protection from the commons; protection already applied stays, since the Settings App doesn't delete protection for an undeclared branch (state how you know, or mark it unestablished). This repository: `master` now declared locally with the values it already has | none; surface read: consumers' `_extends` merge of `branches:` | a revert restores the failing entry | the self-test in AC 3; after the merge, the operator's `gh api …/branches/master/protection` must equal the measured values above |
| P2 | not applicable — touches no persisted state, consumer configuration key, invocation name or artifact path | | | |

## Dependency ordering

P1 → P2.

## Risks

- A local `master` entry that differs from the live state would change this repository's `master` protection on merge. Mitigation: AC P1.2 pins the four values to the measurement; the orchestrator re-reads the API after the merge.
- The Settings App applies `.github/settings.yml` on a push that touches it; a failed App run is silent. Mitigation: verify through the API after the merge, not through the absence of an error.
- Security-sensitive paths (`.github/settings.yml`, branch protection): security-briefed read-only diff review before the lane returns.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| This analysis and ADR-006 said the commons `master` entry never applied and that `restrictions: null` would enforce it for the first time. False: the entry carried `restrictions: null` from 2020 until #355 (2026-05-20) and applied in that form | diff review @ 24d9991 (N1) | fixed directly (docs and comments corrected); the operator was told and confirmed the removal on 2026-11-18 | `git show 2279d2b^:.github/commons-settings.yml`; live protection of gh-plumbing and esphome-configs `master` | — |
| A consumer `develop` entry that omits a required field inherited it from the commons `master` entry; without it that consumer's `develop` protection update is rejected (`kamerplanter`) | diff review @ 24d9991 (N2) | recorded in ADR-006 Consequences; issue to file in nolte/kamerplanter (operator-approved) | inferred from repository-settings/app `lib/plugins/branches.js`; not observed | to file |
| The 422 on `master` stated as observed | diff review @ 24d9991 (N3) | fixed directly (qualified in ADR-006, comments, setup pages) | not observed in this run | — |
| Terraform text and the user-mode setup note still say push restrictions work on a user account | specialist result / diff review (N4) | not fixed here: outside #481; to file | inferred from GitHub's documented limit | to file |
| ADR-002 tense, setup heading "Branch-protection bypass (phase 2)" | diff review (N5) | dismissed: historical context, reconciled by the added closing line | — | — |
| The class guard doesn't catch a commons entry with `restrictions: null` or a branch this repository doesn't declare | diff review @ 24d9991 | dismissed for this PR: the guard covers the defect class of #481 (a push-restricted commons entry); named in Risk / rollout notes | inferred | — |
| no blocking findings | diff review @ 25333d53708571f828fe3f8e005e8803ca8820d6 (lane b, security-briefed; 19 files as in `--stat`; content identical to the fully reviewed 2e50cf0 by `git range-diff`) | — | — | — |

## Dispatch log

- 2026-11-18 P1, P2 dispatched to `nolte-engineering:fullstack-developer` — four commits; pytest 107 in the required job, guard fails on origin/develop's commons file, pre-commit green, mkdocs --strict in a scratch venv, docs_freshness clean.
- 2026-11-18 orchestrator: history and wording corrections after review (two commits); pytest 142, pre-commit green, Vale: no alert on ADR-006.

