# ADR-001: Choose the presentation-branch write strategy from the target

**Status:** Revised (2026-09-14) · **Issues:** [#384](https://github.com/nolte/gh-plumbing/issues/384), [#414](https://github.com/nolte/gh-plumbing/issues/414)

!!! warning "What this revision changes"
    The original decision—always reset with a force-with-lease push—held
    that one strategy could serve every presentation branch. It can't. The
    reset solves a linear-history ruleset and is itself rejected by a branch
    that forbids force pushes, which is the configuration this repository's own
    `master` carries. Two releases published green while `master` stayed on
    `v1.1.26`. The decision below now selects per target; the original text is
    kept under "Superseded decision" because its reasoning still explains why
    the merge alone isn't enough either.

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

Two real consumer configurations forbid opposite things:

| Target rule | Forbids | Breaks |
|---|---|---|
| linear history | merge commits | the `/merges` API call |
| no force pushes | history rewrites | the force-with-lease push |
| `pull_request` ruleset rule | every direct write | both |

A survey of the four presentation branches in the portfolio found three
carrying a `pull_request` rule, and two of those with **no bypass actor at
all**—no credential this workflow can hold will write to them.

## Decision

Read the target's protection and pick the strategy from it:

- **merge commits permitted** → the `/merges` API. Preferred when both work,
  because it adds to the branch instead of rewriting it.
- **merge forbidden, force push permitted** → force-with-lease push of the
  release tag, the strategy this ADR originally chose.
- **neither** → refuse, with a diagnosis naming the rule that blocked it, and
  fail the run.

Both mechanisms are consulted, because classic branch protection and rulesets
are independent and either can forbid either operation. An unreadable endpoint
counts as restrictive rather than permissive: assuming "unprotected" from a
failed read is the mistake [#421](https://github.com/nolte/gh-plumbing/issues/421)
found in the branch-protection audit.

## Alternatives considered

**Exempt the release App from the ruleset.** Rejected in the original decision,
and still rejected as the *only* answer—it hollows out a rule the consumer set
deliberately and has to be repeated in every repository. It remains the right
operator action for a specific target, and the refusal message says so.

**Document that consumers must not apply a linear-history ruleset.** Rejected.
It moves a constraint onto the consumer instead of repairing the shared tool.

**Retire the cascade and point consumers at the release tag.** Considered in
[#414](https://github.com/nolte/gh-plumbing/issues/414) and not chosen here. It
removes the whole class of failure rather than routing around it, but it changes
what `master` means portfolio-wide, which is a larger decision than the one this
ADR governs.

**Fast-forward only.** Rejected. It works only if the presentation branch never
diverges, and this repository's `master` already carries synthetic merge commits
that `develop` never had.

## Consequences

The failure is now loud. A target the workflow can't write to fails the run
with the blocking rule named, instead of leaving a stale presentation branch
behind a green release—the state `v2.0.0` and `v2.0.1` both reached, and which
went unnoticed for six weeks.

Consumers whose presentation branch allows merge commits stop seeing a history
rewrite at each release; they get a merge commit again, as before #404. Only the
branches that forbid merges keep the rewrite.

Dropping `devmasx/merge-branch` survives the revision: the merge path calls the
`/merges` API directly, so the third-party action stays out of a step holding
`contents: write` against a protected branch.

Anyone holding local commits on a presentation branch still needs to move them
before a release. That branch is documented as automatically refreshed and not a
place to commit to, and the reset path still rewrites it.

## Superseded decision (2026-08-01)

Kept because its reasoning still explains why a merge alone isn't enough
either—a linear-history ruleset rejects the `/merges` call outright:

> Replace the merge with a force-with-lease push of the release tag onto the
> target branch. The lease value comes from reading the target ref immediately
> before the push, so a concurrent update aborts instead of losing data.

Its stated consequences turned out to hold only for a target that permits force
pushes: that the presentation branch becomes an exact mirror of the release tag,
and that the reset discards the synthetic merge commits the old mechanism
produced. On a target that forbids force pushes, none of it happened—the push
was rejected and the branch stayed where it was.
