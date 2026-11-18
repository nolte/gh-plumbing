"""Behavioural tests for #492: printed values can't start a workflow command.

The runner reads every line a step prints as a possible workflow command. A
value with a line break followed by `::warning::...` -- a caller input, a draft
tag name, repository content -- would start one, and written as
`name=$value` to `$GITHUB_OUTPUT` it would add an output entry. Nothing fails
when that happens, so the load-bearing cases are the hostile values themselves.

Each test reads a step's real `run:` body from the workflow file and runs it
under bash (or the heredoc's interpreter, through bash) against stubs for `gh`,
in a throwaway git repository where the step needs one. A test asserts on
every line of stdout AND stderr -- split the way the runner would, on any line
break -- that only the intended command lines start with `::`, and on the
exact `$GITHUB_OUTPUT` content. Clean-value cases pin today's behaviour.

The class itself -- every command line in every reusable workflow -- is held
by scripts/workflow_command_masking.py and its tests.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
HOSTILE = "v1\n::warning::injected"

GH_STUB = """#!/usr/bin/env bash
echo "gh $*" >> "$STUB_LOG"
case "$1 $2" in
  "release list") printf '%s\\n' "$STUB_LIST" ;;
  "release view")
    case "$*" in
      *targetCommitish*) printf '%s\\n' "$STUB_TARGET" ;;
      *body*) printf '%s\\n' "$STUB_BODY" ;;
    esac ;;
  "api "*) printf '%s\\n' "$STUB_SHA" ;;
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

    def _run(workflow: str, name: str, env: dict[str, str] | None = None, cwd: pathlib.Path = work):
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
            **(env or {}),
        }
        proc = subprocess.run(["bash", "-e", str(script)], cwd=cwd, env=full,
                              capture_output=True, text=True, check=False)
        return proc, output.read_text(encoding="utf-8"), summary.read_text(encoding="utf-8")

    return _run


def commands(proc: subprocess.CompletedProcess) -> list[str]:
    """Every line of stdout and stderr the runner could read as a command.

    `splitlines()` breaks on CR, NEL and U+2028 as well as LF -- wider than the
    runner, so a value that survives this survives the runner too.
    """
    lines = (proc.stdout + "\n" + proc.stderr).splitlines()
    return [line.lstrip() for line in lines if line.lstrip().startswith("::")]


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
REFUSED = "::error::Tag 'v1?::warning::injected' contains a control character (shown as '?'); " \
          "refusing to continue."


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
    assert commands(proc) == ["::error::Tag 'v1?x' contains a control character (shown as '?'); refusing to continue."]
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
    assert f"- Built `{shown}` (dry run, not uploaded)." in summary
    assert output == ""


def test_hacs_clean_filename_is_unchanged(run, tmp_path):
    repo, sha = hacs_repo(tmp_path, "demo.zip")
    proc, _, summary = run(PUBLISH, HACS_STEP, {
        "TAG": "v1.2.3", "TARGET_SHA": sha, "DRY_RUN": "true", "ASSET_FILENAME": ""}, cwd=repo)
    assert proc.returncode == 0, proc.stderr
    assert commands(proc) == ["::notice::Dry run — built 'demo.zip' but not uploading to draft 'v1.2.3'."]
    assert (repo / "demo.zip").is_file()
    assert "- Built `demo.zip` (dry run, not uploaded)." in summary


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
                              "(shown as '?'); not capturing its project-context block."]
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
                              "character (shown as '?'); check the registry and image_name inputs."]
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
