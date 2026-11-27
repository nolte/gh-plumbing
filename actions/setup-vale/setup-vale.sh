#!/usr/bin/env bash
# Install a pinned Vale binary, verified against a committed SHA-256 (#488).
#
# Called by action.yml in this directory; runnable on its own for tests. The
# asset is downloaded to a file, checked with `sha256sum -c`, and only then
# unpacked -- never `curl | tar` -- so an asset replaced under the same tag
# never runs. Format and verification follow nolte/claude-shared's
# scripts/install_vale.sh (nolte/claude-shared#768), so one `.vale-version`
# works with both.
#
# Inputs, all through the environment, never interpolated into the script:
#   INPUT_VERSION       x.y.z; together with INPUT_SHA256 it replaces the file
#   INPUT_SHA256        64 hex digits, the SHA-256 of the Linux_64-bit asset
#   INPUT_VERSION_FILE  path to a .vale-version file (used when both above are
#                       empty), relative to the working directory or absolute
# Runner environment: RUNNER_TEMP, GITHUB_OUTPUT, GITHUB_PATH.
#
# Outputs (GITHUB_OUTPUT), written for every outcome this script decides
# itself, so a caller that sets `continue-on-error` can tell the failures
# apart. An unexpected error under `set -e` (a tool that fails, the final move
# onto an existing path) leaves `result` empty; a caller treats an empty value
# as a refusal:
#   result        installed | invalid-pin | unsupported-platform |
#                 download-failed | checksum-mismatch | run-failed
#   vale-version  the installed version, on success only
#
# Only `download-failed` says nothing about the asset. Every other failure is a
# refusal: the pin is wrong, the asset does not match it, or the verified
# binary did not run. In none of them does a directory reach GITHUB_PATH.
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP must be set}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT must be set}"
: "${GITHUB_PATH:?GITHUB_PATH must be set}"

readonly VERSION_RE='^[0-9]+\.[0-9]+\.[0-9]+$'
readonly SHA_RE='^[0-9a-f]{64}$'
# The asset name is the only one this action knows how to verify and unpack.
readonly PLATFORM='Linux_64-bit'

work=""
trap '[[ -z "$work" ]] || rm -rf "$work"' EXIT

# Masks $1 for a log line (#492): control characters become '?' and '##['
# becomes '#?[', so the value can neither end the line nor open the runner's
# older '##[command]' syntax in the middle of one.
shown() { local v="${1//[[:cntrl:]]/?}"; printf '%s' "${v//\#\#\[/#?[}"; }

# finish RESULT EXIT_CODE MESSAGE: record the result, report, and stop.
finish() {
  local result="$1" code="$2" message="$3"
  # The message can quote an input (the version-file path). It is masked so
  # it stays one line and can't start a second workflow command.
  message=$(shown "$message")
  echo "result=${result}" >> "$GITHUB_OUTPUT"
  if [[ "$code" -eq 0 ]]; then
    echo "$message"
  else
    echo "::error title=setup-vale (${result})::${message}"
  fi
  exit "$code"
}

version=""
sha256=""
checksum_asset=""

if [[ -n "${INPUT_VERSION:-}" || -n "${INPUT_SHA256:-}" ]]; then
  if [[ -z "${INPUT_VERSION:-}" || -z "${INPUT_SHA256:-}" ]]; then
    finish invalid-pin 2 "Inputs 'version' and 'sha256' go together; set both, or neither to read 'version-file'."
  fi
  if [[ ! "$INPUT_VERSION" =~ $VERSION_RE ]]; then
    finish invalid-pin 2 "Input 'version' must be x.y.z (digits and dots only); refusing it."
  fi
  sha_in="${INPUT_SHA256,,}"
  if [[ ! "$sha_in" =~ $SHA_RE ]]; then
    finish invalid-pin 2 "Input 'sha256' must be 64 hexadecimal digits; refusing it."
  fi
  version="$INPUT_VERSION"
  sha256="$sha_in"
  checksum_asset="vale_${version}_${PLATFORM}.tar.gz"
else
  file="${INPUT_VERSION_FILE:-.vale-version}"
  if [[ ! -f "$file" ]]; then
    finish invalid-pin 2 "Version file '${file}' does not exist. Commit a .vale-version, or set the 'version' and 'sha256' inputs."
  fi
  # Read the two keys with fixed patterns instead of sourcing the file, so it
  # can never inject shell or environment state. Exactly one well-formed line
  # each; a malformed or duplicated key is a refusal, not a guess.
  versions=()
  checksums=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    if [[ "$line" =~ ^VALE_VERSION=([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
      versions+=("${BASH_REMATCH[1]}")
    elif [[ "$line" =~ ^VALE_SHA256=([0-9a-f]{64})\ \ (vale_[0-9]+\.[0-9]+\.[0-9]+_${PLATFORM}\.tar\.gz)$ ]]; then
      checksums+=("${BASH_REMATCH[1]}  ${BASH_REMATCH[2]}")
    fi
  done < "$file"
  if [[ "${#versions[@]}" -ne 1 || "${#checksums[@]}" -ne 1 ]]; then
    finish invalid-pin 2 "'${file}' needs exactly one 'VALE_VERSION=<x.y.z>' line and one 'VALE_SHA256=<sha256>  vale_<x.y.z>_${PLATFORM}.tar.gz' line."
  fi
  version="${versions[0]}"
  sha256="${checksums[0]%%  *}"
  checksum_asset="${checksums[0]#*  }"
fi

asset="vale_${version}_${PLATFORM}.tar.gz"
if [[ "$checksum_asset" != "$asset" ]]; then
  finish invalid-pin 2 "VALE_SHA256 is the checksum of '${checksum_asset}', not of '${asset}'. Copy the ${PLATFORM} line of vale_${version}_checksums.txt from the v${version} release into the version file."
fi

# The probe goes through PATH, so a test can stand in for another platform
# without a switch in this script that a caller could flip.
os="$(uname -s)"
arch="$(uname -m)"
if [[ "$os" != "Linux" || "$arch" != "x86_64" ]]; then
  finish unsupported-platform 3 "This action installs the ${PLATFORM} (Linux x86-64) asset only; this runner reports '${os}' / '${arch}'."
fi

work="$(mktemp -d "${RUNNER_TEMP}/setup-vale.XXXXXXXX")"
url="https://github.com/vale-cli/vale/releases/download/v${version}/${asset}"
echo "Downloading ${url}"
if ! curl -fsSL --retry 3 --retry-all-errors --connect-timeout 20 --max-time 300 \
     -o "${work}/${asset}" "$url"; then
  finish download-failed 4 "Could not download ${asset}. Nothing was installed."
fi

# Verified before anything is unpacked. On a mismatch the archive is removed
# with the work directory and nothing from it ever ran.
if ! (cd "$work" && printf '%s  %s\n' "$sha256" "$asset" | sha256sum --check --strict -); then
  finish checksum-mismatch 5 "${asset} does not match the pinned SHA-256. The asset may have been replaced under the same tag; nothing was unpacked or run."
fi

# Only the `vale` member, into a directory of its own, so the README and
# LICENSE in the archive never land on PATH.
bin="${work}/bin"
mkdir "$bin"
if ! tar -xzf "${work}/${asset}" -C "$bin" --no-same-owner vale \
   || [[ -L "${bin}/vale" || ! -f "${bin}/vale" ]]; then
  finish run-failed 6 "${asset} passed its checksum but holds no regular 'vale' file; nothing was installed."
fi
chmod 0755 "${bin}/vale"
rm -f "${work}/${asset}"

if ! printed="$("${bin}/vale" --version 2>&1)"; then
  finish run-failed 6 "The verified vale binary did not run on this runner; nothing was installed."
fi
if [[ "$printed" != *"$version"* ]]; then
  finish run-failed 6 "The verified vale binary reports '${printed}', not ${version}; nothing was installed."
fi

# Installed: keep the directory beyond this script and publish it.
# -T: never move into a directory that already exists under that name.
install_dir="${RUNNER_TEMP}/setup-vale-${version}-$(basename "$work")"
mv -T "$bin" "$install_dir"
echo "$install_dir" >> "$GITHUB_PATH"
echo "vale-version=${version}" >> "$GITHUB_OUTPUT"
finish installed 0 "Installed ${printed} (SHA-256 verified) into ${install_dir}."
