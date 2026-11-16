# Release-Archive

`reusable-release-archive.yml` baut ein Release-Archiv über ein Task-Target in
deinem Repository, attestiert seine Build-Provenance und hängt es an den
Release-Drafter-Entwurf, **bevor** das Release veröffentlicht wird. Das Release
ist so nie ohne sein Asset öffentlich, und der Weg funktioniert auch noch, wenn
GitHub Immutable Releases aktiviert sind.

Rufe ihn vor `reusable-release-publish.yml` auf und ordne den Publish-Job per
`needs:` dahinter ein.

## Verwendung

```yaml title=".github/workflows/release-publish.yml"
name: Release Publish

on:
  workflow_dispatch:
    inputs:
      tag:
        description: "Tag to publish. Leave empty to use the single open draft."
        required: false
        type: string
        default: ""
      dry_run:
        description: "Validate without publishing."
        required: false
        type: boolean
        default: false

permissions:
  contents: read

jobs:
  archive:
    permissions:
      contents: write
      id-token: write
      attestations: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-archive.yml@<tag>
    with:
      tag: ${{ inputs.tag }}
      task-target: build
      assets: |
        build/nolte-styles.zip
      dry-run: ${{ inputs.dry_run }}

  publish:
    needs: archive
    permissions:
      contents: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-publish.yml@<tag>
    with:
      tag: ${{ needs.archive.outputs.tag }}
      dry_run: ${{ inputs.dry_run }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

!!! danger "Der aufrufende Job muss `contents`, `id-token` und `attestations` mit Schreibrecht gewähren"

    Fehlt eines davon, **startet der Workflow nicht**. Er weicht nicht auf ein
    Archiv ohne Provenance aus und läuft auch nicht mit einem eingeschränkten
    Token: GitHub meldet `startup_failure` mit null Jobs.

    Dieser Fehler sieht aus, als wäre nichts passiert, und er tritt mitten im
    Release auf. Vergib die Rechte am **Job**, der den Workflow aufruft, nicht
    am ganzen Workflow, gemäß `spec/project/github-actions-best-practices` §B
    und §H. Ein Repository, das diesen Workflow nicht aufruft, braucht keine
    neue Berechtigung.

## Inputs

| Input | Standard | Wirkung |
| --- | --- | --- |
| `task-target` | Pflicht | Task-Target, das das Archiv baut; läuft am Ziel-Commit des Entwurfs |
| `assets` | Pflicht | Pfade oder Globs der anzuhängenden Dateien, je Zeile einer; `**` passt über Verzeichnisse hinweg |
| `tag` | leer | Entwurf, an den angehängt wird; leer wählt den einzigen offenen Entwurf |
| `task-version` | `3.52.0` | Exaktes Task-Release, das das Target ausführt |
| `dry-run` | `false` | Bauen und attestieren, nichts hochladen |

Der Workflow gibt den aufgelösten `tag` und die angehängten Dateinamen als
`assets` zurück.

## Was der Workflow garantiert

- **Jedes Muster trifft.** Ein Muster ohne Treffer bricht den Lauf ab, bevor
  etwas hochgeladen wird; der Publish-Job startet dann nicht. Die Dateinamen
  der Treffer müssen eindeutig sein, weil ein Release Assets nach Namen
  speichert.
- **Erst attestieren, dann hochladen.** Jede Datei wird attestiert, bevor der
  Upload-Schritt läuft. Schlägt die Attestierung fehl, stoppt der Job, und
  nichts erreicht den Entwurf.
- **Nur Entwürfe.** Ein `tag`, der ein veröffentlichtes Release benennt,
  bricht den Lauf vor dem Build ab. Direkt vor dem Upload prüft der Workflow
  den Entwurfsstatus erneut, falls das Release während des Builds
  veröffentlicht wurde.
- **Release-Metadaten bleiben unverändert.** Der Workflow ändert nie Text,
  Namen oder die Draft- und Prerelease-Flags. Ein erneuter Lauf ersetzt
  gleichnamige Assets im Entwurf.
- **Der Build hat keine Schreibrechte.** Das Task-Target läuft in einem Job
  mit lesendem `contents` und ohne OIDC-Token. Nur der Job, der attestiert und
  hochlädt, hält die Schreibrechte.

!!! note "Das Ziel des Entwurfs wird hier nicht gegen `develop` geprüft"

    `reusable-release-publish.yml` veröffentlicht keinen Entwurf, dessen Ziel
    von `develop` aus nicht erreichbar ist. Diese Prüfung läuft im
    Publish-Job, nach diesem.

## Entfernte Taskfile-Includes

Der Workflow setzt `TASK_X_REMOTE_TASKFILES=1` und ruft `task --yes` auf. Ein
Taskfile mit entfernten Includes funktioniert so ohne Terminal.

## Ein Archiv prüfen

```sh
gh attestation verify nolte-styles.zip --repo <owner>/<repo>
```

!!! note "Eine Attestierung belegt die Herkunft, nicht die Sicherheit"

    Sie zeigt, welcher Workflow, Commit und Runner ein Archiv erzeugt hat. Sie
    sagt nichts darüber, ob das Archiv frei von Schwachstellen ist.

## Selbsttest

`test-release-archive.yml` prüft den Workflow gegen Wegwerf-Entwürfe, die er
selbst anlegt und löscht; der echte Release-Drafter-Entwurf bleibt unberührt.
Pull Requests, die den Workflow ändern, führen das Positiv-Szenario aus. Die
Negativ-Szenarien laufen nur über `workflow_dispatch`, und ihr Lauf ist
absichtlich rot: Das Ergebnis trägt der Job `verify`.
