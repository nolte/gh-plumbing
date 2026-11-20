"""Behavioural tests for #492: printed values can't start a workflow command.

The runner reads every line a step prints as a possible workflow command, in
two syntaxes: a line that starts (after leading whitespace) with
`::<command>::`, and `##[<command>]` ANYWHERE in a line. That is read from the
runner's source (actions/runner, ActionCommand.cs TryParseV2/TryParse,
OutputManager.cs), not measured on a runner. A value with a line break
followed by `::warning::...`, or with `##[warning]...` and no line break at
all -- a caller input, a draft tag name, repository content -- would start
one, and written as `name=$value` to `$GITHUB_OUTPUT` a line break adds an
output entry. Nothing fails when that happens, so the load-bearing cases are
the hostile values themselves.

Each test reads a step's real `run:` body from the workflow file and runs it
under bash (or the heredoc's interpreter, through bash) against stubs for `gh`
and, where a step needs them, `git`, `vale` or `sleep`, in a throwaway git
repository where the step needs one. A test asserts on every line of stdout
AND stderr, through `commands()`, which models both syntaxes, and on the exact
`$GITHUB_OUTPUT` content. Clean-value cases pin today's behaviour.

The class itself -- every command line in every reusable workflow -- is held
by scripts/workflow_command_masking.py and its tests.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
HOSTILE = "v1\n::warning::injected"

HOSTILE_V1 = "v1##[set-output name=x]y"

# The step summary's encoder (#506), the Python form the masking guard ships.
_guard_spec = importlib.util.spec_from_file_location(
    "workflow_command_masking", REPO_ROOT / "scripts" / "workflow_command_masking.py")
_guard = importlib.util.module_from_spec(_guard_spec)
sys.modules.setdefault(_guard_spec.name, _guard)
_guard_spec.loader.exec_module(_guard)
_md: dict = {}
exec("import re\n" + _guard.PY_MD, _md)
md_code = _md["md_code"]
HOSTILE_WARN = "##[warning]z"

GH_STUB = """#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
case "$1 $2" in
  "release list") printf '%s\\n' "$STUB_LIST" ;;
  "release view")
    case "$*" in
      *targetCommitish*) printf '%s\\n' "$STUB_TARGET" ;;
      *body*) printf '%s\\n' "$STUB_BODY" ;;
      *"--json name"*) printf '%s\\n' "${STUB_TITLE:-}" ;;
      *createdAt*) printf '%s\\n' "${STUB_CREATED:-}" ;;
    esac ;;
  "run list") printf '%s\\n' "$STUB_RUNS" ;;
  "api "*)
    case "$2" in
      */protection) [[ -n "${STUB_PROTECTION:-}" ]] || exit 1; printf '%s\\n' "$STUB_PROTECTION" ;;
      */rules/branches/*) printf '%s\\n' "${STUB_RULES:-[]}" ;;
      *) printf '%s\\n' "$STUB_SHA" ;;
    esac ;;
esac
"""


def step_body(workflow: str, name: str) -> str:
    doc = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    found = [s for job in doc["jobs"].values() for s in job.get("steps", []) if s.get("name") == name]
    assert len(found) == 1, f"{workflow}: step {name!r}"
    return found[0]["run"]


@pytest.fixture
def run(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    gh = stubs / "gh"
    gh.write_text(GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    work = tmp_path / "work"
    work.mkdir()
    output = tmp_path / "github_output"
    summary = tmp_path / "step_summary"

    def _run(workflow: str, name: str, env: dict[str, str] | None = None, cwd: pathlib.Path = work,
             stubs_extra: dict[str, str] | None = None):
        for stub, body in (stubs_extra or {}).items():
            path = stubs / stub
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        output.write_text("", encoding="utf-8")
        summary.write_text("", encoding="utf-8")
        script = tmp_path / "step.sh"
        script.write_text(step_body(workflow, name), encoding="utf-8")
        full = {
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            # Tool shims (asdf and the like) resolve versions through HOME.
            "HOME": os.environ.get("HOME", str(tmp_path)),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_SHA": "a" * 40,
            "RUNNER_OS": "Linux",
            "RUNNER_ARCH": "X64",
            "GH_TOKEN": "unused",
            "STUB_LOG": str(tmp_path / "gh.log"),
            "STUB_LIST": "[]",
            "STUB_TARGET": "",
            "STUB_BODY": "",
            "STUB_SHA": "",
            "STUB_RUNS": "",
            **(env or {}),
        }
        proc = subprocess.run(["bash", "-e", str(script)], cwd=cwd, env=full,
                              capture_output=True, text=True, check=False)
        return proc, output.read_text(encoding="utf-8"), summary.read_text(encoding="utf-8")

    return _run


def commands(proc: subprocess.CompletedProcess) -> list[str]:
    """Every line of stdout and stderr the runner could read as a command.

    Models the two syntaxes read from the runner source: a line that starts,
    after leading whitespace, with `::`, or one that contains `##[` anywhere.
    The runner splits its output at LF, CR and CRLF (StreamReader.ReadLine in
    ProcessInvoker.cs); `splitlines()` also splits at NEL, U+2028 and a few
    more, so it finds every line the runner would see and possibly more. A
    model of the source, not a measurement on a runner.
    """
    lines = (proc.stdout + "\n" + proc.stderr).splitlines()
    return [line.lstrip() for line in lines if line.lstrip().startswith("::") or "##[" in line]


def git(repo: pathlib.Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    return subprocess.run(["git", "-C", str(repo), *args], env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


def make_repo(path: pathlib.Path, files: dict[str, str], message: str = "init") -> str:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "develop")
    for name, text in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)
    sha = git(path, "rev-parse", "HEAD")
    git(path, "update-ref", "refs/remotes/origin/develop", sha)
    return sha


def drafts(*tags: str) -> str:
    return json.dumps([{"isDraft": True, "tagName": t} for t in tags])


# --- reusable-release-publish.yml: Resolve draft ---------------------------

PUBLISH = "reusable-release-publish.yml"
def refused(shown: str) -> str:
    return (f"::error::Tag '{shown}' contains a control character or '##[' (shown as '?' and '#?['); "
            "refusing to continue.")


REFUSED = refused("v1?::warning::injected")


@pytest.mark.parametrize("given, listed", [
    (HOSTILE, drafts("v1.0.0")),       # the caller's input
    (HOSTILE, drafts(HOSTILE)),        # ... matching a draft that carries it
    ("", drafts(HOSTILE)),             # the single open draft's tag name
])
def test_resolve_draft_refuses_a_tag_with_a_control_character(run, given, listed):
    proc, output, _ = run(PUBLISH, "Resolve draft", {"REQUESTED_TAG": given, "STUB_LIST": listed})
    assert proc.returncode == 1
    assert commands(proc) == [REFUSED]
    assert output == "", "nothing reaches $GITHUB_OUTPUT"


def utf8_locale_available() -> bool:
    try:
        out = subprocess.run(["locale", "-a"], capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        return False
    return any(name.lower().replace("-", "") == "c.utf8" for name in out.split())


@pytest.mark.skipif(not utf8_locale_available(), reason="the C.UTF-8 locale is not installed")
@pytest.mark.parametrize("workflow", [PUBLISH, "reusable-release-archive.yml"])
def test_tag_refusal_is_wider_than_git_in_a_utf8_locale(run, workflow):
    # Deliberate (#492): git accepts U+0085 in a ref name, but in the
    # runner's UTF-8 locale [[:cntrl:]] matches it, and whether the runner
    # ends a line there wasn't measured. Pinned so a narrowing is a decision.
    proc, output, _ = run(workflow, "Resolve draft", {
        "LC_ALL": "C.UTF-8", "REQUESTED_TAG": "v1\u0085x", "STUB_LIST": drafts("v1.0.0"), "GH_REPO": "owner/repo"})
    assert proc.returncode == 1
    assert commands(proc) == [refused("v1?x")]
    assert output == ""


@pytest.mark.parametrize("given", ["", "v9.9.9"])
def test_resolve_draft_lists_draft_tag_names_masked(run, given):
    # No tag and two drafts, or a tag no draft carries: both list the drafts.
    proc, output, _ = run(PUBLISH, "Resolve draft", {"REQUESTED_TAG": given, "STUB_LIST": drafts("v1.0.0", HOSTILE)})
    assert proc.returncode == 1
    assert len(commands(proc)) == 1 and commands(proc)[0].startswith("::error::")
    assert "  - v1.0.0\n  - v1?::warning::injected\n" in proc.stderr
    assert output == ""


@pytest.mark.parametrize("given", ["", "v1.2.3"])
def test_resolve_draft_with_a_clean_tag_is_unchanged(run, tmp_path, given):
    repo = tmp_path / "repo"
    sha = make_repo(repo, {"README.md": "x\n"})
    proc, output, _ = run(PUBLISH, "Resolve draft",
                          {"REQUESTED_TAG": given, "STUB_LIST": drafts("v1.2.3"), "STUB_TARGET": sha}, cwd=repo)
    assert proc.returncode == 0, proc.stderr
    assert output == f"tag=v1.2.3\ntarget_sha={sha}\n"
    expected = ["::notice::No tag given; resolved the single open draft 'v1.2.3'."] if not given else []
    assert commands(proc) == expected
    assert proc.stdout.splitlines()[-1] == f"Draft 'v1.2.3' resolved at {sha} (reachable from origin/develop)."


# --- reusable-release-publish.yml: expected-target-sha ---------------------


def test_expected_target_sha_is_masked_when_refused(run):
    proc, _, _ = run(PUBLISH, "Check the draft target against the expected commit",
                     {"EXPECTED_TARGET_SHA": "abc\n::warning::injected", "AUTO_ALIGN": "false",
                      "TAG": "v1.2.3", "DRAFT_TARGET": "b" * 40})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::expected-target-sha 'abc?::warning::injected' is not a full")


def test_expected_target_sha_mismatch_is_unchanged(run):
    proc, _, _ = run(PUBLISH, "Check the draft target against the expected commit",
                     {"EXPECTED_TARGET_SHA": "A" * 40, "AUTO_ALIGN": "false",
                      "TAG": "v1.2.3", "DRAFT_TARGET": "b" * 40})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith(f"::error::Draft 'v1.2.3' targets {'b' * 40}, but the archive was built from {'a' * 40}.")


# --- reusable-release-publish.yml: HACS asset --------------------------------

HACS_STEP = "Attach HACS zip-release asset"


def hacs_repo(tmp_path: pathlib.Path, hacs_filename: str) -> tuple[pathlib.Path, str]:
    repo = tmp_path / "repo"
    sha = make_repo(repo, {
        "custom_components/demo/manifest.json": '{"domain": "demo", "version": "1.2.3"}\n',
        "custom_components/demo/__init__.py": "\n",
        "hacs.json": json.dumps({"name": "Demo", "filename": hacs_filename, "zip_release": True}) + "\n",
    })
    (repo / "vbf.json").write_text(json.dumps({"source": "hacs", "entries": [
        {"path": "custom_components/demo/manifest.json", "selector": "version",
         "transform": "strip-leading-v", "format": "json"}]}), encoding="utf-8")
    return repo, sha


@pytest.mark.parametrize("asset, from_hacs", [
    ("demo\n::warning::injected.zip", "demo.zip"),   # the caller's input
    ("", "demo\r::warning::injected.zip"),           # hacs.json content
])
def test_hacs_asset_filename_is_masked(run, tmp_path, asset, from_hacs):
    repo, sha = hacs_repo(tmp_path, from_hacs)
    proc, output, summary = run(PUBLISH, HACS_STEP, {
        "TAG": "v1.2.3", "TARGET_SHA": sha, "DRY_RUN": "true", "ASSET_FILENAME": asset}, cwd=repo)
    assert proc.returncode == 0, proc.stderr
    shown = (asset or from_hacs).replace("\n", "?").replace("\r", "?")
    expected = [f"::notice::Dry run — built '{shown}' but not uploading to draft 'v1.2.3'."]
    if asset:
        expected.insert(0, f"::warning::asset-filename '{shown}' disagrees with hacs.json filename 'demo.zip' — "
                           "HACS reads hacs.json to pick the asset, so the two MUST match "
                           "(spec/ha/hacs-release §ZIP release distribution).")
    assert commands(proc) == expected
    assert f"Building HACS asset '{shown}' from custom_components/demo at {sha[:8]}." in proc.stdout
    # The summary encodes the name as given; the log mask plays no part there.
    assert f"- Built {md_code(asset or from_hacs)} (dry run, not uploaded)." in summary
    assert output == ""


def test_hacs_clean_filename_is_unchanged(run, tmp_path):
    repo, sha = hacs_repo(tmp_path, "demo.zip")
    proc, _, summary = run(PUBLISH, HACS_STEP, {
        "TAG": "v1.2.3", "TARGET_SHA": sha, "DRY_RUN": "true", "ASSET_FILENAME": ""}, cwd=repo)
    assert proc.returncode == 0, proc.stderr
    assert commands(proc) == ["::notice::Dry run — built 'demo.zip' but not uploading to draft 'v1.2.3'."]
    assert (repo / "demo.zip").is_file()
    assert "- Built <code>demo&#46;zip</code> (dry run, not uploaded)." in summary


# --- reusable-release-publish.yml: Python messages ---------------------------


def test_detect_masks_a_path_from_release_automation(run, tmp_path):
    work = tmp_path / "detect"
    (work / ".github").mkdir(parents=True)
    (work / ".github" / "release-automation.yml").write_text(
        yaml.safe_dump({"version_bearing_files": [{"path": "VERSION\n::warning::injected", "selector": "v"}]}),
        encoding="utf-8")
    proc, output, _ = run(PUBLISH, "Detect project type and load version-bearing files", {"TAG": "v1.2.3"}, cwd=work)
    assert proc.returncode == 1
    assert commands(proc) == ["::error::Cannot infer format for 'VERSION?::warning::injected'; "
                              "declare format: json|toml in .github/release-automation.yml"]
    assert output == ""


def verify_repo(tmp_path: pathlib.Path, version: str, message: str) -> tuple[pathlib.Path, str]:
    repo = tmp_path / "repo"
    sha = make_repo(repo, {"package.json": json.dumps({"name": "x", "version": version}) + "\n"}, message)
    (repo / "vbf.json").write_text(json.dumps({"source": "node", "entries": [
        {"path": "package.json", "selector": "version", "transform": "strip-leading-v", "format": "json"}]}),
        encoding="utf-8")
    return repo, sha


def run_verify(run, repo: pathlib.Path, sha: str):
    helper, _, _ = run(PUBLISH, "Prepare selector helper", cwd=repo)
    assert helper.returncode == 0, helper.stderr
    return run(PUBLISH, "Verify version-bearing-file alignment", {"TAG": "v1.2.3", "TARGET_SHA": sha}, cwd=repo)


def test_verify_masks_a_value_read_from_a_file(run, tmp_path):
    repo, sha = verify_repo(tmp_path, "1.0.0\n::warning::injected", "chore(release): v1.2.3")
    proc, _, _ = run_verify(run, repo, sha)
    assert proc.returncode == 1
    assert [c for c in commands(proc) if not c.startswith("::error::")] == []
    assert "  - package.json: version is '1.0.0?::warning::injected', expected 'v1.2.3' (or '1.2.3')" in proc.stdout


def test_verify_masks_the_commit_subject(run, tmp_path):
    repo, sha = verify_repo(tmp_path, "1.2.3", "fix: bump\r::warning::injected")
    proc, _, _ = run_verify(run, repo, sha)
    assert proc.returncode == 1
    assert [c for c in commands(proc) if not c.startswith("::error::")] == []
    assert "::error::Most recent commit subject on these paths: 'fix: bump?::warning::injected'" in proc.stdout


def test_verify_with_clean_values_is_unchanged(run, tmp_path):
    repo, sha = verify_repo(tmp_path, "1.2.3", "chore(release): v1.2.3")
    proc, _, _ = run_verify(run, repo, sha)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.splitlines() == [
        "All 1 version-bearing file(s) aligned to v1.2.3.",
        "Alignment commit confirmed: 'chore(release): v1.2.3'",
    ]


# --- same-pattern siblings ---------------------------------------------------


@pytest.mark.parametrize("given, listed", [(HOSTILE, drafts("v1.0.0")), ("", drafts(HOSTILE))])
def test_archive_resolve_refuses_a_tag_with_a_control_character(run, given, listed):
    proc, output, _ = run("reusable-release-archive.yml", "Resolve draft",
                          {"REQUESTED_TAG": given, "STUB_LIST": listed, "GH_REPO": "owner/repo"})
    assert proc.returncode == 1
    assert commands(proc) == [REFUSED]
    assert output == ""


def test_archive_resolve_masks_the_api_sha(run):
    proc, output, _ = run("reusable-release-archive.yml", "Resolve draft", {
        "REQUESTED_TAG": "v1.2.3", "STUB_LIST": drafts("v1.2.3"), "GH_REPO": "owner/repo",
        "STUB_TARGET": "develop", "STUB_SHA": "b\n::warning::injected"})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::Draft 'v1.2.3' targets b?::warning::injected, but this run is for")
    assert output == ""


def test_archive_resolve_with_a_clean_tag_is_unchanged(run):
    proc, output, _ = run("reusable-release-archive.yml", "Resolve draft", {
        "REQUESTED_TAG": "", "STUB_LIST": drafts("v1.2.3"), "GH_REPO": "owner/repo",
        "STUB_TARGET": "develop", "STUB_SHA": "a" * 40})
    assert proc.returncode == 0, proc.stderr
    assert commands(proc) == ["::notice::No tag given; resolved the single open draft 'v1.2.3'."]
    tag, target, artifact = output.splitlines()
    assert (tag, target) == ("tag=v1.2.3", f"target_sha={'a' * 40}")
    assert artifact.startswith("artifact=release-archive-")


def test_archive_match_assets_masks_the_pattern(run):
    proc, _, _ = run("reusable-release-archive.yml", "Match assets",
                     {"ASSETS": "dist/*.zip\n", "TASK_TARGET": "build\n::warning::injected",
                      "RUNNER_TEMP": "/nonexistent"})
    assert proc.returncode == 1
    assert commands(proc) == ["::error::Asset pattern 'dist/*.zip' matched no file after "
                              "'task build?::warning::injected'."]


def test_drafter_capture_skips_a_tag_with_a_control_character(run):
    proc, output, _ = run("reusable-release-drafter.yml", "Capture project-context block", {
        "REPO": "owner/repo", "STUB_LIST": json.dumps({"isDraft": True, "tagName": HOSTILE})})
    assert proc.returncode == 0
    assert commands(proc) == ["::warning::Draft tag 'v1?::warning::injected' contains a control character "
                              "or '##[' (shown as '?' and '#?['); not capturing its project-context block."]
    assert output == "had_markers=false\n"


def test_drafter_capture_with_a_clean_tag_is_unchanged(run):
    proc, output, _ = run("reusable-release-drafter.yml", "Capture project-context block", {
        "REPO": "owner/repo", "STUB_LIST": json.dumps({"isDraft": True, "tagName": "v1.2.3"}),
        "STUB_BODY": "notes"})
    assert proc.returncode == 0
    assert commands(proc) == []
    assert proc.stdout == "Draft 'v1.2.3' has no project-context marker pair.\n"
    assert output == "had_markers=false\n"


def test_refresh_master_refusal_masks_the_refs(run):
    proc, _, _ = run("reusable-release-cd-refresh-master.yml", "Refuse: no permitted write path", {
        "TARGET": "master\n::warning::injected", "FROM_REF": "v1.2.3",
        "REASON": "the target forbids merge commits and force pushes alike"})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::Cannot refresh 'master?::warning::injected' to v1.2.3: the target forbids")


def test_docker_image_reference_with_a_control_character_is_refused(run):
    proc, output, _ = run("reusable-docker-publish.yaml", "Resolve the image reference",
                          {"RAW": "ghcr.io/Owner/app\nother=1"})
    assert proc.returncode == 1
    assert commands(proc) == ["::error::Image reference 'ghcr.io/Owner/app?other=1' contains a control "
                              "character or '##[' (shown as '?' and '#?['); check the registry and image_name "
                              "inputs."]
    assert output == ""


def test_docker_image_reference_is_unchanged(run):
    proc, output, _ = run("reusable-docker-publish.yaml", "Resolve the image reference", {"RAW": "ghcr.io/Owner/App"})
    assert proc.returncode == 0
    assert output == "name=ghcr.io/owner/app\n"


@pytest.mark.parametrize("version, refused", [("0.55.0\nother=1", True), ("0.55.0", False)])
def test_tflint_cache_key(run, version, refused):
    proc, output, _ = run("reusable-tf-lint.yaml", "Compute the plugin cache key",
                          {"TFLINT_VERSION": version, "CONFIG_HASH": "f" * 64, "ImageOS": "ubuntu24"})
    if refused:
        assert proc.returncode == 1
        assert len(commands(proc)) == 1 and commands(proc)[0].startswith("::error::Cache key '")
        assert "0.55.0?other=1" in commands(proc)[0]
        assert output == ""
    else:
        assert proc.returncode == 0
        assert output == f"key=tflint-plugins|Linux|X64|image:ubuntu24|0.55.0|{'f' * 64}\n"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_nodejs_coverage_masks_the_percentage(run, tmp_path):
    summary = tmp_path / "coverage-summary.json"
    summary.write_text(json.dumps({"total": {"lines": {"pct": "100\n::warning::injected"}}}), encoding="utf-8")
    proc, _, _ = run("reusable-nodejs-coverage.yaml", "Enforce coverage threshold",
                     {"SUMMARY_PATH": str(summary), "FAIL_UNDER": "80"})
    # A string compares false against the threshold, so it reached the
    # plain log line -- unmasked before #492.
    assert commands(proc) == []
    assert "Line coverage 100?::warning::injected% meets the required 80%." in proc.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_nodejs_coverage_masks_the_missing_path(run):
    proc, _, _ = run("reusable-nodejs-coverage.yaml", "Render coverage into the job summary",
                     {"SUMMARY_PATH": "missing\n::warning::injected"})
    assert proc.returncode == 1
    assert commands(proc) == ["::error::Coverage summary not found at missing?::warning::injected"]


# --- '##[' mid-line, no control character (#492 F1) -----------------------
#
# The older command syntax is read anywhere in a line, so these values need no
# line break. Each test shows the value reaches no line that `commands()`
# would hand the runner, except the one intended `::` line.


def no_v1_commands(proc: subprocess.CompletedProcess) -> None:
    lines = (proc.stdout + "\n" + proc.stderr).splitlines()
    assert not [line for line in lines if "##[" in line and not line.lstrip().startswith("::")]


@pytest.mark.parametrize("workflow", [PUBLISH, "reusable-release-archive.yml"])
@pytest.mark.parametrize("given, listed, shown", [
    (HOSTILE_V1, drafts("v1.0.0"), "v1#?[set-output name=x]y"),
    ("", drafts("v2" + HOSTILE_WARN), "v2#?[warning]z"),
])
def test_tag_with_v1_command_is_refused(run, workflow, given, listed, shown):
    proc, output, _ = run(workflow, "Resolve draft",
                          {"REQUESTED_TAG": given, "STUB_LIST": listed, "GH_REPO": "owner/repo"})
    assert proc.returncode == 1
    assert commands(proc) == [refused(shown)]
    assert output == ""


def test_archive_lists_draft_tag_names_masked(run):
    proc, output, _ = run("reusable-release-archive.yml", "Resolve draft", {
        "REQUESTED_TAG": "", "STUB_LIST": drafts("v1.0.0", HOSTILE, "v3" + HOSTILE_WARN), "GH_REPO": "owner/repo"})
    assert proc.returncode == 1
    assert len(commands(proc)) == 1 and commands(proc)[0].startswith("::error::No tag given and 3 drafts")
    assert "  - v1.0.0\n  - v1?::warning::injected\n  - v3#?[warning]z\n" in proc.stderr
    assert output == ""


def test_drafter_capture_skips_a_tag_with_a_v1_command(run):
    proc, output, _ = run("reusable-release-drafter.yml", "Capture project-context block", {
        "REPO": "owner/repo", "STUB_LIST": json.dumps({"isDraft": True, "tagName": HOSTILE_V1})})
    assert proc.returncode == 0
    [line] = commands(proc)
    assert line.startswith("::warning::Draft tag 'v1#?[set-output name=x]y' contains")
    assert output == "had_markers=false\n"


def test_expected_target_sha_with_a_v1_command_is_masked(run):
    proc, _, _ = run(PUBLISH, "Check the draft target against the expected commit",
                     {"EXPECTED_TARGET_SHA": "abc" + HOSTILE_WARN, "AUTO_ALIGN": "false",
                      "TAG": "v1.2.3", "DRAFT_TARGET": "b" * 40})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::expected-target-sha 'abc#?[warning]z' is not a full")


def test_hacs_asset_filename_with_a_v1_command_is_masked(run, tmp_path):
    repo, sha = hacs_repo(tmp_path, "demo.zip")
    proc, _, summary = run(PUBLISH, HACS_STEP, {
        "TAG": "v1.2.3", "TARGET_SHA": sha, "DRY_RUN": "true", "ASSET_FILENAME": "demo" + HOSTILE_WARN + ".zip"},
        cwd=repo)
    assert proc.returncode == 0, proc.stderr
    no_v1_commands(proc)
    assert "Building HACS asset 'demo#?[warning]z.zip' from custom_components/demo" in proc.stdout
    assert "asset: demo#?[warning]z.zip" in proc.stdout
    assert f"- Built {md_code('demo' + HOSTILE_WARN + '.zip')} (dry run, not uploaded)." in summary
    assert "##[" not in summary


@pytest.mark.parametrize("version", ["0.55.0##[set-output name=key]attacker", "0.55.0" + HOSTILE_WARN])
def test_tflint_version_with_a_v1_command_is_refused(run, version):
    proc, output, _ = run("reusable-tf-lint.yaml", "Compute the plugin cache key",
                          {"TFLINT_VERSION": version, "CONFIG_HASH": "f" * 64, "ImageOS": "ubuntu24"})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::Cache key '") and "0.55.0#?[" in line
    assert "Cache key: " not in proc.stdout
    assert output == ""


def test_docker_image_reference_with_a_v1_command_is_refused(run):
    proc, output, _ = run("reusable-docker-publish.yaml", "Resolve the image reference",
                          {"RAW": "ghcr.io/owner/app" + HOSTILE_WARN})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::Image reference 'ghcr.io/owner/app#?[warning]z' contains")
    assert output == ""


def test_docker_image_reference_with_a_trailing_line_break_is_unchanged(run):
    # An image_name written as a YAML block scalar ends in a line break. The
    # runner ignored the blank line it left in $GITHUB_OUTPUT; the refusal
    # must not turn that into a failure.
    proc, output, _ = run("reusable-docker-publish.yaml", "Resolve the image reference",
                          {"RAW": "ghcr.io/Owner/App\n\n"})
    assert proc.returncode == 0, proc.stdout
    assert output == "name=ghcr.io/owner/app\n"
    proc, output, _ = run("reusable-docker-publish.yaml", "Resolve the image reference",
                          {"RAW": "ghcr.io/Owner/App\nother=1\n"})
    assert proc.returncode == 1 and output == ""


def test_verify_masks_a_v1_command_in_the_confirmed_subject(run, tmp_path):
    repo, sha = verify_repo(tmp_path, "1.2.3", "chore(release): v1.2.3 " + HOSTILE_WARN)
    proc, _, _ = run_verify(run, repo, sha)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert commands(proc) == []
    assert "Alignment commit confirmed: 'chore(release): v1.2.3 #?[warning]z'" in proc.stdout


def test_verify_masks_a_v1_command_in_a_file_value(run, tmp_path):
    repo, sha = verify_repo(tmp_path, "1.0.0" + HOSTILE_WARN, "chore(release): v1.2.3")
    proc, _, _ = run_verify(run, repo, sha)
    assert proc.returncode == 1
    no_v1_commands(proc)
    assert "version is '1.0.0#?[warning]z'" in proc.stdout


def test_detect_neutralises_v1_commands_in_the_printed_vbf_json(run, tmp_path):
    work = tmp_path / "detect"
    (work / ".github").mkdir(parents=True)
    (work / ".github" / "release-automation.yml").write_text(
        yaml.safe_dump({"version_bearing_files": [{"path": "pkg" + HOSTILE_WARN + ".json", "selector": "version"}]}),
        encoding="utf-8")
    proc, output, _ = run(PUBLISH, "Detect project type and load version-bearing files", {"TAG": "v1.2.3"}, cwd=work)
    assert proc.returncode == 0, proc.stderr
    no_v1_commands(proc)
    assert '"path": "pkg#?[warning]z.json"' in proc.stdout
    assert json.loads((work / "vbf.json").read_text())["entries"][0]["path"] == "pkg" + HOSTILE_WARN + ".json", \
        "the file itself keeps the value; only the log line is neutralised"
    assert output == "source=override\ncount=1\n"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_nodejs_coverage_masks_a_v1_command_in_the_percentage(run, tmp_path):
    summary = tmp_path / "coverage-summary.json"
    summary.write_text(json.dumps({"total": {"lines": {"pct": "100" + HOSTILE_WARN}}}), encoding="utf-8")
    proc, _, _ = run("reusable-nodejs-coverage.yaml", "Enforce coverage threshold",
                     {"SUMMARY_PATH": str(summary), "FAIL_UNDER": "80"})
    assert commands(proc) == []
    assert "Line coverage 100#?[warning]z% meets the required 80%." in proc.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("step", ["Enforce coverage threshold", "Render coverage into the job summary"])
@pytest.mark.parametrize("content", [None, '{"total": "' + HOSTILE_WARN + '\n::warning::injected'])
def test_nodejs_coverage_masks_an_unreadable_summary(run, tmp_path, step, content):
    path = tmp_path / ("cov" + HOSTILE_WARN + ".json")
    if content is not None:
        path.write_text(content, encoding="utf-8")
    proc, _, _ = run("reusable-nodejs-coverage.yaml", step, {"SUMMARY_PATH": str(path), "FAIL_UNDER": "80"})
    assert proc.returncode == 1
    [line] = commands(proc)
    assert line.startswith("::error::") and "cov#?[warning]z.json" in line
    assert "at Object" not in proc.stderr, "no Node stack trace"


# --- plain log lines the first round left without a test --------------------


def test_archive_matched_line_masks_the_directory(run, tmp_path):
    work = tmp_path / "build"
    for d in ("d" + HOSTILE_WARN, "e\r::warning::x"):
        (work / d).mkdir(parents=True)
        (work / d / "a.zip" if d.startswith("d") else work / d / "b.zip").write_text("x", encoding="utf-8")
    temp = tmp_path / "runner-temp"
    temp.mkdir()
    proc, _, _ = run("reusable-release-archive.yml", "Match assets",
                     {"ASSETS": "d*/a.zip\ne*/b.zip\n", "TASK_TARGET": "build", "RUNNER_TEMP": str(temp)}, cwd=work)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert commands(proc) == []
    assert proc.stdout.splitlines() == ["Matched: d#?[warning]z/a.zip", "Matched: e?::warning::x/b.zip"]


@pytest.mark.parametrize("target, shown", [("main" + HOSTILE_WARN, "main#?[warning]z"),
                                           ("main\r::warning::x", "main?::warning::x")])
def test_refresh_strategy_line_masks_the_target(run, target, shown):
    proc, output, _ = run("reusable-release-cd-refresh-master.yml",
                          "Determine the write strategy from the target's protection", {"TARGET": target})
    assert proc.returncode == 0, proc.stderr
    assert commands(proc) == []
    assert proc.stdout.splitlines()[0] == f"Strategy for '{shown}': merge -- merge commits are permitted"
    assert output == "mode=merge\nreason=merge commits are permitted\n"


GIT_STUB = """#!/usr/bin/env bash
case "$1" in
  fetch|push) exit 0 ;;
  rev-parse) echo "$STUB_SOURCE_SHA" ;;
  ls-remote) [[ -z "$STUB_EXPECTED" ]] || printf '%s\\trefs/heads/x\\n' "$STUB_EXPECTED" ;;
esac
"""


@pytest.mark.parametrize("expected, says", [("", "does not exist yet; creating it."),
                                            ("c" * 40, f"already points at {'c' * 40}; nothing to do.")])
def test_refresh_branch_lines_mask_the_target(run, expected, says):
    proc, _, _ = run("reusable-release-cd-refresh-master.yml", "Refresh the presentation branch", {
        "FROM_REF": "v1.2.3", "TARGET": "pres" + HOSTILE_WARN, "MODE": "merge",
        "STUB_SOURCE_SHA": "c" * 40, "STUB_EXPECTED": expected}, stubs_extra={"git": GIT_STUB})
    assert proc.returncode == 0, proc.stderr
    assert commands(proc) == []
    assert proc.stdout.splitlines() == [f"Target branch 'pres#?[warning]z' {says}"]


def test_probe_masks_the_run_json(run):
    proc, _, _ = run(PUBLISH, "Probe cascade run (App token path)",
                     {"TARGET_SHA": "a" * 40, "STUB_RUNS": '{"status":"' + HOSTILE_WARN + '"}'},
                     stubs_extra={"sleep": "#!/usr/bin/env bash\nexit 0\n"})
    assert proc.returncode == 0
    assert commands(proc) == []
    assert 'run detected: {"status":"#?[warning]z"}' in proc.stdout


VALE_STUB = """#!/usr/bin/env bash
if [[ "$1" == "sync" ]]; then echo "Downloading pkg##[warning]sync"; exit 0; fi
echo " release-notes.vale.md"
printf ' 1:1  error  Did you really mean %s?  Vale.Spelling\\r::warning::cr\\n' "'x##[warning]z'"
exit 1
"""


def test_vale_output_is_neutralised_and_its_status_kept(run):
    proc, _, _ = run(PUBLISH, "Check the release notes with Vale", {
        "TAG": "v1.2.3", "VALE_OUTCOME": "success", "VALE_RESULT": "installed", "STUB_BODY": "Some notes."},
        stubs_extra={"vale": VALE_STUB})
    assert proc.returncode == 1, "a Vale error still blocks through the filter"
    assert commands(proc) == ["::error::The release notes for 'v1.2.3' carry Vale errors. Edit the draft body "
                              "(gh release edit 'v1.2.3' --notes-file ...) and re-run -- publishing freezes this text."]
    assert "Downloading pkg#?[warning]sync" in proc.stdout
    assert "'x#?[warning]z'?  Vale.Spelling?::warning::cr" in proc.stdout


def test_docs_freshness_report_is_neutralised_and_its_status_kept(run, tmp_path):
    work = tmp_path / "consumer"
    (work / "docs").mkdir(parents=True)
    checker = work / ".gh-plumbing" / "scripts" / "docs_freshness.py"
    checker.parent.mkdir(parents=True)
    checker.write_text("import sys\nprint('- docs/x##[warning]z.md\\r::warning::cr')\n"
                       "print('::error::1 blocking documentation-freshness finding(s)', file=sys.stderr)\n"
                       "sys.exit(1)\n", encoding="utf-8")
    proc, _, _ = run(PUBLISH, "Check documentation freshness", {"TAG": "v1.2.3"}, cwd=work)
    assert proc.returncode == 1
    assert commands(proc) == ["::error::1 blocking documentation-freshness finding(s)",
                              "::error::The documentation carries critical freshness findings. Publishing 'v1.2.3' "
                              "would ship them, because the site and the notes freeze with the tag. Fix them on "
                              "develop and re-run."]
    assert "- docs/x#?[warning]z.md?::warning::cr" in proc.stdout


# --- last round: keys in vbf.json, the publish draft listings ---------------


def test_detect_neutralises_v1_commands_in_vbf_json_keys(run, tmp_path):
    # On the override path an entry is a whole mapping from the repository,
    # keys included; the logged JSON neutralises keys as well as values.
    work = tmp_path / "detect"
    (work / ".github").mkdir(parents=True)
    entry = {"path": "pkg.json", "selector": "version", "##[error]from-a-key": 1, "k\x07##[x": 2}
    (work / ".github" / "release-automation.yml").write_text(
        yaml.safe_dump({"version_bearing_files": [entry]}), encoding="utf-8")
    proc, output, _ = run(PUBLISH, "Detect project type and load version-bearing files", {"TAG": "v1.2.3"}, cwd=work)
    assert proc.returncode == 0, proc.stderr
    assert commands(proc) == []
    assert '"#?[error]from-a-key": 1,' in proc.stdout
    assert '"k\\u0007#?[x": 2' in proc.stdout, "JSON escapes the control character, the filter the '##['"
    assert output == "source=override\ncount=1\n"


@pytest.mark.parametrize("given", ["", "v9.9.9"])
def test_publish_lists_draft_tag_names_with_v1_commands_masked(run, given):
    proc, output, _ = run(PUBLISH, "Resolve draft", {
        "REQUESTED_TAG": given, "STUB_LIST": drafts("v1.0.0", "v3" + HOSTILE_WARN, "v4###[x")})
    assert proc.returncode == 1
    assert len(commands(proc)) == 1 and commands(proc)[0].startswith("::error::")
    assert "  - v1.0.0\n  - v3#?[warning]z\n  - v4##?[x\n" in proc.stderr
    assert output == ""



# --- the step summary is Markdown (#506) -------------------------------------------
#
# GitHub renders $GITHUB_STEP_SUMMARY. A caller input, draft text, a file name
# or a figure from the test run must not add a link, an image, a heading, a
# mention or a table cell there. Each test runs a repaired step and checks that
# outside the <code>/<pre> elements the helper writes, none of the value's
# Markdown survives, and that inside them only entities stand for punctuation.

MD_HOSTILE = "[x](https://example.com) <img src=x> @octocat #1 |c| `d` **e** a@b.co"
MD_FRAGMENTS = ("[x](", "<img", "@octocat", "#1", "|c|", "`d`", "**e**", "https://", "a@b.co")


def assert_inert(summary: str, allowed: tuple[str, ...] = ()) -> None:
    # The encoder writes `@` as `&#64;<!-- -->`; that comment is the only tag
    # it emits inside an element.
    summary = summary.replace("&#64;<!-- -->", "&#64;")
    rest = re.sub(r"(?s)<code>[^<]*</code>|<pre>[^<]*</pre>", "", summary)
    for fragment in MD_FRAGMENTS:
        if fragment not in allowed:
            assert fragment not in rest, (fragment, rest)
    for element in re.findall(r"(?s)<code>([^<]*)</code>|<pre>([^<]*)</pre>", summary):
        inner = re.sub(r"&#[0-9]+;", "", "".join(element))
        assert not re.search(r"[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]", inner), inner


def test_disclose_encodes_tag_title_and_body(run):
    body = f"## Notes\n\n{MD_HOSTILE}\n```\n</pre>\n# heading\r\nlast"
    proc, _, summary = run(PUBLISH, "Disclose target state in job summary", {
        "TAG": "v1.2.3[x](u)", "TARGET_SHA": "a" * 40, "DRY_RUN": "true", "VBF_SOURCE": "python",
        "VBF_COUNT": "1", "STUB_TITLE": MD_HOSTILE, "STUB_BODY": body, "STUB_CREATED": "2026-11-20T00:00:00Z",
        "GITHUB_ACTOR": "octocat", "GITHUB_SERVER_URL": "https://github.com", "GITHUB_RUN_ID": "1"})
    assert proc.returncode == 0, proc.stderr
    # The triggerer stays a mention and the run URL a link, on purpose.
    assert_inert(summary, allowed=("@octocat", "https://"))
    assert "| Triggerer | @octocat |" in summary
    assert "| Run URL | https://github.com/owner/repo/actions/runs/1 |" in summary
    assert f"| Title | {md_code(MD_HOSTILE)} |" in summary
    assert summary.count("<pre>") == 1 and summary.count("</pre>") == 1
    assert "```" not in summary and "# heading" not in summary


def test_disclose_keeps_the_empty_title_fallback(run):
    proc, _, summary = run(PUBLISH, "Disclose target state in job summary", {
        "TAG": "v1.2.3", "TARGET_SHA": "a" * 40, "DRY_RUN": "false", "VBF_SOURCE": "python", "VBF_COUNT": "1",
        "GITHUB_ACTOR": "octocat", "GITHUB_SERVER_URL": "https://github.com", "GITHUB_RUN_ID": "1"})
    assert proc.returncode == 0, proc.stderr
    assert "| Title | _(empty)_ |" in summary


def test_refresh_master_refusal_encodes_the_refs_in_the_summary(run):
    proc, _, summary = run("reusable-release-cd-refresh-master.yml", "Refuse: no permitted write path", {
        "TARGET": "master" + MD_HOSTILE, "FROM_REF": "v1.2.3",
        "REASON": "a `pull_request` ruleset rule requires every change to arrive through a pull request"})
    assert proc.returncode == 1
    assert_inert(summary)
    assert f"Cannot refresh {md_code('master' + MD_HOSTILE)} to {md_code('v1.2.3')}: a `pull_request`" in summary
    assert "| Reason | a `pull_request` ruleset rule" in summary, "REASON keeps its intended Markdown"


def test_archive_dry_run_encodes_the_asset_names(run, tmp_path):
    archive = tmp_path / "work" / "release-archive"
    archive.mkdir(parents=True)
    hostile = "a[x](u) @octocat #1 |c| `d`.tar.gz"
    (archive / hostile).write_text("x", encoding="utf-8")
    proc, _, summary = run("reusable-release-archive.yml", "Attach to the draft", {
        "TAG": "v1.2.3", "BUILT_SHA": "a" * 40, "DRY_RUN": "true", "GH_REPO": "owner/repo"})
    assert proc.returncode == 0, proc.stderr
    assert_inert(summary)
    assert summary == f"### Release archive (dry run)\n- {md_code(hostile)}\n"


def test_python_coverage_writes_the_report_as_one_pre_block(run):
    stub = "#!/usr/bin/env bash\n" + 'printf \'%s\\n\' "Name    Stmts" "' + MD_HOSTILE + '.py  3" "</pre>"\n'
    proc, _, summary = run("reusable-python-coverage.yaml", "Render coverage into the job summary",
                           stubs_extra={"coverage": stub})
    assert proc.returncode == 0, proc.stderr
    assert_inert(summary)
    assert summary.startswith("## Test coverage\n\n<pre>Name    Stmts\n")
    assert summary.count("<pre>") == 1 and summary.endswith("</pre>\n")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_nodejs_coverage_encodes_the_figures(run, tmp_path):
    report = tmp_path / "coverage-summary.json"
    metric = {"pct": MD_HOSTILE, "covered": 1, "total": 2}
    report.write_text(json.dumps({"total": {k: metric for k in ("lines", "statements", "functions", "branches")}}),
                      encoding="utf-8")
    proc, _, table = run("reusable-nodejs-coverage.yaml", "Render coverage into the job summary",
                         {"SUMMARY_PATH": str(report)})
    assert proc.returncode == 0, proc.stderr
    assert_inert(table)
    rows = [line for line in table.splitlines() if line.startswith("| <code>")]
    assert len(rows) == 4 and all(row.count("|") == 4 for row in rows), "three cells per row"
