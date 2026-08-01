# Container-Images

Zwei Reusables decken die Container-Arbeit ab. `reusable-docker-lint-build.yaml`
lintet das Dockerfile und baut es für Pull-Request-Feedback ohne Push.
`reusable-docker-publish.yaml` baut ein Multi-Architektur-Image, pusht es in eine
Registry und attestiert dessen Build-Provenance.

## Verwendung

```yaml
name: Release Deliver Docker

on:
  release:
    types: [published]

permissions:
  contents: read

jobs:
  publish:
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-docker-publish.yaml@<tag>
    with:
      image_name: my-service
      context: "."
      dockerfile: Dockerfile
      platforms: linux/amd64,linux/arm64
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

!!! danger "Der aufrufende Job muss `id-token` und `attestations` gewähren"

    Ohne sie **startet der Workflow nicht**. Er weicht nicht auf ein Image ohne
    Provenance aus und läuft auch nicht mit eingeschränktem Token: GitHub meldet
    `startup_failure` mit null Jobs.

    Dieser Fehler sieht aus, als sei überhaupt nichts passiert, und er tritt
    während eines Releases auf — also leicht zu übersehen. Gewähre beide Scopes,
    bevor du auf eine attestierende Version des Reusables bumpst.

    Beide gehören an den **Job**, nicht an den Workflow. `id-token` ist eine
    Signatur-Identität, und genau deren Ausweitung über den benötigenden Job
    hinaus verbietet `spec/project/github-actions-best-practices` §H.

## Build-Provenance

Der Publish-Workflow hält fest, wie jedes Image gebaut wurde, über GitHubs eigenen
Attestation-Mechanismus mittels
[`actions/attest-build-provenance`](https://github.com/actions/attest-build-provenance).
Die Plattform erzeugt und signiert den Nachweis unabhängig vom Build.

Diese Unabhängigkeit ist der Kern. Ein Build, der seine eigene Integrität
bezeugt, kann seine eigene Kompromittierung nicht erkennen — deshalb verlangt
`spec/project/continuous-delivery/` §C, dass die Pipeline den Nachweis erzeugt
und nicht der Build. Frühere Versionen dieses Workflows nutzten BuildKits
`provenance`-Ausgabe, die vom attestierten Build selbst stammt.

Ein veröffentlichtes Image prüfst du mit:

```sh
gh attestation verify oci://ghcr.io/<owner>/<image>:<tag> --owner <owner>
```

!!! note "Eine Attestation belegt Herkunft, nicht Sicherheit"

    Sie sagt dir, welcher Workflow, welcher Commit und welcher Runner ein Image
    erzeugt haben. Sie behauptet nicht, dass das Image frei von Schwachstellen
    ist. Sicherheitsbefunde bleiben Sache der Scanning-Stufen.

## Tags

Der Metadata-Schritt veröffentlicht einen unveränderlichen `type=sha`-Tag und bei
Releases zusätzlich `type=semver`-Tags. Bei einem Nicht-Prerelease setzt er
außerdem `latest`.

`latest` ist ein Komfort-Alias für Menschen und **niemals** eine
Deployment-Referenz: er bewegt sich unabhängig von jedem Artefakt. Deployments
konsumieren den unveränderlichen Digest oder den daneben veröffentlichten
Semver-Tag.

## Trockenbau

`reusable-docker-lint-build.yaml` baut ohne Push, erzeugt also weder Digest noch
Attestation. Lint und Build laufen unabhängig, sodass ein Lauf sowohl einen
Dockerfile-Befund als auch einen Build-Fehler meldet, statt den zweiten hinter
dem ersten zu verstecken.
