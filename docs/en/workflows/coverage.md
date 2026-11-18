# Coverage

Runs a project's tests and surfaces the coverage report in the GitHub Actions job summary, so consumers see coverage without an external service. Two variants cover the common ecosystems.

- [`reusable-python-coverage.yaml`](#python): `pytest` with `pytest-cov`
- [`reusable-nodejs-coverage.yaml`](#nodejs): `Vitest` or Jest via the Istanbul `json-summary` report

Both render a Markdown table into `$GITHUB_STEP_SUMMARY` (even when the tests fail) and expose an optional `fail-under` gate.

Neither workflow persists the checkout token (`persist-credentials: false`), so the install and test commands can't read it. A command that fetches from `origin` therefore works only in a public repository.

---

## Python

```yaml title=".github/workflows/coverage.yaml"
jobs:
  coverage:
    uses: nolte/gh-plumbing/.github/workflows/reusable-python-coverage.yaml@<tag>
    with:
      coverage-source: my_package
      fail-under: 80
```

!!! tip "Requirements"
    The `install-command` (default `pip install -e .[test]`) must pull in `pytest` and `pytest-cov`. Coverage is rendered via `coverage report --format=markdown`, which needs Coverage.py ≥ 7.0 (shipped with current `pytest-cov`).

---

## Node.js

```yaml title=".github/workflows/coverage.yaml"
jobs:
  coverage:
    uses: nolte/gh-plumbing/.github/workflows/reusable-nodejs-coverage.yaml@<tag>
    with:
      fail-under: 80
```

The workflow turns off the built-in npm cache of `actions/setup-node` (`package-manager-cache: false`). The action saves that cache after the install and test commands ran, so those commands could change what later runs restore, on the default branch included. Each run installs the dependencies without a restored npm cache.

!!! tip "json-summary report"
    The `test-command` (default `npm test`) must write an Istanbul `json-summary` report to `coverage-summary-path` (default `coverage/coverage-summary.json`). Both `Vitest` (`--coverage.reporter=json-summary`) and Jest (`--coverageReporters=json-summary`) emit this format.

---

## Central configuration

=== "Python coverage workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-python-coverage.yaml"
    %}
    ```

=== "Node.js coverage workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-nodejs-coverage.yaml"
    %}
    ```
