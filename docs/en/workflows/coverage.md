# Coverage

Runs a project's tests and surfaces the coverage report in the GitHub Actions job summary, so consumers see coverage without an external service. Two variants cover the common ecosystems.

- [`reusable-python-coverage.yaml`](#python): `pytest` with `pytest-cov`
- [`reusable-nodejs-coverage.yaml`](#nodejs): `Vitest` or Jest via the Istanbul `json-summary` report

Both render a Markdown table into `$GITHUB_STEP_SUMMARY` (even when the tests fail) and expose an optional `fail-under` gate.

---

## Python

```yaml title=".github/workflows/coverage.yaml"
jobs:
  coverage:
    uses: nolte/gh-plumbing/.github/workflows/reusable-python-coverage.yaml@develop
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
    uses: nolte/gh-plumbing/.github/workflows/reusable-nodejs-coverage.yaml@develop
    with:
      fail-under: 80
```

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
