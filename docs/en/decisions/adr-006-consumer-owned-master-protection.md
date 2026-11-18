# ADR-006: Consumers declare their own master protection

**Status:** Accepted (2026-11-18) · **Issues:** [#481](https://github.com/nolte/gh-plumbing/issues/481), [#442](https://github.com/nolte/gh-plumbing/issues/442)

## Context

`commons-settings.yml` used to declare a `master` entry: `enforce_admins: true`,
no required checks, no required reviews, and `restrictions.apps` naming
`nolte-portfolio-app`. Phase 2 of
[#330](https://github.com/nolte/gh-plumbing/issues/330) added the restriction
so that only the portfolio App could push to `master`.

The entry never worked on any consumer of this portfolio. GitHub accepts push
restrictions only on organisation-owned repositories, and every consumer
belongs to the user account `nolte`. The Settings App passes a branch entry to
the update endpoint as it stands, so GitHub rejects the whole `master` update
with 422. That's the failure
[ADR-005](adr-005-consumer-owned-develop-protection.md) describes for
`develop`. ADR-005 left `master` for a follow-up, and this record is that
follow-up.

The documentation said `master` was push-restricted after phase 2. It wasn't.
This repository's own `master` has protection that includes admins and
blocks force pushes and deletions, but no configuration that applies declared
that state.

## Decision

Remove the `master` entry from the commons. The commons then declare no
`branches:` key at all. Each consumer that wants `master` protected declares a
complete `master` entry in its own `.github/settings.yml`, with all four fields
the API requires and `restrictions: null`.

This repository declares its own `master` entry with the values that are live
today, so applying it changes nothing.

## Alternatives considered

**Keep the entry and set `restrictions: null`.** Rejected. The entry would
then apply for the first time, on every consumer at once. It would enforce
`enforce_admins` on each consumer's `master` and replace whatever protection a
consumer has there with the commons' values, because the update replaces the
whole protection of a branch. Nobody asked for that change. A commons entry
also races a consumer's own `master` entry when the App concatenates arrays,
as ADR-005 explains for `develop`.

**Keep the entry for organisation-owned consumers.** Rejected. The portfolio
has none, and a shared file can't make a field depend on who owns the
repository that extends it. The entry would keep failing everywhere it lands.

**Move the portfolio to an organisation.** Deferred, as in
[ADR-002](adr-002-branch-protection-verification.md) and ADR-005.

## Consequences

No live protection changes on any consumer. The removed entry applied nothing,
and the Settings App updates only the branches a configuration lists. It
doesn't remove protection from a branch that the configuration no longer
lists.

A consumer that wants `master` protected declares the whole entry:

```yaml title=".github/settings.yml"
branches:
  - name: master
    protection:
      required_pull_request_reviews: null
      required_status_checks: null
      enforce_admins: true
      restrictions: null
```

The update replaces the branch's whole protection. Fields the entry leaves
out, such as `allow_force_pushes` and `allow_deletions`, take the API default
`false`. A consumer whose `master` needs a different value has to declare it.
An organisation-owned consumer that wants only the App to push declares
`restrictions.apps` in its own entry.

`reusable-release-cd-refresh-master.yml` reads the target's protection and
rulesets and picks its write strategy from them
([ADR-001](adr-001-presentation-branch-reset.md)). Nothing it reads changes,
so it behaves as before. Where the `GITHUB_TOKEN` fallback could push to
`master` before, it still can.

A test in `scripts/tests/test_required_check_triggers.py` fails when a
commons branch entry that carries `restrictions` comes back. After a consumer
changes its entry, verify the result through the API, not the settings page.
