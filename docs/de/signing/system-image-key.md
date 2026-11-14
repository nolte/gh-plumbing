# System-Image-Signierschlüssel

Die öffentliche Hälfte des gemeinsamen Sigstore-Schlüssels, der
`bootc`-System-Images im Portfolio signiert. Erster Konsument ist
[`nolte/kamerplanter-appliance`](https://github.com/nolte/kamerplanter-appliance).

Eine installierte Appliance prüft jedes Update gegen diesen Schlüssel, bevor
sie das neue Image bereitstellt. Die Prüfung läuft über `containers-policy.json`
mit einer `sigstoreSigned`-Anforderung, die auf einen `keyPath` zeigt. Diese
Policy kann keyless GitHub-Workflow-Identitäten noch nicht verifizieren, darum
tragen die Images eine schlüsselbasierte Signatur. Keyless Signing bleibt
zusätzlich bestehen.

Dieses Repository veröffentlicht den Schlüssel, damit jeder Image-Build ihn
von einer öffentlichen, gepinnten Stelle holt. Konsumenten-Repositories
committen keine Kopie.

---

## Wo der Schlüssel liegt

Die kanonische Datei ist
[`keys/system-image.pub`](https://github.com/nolte/gh-plumbing/blob/develop/keys/system-image.pub),
eine PEM-Datei (`-----BEGIN PUBLIC KEY-----`). Zwei Adressen liefern sie aus:

| Adresse | Inhalt | Wofür |
|---|---|---|
| `https://raw.githubusercontent.com/nolte/gh-plumbing/<tag>/keys/system-image.pub` | Der Schlüssel im Stand von Release `<tag>`. Ändert sich nie. | Image-Builds. Ein Build **MUSS [MUST]** diese Form nutzen. |
| `https://nolte.github.io/gh-plumbing/keys/system-image.pub` | Der Schlüssel des zuletzt veröffentlichten Releases. | Den aktuellen Schlüssel von Hand nachlesen. |

Die Doku-Site wird bei jedem veröffentlichten Release neu deployt, die
Pages-Adresse wandert also mit jedem Release mit. Die Raw-Adresse auf `develop` ist der
unveröffentlichte Stand. Keine der beiden gehört in einen Build.

Beide Adressen liefern den Schlüssel erst ab dem ersten `gh-plumbing`-Release aus,
das `keys/system-image.pub` enthält.

### Fingerprint

Der SHA-256-Digest der Datei:

```text
35eab2c5b1a413e82ebd8919f2158e68af7c165da4535533ebf15a9f9a8bd084
```

Mit dem eigenen Download vergleichen:

```sh
curl -fsSL https://nolte.github.io/gh-plumbing/keys/system-image.pub | sha256sum
```

---

## Den Schlüssel ins Image einbacken

Den Schlüssel zur Build-Zeit von einem gepinnten Release-Tag holen, den Digest
prüfen und die Datei an den Pfad legen, den die Policy nennt. Ein abweichender
Digest bricht den Build ab.

```dockerfile
# Pin both values. Change them together, and only during a key rotation.
ARG GH_PLUMBING_TAG=vX.Y.Z
ARG SYSTEM_IMAGE_KEY_SHA256=35eab2c5b1a413e82ebd8919f2158e68af7c165da4535533ebf15a9f9a8bd084

RUN mkdir -p /etc/pki/containers \
 && curl -fsSL -o /etc/pki/containers/system-image.pub \
      "https://raw.githubusercontent.com/nolte/gh-plumbing/${GH_PLUMBING_TAG}/keys/system-image.pub" \
 && echo "${SYSTEM_IMAGE_KEY_SHA256}  /etc/pki/containers/system-image.pub" | sha256sum -c -
```

`vX.Y.Z` durch einen `gh-plumbing`-Release-Tag ersetzen, der den Schlüssel
enthält. Fehlt `curl` im Basis-Image, dieselben drei Schritte in einem
Workflow-Step vor dem Build ausführen und die geprüfte Datei per `COPY` ins
Image übernehmen.

Der Policy-Eintrag, der den Schlüssel nutzt, als Auszug aus
`/etc/containers/policy.json`:

```json
{
  "transports": {
    "docker": {
      "ghcr.io/<owner>/<image>": [
        {
          "type": "sigstoreSigned",
          "keyPath": "/etc/pki/containers/system-image.pub",
          "signedIdentity": { "type": "matchRepository" }
        }
      ]
    }
  }
}
```

Der `default`-Eintrag und alle anderen Scopes bleiben Sache des jeweiligen
Images. Signaturen werden nur gefunden, wenn die Registry-Konfiguration unter
`/etc/containers/registries.d/` für diese Registry
`use-sigstore-attachments: true` setzt.

---

## Was hier nicht liegt

Der private Schlüssel und seine Passphrase kommen nie in dieses Repository.
Sie liegen in `gopass` und erreichen die signierenden Repositories als
Actions-Secrets `SYSTEM_IMAGE_SIGNING_KEY` und
`SYSTEM_IMAGE_SIGNING_PASSPHRASE`, dazu die Actions-Variable
`SYSTEM_IMAGE_SIGNING_PUBLIC_KEY`. Terraform in
`nolte/terraform-github-bootstrap` verteilt alle drei. Dessen Betriebsanleitung
beschreibt Erzeugung und Verteilung des Schlüssels:
[System image signing](https://github.com/nolte/terraform-github-bootstrap/blob/develop/docs/en/system-image-signing.md).

---

## Rotation

Eine Appliance akzeptiert nur ein Update, das mit dem Schlüssel signiert ist,
den sie bereits trägt. Wer zuerst den Signierschlüssel wechselt, sperrt jede
installierte Appliance von Updates aus. Darum in dieser Reihenfolge rotieren:

1. Den neuen öffentlichen Schlüssel hier in einem neuen `gh-plumbing`-Release
   veröffentlichen.
2. Jeder Konsument hebt `GH_PLUMBING_TAG` und den Digest an und liefert ein
   Release aus, das den neuen Schlüssel enthält, aber **noch mit dem alten
   Schlüssel signiert** ist. Die Appliances installieren es und tragen danach
   den neuen Schlüssel.
3. Erst dann die Signing-Secrets auf das neue Schlüsselpaar umstellen.

Eine Appliance, die das Release aus Schritt 2 übersprungen hat, trägt noch den
alten Schlüssel und lehnt jedes spätere Update ab. Sie braucht das
Übergangs-Release oder einen manuellen Schlüsseltausch, bevor sie weiterkommt.
