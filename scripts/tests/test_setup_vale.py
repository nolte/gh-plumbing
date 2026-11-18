"""Tests for actions/setup-vale/setup-vale.sh (#488).

The script downloads a binary and runs it, so the load-bearing cases are the
refusals: a checksum mismatch must leave nothing unpacked, run or on PATH; a
hostile or malformed pin must be refused before any network call; and a
download failure must be distinguishable from a mismatch, because
reusable-release-publish.yml warns on the first and fails on the second.

Everything runs offline. `curl` and `uname` are stubs placed first on PATH --
the script resolves both through PATH, so no test-only switch exists in the
script itself. The release asset is a tarball built here, holding a `vale`
that prints a version and touches a marker file when it runs.
"""

from __future__ import annotations

import hashlib
import io
import os
import pathlib
import subprocess
import tarfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "actions" / "setup-vale" / "setup-vale.sh"
VERSION = "3.15.2"
ASSET = f"vale_{VERSION}_Linux_64-bit.tar.gz"

CURL_STUB = """#!/usr/bin/env bash
# Records every call, then serves STUB_ASSET to the -o path or fails like
# `curl -f` does on an HTTP error.
printf '%s\\n' "$*" >> "$STUB_CURL_LOG"
out=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then out="$2"; shift; fi
  shift
done
if [[ "$STUB_CURL_MODE" == "fail" ]]; then
  echo "curl: (22) The requested URL returned error: 503" >&2
  exit 22
fi
cp "$STUB_ASSET" "$out"
"""

UNAME_STUB = """#!/usr/bin/env bash
case "$1" in
  -s) echo "$STUB_UNAME_S" ;;
  -m) echo "$STUB_UNAME_M" ;;
  *) echo "$STUB_UNAME_S" ;;
esac
"""


def fake_vale(prints: str) -> bytes:
    return (
        "#!/bin/sh\n"
        'if [ -n "$VALE_RAN_MARKER" ]; then touch "$VALE_RAN_MARKER"; fi\n'
        f'echo "vale version {prints}"\n'
    ).encode()


def build_asset(path: pathlib.Path, prints: str = VERSION) -> str:
    """Write a release-shaped tarball and return its SHA-256."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data, mode in (
            ("LICENSE", b"license\n", 0o644),
            ("README.md", b"readme\n", 0o644),
            ("vale", fake_vale(prints), 0o755),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            tar.addfile(info, io.BytesIO(data))
    path.write_bytes(buf.getvalue())
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Harness:
    def __init__(self, root: pathlib.Path):
        self.root = root
        self.stubs = root / "stubs"
        self.stubs.mkdir()
        for name, body in (("curl", CURL_STUB), ("uname", UNAME_STUB)):
            stub = self.stubs / name
            stub.write_text(body, encoding="utf-8")
            stub.chmod(0o755)
        self.temp = root / "runner-temp"
        self.temp.mkdir()
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.output = root / "github-output"
        self.path_file = root / "github-path"
        self.curl_log = root / "curl.log"
        self.marker = root / "vale-ran"
        self.asset = root / "served" / ASSET
        self.asset.parent.mkdir()
        self.sha = build_asset(self.asset)
        for f in (self.output, self.path_file, self.curl_log):
            f.write_text("", encoding="utf-8")

    def version_file(self, text: str, name: str = ".vale-version") -> pathlib.Path:
        path = self.workspace / name
        path.write_text(text, encoding="utf-8")
        return path

    def pin(self, version: str = VERSION, sha: str | None = None, asset_version: str | None = None) -> str:
        return (
            "# comment lines are ignored\n"
            f"VALE_VERSION={version}\n"
            f"VALE_SHA256={sha or self.sha}  vale_{asset_version or version}_Linux_64-bit.tar.gz\n"
        )

    def run(self, *, curl_mode: str = "serve", uname: tuple[str, str] = ("Linux", "x86_64"), **inputs: str):
        env = {
            "PATH": f"{self.stubs}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.root),
            "RUNNER_TEMP": str(self.temp),
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_PATH": str(self.path_file),
            "STUB_CURL_LOG": str(self.curl_log),
            "STUB_CURL_MODE": curl_mode,
            "STUB_ASSET": str(self.asset),
            "STUB_UNAME_S": uname[0],
            "STUB_UNAME_M": uname[1],
            "VALE_RAN_MARKER": str(self.marker),
        }
        for key, value in inputs.items():
            env[f"INPUT_{key.upper()}"] = value
        return subprocess.run(
            ["bash", str(SCRIPT)], cwd=self.workspace, env=env,
            capture_output=True, text=True, check=False,
        )

    def outputs(self) -> dict[str, str]:
        pairs = (line.split("=", 1) for line in self.output.read_text(encoding="utf-8").splitlines() if "=" in line)
        return dict(pairs)

    def path_entries(self) -> list[str]:
        return [line for line in self.path_file.read_text(encoding="utf-8").splitlines() if line]

    def curl_calls(self) -> list[str]:
        return [line for line in self.curl_log.read_text(encoding="utf-8").splitlines() if line]

    def vale_files(self) -> list[pathlib.Path]:
        return [p for p in self.temp.rglob("vale") if p.is_file()]


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


def assert_refused(h: Harness, proc, result: str, code: int, *, network: bool) -> None:
    assert proc.returncode == code, proc.stdout + proc.stderr
    assert h.outputs().get("result") == result
    assert "vale-version" not in h.outputs()
    assert h.path_entries() == []
    assert h.vale_files() == []
    assert not h.marker.exists(), "the binary ran although the action refused"
    assert bool(h.curl_calls()) is network
    assert f"::error title=setup-vale ({result})::" in proc.stdout


# --- installs ---------------------------------------------------------------


def test_installs_from_version_file(h):
    h.version_file(h.pin())
    proc = h.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert h.outputs() == {"result": "installed", "vale-version": VERSION}
    [entry] = h.path_entries()
    installed = pathlib.Path(entry) / "vale"
    assert installed.is_file() and os.access(installed, os.X_OK)
    assert sorted(p.name for p in pathlib.Path(entry).iterdir()) == ["vale"], "only the vale member is unpacked"
    assert pathlib.Path(entry).parent == h.temp
    assert subprocess.run([str(installed), "--version"], capture_output=True, text=True, check=True).stdout.strip() == f"vale version {VERSION}"
    [call] = h.curl_calls()
    assert f"https://github.com/vale-cli/vale/releases/download/v{VERSION}/{ASSET}" in call
    assert "--max-time" in call
    # Nothing but the installed directory is left behind in RUNNER_TEMP.
    assert [p.name for p in h.temp.iterdir()] == [pathlib.Path(entry).name]


def test_installs_from_inputs_and_ignores_the_file(h):
    proc = h.run(version=VERSION, sha256=h.sha.upper(), version_file="does-not-exist")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert h.outputs()["result"] == "installed"
    assert len(h.path_entries()) == 1


def test_version_file_accepts_an_absolute_path_and_crlf(h):
    path = h.version_file(h.pin().replace("\n", "\r\n"), name="pin.txt")
    proc = h.run(version_file=str(path))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_claude_shared_file_format_is_accepted(h):
    # Verbatim shape of nolte/claude-shared's .vale-version, with this asset's
    # checksum: comment block, then the two keys.
    h.version_file(
        "# The one committed source for the Vale binary (#768)\n"
        "# Renovate bumps VALE_VERSION but can't recompute the checksum.\n"
        f"VALE_VERSION={VERSION}\n"
        f"VALE_SHA256={h.sha}  {ASSET}\n"
    )
    assert h.run().returncode == 0


# --- fails closed -----------------------------------------------------------


def test_checksum_mismatch_refuses_before_unpacking(h):
    h.version_file(h.pin(sha="0" * 64))
    proc = h.run()
    assert_refused(h, proc, "checksum-mismatch", 5, network=True)
    assert list(h.temp.iterdir()) == [], "the downloaded archive is removed"


def test_checksum_line_for_another_version_refuses_without_download(h):
    h.version_file(h.pin(asset_version="3.15.1"))
    proc = h.run()
    assert_refused(h, proc, "invalid-pin", 2, network=False)
    assert "vale_3.15.1_Linux_64-bit.tar.gz" in proc.stdout


def test_binary_reporting_another_version_is_not_installed(h):
    h.sha = build_asset(h.asset, prints="9.9.9")
    h.version_file(h.pin())
    proc = h.run()
    assert proc.returncode == 6
    assert h.outputs()["result"] == "run-failed"
    assert h.path_entries() == []


def test_download_failure_is_distinct_from_a_mismatch(h):
    h.version_file(h.pin())
    proc = h.run(curl_mode="fail")
    assert_refused(h, proc, "download-failed", 4, network=True)


@pytest.mark.parametrize("uname", [("Darwin", "x86_64"), ("Linux", "aarch64"), ("MINGW64_NT-10.0", "x86_64")])
def test_other_platforms_refuse_without_download(h, uname):
    h.version_file(h.pin())
    proc = h.run(uname=uname)
    assert_refused(h, proc, "unsupported-platform", 3, network=False)
    assert "Linux x86-64" in proc.stdout


# --- hostile and malformed pins ---------------------------------------------


@pytest.mark.parametrize("version", [
    "../x", "3.15.2;id", "3.15.2 ", " 3.15.2", "3.15 .2", "$(id)", "3.15.2/../../x",
    "v3.15.2", "3.15", "3.15.2\nid", "3.15.2-rc1",
])
def test_hostile_version_input_refuses_without_network(h, version):
    proc = h.run(version=version, sha256=h.sha)
    assert_refused(h, proc, "invalid-pin", 2, network=False)
    assert version not in proc.stdout, "the refused value is not echoed into an annotation"


@pytest.mark.parametrize("inputs", [
    {"version": "", "sha256": "a" * 64},
    {"version": VERSION, "sha256": ""},
    {"version": VERSION, "sha256": "a" * 63},
    {"version": VERSION, "sha256": "g" * 64},
    {"version": VERSION, "sha256": "a" * 64 + ";id"},
])
def test_incomplete_or_malformed_inputs_refuse(h, inputs):
    assert_refused(h, h.run(**inputs), "invalid-pin", 2, network=False)


@pytest.mark.parametrize("text", [
    "",
    "VALE_VERSION=3.15.2\n",
    "VALE_VERSION=3.15.2;id\nVALE_SHA256={sha}  vale_3.15.2_Linux_64-bit.tar.gz\n",
    "VALE_VERSION=../x\nVALE_SHA256={sha}  vale_3.15.2_Linux_64-bit.tar.gz\n",
    "VALE_VERSION= 3.15.2\nVALE_SHA256={sha}  vale_3.15.2_Linux_64-bit.tar.gz\n",
    "VALE_VERSION=3.15.2\nVALE_VERSION=3.15.2\nVALE_SHA256={sha}  vale_3.15.2_Linux_64-bit.tar.gz\n",
    "VALE_VERSION=3.15.2\nVALE_SHA256={sha} vale_3.15.2_Linux_64-bit.tar.gz\n",
    "VALE_VERSION=3.15.2\nVALE_SHA256={sha}  vale_3.15.2_macOS_64-bit.tar.gz\n",
    "VALE_VERSION=3.15.2\nVALE_SHA256={sha}  ../vale_3.15.2_Linux_64-bit.tar.gz\n",
    "VALE_VERSION=$(id)\nVALE_SHA256={sha}  vale_3.15.2_Linux_64-bit.tar.gz\n",
])
def test_malformed_version_file_refuses_without_network(h, text):
    h.version_file(text.format(sha=h.sha))
    assert_refused(h, h.run(), "invalid-pin", 2, network=False)


def test_missing_version_file_refuses(h):
    assert_refused(h, h.run(version_file="nope/.vale-version"), "invalid-pin", 2, network=False)


def test_version_file_is_never_sourced(h):
    # Lines that would run a command if the file were sourced or evaluated.
    sourced = h.root / "sourced"
    h.version_file(f"touch {sourced}\nVALE_X=$(touch {sourced})\n" + h.pin())
    proc = h.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not sourced.exists()
