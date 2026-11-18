# ADR-005: Consumers declare their own complete develop protection

**Status:** Accepted (2026-11-17) · **Issues:** [#442](https://github.com/nolte/gh-plumbing/issues/442), [#387](https://github.com/nolte/gh-plumbing/issues/387)

## Context

`commons-settings.yml` used to declare a `develop` entry with
`restrictions.apps` and empty required contexts. That entry can't be right for
any consumer of this portfolio, for two reasons.

First, GitHub accepts push restrictions only on organisation-owned
repositories, and every consumer belongs to the user account `nolte`. The
Settings App passes `restrictions` through unchanged, so the update for that
branch fails with 422. It doesn't skip the one field and carry on.

Second, the current Settings App source merges `_extends` with
`@fastify/deepmerge`. That library ignores the App's `arrayMerge` option and
concatenates arrays. A commons `develop` entry then reaches the API next to
the consumer's own entry, both updates run in parallel, and the last write
wins. With `contexts: []` the commons entry can wipe a consumer's required
checks.

The hosted App behaves differently today. On 2026-11-17 this repository's
`develop` entry lacked `enforce_admins` and `required_pull_request_reviews`,
two fields the API requires, yet its contexts applied. Only a merge with the
commons entry by `name` explains that. The race is therefore latent, and it
becomes real the day the hosted App runs the current source.

This record answers the question
[ADR-002](adr-002-branch-protection-verification.md) left open, whether
`restrictions` on `develop` buys anything. It doesn't. On a user-owned
repository GitHub rejects it with 422. Classic push restrictions also never
grant a bypass of required checks. They only narrow who may push. Whether the
portfolio App may push to `develop` when it aligns release versions depends on
`develop`'s own branch protection and rulesets.

## Decision

Remove the `develop` entry from the commons. Each consumer declares a complete
`develop` entry in its own `.github/settings.yml`, with all four fields the API
requires and `restrictions: null`.

This gives the same result whether the App concatenates arrays or merges them
by `name`. For `develop`, it records option 2 of
[#387](https://github.com/nolte/gh-plumbing/issues/387): fix the default.
The `master` entry is out of scope and stays for a follow-up.

## Alternatives considered

**Keep the `develop` entry and set `restrictions: null`.** Rejected. Under
concatenation it keeps the race alive. It also adds `develop` protection with
no contexts to every consumer that declares no entry of its own.

**Drop only `required_status_checks` from the commons entry.** Rejected. The
remaining entry is an incomplete payload and fails with 422. Under a merge by
`name` it still supplies fields that consumers come to depend on without
noticing.

**Fix the merge upstream in the Settings App.** Passing `mergeArray` to the
merge library would restore merging by `name`. Worth proposing, but it isn't
under this portfolio's control.

**Move the portfolio to an organisation.** Deferred, as in ADR-002.

## Consequences

Option 1 of #387, a `restrictions: null` line in every consumer, becomes the
rule in a wider form. Each consumer already had to declare its own contexts.
It now declares the whole entry:

```yaml title=".github/settings.yml"
branches:
  - name: develop
    protection:
      required_pull_request_reviews: null
      required_status_checks:
        strict: true
        contexts:            # your own required checks
          - static / Static CI Tests
      enforce_admins: true
      restrictions: null
```

Consumers with a complete `develop` entry see no change. Consumers with no
`develop` entry received nothing from the commons before either, because the
update failed with 422.

Two consumers have an incomplete entry. `kamerplanter` omits
`required_pull_request_reviews` and relied on the merge with the commons to
fill it in. Its `develop` sync fails until it adds
`required_pull_request_reviews: null`. `kamerplanter-android` declares only
`required_status_checks` and was already failing, because it inherited
`restrictions.apps`. A failed sync doesn't remove live protection, but no later
change applies.

`scripts/branch_protection_audit.py` reports a `develop` entry that omits one
of the four fields (`null` counts as present) and a branch that both the
repository and the commons declare. The weekly portfolio audit therefore
surfaces both consumers. After a consumer changes its entry, verify the result
through the API, not the settings page.

This record changes nothing for `master`.
[ADR-006](adr-006-consumer-owned-master-protection.md) covers `master`.
