---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "388"
classification: "security"
secondary-classes: ["infra"]
route: "direct"
status: approved
created: "2026-08-01"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #388 — Reusable workflows run unpinned third-party actions, three of them from moving branches
- **URL**: https://github.com/nolte/gh-plumbing/issues/388
- **Labels**: dependencies, cicd, github-actions, security
- **Author trust**: `nolte` — repository owner and admin collaborator, in the trusted-author set per `spec/claude/trusted-author-injection-guard/`. The issue's staging advice and Renovate instruction are therefore treated as operator direction, not as untrusted data.
- **Linked items**: none — no closing PRs, no open PRs in the repository, no comments.
- **Prior art checked**: `project/roadmap.md` (R-1 reusable workflow library, R-2 Probot commons, R-3 Renovate presets — thematically adjacent, none covers action pinning), `project/features/*.md` (only `reusable-workflow-adoption.md` mentions pinning, and about consumers pinning *this* repo by tag, not about this repo pinning its own dependencies). No prior art found; the issue is not self-resolved.

### Requirements gate

No artifact exists under `project/requirements/` (the directory itself is absent). Per `spec/project/issue-orchestration/` §Issue acquisition, the operator recorded an **explicit override** of the `requirements-elicit` consumer gate on 2026-08-01. Rationale: the issue already states a full reference inventory, a staged rollout order, and a five-item checkable Definition of Done, so an elicitation interview would restate rather than sharpen the requirements. The issue body's "Definition of done" section is the requirement of record for this run.

### Precondition deviations recorded

1. `spec/project/issue-orchestration/` does not exist in `nolte/gh-plumbing` — the repository carries no `spec/` tree at all. The orchestration runs against the plugin-distributed spec at `claude-shared/spec/project/issue-orchestration/en.md`.
2. `task worktree:add` is not available here (`Taskfile.yml` includes only `mkdocs` and `pre-commit` namespaces). The worktree was created with the equivalent `git worktree add -b fix/388-pin-third-party-actions ~/repos/.worktrees/gh-plumbing/388-pin-actions origin/develop`, which lands on the spec-conformant `${NOLTE_WORKTREE_ROOT:-~/repos/.worktrees}/<repo>/` path. The primary checkout stays on `develop`.

## Classification

- **Primary class**: security
- **Secondary class(es)**: infra
- **Rationale**: a mutable branch reference executing inside a job that holds `security-events: write` is a supply-chain execution exposure, not CI hygiene; the pinning work is the remediation, not the goal.

The operator confirmed this classification on 2026-08-01 before the work-package table was populated, per §Classification (`security` requires explicit confirmation).

Note on the `infra` short-circuit: §Classification hands an `infra` issue *about CI* to `workflow-health-triage`. That short-circuit does not apply here — `workflow-health-triage` triages a *failing run*, and no run is red. The primary class is `security` regardless.

## Scope

**In scope**

- All **30 distinct third-party references** across **57 `uses:` occurrences** in 22 `reusable-*.y{a}ml` files, replaced by full-length commit digests with a `# vX.Y.Z` version comment.
- The three moving-branch references specifically: `aquasecurity/trivy-action@master`, `errata-ai/vale-action@reviewdog`, `home-assistant/actions/hassfest@master`.
- Normalising `actions/checkout`, which currently appears as `@v4` (3×), `@v6` (2×) and `@v6.0.0` (10×), onto one digest.
- A decision plus implementation for the deliberately parameterised `hacs/action@${{ inputs.hacs_action_ref }}`.
- `"pinDigests": true` for the `github-actions` manager in `renovate-configs/common.json`.

The issue's inventory lists 28 references. The repository scan found **two further ones the issue omits**, both release-critical, and the operator confirmed on 2026-08-01 that they join the scope:

| Reference | Location | Why it matters |
|---|---|---|
| `devmasx/merge-branch@1.4.0` | `reusable-release-cd-refresh-master.yml:64` | Writes to `master` on every published release |
| `release-drafter/release-drafter@v6` | `reusable-release-drafter.yml:109` | Runs under a GitHub App token |

The issue's Definition of Done ("No `uses:` in `.github/workflows/`" resolves to a branch; every third-party reference is a digest) already covers both, so this widens the inventory, not the goal.

**Out of scope**

- The nine non-reusable wrapper workflows (`build-static-tests.yaml`, `automerge.yaml`, `release-*.yml`, `spelling.yaml`, `stale.yaml`, `dependency-review.yaml`). Verified: each contains only `nolte/gh-plumbing/.github/workflows/reusable-*@develop` references. Nothing third-party to pin. The `@develop` self-references are the documented branching model per `CLAUDE.md`, not a pinning defect.
- Rolling the change out to consumer repositories. Consumers pin `gh-plumbing` by tag or digest, so they pick this up on their own Renovate cadence after the next release.
- Retrofitting `pinDigests` into consumer repositories that do not extend the shared preset.

## Route

- **Decision**: direct — confirmed by the operator on 2026-08-01 at the operation-4 gate.
- **Rationale**: one coherent goal outcome (supply-chain hardening of the shared workflow surface), one feature branch, one pull request, no new or retargeted roadmap item. The issue's three-stage advice is a *sequencing* instruction, not a second PR strand: because consumers only pick up `gh-plumbing` changes at a release boundary, splitting the stages across separate PRs would only reduce blast radius if each were released separately, which is not the intent stated in the issue. The stages are therefore realised as ordered commits inside one strand, preserving the issue's risk ordering without fragmenting the change.
- **Pipeline hand-off**: not applicable.

## Work packages

### P1 — Eliminate the three moving-branch references

- **Problem statement**: three `uses:` references resolve to branches whose heads any upstream write-holder can move. `aquasecurity/trivy-action@master` is the sharp end: it runs in a job holding `security-events: write`, reached from `build-static-tests.yaml`, which fires on every push in consuming repositories.
- **Acceptance criteria**:
  1. `grep -rn "@master\|@reviewdog" .github/workflows/` returns no `uses:` line.
  2. Each of the three is a 40-character commit digest carrying a `# vX.Y.Z` comment.
  3. Each digest is reachable from a tag in the action's **own** repository — verified upstream as non-fork, non-archived: `aquasecurity/trivy-action` (latest `v0.36.0` → `ed142fd0673e97e23eac54620cfb913e5ce36c25`), `errata-ai/vale-action` (latest `v2.1.2` → `85f9f7f2c5f449ac0ae5b66662961bae3f77ca6a`), `home-assistant/actions` (tag `1.0.0` → `4b258cf2bf1668d8e0adcb6b2be96b6cda36f42f`; note the `master` head is `ab22029…`, so the tag lags — the specialist must decide tag-versus-head and record the choice).
  4. `reusable-spelling-vale.yaml` still passes its own Vale run, since `@reviewdog` is that action's historical release channel and `v2.x` may have changed inputs.
- **Touched files**: `.github/workflows/reusable-trivy.yaml:20`, `.github/workflows/reusable-spelling-vale.yaml:12`, `.github/workflows/reusable-hacs-validate.yaml:88`
- **Specialist**: `nolte-shared:cicd-pipeline-design`
- **Depends on**: none

### P2 — Pin the always-on reusables

- **Problem statement**: `reusable-pre-commit`, `reusable-trivy`, `reusable-chain-bench` and `reusable-mkdocs-build` are the four called from `build-static-tests.yaml`, which carries the `static / Static CI Tests` required context. They execute on every push in every consumer, so their unpinned references have the widest exposure and the tightest failure feedback.
- **Acceptance criteria**:
  1. Every third-party `uses:` in those four files is a full-length digest with a version comment.
  2. `actions/checkout` is normalised to a single digest across all four (currently `@v6.0.0` and `@v6` are mixed).
  3. This repository's own `static / Static CI Tests` check is green on the feature branch — this repository dog-foods the same four workflows, so it is a real gate, not a proxy.
- **Touched files**: `.github/workflows/reusable-pre-commit.yaml`, `reusable-trivy.yaml`, `reusable-chain-bench.yaml`, `reusable-mkdocs-build.yaml`
- **Specialist**: `nolte-shared:cicd-pipeline-design`
- **Depends on**: P1

### P3 — Pin the remaining third-party references

- **Problem statement**: the balance of the inventory — the Docker, release, Ansible, docs-deploy, Terraform and dependency-review reusables — still floats on tags, including the two the issue omits.
- **Acceptance criteria**:
  1. `grep -rn "uses:" .github/workflows/ | grep -v "nolte/gh-plumbing"` yields only `<owner>/<repo>@<40-hex>` forms, with the single documented exception of the parameterised `hacs/action` handled by P4.
  2. All three `actions/checkout` spellings (`@v4`, `@v6`, `@v6.0.0`) collapse to one digest repository-wide.
  3. `devmasx/merge-branch` and `release-drafter/release-drafter` are pinned.
  4. Every digest verified against the action's own repository (non-fork), recorded in the commit body.
- **Touched files**: the remaining 15 `reusable-*.y{a}ml` files carrying third-party references
- **Specialist**: `nolte-shared:cicd-pipeline-design`
- **Depends on**: P2

### P4 — Resolve the parameterised `hacs/action` reference

- **Problem statement**: `hacs/action@${{ inputs.hacs_action_ref }}` (default `main`) is deliberately caller-overridable. Its default currently resolves to a branch, which reproduces the P1 exposure for every caller that does not override it, but removing the input would break the escape hatch it exists to provide.
- **Acceptance criteria**:
  1. The `hacs_action_ref` input's **default** is a full-length digest with a version comment, so the unconfigured caller is safe.
  2. The input remains, so a caller can still pin forward or test a pre-release.
  3. The input's `description` states that a non-digest value is accepted but unpinned.
- **Touched files**: `.github/workflows/reusable-hacs-validate.yaml` (input block and line 69)
- **Specialist**: `nolte-shared:cicd-pipeline-design`
- **Depends on**: P1

### P5 — Enable `pinDigests` in the shared Renovate preset

- **Problem statement**: `renovate-configs/common.json` extends `config:base` plus a Vale custom manager and never sets `pinDigests`. Without it, the 29 pins P1–P4 create would age silently — a stale pin fails the same reproducibility goal as a floating reference. Enabling it in the shared preset also reaches every consumer that extends it, which the issue names as the point.
- **Acceptance criteria**:
  1. `renovate-configs/common.json` enables `pinDigests` for the `github-actions` manager.
  2. The file is valid JSON and validates against the Renovate config schema.
  3. The existing `customManagers` Vale entry and the `labels` array are unchanged.
  4. The change is scoped to `github-actions`, not applied globally, so Docker and npm digest behaviour in consumers is unaffected.
- **Touched files**: `renovate-configs/common.json`
- **Specialist**: **no matching specialised agent — generalist remediation.** `cicd-pipeline-design`'s stated scope is workflow files; `project-structure-apply` scaffolds a *missing* Renovate config rather than tuning an existing preset; `yaml-json-schema` governs JSON Schema authoring, not Renovate presets. Recorded as a portfolio gap under `continuous-improvement` §Portfolio gap closure — see Risks. The operator confirmed generalist remediation on 2026-08-01 rather than authoring a specialist now, since the three-recurrence rule is not yet met.
- **Depends on**: P3

### P6 — Security verification of the produced diff

- **Problem statement**: the change is `security`-class and every digest introduced is a trust decision. A digest that silently points at a fork, or at a commit not reachable from the claimed tag, would look identical in review while defeating the change's entire purpose.
- **Acceptance criteria**:
  1. `nolte-shared:cicd-pipeline-reviewer` reports no remaining floating reference and no permission-scope regression.
  2. The built-in `security-review` skill runs on the branch diff and its findings are resolved or explicitly accepted.
  3. Every digest independently re-resolved: `gh api repos/<owner>/<repo>/commits/<digest>` succeeds against the action's own repository, and the version comment matches the tag that contains it.
- **Touched files**: none (read-only verification)
- **Specialist**: `nolte-shared:cicd-pipeline-reviewer`, then the built-in `security-review` skill. The spec's §Specialist dispatch names `code-security-reviewer` for the audit leg; **that agent does not exist in this distribution** (`claude-shared/agents/` has no `code-security-reviewer.md`). `cicd-pipeline-reviewer` is the closest description match, since it names unpinned actions and permission scope explicitly, and it covers the audit leg for this diff.
- **Depends on**: P5

## Dependency ordering

```
P1 → P2 → P3 → P5 → P6
 └─→ P4 ─────────↗
```

P1 first (smallest diff, removes the actual exposure), then P2 (widest blast radius, fastest feedback), then P3 (the balance), with P4 branching off P1 independently. P5 lands with the pins so they never exist without an ageing mechanism. P6 gates the PR.

## Risks

- **Blast radius**: every consumer's CI changes at once, and `build-static-tests.yaml` carries a required check in at least `nolte/kamerplanter`. *Mitigation*: this repository dog-foods all four always-on reusables, so its own `static / Static CI Tests` is a genuine pre-merge gate (P2 AC-3); the commit ordering keeps the risky stages separable if a revert is needed.
- **Tag-to-digest drift on `home-assistant/actions`**: tag `1.0.0` (`4b258cf…`) lags the `master` head (`ab22029…`), and the file carries a comment saying hassfest is canonically referenced `@master`. Pinning to a stale tag could miss upstream fixes. *Mitigation*: P1 AC-3 forces the specialist to state the choice; `pinDigests` (P5) makes the pin's age visible afterwards.
- **`errata-ai/vale-action@reviewdog` is a release channel, not a stray branch**: moving to `v2.1.2` may change inputs. *Mitigation*: P1 AC-4 requires the Vale run to still pass.
- **Renovate PR volume**: `pinDigests` plus 30 pinned references will raise the update rate across every consumer extending the preset. *Mitigation*: the preset already sets `:dependencyDashboard` and `automerge` labelling exists; accepted as the cost of visible ageing.
- **Security-sensitive path**: `.github/workflows/**` is security-sensitive by definition here. Per §Verification, the audit-then-verify chain (P6) **must** run before the PR opens.
- **Portfolio gap — `code-security-reviewer` absent**: the spec's security chain names an agent this distribution does not ship. First recorded occurrence for this finding class. Per `continuous-improvement` §Portfolio gap closure, three generalist-handled recurrences (or a recorded high-impact justification) trigger an offer to author it via `nolte-claude-dev:claude-plugin-developer`.
- **Portfolio gap — no Renovate-preset specialist**: P5 has no description match. First recorded occurrence for this finding class.

## Open questions

- **The Definition of Done item "A consumer's `static / Static CI Tests` confirmed green after the change, not assumed" cannot be satisfied before this PR merges.** Consumers pin `gh-plumbing` by tag or digest, so they only see the change after the next release. This is recorded as a **post-merge obligation** in the PR's Risk / rollout notes rather than as a work package, because it has no pre-merge acceptance test. The nearest pre-merge equivalent is P2 AC-3, this repository's own dog-fooded run.
- Whether `home-assistant/actions/hassfest` pins to the `1.0.0` tag or to the current `master` head — deferred to P1's specialist, who must record the choice.

## Dispatch log

<!-- Appended during operation 5; one line per package once its specialist reports. -->
