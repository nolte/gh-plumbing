---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "399"
classification: "security"
secondary-classes: ["infra"]
route: "direct"
status: approved
created: "2026-08-01"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #399 — reusable-docker-publish self-attests provenance instead of using the platform attestation
- **URL**: https://github.com/nolte/gh-plumbing/issues/399
- **Labels**: cicd, github-actions, security
- **Author trust**: `nolte` — repository owner, in the trusted-author set.
- **Linked items**: none. No comments, no closing PRs, no open PRs in the repository.
- **Prior art**: no roadmap item, no feature, not self-resolved. Split out of #393 on 2026-08-01 precisely so it would not ship unverified.

### Requirements gate

No artefact under `project/requirements/`. Operator recorded an **explicit override** on 2026-08-01. Rationale: the issue states the finding location, the spec clauses, a Definition of Done and its one open question — and `nolte/kamerplanter` already carries a working answer to that question. The issue body plus that reference implementation are the requirement of record.

### Precondition deviation

`spec/project/issue-orchestration/` does not exist in this repository; the orchestration runs against the plugin-distributed spec in `claude-shared`. Same deviation recorded for issue #388.

## Classification

- **Primary class**: security
- **Secondary class(es)**: infra
- **Rationale**: a build that attests to its own integrity cannot detect its own compromise (SLSA v1.0; `continuous-delivery` §C). An attestation is a supply-chain trust anchor, so the question is who issues the proof, not how the build is shaped.

Operator confirmed this classification on 2026-08-01 before the work-package table was populated, per §Classification.

## Scope

**In scope**

- `reusable-docker-publish.yaml`: replace BuildKit's self-generated `provenance: mode=max` / `sbom: true` with `actions/attest-build-provenance`, granting `id-token: write` and `attestations: write` **at job level**.
- Consumer-facing documentation of the permissions a caller must now grant.

**Out of scope**

- Migrating `nolte/kamerplanter` onto this reusable. It publishes containers through its own `docker-publish.yml` and already implements platform attestation correctly. `github-actions-best-practices` §E says shared logic belongs upstream rather than copied, so that migration is real work — but it is a **second outcome**, and folding it in would make this a pipeline case rather than a bounded change.
- Any judgement about image *security*. An attestation records origin, not safety.

### Two findings that change the issue's own framing

**#399 says "no workflow in this repository calls `reusable-docker-publish`" and concludes it cannot be verified. The first half is true and the conclusion is wrong.** `nolte/reachy-mini-mcp` calls it from `release-cd-deliver-docker.yml` at `@v1.1.19`. Verification is possible; it just cannot happen inside this repository's own CI.

**A working reference implementation already exists in the portfolio.** `nolte/kamerplanter`'s `docker-publish.yml` uses `actions/attest-build-provenance@0f67c3f4…` with `id-token: write` and `attestations: write` scoped to the producing job, and comments citing the same spec clauses. Notably it carries **no** BuildKit `provenance:` or `sbom:` — there, the platform attestation *replaces* self-attestation rather than sitting beside it. That answers this issue's open question ("decide what happens to the existing `provenance: mode=max`") from a decision already taken against the same spec.

## Route

- **Decision**: direct — confirmed by the operator on 2026-08-01.
- **Rationale**: one coherent outcome (the reusable issues platform-signed provenance), one file plus its documentation, one PR strand, no roadmap item. The kamerplanter migration would be a second outcome and is explicitly out of scope above rather than left unplanned.

## ⚠️ This is a breaking change for an existing consumer

`reachy-mini-mcp`'s caller declares exactly:

```yaml
permissions:
  contents: read
  packages: write
```

A called workflow whose job requests permissions the caller does not grant does not receive a reduced token. **GitHub refuses to start the workflow**, with `startup_failure` and zero jobs. This repository hit that exact failure on 2026-08-01 in #406 while adding `checks: write` to the actionlint reusable.

So on the next release after this lands, `reachy-mini-mcp`'s container delivery stops entirely until its caller grants `id-token: write` and `attestations: write`. Not degraded output — no run at all.

**Operator decision, 2026-08-01: option 1, coordinate.** The consumer's caller is updated *first*, because granting a caller permissions it does not yet need is harmless while the reverse breaks it. Sequencing therefore inverts: consumer, then reusable, then release.

Three ways were weighed:

1. **Coordinate.** Update `reachy-mini-mcp`'s caller before or alongside the release. It is the only affected consumer and the portfolio owns it. **A major release is already pending (v2.0.0), which is exactly where a breaking change belongs.**
2. **Make it opt-in.** An `attest` input defaulting to `false`. Nothing breaks, and the spec violation persists for every consumer that never opts in — which is most of them, since the default is what ships.
3. **Ship it and let the consumer break.** Cheapest, and it fails at the worst moment: during a release, silently to anyone not watching the Actions tab.

## Work packages

### P1 — Platform-signed provenance in the reusable

- **Problem statement**: `reusable-docker-publish.yaml:133-134` sets `provenance: mode=max` and `sbom: true`, which is BuildKit provenance produced by the very build it attests. `continuous-delivery` §C forbids that, and §H of `github-actions-best-practices` requires the platform's attestation mechanism.
- **Acceptance criteria**:
  1. `actions/attest-build-provenance` runs after the build, consuming `steps.build.outputs.digest`, pinned by digest with a version comment.
  2. `id-token: write` and `attestations: write` are granted **at the job**, never at workflow level (§H MUST NOT widen). Verified by parsing the workflow, not by reading it.
  3. The BuildKit `provenance:` / `sbom:` inputs are removed, matching kamerplanter's decision that the platform record replaces rather than supplements. The reasoning is recorded inline.
  4. The step is skipped when `inputs.push` is false — there is no published digest to attest for a dry build.
  5. `actionlint` clean.
- **Touched files**: `.github/workflows/reusable-docker-publish.yaml`
- **Specialist**: `nolte-shared:cicd-pipeline-design`
- **Depends on**: none

### P2 — Consumer documentation of the newly required permissions

- **Problem statement**: a consumer whose caller lacks `id-token: write` / `attestations: write` gets `startup_failure` with zero jobs and no obvious cause. Nothing in the docs would tell them why.
- **Acceptance criteria**:
  1. `docs/{en,de}/workflows/` state the two permissions a caller must grant, with a copyable `permissions:` block.
  2. The failure mode is named explicitly — the workflow does not start, rather than producing an unattested image.
  3. Vale clean on the added lines.
- **Touched files**: `docs/en/workflows/*.md`, `docs/de/workflows/*.md`
- **Specialist**: no matching specialised agent — generalist remediation. `audience-doc-author` requires an audience artefact this repository does not carry; the change is a correction to existing consumer instructions rather than new audience-targeted prose.
- **Depends on**: P1

### P3 — Security verification of the produced diff

- **Problem statement**: this change alters what the portfolio's container provenance means. A subtly wrong attestation looks present while not being trustworthy, which is worse than the honest gap it replaces.
- **Acceptance criteria**:
  1. `nolte-shared:cicd-pipeline-reviewer` reports no permission-scope regression and no new §B/§H finding.
  2. The built-in `security-review` skill runs on the branch diff; findings resolved or explicitly accepted.
  3. The attestation action's digest is verified to belong to `actions/attest-build-provenance` and that repository is not a fork.
- **Touched files**: none (read-only)
- **Specialist**: `nolte-shared:cicd-pipeline-reviewer`, then the built-in `security-review` skill. `spec/project/issue-orchestration/` names `code-security-reviewer` for the audit leg; **that agent does not exist in this distribution** — second recorded occurrence of this gap (first: issue #388).
- **Depends on**: P2

## Dependency ordering

```
P1 → P2 → P3
```

## Risks

- **Breaking change for `reachy-mini-mcp`** — see the section above. This is the dominant risk and needs an operator decision before dispatch.
- **Not verifiable inside this repository.** No workflow here calls `reusable-docker-publish`. The real proof is a consumer publishing an image and `gh attestation verify` succeeding against it. That is a **post-merge, post-release obligation**, not a pre-merge acceptance test.
- **Attestation records origin, not safety.** Worth stating in the documentation so a reader does not treat an attested image as a vetted one.
- **Security-sensitive path.** `.github/workflows/**` plus a signing identity; the audit-then-verify chain in P3 is mandatory before the PR.
- **Portfolio gap — `code-security-reviewer` absent.** Second occurrence. `continuous-improvement` §Portfolio gap closure triggers an offer to author the specialist at three.

## Open questions

- Which of the three handling options for the breaking change (coordinate / opt-in / ship-and-break) the operator picks. Dispatch of P1 is shaped by the answer: option 2 changes P1's acceptance criteria to add an `attest` input.
- Whether `sbom: true` should return alongside the attestation later. Removing it matches kamerplanter, but an SBOM and a provenance record answer different questions. Deferred rather than decided here.

## Dispatch log

- **2026-08-01 P0 (coordination, cross-repo)** — `nolte/reachy-mini-mcp#8` opened, granting `id-token: write` and `attestations: write` at the calling job. Lands before the reusable requires them, so the transition is a non-event. Not part of this repository's PR strand.
- **2026-08-01 P1** dispatched to `nolte-shared:cicd-pipeline-design` — done. Brief confirmed, not refuted. All five acceptance criteria verified by parsing the workflow rather than reading it: attestation step present and pinned (`0f67c3f4…` / v4.1.1, non-fork), `id-token`/`attestations` at job level with **no** workflow-level block, BuildKit `provenance`/`sbom` removed, step skipped when `inputs.push` is false, `actionlint` clean.
  - **One defect caught during implementation.** The first draft derived `subject-name` from `env.REGISTRY`, which this workflow does not define — the metadata step uses `inputs.registry`. A mismatched subject-name produces an attestation that exists and does not verify against the pushed image: precisely the "looks present, is not trustworthy" failure this issue warns about. Now derived identically to the metadata step's `images:` value, asserted equal by parsing both.
- **2026-08-01 P2** handled by the generalist — done. No matching specialist. Found that the two Docker reusables had **no consumer documentation at all**, while every other workflow family has a page; that absence is part of why the permissions failure would surprise someone. Added `docs/{en,de}/workflows/container.md` with the required `permissions:` block, the `startup_failure` failure mode named explicitly, provenance verification via `gh attestation verify`, and the origin-not-safety caveat. Vale clean on the new pages.

- **2026-08-01 P3** dispatched to `nolte-shared:cicd-pipeline-reviewer` (audit leg) and the built-in `security-review` skill (verify leg). **0 Critical, 0 HIGH, 0 MEDIUM.** The audit returned 5 Warnings and 5 Suggestions and **partially refuted the brief** — recorded below, because two of them contradicted statements the implementation itself made.

### P3 refutations, and what changed because of them

**`sbom: true` should not have been removed.** The brief and the first implementation treated it as part of the self-attestation problem. An SBOM is not a provenance record: it lists contents rather than asserting who built the image, so §C's objection does not transfer to it. Worse, the inline comment asserted a decision this very artifact had **deferred** under Open questions. Restored, and the comment now justifies only the `provenance` input.

**Omitting `provenance` does not disable it.** Buildx attaches inline provenance by default when pushing, so the change would have left a second provenance record beside the platform-signed one — precisely what the comment claimed it avoided. The action's documentation for the pinned version is not published in its repository, so the default could not be confirmed; `provenance: false` is now explicit, which makes the outcome correct whatever the default is.

**The multi-arch concern did not reproduce.** The brief asked whether attesting the build digest attests only part of a multi-platform manifest. It does not: buildx emits the **index** digest, every tag resolves to it, and `gh attestation verify` against a tag lands on the same digest. The only real path to a non-verifying attestation is a consumer pinning a per-architecture manifest digest — a documentation gap, now closed in both locales.

**One genuine code defect.** `subject-name` did not lowercase while `docker/metadata-action` does, so any owner or image name with an uppercase letter would have produced an attestation naming a reference that was never pushed. Both now derive from one lowercased value; equality asserted by parsing the workflow.

Four documentation findings were also fixed: the index-versus-per-architecture digest distinction, the second path on which `latest` moves (the one that already caused drift in `nolte/reachy-mini-mcp` v0.1.1), the fact that `type=ref` tags move too, and that multi-arch is opt-in rather than a property of the workflow.

### Digest verification (§A, recorded in the change rather than only here)

`actions/attest-build-provenance@0f67c3f4856b2e3261c31976d6725780e5e4c373` — owner `actions`, `fork: false`, `archived: false`, and `v4.1.1` resolves to exactly that digest.

### Out-of-scope finding, filed separately

While making the documentation Vale-clean: `.github/styles/*` is gitignored, so the repository cannot carry a local vocabulary. The `[Rr]uleset` entry #403 reports adding was never committed, and `docs/en/decisions/adr-001-presentation-branch-reset.md` produces three Vale errors on `develop` today. It goes unnoticed because `errata-ai/vale-action` runs with its `fail_on_error: false` default. Filed as **#409**; not fixed here, since it is neither caused by nor related to this change.
