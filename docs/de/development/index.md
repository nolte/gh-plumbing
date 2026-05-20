# Entwicklung

Lokale Entwicklungsumgebung für Beiträge zu `gh-plumbing` selbst.

---

## Tooling

Das Projekt pinnt seine Tools mit [asdf](https://asdf-vm.com/) (`.tool-versions`).

```sh
asdf install
```

Damit werden `act`, `python` und `task` in den gepinnten Versionen installiert.

---

## Übliche Tasks

Die geteilte Sammlung [nolte/taskfiles](https://github.com/nolte/taskfiles) liefert die Task-Definitionen.

```sh
task -l
```

=== "Pre-Commit"

    ```sh
    task pre-commit:install   # Hooks registrieren
    task pre-commit:start     # gegen alle Dateien ausführen
    ```

=== "Dokumentation"

    ```sh
    task mkdocs:start         # auf http://localhost:8001 serven
    ```

!!! note "Ohne task"
    Wer rohe Kommandos bevorzugt:

    ```sh
    virtualenv ~/.vens/development
    source ~/.vens/development/bin/activate
    pip install -r requirements-dev.txt
    mkdocs serve -a localhost:8001
    ```

---

## Workflows lokal ausführen

Mit [nektos/act](https://github.com/nektos/act) lassen sich GitHub Actions lokal ausführen:

```sh
act push -j static -W .github/workflows/build-static-tests.yaml
```

---

## Prose-Linting

[Vale](https://vale.sh/) prüft Markdown-Dateien im CI über `reusable-spelling-vale.yaml`. Die Regeln liegen in `.vale.ini`, die Styles unter `.github/styles/`.

!!! info "CLAUDE.md ist ausgenommen"
    `CLAUDE.md` trägt LLM-Kontext, keine Endnutzer-Dokumentation — Vale überspringt die Datei bewusst.
