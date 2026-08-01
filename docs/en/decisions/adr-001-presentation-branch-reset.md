# ADR-001: Reset the presentation branch to the release tag

**Status:** Accepted (2026-08-01) · **Issue:** [#384](https://github.com/nolte/gh-plumbing/issues/384)

## Context

After a release, `reusable-release-cd-refresh-master.yml` updates the
presentation branch (`main` or `master`) so it tracks the newest release. It did
this with `devmasx/merge-branch`, which calls the GitHub `merges` API. That API
creates a merge commit.

A consumer whose presentation branch carries a linear-history ruleset rejects
that call:

```text
POST /repos/nolte/workstation/merges: 409
This branch must not contain merge commits.
```

The release itself publishes and the docs deploy. Only the presentation branch
stays stale, so the failure is easy to miss.

The branch also drifts. In this repository `master` carries synthetic merge
commits that never existed on `develop`, and `master` isn't an ancestor of
`develop`. A plain fast-forward push is therefore rejected as well.

## Decision

Replace the merge with a force-with-lease push of the release tag onto the
target branch. The lease value comes from reading the target ref immediately
before the push, so a concurrent update aborts instead of losing data.

## Alternatives considered

**Exempt the release App from the ruleset.** Rejected. It hollows out a rule the
consumer set deliberately, and it has to be repeated in every repository.

**Document that consumers must not apply a linear-history ruleset.** Rejected.
It moves a constraint onto the consumer instead of repairing the shared tool.

## Consequences

The presentation branch becomes an exact mirror of the release tag, which is
what it always claimed to be. The reset discards the synthetic merge commits the
old mechanism produced. Nothing references them.

The workflow no longer depends on `devmasx/merge-branch`, which removes one
third-party action from a step holding `contents: write` against a protected
branch.

Consumers see a history rewrite on the presentation branch at the next release.
That branch is documented as automatically refreshed and not a place to commit
to, so no work should be lost. Anyone holding local commits there needs to move
them first.
