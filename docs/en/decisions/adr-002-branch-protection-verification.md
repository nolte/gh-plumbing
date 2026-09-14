# ADR-002: Verify branch protection before changing its defaults

**Status:** Accepted (2026-08-01) · **Issue:** [#387](https://github.com/nolte/gh-plumbing/issues/387)

## Context

Branch protection declared in `.github/settings.yml` is often not applied. The
declaration looks correct, the Probot Settings App reports nothing, and the
protection is absent. A survey of nine consumers on 2026-07-26 found five that
drift, in at least three different shapes.

One cause is confirmed. The commons declare `restrictions.apps` for `develop`
and `master`. GitHub accepts push restrictions only on organisation-owned
repositories, and `nolte` is a user account. The Settings App drops the whole
protection update rather than skipping the one unsupported field.

That cause doesn't explain the rest. Three repositories declare
`restrictions: null` and still have no protection at all. One has protection
with zero contexts despite declaring one. Another receives three of its four
declared contexts.

## Decision

Build a check that compares declared protection against live protection across
the portfolio, and run it on a schedule. Decide what to change in the commons
afterwards, using its output.

## Alternatives considered

**Remove `restrictions` from the `develop` commons now.** Rejected for the
moment. It would close this repository's case and leave four unexplained ones
untouched, while looking like the problem was solved.

**Have every consumer declare `restrictions: null`.** Rejected. It repeats
boilerplate in every repository, and forgetting it fails silently, which is the
mechanism that caused this.

**Move the portfolio to an organisation.** Deferred. It would make
`restrictions.apps` work as designed, but its consequences reach well beyond
branch protection.

## Consequences

The defining property of this class of fault is invisibility. There is no error,
no log, and no failed check. The repository looks configured and isn't. Nobody
notices until a merge that should have been blocked goes through. A comparison
check addresses that property rather than one instance of it.

Until the check exists, any claim that a required status check is active in this
portfolio is unproven. [ADR-003](adr-003-workflow-validation-gate.md) adds a
required check and therefore inherits this doubt. Its acceptance criteria call
for verification through the API rather than the settings page.

The open question of whether `restrictions` on `develop` serves any purpose
stays open. The commons justify it for `master`, where the release cascade
pushes with an App token. That reasoning doesn't obviously transfer.
