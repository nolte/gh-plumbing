# Decisions

Architecture decision records for choices that reach beyond this repository.

`gh-plumbing` is a configuration-only library. Its reusable workflows and Probot
commons run inside every consumer repository, so a decision here changes other
people's CI without their involvement. These records exist so a consumer can
find out why, without reading a closed issue thread.

Decisions that only affect this repository stay in their issue. A record lands
here when it changes what consumers inherit.

| Record | Subject | Status |
|---|---|---|
| [ADR-001](adr-001-presentation-branch-reset.md) | Reset the presentation branch to the release tag | Accepted |
| [ADR-002](adr-002-branch-protection-verification.md) | Verify branch protection before changing its defaults | Accepted |
| [ADR-003](adr-003-workflow-validation-gate.md) | Gate workflow validity on a required check | Accepted |
| [ADR-004](adr-004-spec-drift-routing.md) | Route the Q2 spec-drift cluster through the roadmap | Accepted |

## Format

Each record states the context, the decision, the alternatives that lost, and
the consequences a consumer should expect. The GitHub issue linked from each
record carries the acceptance criteria and the implementation trail.
