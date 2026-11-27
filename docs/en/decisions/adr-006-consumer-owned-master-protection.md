# ADR-006: Consumers declare their own master protection

**Status:** Accepted (2026-11-18) · **Issues:** [#481](https://github.com/nolte/gh-plumbing/issues/481), [#442](https://github.com/nolte/gh-plumbing/issues/442)

## Context

`commons-settings.yml` used to declare a `master` entry: `enforce_admins: true`,
no required checks, no required reviews. From 2020 until May 2026 the entry
carried `restrictions: null`. In that form it could apply, and the two
consumers that have a `master` branch, this repository and `esphome-configs`,
carry exactly that protection today.

Phase 2 of [#330](https://github.com/nolte/gh-plumbing/issues/330) replaced
`restrictions: null` with `restrictions.apps` naming `nolte-portfolio-app`
([#355](https://github.com/nolte/gh-plumbing/pull/355)), so that only the
portfolio App could push to `master`. GitHub accepts push restrictions only on
organisation-owned repositories, and every consumer belongs to the user
account `nolte`. The Settings App passes a branch entry to the update endpoint
as it stands. In that form GitHub rejects the whole `master` update, as it did
for `develop` ([#416](https://github.com/nolte/gh-plumbing/issues/416),
[ADR-005](adr-005-consumer-owned-develop-protection.md)). Nobody recorded the
rejection for `master` itself. This record rests on GitHub's documented limit
and on the `develop` case. ADR-005 left `master` for a follow-up, and this
record is that follow-up.

The documentation said `master` was push-restricted after phase 2. It wasn't.
This repository's own `master` still carries the protection from before phase
2, but since phase 2 no configuration that applies has declared it.

## Decision

Remove the `master` entry from the commons. The commons then declare no
`branches:` key at all. Each consumer that wants `master` protected declares a
complete `master` entry in its own `.github/settings.yml`, with all four fields
the API requires and `restrictions: null`.

This repository declares its own `master` entry with the values that are live
today, so applying it changes nothing.

## Alternatives considered

**Keep the entry and set `restrictions: null`.** Rejected, although it would
work: it restores the form the entry had until May 2026 and changes nothing
live on the two consumers that have a `master` branch. Three reasons outweigh
that. A commons entry races a consumer's own `master` entry when the App
concatenates arrays, as ADR-005 explains for `develop`. Most consumers have no
`master` branch, so the commons would send them an update for a branch that
doesn't exist. And one rule is easier to hold than two: since ADR-005 a
consumer owns its `develop` protection, and now it owns every branch.

**Keep the entry for organisation-owned consumers.** Rejected. The portfolio
has none, and a shared file can't make a field depend on who owns the
repository that extends it. The entry would keep failing everywhere it lands.

**Move the portfolio to an organisation.** Deferred, as in
[ADR-002](adr-002-branch-protection-verification.md) and ADR-005.

## Consequences

No live protection changes on any consumer. The Settings App updates only the
branches a configuration lists. It doesn't remove protection from a branch
that the configuration no longer lists. That follows from the App's source,
`lib/plugins/branches.js`. Nobody observed the hosted App doing it.

The same source shows a side effect. The App builds each branch update on top
of the previous one, so an entry that leaves out a required field inherits it
from the entry before. A consumer whose `develop` entry omits
`required_pull_request_reviews` got that field from the commons `master` entry
until now. Without it, GitHub rejects the `develop` protection update in that
consumer's next settings sync until its entry is complete. Repository settings
and labels in the same sync still apply. `kamerplanter` is the known case; ADR-005 already names
the missing field.

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
