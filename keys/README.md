# Keys

Canonical **public** keys that consumer repositories fetch from a pinned
`gh-plumbing` release tag.

| File | Purpose |
|---|---|
| `system-image.pub` | Sigstore public key for `bootc` system images. See [System image signing key](../docs/en/signing/system-image-key.md). |

Never commit private keys, passphrases, or any other secret material here.
Private halves live in `gopass`, and
`nolte/terraform-github-bootstrap` distributes them.

`docs/en/keys/` holds a symlink to each file, so the documentation site serves
the key at `https://nolte.github.io/gh-plumbing/keys/<file>`. Because it's a
symlink, it can't drift from the file in this directory. Keep it a symlink and
add one for every new key.
