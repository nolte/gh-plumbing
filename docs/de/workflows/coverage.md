# Coverage

Führt die Tests eines Projekts aus und stellt den Coverage-Bericht in der Job-Zusammenfassung von GitHub Actions dar, sodass Konsumenten die Testabdeckung ohne externen Dienst sehen. Zwei Varianten decken die gängigen Ökosysteme ab.

- [`reusable-python-coverage.yaml`](#python) — pytest mit pytest-cov
- [`reusable-nodejs-coverage.yaml`](#nodejs) — Vitest oder Jest über den Istanbul-`json-summary`-Bericht

Beide rendern eine Markdown-Tabelle in `$GITHUB_STEP_SUMMARY` — auch wenn die Tests fehlschlagen — und bieten ein optionales `fail-under`-Gate.

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

!!! tip "Voraussetzungen"
    Das `install-command` (Standard `pip install -e .[test]`) muss `pytest` und `pytest-cov` mitbringen. Die Coverage wird über `coverage report --format=markdown` gerendert, was Coverage.py ≥ 7.0 voraussetzt (im aktuellen `pytest-cov` enthalten).

---

## Node.js

```yaml title=".github/workflows/coverage.yaml"
jobs:
  coverage:
    uses: nolte/gh-plumbing/.github/workflows/reusable-nodejs-coverage.yaml@develop
    with:
      fail-under: 80
```

!!! tip "json-summary-Bericht"
    Das `test-command` (Standard `npm test`) muss einen Istanbul-`json-summary`-Bericht nach `coverage-summary-path` (Standard `coverage/coverage-summary.json`) schreiben. Sowohl Vitest (`--coverage.reporter=json-summary`) als auch Jest (`--coverageReporters=json-summary`) erzeugen dieses Format.

---

## Zentrale Konfiguration

=== "Python-Coverage-Workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-python-coverage.yaml"
    %}
    ```

=== "Node.js-Coverage-Workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-nodejs-coverage.yaml"
    %}
    ```
