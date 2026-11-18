---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "488"
classification: "feature-request"
secondary-classes: ["security"]
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #488 — feat(actions): composite action that installs a pinned Vale binary verified against a committed SHA-256
- **URL**: https://github.com/nolte/gh-plumbing/issues/488
- **Labels**: none
- **Linked items**: nolte/claude-shared#768 (prior art: `scripts/install_vale.sh`, `.vale-version` format). #484 / PR #491 merged (same file, landed first). No open PR references #488.
- **Prior art checked**: hand-off record from `issue-backlog-partition` run 2026-11-18-gh-plumbing, re-checked against the live issue (open, author `nolte`, 0 comments). Not part of roadmap R-4 / sprint 0002; the issue cites neither.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/488-setup-vale-action`, branch `feat/488-setup-vale-action` off `origin/develop` @ 078116b; detect=200; fallback `git worktree add -b`; ignore check: ignored=1
- **Lane**: `lane: true` — returns `committed-locally`.
- **Gates**: scope, requirements override (the issue carries problem, proposal and four acceptance criteria), route, decomposition and the design decisions below approved under the operator's standing authorisation of 2026-11-18 ("arbeite möglichst autonom"), recorded in `.resume/issue-backlog-partition/2026-11-18-gh-plumbing.yml`. The partition approval already settled the bounded verdict (reading A: one PR here; the AC3 follow-up issues are filed by the lane).

## Classification

- **Primary class**: feature-request
- **Secondary class(es)**: security (unverified binary download)
- **Rationale**: a new consumable capability (a composite action), motivated by a supply-chain gap.
- **Asserted cause verified**: confirmed for this repository: `.github/workflows/reusable-release-publish.yml` step "Check the release notes with Vale" sets `VALE_VERSION: "3.15.2"` and runs `curl -fsSL …/vale_${VALE_VERSION}_Linux_64-bit.tar.gz | sudo tar -xz -C /usr/local/bin vale` with no checksum. Neither `actions/` nor `.github/actions/` exists; no `.vale-version` file exists; `.tool-versions` pins `vale 3.15.2`. **Unestablished**: the issue's findings in claude-goose, terraform-github-bootstrap and claude-shared — not re-read here; AC3 only files issues that quote them as the issue states them.

## Scope

- **In scope**: the composite action `actions/setup-vale` (path named in the issue); a `.vale-version` for this repository; `reusable-release-publish.yml` consuming the action; a self-test workflow; README documentation of the file format and the Renovate pattern; the Renovate custom manager in `renovate-configs/common.json`; after the merge, three follow-up issues (AC3).
- **Out of scope**: `reusable-spelling-vale.yaml` (uses `errata-ai/vale-action`, a different acquisition path); non-Linux runners (the issue names the `Linux_64-bit` asset; the action refuses anything else with a clear message); changing the inline copies in other repositories.

## Design decisions (recorded so the reviewer can challenge them)

1. **How the reusable reaches the action.** A `uses: ./…` path in a reusable workflow resolves in the caller's workspace, and `nolte/gh-plumbing/actions/setup-vale@<sha>` can't name a commit that doesn't exist before the merge. The file already checks out its own repository at `job.workflow_sha` into `.docs-freshness` (around `:865-872`) for the freshness checker. The Vale step uses the same mechanism: a self-checkout at the pinned commit, then the action by local path from that checkout, with `version`/`sha256` read from that checkout's `.vale-version`. One PR, and the workflow can never run an action version other than its own commit's.
2. **Failure policy in release-publish.** Today an acquisition failure warns and skips the check (a release refused because a download server is down is the worse outcome; comment at the Vale step). That stays for a download failure. A **checksum mismatch is not an acquisition failure**: the action never runs the binary (fail closed) and the publish run **fails**, because a replaced asset is exactly the event the check exists to surface.
3. **Negative self-tests end green.** A job that proves "the action refuses a wrong checksum" asserts the step's failed outcome and passes. A red-by-design run on `develop` blocks the develop-health pre-flight (seen 2026-11-18 with `test-release-archive.yml` run 43964109508).
4. **One version, checked.** `.vale-version` becomes the source for CI; `.tool-versions` keeps its `vale` line for local asdf use. A check fails when the two disagree, so the release gate and local runs can't drift apart silently.

## Work packages

### P1 — Composite action `actions/setup-vale` with a self-test

- **Acceptance criteria**:
  1. Inputs `version-file` (default `.vale-version`) or `version` plus `sha256`; output `vale-version`. Format of the file as in nolte/claude-shared#768: `VALE_VERSION=<ver>` and `VALE_SHA256=<sha>  vale_<ver>_Linux_64-bit.tar.gz`.
  2. Downloads to `$RUNNER_TEMP`, verifies with `sha256sum -c` before anything is unpacked, refuses when the checksum line names another version than `VALE_VERSION`, extracts only the `vale` member, runs it once, appends its directory to `$GITHUB_PATH`. No `sudo`, no pipe from `curl` into `tar`.
  3. Fails closed: on a mismatch no `vale` binary from this run is on `PATH` and nothing was executed. Mismatch and download failure are distinguishable by the caller (decision 2).
  4. Inputs reach scripts through `env:`; a version string with shell metacharacters or path separators is refused, not interpolated into a URL or path.
  5. Refuses non-Linux or non-x86-64 runners with a message naming the limit.
  6. Self-test workflow on `pull_request` (paths: the action, the test, `.vale-version`) and `workflow_dispatch`: installs from the repository's `.vale-version` and runs `vale --version`; proves refusal for a wrong checksum, for a checksum line naming another version, and for a malformed version — each negative job green when the action refused (decision 3).
  7. The committed SHA-256 for the pinned version is computed from the downloaded asset and cross-checked against the upstream release's checksum file; both values shown.
- **Touched files**: `actions/setup-vale/action.yml` (+ script if split out), `.vale-version`, `.github/workflows/test-setup-vale.yml`
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: none

### P2 — `reusable-release-publish.yml` uses the action

- **Acceptance criteria**:
  1. The "Check the release notes with Vale" path installs Vale only through the action, reached per decision 1; `curl | sudo tar` and the inline `VALE_VERSION` are gone.
  2. Download failure → warning, check skipped, publish continues (as today). Checksum mismatch → the run fails before any publish write. `vale sync` failure → warning as today. A Vale error in the notes → blocks as today.
  3. The existing self-checkout for the freshness checker isn't duplicated: one checkout serves both, or the reason for two is stated.
  4. No new permission; no secret reaches the action.
  5. `actionlint` (CI flags) passes.
- **Touched files**: `.github/workflows/reusable-release-publish.yml`
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: P1

### P3 — Renovate manager, version agreement check, documentation

- **Acceptance criteria**:
  1. `renovate-configs/common.json` gains a regex custom manager on `VALE_VERSION` in `.vale-version` (datasource for errata-ai/vale releases), with no automerge for it. JSON stays valid; the repository's existing Renovate config tests or validators, if any, pass.
  2. Because Renovate can't recompute the checksum, a bumped `VALE_VERSION` with the old `VALE_SHA256` line fails a check that runs on the Renovate PR (the action's own version/checksum-line agreement in the self-test satisfies this if the self-test's paths include `.vale-version`; say which mechanism covers it).
  3. A check fails when `.vale-version` and `.tool-versions` name different Vale versions (decision 4), in the existing static gate.
  4. `README.md` documents the action (usage with a digest pin), the `.vale-version` format, and the Renovate pattern including the manual checksum step (AC4). The docs site gets what `scripts/docs_freshness.py` requires for a new workflow/action in both languages, if anything; run it and show the result.
  5. Vale on added English prose: `vale --minAlertLevel=suggestion`, new alerts kept under ten and no errors.
- **Touched files**: `renovate-configs/common.json`, `README.md`, `docs/{en,de}/…` as required, `.pre-commit-config.yaml` or the static gate for the agreement check
- **Specialist**: `nolte-engineering:fullstack-developer` (no specialist names Renovate preset authoring; known gap tracked as nolte/claude-shared#785, not re-counted)
- **Depends on**: P1

### P4 — Follow-up issues in the three consumer repositories (AC3)

- **Acceptance criteria**: after the PR merged, one issue each in nolte/claude-goose, nolte/terraform-github-bootstrap and nolte/claude-shared, naming the inline copy as #488 states it, the action with its merge commit SHA, and the `.vale-version` format. Links recorded in #488 before it closes.
- **Specialist**: orchestrator (`gh issue create`; externally visible, done by the run that holds the operator's authorisation)
- **Depends on**: merge of P1–P3

## Existing installations / upgrade / rollback

Health gate: none (reusable workflow and composite action consumed by ref).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P1 | new invocation name `nolte/gh-plumbing/actions/setup-vale`; nothing existing changes | none; surfaces: the action's inputs/outputs become public API | revert removes the action; consumers that pinned its digest keep working (the commit stays reachable) | self-test workflow |
| P2 | consumers of `reusable-release-publish.yml` get the verified install at their next ref bump; inputs, outputs, secrets, permissions unchanged. New failure mode: a checksum mismatch fails the publish | none; surfaces: none read from the consumer (version file comes from this repository's pinned checkout) | revert restores the unverified install | extracted-script tests for the four outcomes in P2 AC2; no live publish possible before a release |
| P3 | consumers extending `renovate-configs/common` get one more custom manager; it matches only a `.vale-version` file | none; surfaces: consumer Renovate behaviour | revert removes the manager; an open Renovate PR it created stays open | JSON validity + a regex test against the committed `.vale-version` |

## Dependency ordering

P1 → P2, P3 → (merge) → P4.

## Risks

- Release path of every consumer: a mistake in P2 blocks or silently skips the notes check. Mitigation: the four outcomes are tested on the extracted scripts; the PR states that no live publish ran.
- `job.workflow_sha` self-checkout is the mechanism the freshness gate already relies on; if it were unavailable the Vale step would have no action. Mitigation: same failure policy as a download failure is NOT acceptable here silently — the specialist states what happens and makes it visible.
- A wrong committed checksum would fail every publish. Mitigation: P1 AC7 and the self-test's positive job.
- Security-sensitive paths (`.github/workflows/`, a new action that downloads and executes a binary): security-briefed read-only diff review before the lane returns.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|

## Dispatch log
