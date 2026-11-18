---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "497"
classification: "docs"
secondary-classes: ["bug"]
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #497 — terraform/portfolio-app still says the App can be a push-restriction actor on a user account
- **URL**: https://github.com/nolte/gh-plumbing/issues/497
- **Labels**: project-config
- **Linked items**: #481 / PR #496 (merged, where this was found; touched no `terraform/` file), #442 (closed, same assumption removed from the Probot settings). `closedByPullRequestsReferences` is empty.
- **Prior art checked**: `docs/en/portfolio-app/setup.md:297-304` already carries the "Push restrictions need an organisation" warning for the Probot path; ADR-005 and ADR-006; no open PR; no roadmap item or feature names the module.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/497-portfolio-app-user-mode-bypass`, branch `fix/497-portfolio-app-user-mode-bypass` off `origin/develop` @ f4f1d99; detect=200; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: ignored=1
- **Caller**: `issue-backlog-partition` run `2026-11-18-2-gh-plumbing`, `lane: true` → ends at `committed-locally`.

## Classification

- **Primary class**: docs
- **Secondary class(es)**: bug (the module accepts a combination GitHub documents as unavailable)
- **Rationale**: the deliverable is true statements in comments, README and setup pages; AC1 adds one plan-time validation.
- **Asserted cause verified**:
  - *Stale text present* — established. `terraform/portfolio-app/variables.tf:45` ("every listed repo also gets the App declared as a push-restriction actor"), `:55` ("Works identically in organisation and user mode"); `main.tf:98-101` ("Identical shape in organisation and user mode"); `README.md:48` (under "Both modes"), `:188` ("let the App through"); `docs/en/portfolio-app/setup.md:134-136`; `docs/de/portfolio-app/setup.md:137-139`. The resource at `main.tf:109-125` has no mode condition: it is created whenever `enable_branch_bypass` is true.
  - *GitHub limits push restrictions to organisation-owned repositories* — established from GitHub's documentation, read 2026-11-18: REST "Update branch protection", `restrictions`: "User, app, and team restrictions are only available for organization-owned repositories." About protected branches, "Restrict who can push to matching branches": "You can enable branch restrictions in public repositories owned by a GitHub Free organization, and in all repositories owned by an organization using GitHub Team or GitHub Enterprise Cloud."
  - *A user-mode `terraform apply` with `enable_branch_bypass = true` fails* — **unestablished**. No apply was run. The provider's `restrict_pushes` documentation and the GraphQL `CreateBranchProtectionRuleInput` reference could not be read in this run (registry page didn't render, raw source 404, GraphQL page returned its index only). The observation that would settle it: a user-mode apply against a test repository. The operator chose to decide AC1 from GitHub's documented feature limit and to say so.

## Scope

- **In scope**: a plan-time validation that refuses `user` together with `enable_branch_bypass = true`; true statements in `variables.tf`, `main.tf`, `outputs.tf`, the module README, both example READMEs and the personal-account example comment; the Terraform tip in `docs/{en,de}/portfolio-app/setup.md`.
- **Out of scope**: whether a push restriction is a bypass at all in organisation mode (ADR-005 notes it isn't; the resource's naming stays); the `Administration` permission row of the setup page (#490, next lane); any `terraform apply`.

## Requirements gate

No artefact under `project/requirements/` covers #497. **Operator override, 2026-11-18:** `requirements-elicit` skipped; the issue states two testable acceptance criteria and the operator settled AC1's variant (validation from documentation).

## Route

- **Decision**: direct
- **Rationale**: one coherent outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Refuse the user-mode bypass and correct the module's own statements

- **Problem statement**: the module creates `github_branch_protection.bypass` with `restrict_pushes` in user mode and says that works; GitHub documents push restrictions as organisation-only.
- **Acceptance criteria**:
  1. With `user` set and `enable_branch_bypass = true`, `terraform plan` (or `terraform test`) fails with a message that names the cause (push restrictions exist only on organisation-owned repositories) and the remedy (leave the flag off in user mode, or use organisation mode). Shown by a committed `terraform test` case with a mocked provider, or, if that isn't workable, by the captured output of a command that needs no credentials.
  2. With `organization` set and `enable_branch_bypass = true`, and with `user` set and the flag off, the same check passes.
  3. `terraform fmt -check -recursive terraform/portfolio-app` and `terraform validate` are clean.
  4. No sentence in `terraform/portfolio-app/**` (tracked files) says or implies the bypass works in user mode. Where the text states the GitHub limit, it states it as GitHub's documented limit, not as something this repository observed through Terraform.
- **Touched files / artifacts**: `terraform/portfolio-app/{main.tf,variables.tf,outputs.tf,README.md}`, `terraform/portfolio-app/examples/personal-account/{README.md,main.tf}`, `terraform/portfolio-app/examples/basic/README.md` (only if a statement there is wrong for organisation mode — expected: no change), optionally `terraform/portfolio-app/tests/*.tftest.hcl`.
- **Specialist**: `nolte-engineering:fullstack-developer` (its description names infrastructure; no candidate in the four roots names Terraform module authoring — recorded as a narrow gap, generalist-adjacent match).
- **Depends on**: none

### P2 — Correct the Terraform tip on both setup pages

- **Problem statement**: the tip says the module supports both modes and optionally declares the App as a bypass actor, without the user-mode limit.
- **Acceptance criteria**: the EN and DE tips say the branch-protection part applies to organisation mode only and that the module refuses it in user mode; both pages say the same thing; `vale --minAlertLevel=suggestion` on the added EN lines reports no error and fewer than 10 alerts; the corpus grep for the old claim (`bypass actor`, `Bypass-Actor`, `identical`, `let the App through`) finds no surviving user-mode claim under `docs/` or `terraform/`.
- **Touched files / artifacts**: `docs/en/portfolio-app/setup.md:131-141`, `docs/de/portfolio-app/setup.md:134-143`.
- **Specialist**: `nolte-engineering:fullstack-developer`, same dispatch as P1 so the wording matches the validation message. `nolte-shared:audience-doc-author` needs an audience artefact first and is oversized for a three-line tip.
- **Depends on**: P1

## Existing installations / upgrade / rollback

Health gate: none (Terraform module consumed by source reference).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P1 | A consumer in user mode with `enable_branch_bypass = true` gets a plan-time error instead of whatever the apply did before. Organisation-mode consumers and user-mode consumers with the flag off see no change in plan. Surfaces read: the input variables `user`, `organization`, `enable_branch_bypass`; no state schema change, no resource address change. | none (Terraform module) | Reverting restores the permissive plan. It can't restore anything in state, because the validation removes nothing. A user-mode state that already holds `github_branch_protection.bypass` entries (unestablished whether one can exist) would have to set the flag to false, which plans their removal. | AC 1.1 and 1.2 |
| P2 | not applicable — touches no persisted state, consumer configuration key, invocation name or artifact path | | | |

## Dependency ordering

P1 → P2 (one dispatch, in that order).

## Risks

- **The validation rests on documentation, not on an observed apply.** Mitigation: the error message and the PR say so; the message tells a consumer for whom it did work to report it.
- **A precondition placed on a resource that needs provider data can't be tested without credentials.** Mitigation: attach it where it evaluates from input variables alone (the existing `terraform_data.owner_check` pattern at `main.tf:15-22`, or a variable-level cross-validation, which Terraform ≥ 1.9 allows — but `versions.tf` requires only ≥ 1.6, so the `terraform_data` precondition is the compatible form).
- **`terraform test` with `mock_provider` needs Terraform ≥ 1.7**, above the module's floor of 1.6. Mitigation: tests don't bind consumers; note the tool version in the test file or README. Local Terraform is 1.15.8.
- **No CI lane runs Terraform in this repository** (`build-static-tests.yaml` and `.pre-commit-config.yaml` name none). The test is run locally and its output recorded; wiring a lane is out of scope and would be filed.
- **Vale**: the PR check fails on an error on an added line and on more than 10 annotations; `docs/de/**` is exempt.
- Not a security-sensitive path: no workflow, no credential handling changes.

## Open questions

None blocking. AC1's variant was decided by the operator (validation from documentation).

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| 1.6 floor claim too wide: `init`/`validate` in the module directory fail under 1.6.6 on `mock_provider` | diff review @ d958d9f | fixed directly (da2e90b, wording sharpened in 37bc179) | reviewer ran Terraform 1.6.6: `Blocks of type "mock_provider" are not expected here`; as child module init and validate pass | none |
| bypass precondition also fired when both owners were set and advised "set `organization`" | diff review @ d958d9f | fixed directly (da2e90b) | plan with both owners + flag on showed both messages; after the fix only the owner message | none |
| message stated the inference from documentation as fact ("can't apply") | diff review @ d958d9f | fixed directly (da2e90b) | `main.tf:32` at d958d9f | none |
| Phase 0 row named only the organisation resources | diff review @ d958d9f | fixed directly (da2e90b) | `README.md:192` at d958d9f | none |
| test-file comments claimed more than measured ("every command", "only the owner precondition is meant to fire") | diff review @ da2e90b | fixed directly (37bc179) | 1.6.6 `plan`/`fmt`/`output` run without error; reverting the narrowing keeps the run green | none |
| no blocking findings; remaining non-blocking: long line `README.md:53`, the `null_resource` → `terraform_data` comment correction | diff review @ 37bc179 | dismissed (cosmetic; the comment correction is right) | — | none |
| `push_allowances = ["/${var.app_slug}"]` resolves a user login, not an App, per provider source `getNodeIDv4` — in organisation mode too | specialist result | to file (asserted from source, not observed; needs a decision on the App node id input) | read of integrations/github v6.12.1 `github/util_v4_branch_protection.go` by the specialist; no apply | to be filed |
| `plaintext_value` deprecated in provider 6.12.1 | specialist result | to file (outside the issue's files' purpose; changes a resource argument) | `terraform test` prints "Argument is deprecated … Use value." at `main.tf:106` | to be filed |
| no CI lane runs `terraform fmt/validate/test` | specialist result | to file (needs a workflow decision) | `grep -n terraform .github/workflows/build-static-tests.yaml .pre-commit-config.yaml` → nothing | to be filed |

## Dispatch log
2026-11-18 P1+P2 dispatched to nolte-engineering:fullstack-developer — implemented, d958d9f; review fixes da2e90b and 37bc179. No refutation of the plan; the specialist read the provider docs and source (v6.12.1): the provider doesn't check the owner type itself.
2026-11-18 verify — `terraform fmt -check -recursive`: rc 0; `terraform validate`: Success; `terraform test`: 4 passed, 0 failed; pre-commit on the changed files: passed; Vale on changed EN lines: 0 alerts. Diff review lane (b), independent read-only agent, three passes; final head 37bc179197d993e3f9ed61bcf43c1a0eeb6e55d7, 10 files, 0 blocking. Class sweep predicate (7 hits on origin/develop, 0 on HEAD) recorded in the PR draft.
