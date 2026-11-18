#!/usr/bin/env python3
"""Refuse a Vale pin that disagrees with itself or with .tool-versions (#488).

`.vale-version` is the source CI installs Vale from (actions/setup-vale), and
`.tool-versions` pins the local, asdf-managed one. Two drifts break the promise
that the same text yields the same alerts everywhere, and neither fails loudly
on its own:

  * a `VALE_SHA256` line that names another version than `VALE_VERSION`. This
    is the shape of every Renovate bump: Renovate rewrites `VALE_VERSION` but
    can't recompute the checksum. The action refuses it too, but only where it
    runs -- this check runs in the static gate of every pull request;
  * a `vale` line in `.tool-versions` that names another version, so local
    runs and the release gate disagree silently.

The file format is nolte/claude-shared's (#768): one `VALE_VERSION=<x.y.z>`
line and one `VALE_SHA256=<sha256>  vale_<x.y.z>_Linux_64-bit.tar.gz` line;
`#` lines are comments. A repository without `.vale-version` has nothing to
check. One without a `vale` line in `.tool-versions` has nothing to compare.

Reads only. Exits non-zero on any finding.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# [0-9], not \d: \d also matches non-ASCII digits, which the action refuses.
VERSION_LINE = re.compile(r"^VALE_VERSION=(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$")
SHA_LINE = re.compile(
    r"^VALE_SHA256=(?P<sha>[0-9a-f]{64})  vale_(?P<version>[0-9]+\.[0-9]+\.[0-9]+)_Linux_64-bit\.tar\.gz$"
)
TOOL_LINE = re.compile(r"^vale\s+(?P<version>\S+)")


def read_pin(path: Path) -> tuple[str | None, str | None, list[str]]:
    """Return (VALE_VERSION, version named by VALE_SHA256, findings)."""
    versions: list[str] = []
    sha_versions: list[str] = []
    findings: list[str] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if m := VERSION_LINE.match(line):
            versions.append(m["version"])
        elif m := SHA_LINE.match(line):
            sha_versions.append(m["version"])
        elif line.startswith(("VALE_VERSION", "VALE_SHA256")):
            findings.append(
                f"{path.name}:{number}: malformed line; expected 'VALE_VERSION=<x.y.z>' or "
                "'VALE_SHA256=<sha256>  vale_<x.y.z>_Linux_64-bit.tar.gz'"
            )
        else:
            findings.append(f"{path.name}:{number}: unexpected line; only VALE_VERSION, VALE_SHA256 and comments belong here")
    if len(versions) != 1:
        findings.append(f"{path.name}: needs exactly one VALE_VERSION line, found {len(versions)}")
    if len(sha_versions) != 1:
        findings.append(f"{path.name}: needs exactly one VALE_SHA256 line, found {len(sha_versions)}")
    version = versions[0] if len(versions) == 1 else None
    sha_version = sha_versions[0] if len(sha_versions) == 1 else None
    return version, sha_version, findings


def read_tool_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if m := TOOL_LINE.match(raw.strip()):
            return m["version"]
    return None


def audit(root: Path) -> list[str]:
    pin = root / ".vale-version"
    if not pin.is_file():
        return []
    version, sha_version, findings = read_pin(pin)
    if version and sha_version and version != sha_version:
        findings.append(
            f".vale-version: VALE_SHA256 is the checksum of vale {sha_version}, but VALE_VERSION is {version}. "
            f"Replace it with the Linux_64-bit line of vale_{version}_checksums.txt from the v{version} release "
            "(Renovate bumps the version but can't recompute the checksum)."
        )
    tool_version = read_tool_version(root / ".tool-versions")
    if version and tool_version and tool_version != version:
        findings.append(
            f".tool-versions pins vale {tool_version}, .vale-version pins {version}. "
            "Make them agree, so local runs and CI report the same alerts."
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    args = parser.parse_args(argv)
    findings = audit(args.root)
    for message in findings:
        print(message, file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
