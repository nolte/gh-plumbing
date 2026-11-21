# Coverage

Führt die Tests eines Projekts aus und stellt den Coverage-Bericht in der Job-Zusammenfassung von GitHub Actions dar, sodass Konsumenten die Testabdeckung ohne externen Dienst sehen. Zwei Varianten decken die gängigen Ökosysteme ab.

- [`reusable-python-coverage.yaml`](#python) — pytest mit pytest-cov
- [`reusable-nodejs-coverage.yaml`](#nodejs) — Vitest oder Jest über den Istanbul-`json-summary`-Bericht

Beide schreiben die Coverage in `$GITHUB_STEP_SUMMARY` — auch wenn die Tests fehlschlagen — und bieten ein optionales `fail-under`-Gate. Die Python-Variante zeigt den Textbericht als einen vorformatierten Block, die Node.js-Variante eine Tabelle, deren Werte als Inline-Code erscheinen. Beide kodieren den Text aus dem Testlauf vorher, sodass ein Dateiname oder ein Wert keinen Link, kein Bild und keine Tabellenzelle in die Zusammenfassung einfügen kann.

Keiner der beiden Workflows persistiert das Checkout-Token (`persist-credentials: false`), damit die Install- und Test-Befehle es nicht lesen können. Ein Befehl, der von `origin` fetcht, funktioniert deshalb nur in einem öffentlichen Repository.

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

!!! tip "Voraussetzungen"
    Das `install-command` (Standard `pip install -e .[test]`) muss `pytest` und `pytest-cov` mitbringen. Die Zusammenfassung zeigt die Ausgabe von `coverage report --format=text`, was Coverage.py ≥ 7.0 voraussetzt (im aktuellen `pytest-cov` enthalten).

---

## Node.js

```yaml title=".github/workflows/coverage.yaml"
jobs:
  coverage:
    uses: nolte/gh-plumbing/.github/workflows/reusable-nodejs-coverage.yaml@<tag>
    with:
      fail-under: 80
```

Der Workflow schaltet den eingebauten npm-Cache von `actions/setup-node` ab (`package-manager-cache: false`). Eingeschaltet nutzt die Action diesen Cache, wenn die `package.json` des Aufrufers npm als Paketmanager nennt. Sie speichert ihn dann, nachdem die Install- und Test-Befehle gelaufen sind, sodass diese Befehle verändern könnten, was spätere Läufe wiederherstellen, auch auf dem Default-Branch. Jeder Lauf installiert die Abhängigkeiten ohne wiederhergestellten npm-Cache.

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
