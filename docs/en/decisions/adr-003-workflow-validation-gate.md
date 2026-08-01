# ADR-003: Gate workflow validity on a required check

**Status:** Accepted (2026-08-01) · **Issue:** [#398](https://github.com/nolte/gh-plumbing/issues/398)

## Context

`reusable-hacs-validate.yaml` failed GitHub's workflow validation for five
weeks. It used an expression in a step's `uses:` keyword, which GitHub Actions
doesn't support, so the file never parsed and the workflow never ran. No
consumer could call it.

GitHub does report this. It creates a run named after the file path, carrying
zero jobs. That run sat red on `develop` from 2026-06-26 onward. It went
unnoticed because it blocks nothing, it's named after a path rather than a
workflow, and it only reappears when the file itself changes.

The signal existed. Nothing acted on it.

## Decision

Add `reusable-actionlint.yaml`, wire it into `build-static-tests.yaml`, and add
its job name to the required status checks for `develop`.

Separately, repair the broken file by pinning the action digest directly and removing
the input that fed the unsupported expression. That input existed only to feed
it, so no version of the file keeps both.

## Alternatives considered

**Add the check without making it required.** Rejected on this issue's own
evidence. A non-blocking signal already existed and was ignored for five weeks.
A second one would reproduce the failure with better tooling.

**Watch the existing validation runs instead.** Rejected. It relies on someone
looking, which is what failed here. `actionlint` also catches more: invalid
expression contexts, unknown `uses:` shapes, shell issues in `run:` blocks, and
type errors in inputs.

**Keep the broken input as a deprecated no-op.** Rejected. A deprecation shim
protects working callers, and there were none.

## Consequences

The check ships as a reusable workflow rather than as inline steps, so consumers
inherit it. A shared workflow library that lints only its own workflows would
repeat this fault one level up.

The first run will find more than one broken file. Thirty workflow files have
never been linted. The reusable therefore lands first, the tree gets clean, and
the required context comes last. Adding the context first would block every pull
request on unrelated findings.

Consumers gain a check that fails a pull request whose workflow files don't
parse. Repositories that already carry invalid workflow files will see them.
