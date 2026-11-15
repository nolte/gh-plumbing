# Issue Orchestration — Pre-analysis

## Issue metadata

- Issue: nolte/gh-plumbing#447, "Keep nolte/gh-plumbing pin and digest updates out of the shared Renovate digests group"
- Author: `nolte` (repository owner, trusted); no comments; no linked or open PR
- Branch / worktree: `feat/renovate-gh-plumbing-own-pr` at `/home/nolte/repos/.worktrees/gh-plumbing-447`, off `origin/develop` e1d72b0
- Requirements gate: no artefact under `project/requirements/`; **operator override** (2026-11-15) — the issue's three checklist items are the requirement

## Classification

- Primary: `feature-request` — changes the shared preset's grouping behaviour so `spec/project/workflow-health/` §Upstream (`nolte/gh-plumbing`) drift (`en.md:86-90`, nolte/claude-shared) holds once consumers digest-pin gh-plumbing references.
- Secondary: none.

## Scope

In scope:
- One `packageRules` entry in `renovate-configs/common.json` that removes `nolte/gh-plumbing` from the `digests` group and sets `automerge: false`.
- Validation of the resulting preset and of which update types Renovate emits for gh-plumbing references.

Out of scope:
- Consumer-side guards against a consumer automerge rule (operator decision: document the limit in the PR only).
- F-3 (digest-pin check) and every other R-4 feature.

## Evidence

- **Established** — the group rule matches every `github-actions` `digest` / `pinDigest` update with no package filter: `renovate-configs/common.json:23-28`.
- **Established** — gh-plumbing updates reach consumers today as their own version PRs with Renovate type `workflow`, not via the group: kamerplanter-appliance, kamerplanter-goose (2026-11-11/13, "update nolte/gh-plumbing action to v2.2.1"), kamerplanter-ha#79 (`gh search prs --owner nolte --author app/renovate "nolte/gh-plumbing"`). None of the 10 most recent `digests`-titled Renovate PRs touches a gh-plumbing reference (per-PR `files` / body check).
- **Established** — a version bump of a digest-pinned reference is emitted as `major`/`minor`/`patch`, which the group rule does not match; only `pinDigest` and `digest` would be grouped. (Renovate update-type semantics; to be re-confirmed by the validator / dry run in P1.)
- **Established (P1 dry run, renovate@41 `--platform=local --dry-run=lookup`, 2026-11-16)** — `pinDigests` does apply to reusable-workflow references (`depType: action`): a tag-pinned `nolte/gh-plumbing/...@v2.2.0` gets a `pinDigest` update. With the new rule it lands in `renovate/nolte-gh-plumbing-.x`, its own branch; the third-party `pinDigest` updates (`actions/checkout`, `actions/setup-python`) still land in `renovate/digests`. A digest-pinned `@80cb5eb… # v2.2.0` reference gets a `patch` update to v2.2.1 in `renovate/nolte-gh-plumbing-2.x`, outside the group.
- **Inferred, not run** — without the rule, the gh-plumbing `pinDigest` would match the group rule exactly like `actions/checkout` does and land in `renovate/digests`; no negative-control run was made.
- **Established** — `renovate-config-validator` (renovate@41) on the worktree file: `Config validated successfully`; the pre-existing `config:base` → `config:recommended` migration warning is unrelated to this change.
- **Established limit** — a consumer's own `packageRules` are evaluated after the preset's, so a consumer automerge rule overrides the preset's `automerge: false`; the preset can set the default only.

## Route

Implement directly (operator-confirmed 2026-11-15): one outcome, one file, one PR strand, no new or retargeted roadmap item.

## Work packages

### P1 — Exclude nolte/gh-plumbing from the digests group

- Problem: the `digests` group would bundle gh-plumbing `pinDigest`/`digest` updates with third-party action digests, hiding the acknowledgement the workflow-health spec requires.
- Acceptance criteria:
  - A rule after the group rule matches `nolte/gh-plumbing` in the `github-actions` manager, sets `groupName: null`, `groupSlug: null`, `automerge: false`, and carries a `description` naming the spec and the consumer-override limit.
  - `renovate-config-validator` accepts `renovate-configs/common.json`.
  - A local dry run against a fixture workflow using `nolte/gh-plumbing/...@<sha> # vX` and a third-party action shows the gh-plumbing update outside the `digests` branch, and records which update types it emits.
- Files: `renovate-configs/common.json`
- Specialist: no matching specialised agent available in this session (`fullstack-developer` exists in nolte-engineering but isn't dispatchable here) — generalist remediation. Renovate-preset specialist gap recurrence 2.
- Dependencies: none.

## Risks

- Renovate's handling of `groupName: null` in a later rule: if it doesn't reset the group, the dry run shows it and the rule uses `matchPackageNames` with a negation on the group rule instead.
- Consumers on a pre-v2 preset don't receive the rule (same as `pinDigests`).

## Open questions

None.
