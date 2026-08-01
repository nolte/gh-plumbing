# ADR-004: Route the Q2 spec-drift cluster through the roadmap

**Status:** Accepted (2026-08-01) · **Issue:** [#386](https://github.com/nolte/gh-plumbing/issues/386)

## Context

The 2026-Q2 spec-drift audit of `nolte/claude-shared` left a cluster of findings
that belong in this repository rather than in a consumer. Building a reference
to a reusable workflow that doesn't exist would break a consumer's CI, so the
work has to happen upstream first.

The cluster spans four separate outcomes:

1. a PR-lint reusable workflow, plus adoption by consumers and a new required check
2. five hardening items on `reusable-release-publish.yml`, several of them gates
3. two pre-release gates, for documentation freshness and release-notes prose
4. an `exp/` `autolabeler` in the release-drafter commons

## Decision

Create a roadmap item for outcomes one to three and decompose it into features.
Ship the `exp/` `autolabeler` entry separately, ahead of that work.

## Alternatives considered

**Split into four issues and work them individually.** Rejected. The issue-
orchestration spec routes work spanning more than one outcome into the planning
layer. Four issues worked one at a time would bypass it.

**Implement the release hardening first and plan the rest later.** Rejected. It
mixes routes, and the spec forbids a partial implementation that leaves the
remainder unplanned.

## Consequences

All three roadmap items in this repository carry `status: done`, so this needs a
new one rather than a change to an existing one.

The `exp/` `autolabeler` entry is one addition to a single commons file. It depends on
nothing else in the cluster and nothing depends on it. Inside a collective item
it would wait for a sprint it doesn't need. Pulling it forward is a scope
decision recorded here, not an unplanned remainder.

Two dependencies matter when the work gets planned. The release hardening bears
on a pending major release, and two of its items guard against faults that have
already occurred once. The PR-lint check adds a required status context, which
[ADR-002](adr-002-branch-protection-verification.md) shows can't yet be proven
to take effect.
