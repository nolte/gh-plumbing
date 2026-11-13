# System image signing key

The public half of the shared Sigstore key that signs `bootc` system
images in the portfolio. The first consumer is
[`nolte/kamerplanter-appliance`](https://github.com/nolte/kamerplanter-appliance).

An installed appliance verifies every update against this key before it
stages the new image. The check runs through `containers-policy.json` with a
`sigstoreSigned` requirement that points at a `keyPath`. That policy can't
verify keyless GitHub workflow identities yet, so the images carry a
key-based signature. Keyless signing stays in place on top of it.

This repository publishes the key so every image build fetches it from one
public, pinned place. Consumer repositories don't commit a copy.

---

## Where the key lives

The canonical file is
[`keys/system-image.pub`](https://github.com/nolte/gh-plumbing/blob/develop/keys/system-image.pub),
a PEM file (`-----BEGIN PUBLIC KEY-----`). Two addresses serve it:

| Address | Content | Use it for |
|---|---|---|
| `https://raw.githubusercontent.com/nolte/gh-plumbing/<tag>/keys/system-image.pub` | The key as of release `<tag>`. Never changes. | Image builds. A build **MUST** use this form. |
| `https://nolte.github.io/gh-plumbing/keys/system-image.pub` | The key of the latest published release. | Reading the current key by hand. |

The documentation site redeploys on every published release, so the Pages address
moves with each release. The raw address on `develop` is the unreleased state.
Neither belongs in a build.

Both addresses serve the key only from the first `gh-plumbing` release that contains
`keys/system-image.pub`.

### Fingerprint

The SHA-256 digest of the file:

```text
35eab2c5b1a413e82ebd8919f2158e68af7c165da4535533ebf15a9f9a8bd084
```

Compare it against your own download:

```sh
curl -fsSL https://nolte.github.io/gh-plumbing/keys/system-image.pub | sha256sum
```

---

## Bake the key into an image

Fetch the key at build time from a pinned release tag, check the digest, and
place the file at the path the policy names. A digest mismatch fails the build.

```dockerfile
# Pin both values. Change them together, and only during a key rotation.
ARG GH_PLUMBING_TAG=vX.Y.Z
ARG SYSTEM_IMAGE_KEY_SHA256=35eab2c5b1a413e82ebd8919f2158e68af7c165da4535533ebf15a9f9a8bd084

RUN mkdir -p /etc/pki/containers \
 && curl -fsSL -o /etc/pki/containers/system-image.pub \
      "https://raw.githubusercontent.com/nolte/gh-plumbing/${GH_PLUMBING_TAG}/keys/system-image.pub" \
 && echo "${SYSTEM_IMAGE_KEY_SHA256}  /etc/pki/containers/system-image.pub" | sha256sum -c -
```

Replace `vX.Y.Z` with a `gh-plumbing` release tag that contains the key. If the
base image lacks `curl`, run the same three steps in a workflow step before the
build and `COPY` the verified file into the image.

The policy entry that uses the key, as an excerpt of
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

The `default` entry and every other scope stay the image's own decision.
Signatures are only found when the registry configuration under
`/etc/containers/registries.d/` sets `use-sigstore-attachments: true` for that
registry.

---

## What isn't here

The private key and its passphrase never enter this repository. They live in
`gopass` and reach the signing repositories as the Actions secrets
`SYSTEM_IMAGE_SIGNING_KEY` and `SYSTEM_IMAGE_SIGNING_PASSPHRASE`, plus the
Actions variable `SYSTEM_IMAGE_SIGNING_PUBLIC_KEY`. Terraform in
`nolte/terraform-github-bootstrap` distributes all three. Its operator guide
covers key creation and distribution:
[System image signing](https://github.com/nolte/terraform-github-bootstrap/blob/develop/docs/en/system-image-signing.md).

---

## Rotation

An appliance only accepts an update signed with the key it already carries.
Switching the signing key first would lock every installed appliance out of
updates. Rotate in this order:

1. Publish the new public key here in a new `gh-plumbing` release.
2. Each consumer bumps `GH_PLUMBING_TAG` and the digest, and ships a release
   that carries the new key but is **still signed with the old key**.
   Appliances install it and now hold the new key.
3. Only then switch the signing secrets to the new key pair.

An appliance that skipped the release from step 2 still holds the old key and
rejects every later update. It needs the transition release, or a manual key
update, before it can move on.
