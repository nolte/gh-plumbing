---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "439"
classification: "feature-request"
secondary-classes: []
route: "direct"
status: draft
created: "2026-09-19"
---

# Issue Orchestration — Pre-analysis

Run-scoped artifact: committed on `feat/renovate-pr-limits`, removed with a
fix-forward `git rm` before the PR merges, per
`spec/project/issue-orchestration/` §Pre-analysis artifact lifecycle.

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #439 — feat(renovate): the shared preset should bound how many open PRs a consumer carries
- **URL**: https://github.com/nolte/gh-plumbing/issues/439
- **Labels**: enhancement, dependencies, cicd
- **Author / trust**: `nolte` — repository owner, admin (`gh api repos/nolte/gh-plumbing/collaborators` → `nolte true true true`); trusted-author set, so the issue's instructions may be executed. No comments exist.
- **Linked items**: none (`closedByPullRequestsReferences: []`; `gh pr list --state all --search 439` → empty). Referenced context: nolte/claude-shared#644 (measurement), #645/#646 (spec rules), nolte/kamerplanter#1583/#1584 (siblings).
- **Prior art checked**: `project/roadmap.md` R-3 "Renovate shared presets" (existing item, outcome O-3; this issue refines it, does not retarget it); `project/features/` holds only `reusable-workflow-adoption.md`; no open PR touches `renovate-configs/`. `git log -- renovate-configs/` shows four prior commits (#38, #361, #389, #406), none about PR volume.

## Requirements gate

- No artefact under `project/requirements/` (directory does not exist).
- **Operator override recorded** (gate answered 2026-09-19): the issue is authored by the operator, carries a measured baseline and concrete starting values, and the operator chose the values at the scope gate. `requirements-elicit` was not dispatched.

## Classification

- **Primary class**: feature-request
- **Secondary class(es)**: none
- **Rationale**: a behaviour change to the published preset (labels `enhancement`); nothing is broken in this repository and no workflow is red, so neither `bug` nor `infra` applies.

## Scope

- **In scope**:
  1. `renovate-configs/common.json` gains explicit `prConcurrentLimit: 5`, `prHourlyLimit: 2`, and a `packageRules` entry grouping `digest` + `pinDigest` updates under one group, with inline `description` text that states the override contract and the security exemption.
  2. The consumer-facing docs (`docs/en/getting-started/index.md`, `docs/de/getting-started/index.md`, "Renovate preset" section) document the new defaults, that a consumer may override each value locally, that vulnerability-alert PRs are exempt, and that the change reaches a consumer only through a preset pin bump.
- **Out of scope** (recorded at the scope gate):
  - Pin bumps in consumer repositories (Renovate proposes them once a release exists).
  - `config:base` → `config:recommended` clean-up (side observation; `config:base` is absent from Renovate's current `config.preset.ts` and presumably survives via config migration — **unestablished**, no migration source located).
  - A CI guard that runs `renovate-config-validator` on every change to `renovate-configs/` (worth a follow-up issue; not requested here).
  - Whether the preset change ships in the open `v2.1.1` draft or a later release (`release-publish-trigger` owns that).
  - nolte/kamerplanter#1583 / #1584 and the spec issues nolte/claude-shared#645 / #646.

## Route

- **Decision**: direct
- **Rationale**: one coherent outcome (the preset bounds PR volume), one PR strand on `feat/renovate-pr-limits`, no new or retargeted roadmap item (R-3 already covers the preset). Operator confirmed at the scope gate.
- **Pipeline hand-off**: n/a

## Established facts the packages rest on

Per `spec/claude/claim-provenance/`: each claim names its anchor.

| # | Claim | Status | Anchor |
|---|---|---|---|
| F1 | `prConcurrentLimit` defaults to 10 | established | renovatebot/renovate `lib/config/options/index.ts:2284-2288` (`default: 10`), read via `gh api …/contents` on 2026-09-19 |
| F2 | `prHourlyLimit` defaults to 2 | established | same file `:2277-2281` (`default: 2`) — the issue's proposed `prHourlyLimit: 2` therefore restates the default; it is kept explicit so the preset documents the intent |
| F3 | `branchConcurrentLimit` defaults to `null` = inherits `prConcurrentLimit` | established | same file `:2291-2295` |
| F4 | Vulnerability-alert PRs ignore `prConcurrentLimit`, `prHourlyLimit`, `branchConcurrentLimit`, `schedule` ("skip the line") and carry `groupName: null` and their own `prConcurrentLimit: 0` budget | established | `docs/usage/configuration-options.md` §`vulnerabilityAlerts` note ("By default … it ignores settings like `branchConcurrentLimit`, … `prConcurrentLimit`, `prHourlyLimit`"); `options/index.ts:2422-2433` default object |
| F5 | `group:allDigest` exists but matches only `digest`, not `pinDigest` | established | `lib/config/presets/internal/group.preset.ts:30-40` |
| F6 | Consumers can override the preset: `kamerplanter` and `claude-shared` already append their own `packageRules` on top of `#v2.1.0` | established | `gh api repos/nolte/kamerplanter/contents/renovate.json5`, `…/claude-shared/contents/renovate.json5` (read 2026-09-19) |
| F7 | 13 portfolio repositories consume the preset via `renovate.json5` | established | `gh search code "gh-plumbing//renovate-configs/common" --owner nolte` (2026-09-19) |
| F8 | The measured baseline (18 open PRs / 10 Renovate, 100+ jobs per merge, 55 % of PR runs from `renovate/` branches) | **unestablished here** | inherited from nolte/claude-shared#644 and the issue body; not re-measured in this run. The packages do not depend on the exact numbers, only on F1 (the default is in force). |
| F9 | The preset currently has no limits and no grouping | established | `renovate-configs/common.json` on `origin/develop` @ `51d0b4b` — keys absent |

## Work packages

### P1 — Bound PR volume in the shared preset

- **Problem statement**: `renovate-configs/common.json` sets no PR-volume limits and no digest grouping, so every consumer inherits Renovate's `prConcurrentLimit: 10` and one PR per digest bump (F1, F9). Hypothesis: adding `prConcurrentLimit: 5`, `prHourlyLimit: 2`, and a `packageRules` entry `matchUpdateTypes: ["digest", "pinDigest"]` → `groupName: "digests"` reduces open Renovate PRs per consumer without touching security fixes (F4).
- **Acceptance criteria**:
  1. `renovate-configs/common.json` carries top-level `prConcurrentLimit: 5` and `prHourlyLimit: 2`, plus a new `packageRules` entry matching update types `digest` and `pinDigest` with `groupName: "digests"`; the existing `pinDigests` rule and the three `customManagers` are unchanged.
  2. The new rule and the top-level file carry `description` text (Renovate's own `description` field, valid at top level and in rules) that states: the values are defaults a consumer may override locally by setting the same key; vulnerability-alert PRs are exempt (F4); the group exists because digest bumps carry no individual changelog.
  3. `npx --yes --package renovate -- renovate-config-validator renovate-configs/common.json` exits 0 (run from the worktree; output recorded in the dispatch log). `--strict` is not required because `config:base` is out of scope.
  4. `python3 -m json.tool renovate-configs/common.json` parses; `pre-commit run --all-files` stays green.
- **Touched files / artifacts**: `renovate-configs/common.json`
- **Specialist**: `nolte-engineering:fullstack-developer` (matched on "infrastructure … against the consuming project's own tech stack"). No specialist names Renovate configuration as its responsibility — **portfolio gap recorded** (first observed recurrence for the class "Renovate preset authoring"; below the three-recurrence threshold of `continuous-improvement` §Portfolio gap closure).
- **Depends on**: none

### P2 — Document the defaults and the override contract

- **Problem statement**: the docs' "Renovate preset" section (`docs/en/getting-started/index.md:72-79`, `docs/de/getting-started/index.md` counterpart) shows only the `extends` snippet; a consumer cannot learn that the preset now bounds PR volume, how to override it, or that the change arrives only with a pin bump. AUDIENCES.md:58-63 records that this audience expects "no surprise changes to update cadence or grouping behaviour".
- **Acceptance criteria**:
  1. Both language pages gain, inside the existing "Renovate preset" section, a short block naming the three defaults (`prConcurrentLimit: 5`, `prHourlyLimit: 2`, digest/pinDigest grouped as `digests`), an override snippet (`renovate.json` setting `prConcurrentLimit` locally), the vulnerability-alert exemption, and the note that consumers pinned to `#vX.Y.Z` receive the change with their next pin bump.
  2. EN and DE carry the same facts (parity); every value quoted is verified against the P1 diff in the worktree, not against this artifact.
  3. `vale --minAlertLevel=suggestion` on the two files reports ≤10 findings on the added lines (the reviewdog annotation cap that turns the spelling check red — see memory `reference_vale_annotation_cap`).
  4. `pre-commit run --all-files` stays green.
- **Touched files / artifacts**: `docs/en/getting-started/index.md`, `docs/de/getting-started/index.md`
- **Specialist**: `nolte-shared:audience-doc-author` (MkDocs pages against the existing `AUDIENCES.md`)
- **Depends on**: P1 (the documented values must be read from the applied diff)

### P3 — Vale remediation (conditional)

- **Problem statement**: if P2's added lines carry more than 10 Vale findings, the `spelling / vale` check goes red and blocks clean automerge.
- **Acceptance criteria**: `vale --minAlertLevel=suggestion docs/en/getting-started/index.md docs/de/getting-started/index.md` → ≤10 findings on added lines; wording preserved.
- **Touched files / artifacts**: same as P2
- **Specialist**: `nolte-shared:prose-vale-curator`
- **Depends on**: P2; dispatched only when P2's criterion 3 fails.

## Dependency ordering

P1 → P2 → (P3 only if P2's Vale criterion fails).

## Risks

- **Grouped digest PR blocks on one failing member**: a single digest bump that breaks CI holds the whole `digests` group. Mitigation: consumers override per rule (F6); documented in P2.
- **Behaviour change for 13 consumers** (F7): reaches them only via a pin bump they review (`#v2.1.0` pins). Release notes must name the change; the PR title `feat(renovate): …` lets release-drafter file it under features.
- **`prHourlyLimit: 2` restates the default** (F2): no behaviour change from that key; kept explicit and documented as such so nobody removes it believing it is load-bearing.
- **`prConcurrentLimit` does not close existing PRs**: Renovate docs note the lower limit "won't go and delete any existing" — consumers see the effect only as open PRs merge or close. Documented in P2.
- **No security-sensitive path** touched: `code-security-reviewer` / `security-review` not required.
- **Verification scoping**: the session runs in the primary checkout; every gate command is run with `-C <worktree>` and the `git diff --stat origin/develop...HEAD` capture is recorded before any verdict.

## Open questions

- none blocking. Follow-up candidates (not part of this run): CI guard running `renovate-config-validator` on `renovate-configs/**`; `config:base` → `config:recommended`.

## Dispatch log

<!-- <YYYY-MM-DD> P<k> dispatched to <subagent_type> — <result one-liner> -->
2026-09-19 P1 dispatched to nolte-engineering:fullstack-developer — hypothesis confirmed; renovate-configs/common.json +14 lines (prConcurrentLimit 5, prHourlyLimit 2, packageRule digest+pinDigest → groupName "digests", description texts); `renovate-config-validator` exit 0 with only the pre-existing config:base migration WARN; `pinDigest` verified in renovate 44.79.1 dist/config/types.d.ts:448. Orchestrator editorial fix before commit: "Branch protection runs with strict: true" → "Where branch protection runs with strict: true" (not every consumer runs strict). Committed as 276ba69.
2026-09-19 P2 dispatched to nolte-shared:audience-doc-author — docs/en+de/getting-started/index.md +26 lines each ("Pull request volume" / "Pull-Request-Volumen" H3 inside the Renovate preset section: defaults list, rationale, override snippet, note admonition); values verified against HEAD common.json; `vale --minAlertLevel=error` 0 errors (1 Microsoft.Vocab suggestion on "alert"); pre-commit green. Flagged fact "consumer packageRules are appended after the preset's" established by the orchestrator: Renovate docs configuration-options.md:15 (mergeable arrays append) and :2733 (last matching rule wins), key-concepts/presets.md:71 (later entry wins on conflict).
2026-09-19 P3 not dispatched — P2 criterion 3 met (0 error-level findings), so the conditional Vale remediation package was not needed.
