"""Runs the step summary's canonical helpers on hostile text (#506).

GitHub renders `$GITHUB_STEP_SUMMARY` as Markdown. The reusable workflows and
the scripts they run write caller-, draft- and repository-controlled text
there through one helper per language: control characters become `?`, every
ASCII punctuation character its numeric HTML entity, and the result sits
inside `<code>` (one line) or `<pre>` (line ends kept). With no punctuation
left, nothing in the value can open a link, an image, a heading, a code span,
a table cell or raw HTML; inside `<code>`/`<pre>` GitHub links no `@name` or
`#1` either. That rendering was measured once on GitHub's `/markdown`
endpoint (gfm mode), not on a rendered step summary.

Each helper is taken from where it ships -- the bash and Node lines from the
workflow files, the Python one from scripts/workflow_command_masking.py and
the scripts that copy it -- and executed, so the tested helper is the shipped
one. scripts/workflow_command_masking.py holds the workflows to these exact
lines; its own tests hold the rule.
"""

from __future__ import annotations

import html
import importlib.util
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCRIPTS = REPO_ROOT / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # Registered first: @dataclass resolves its module through sys.modules.
    sys.modules.setdefault(name, module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return sys.modules[name]


guard = load("workflow_command_masking")

# Backticks, a pipe, a CRLF and a lone CR, a closing </pre>, a link, an image,
# a mention, an issue reference, an ampersand, a fence, a bell and an escape,
# a bare URL, a heading marker, and a non-ASCII letter that must pass as is.
HOSTILE = ("a`b`|c\r\nd</pre>[x](https://example.com)<img src=x>@name #1 & ```\x07\x1b"
           "\n# h\nwww.example.com é\rz")
PUNCTUATION = re.compile(r"[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]")


def inert(inner: str, line_ends: bool) -> None:
    """No ASCII punctuation outside `&#NN;`, no control character but kept line ends."""
    rest = re.sub(r"&#[0-9]+;", "", inner)
    assert not PUNCTUATION.search(rest), rest
    controls = [c for c in rest if ord(c) < 0x20 or 0x7f <= ord(c) <= 0x9f]
    assert controls == (["\n"] * controls.count("\n") if line_ends else []), controls


def check_code(out: str) -> None:
    m = re.fullmatch(r"<code>(.*)</code>", out, re.DOTALL)
    assert m, out
    inert(m.group(1), line_ends=False)
    # Lossless: decoding gives the value back, control characters as '?'.
    assert html.unescape(m.group(1)) == re.sub(r"[\x00-\x1f\x7f-\x9f]", "?", HOSTILE)


def check_pre(out: str) -> None:
    m = re.fullmatch(r"<pre>(.*)\n</pre>\n?", out, re.DOTALL)
    assert m, out
    inert(m.group(1), line_ends=True)
    lines = HOSTILE.replace("\r\n", "\n").split("\n")
    assert html.unescape(m.group(1)) == "\n".join(re.sub(r"[\x00-\x1f\x7f-\x9f]", "?", line) for line in lines)
    assert "</pre>" not in m.group(1)


def shipped_lines(workflow: str, block: tuple[str, ...]) -> str:
    """The helper's lines as they stand in the workflow file, each exactly the guard's."""
    lines = [line.strip() for line in (WORKFLOWS / workflow).read_text(encoding="utf-8").splitlines()]
    for wanted in block:
        assert wanted in lines, f"{workflow} does not ship {wanted[:40]!r}"
    return "\n".join(line for line in lines if line in block)


def run_bash(form: str, workflow: str = "reusable-release-publish.yml") -> str:
    script = shipped_lines(workflow, guard.SHELL_MD) + f'\nset -euo pipefail\n{form} "$1"\n'
    return subprocess.run(["bash", "-c", script, "bash", HOSTILE], capture_output=True, text=True,
                          check=True).stdout


@pytest.mark.parametrize("workflow", [
    "reusable-release-publish.yml", "reusable-release-archive.yml",
    "reusable-release-cd-refresh-master.yml", "reusable-python-coverage.yaml",
])
def test_the_bash_helper_encodes_and_wraps(workflow):
    check_code(run_bash("md_code", workflow))
    check_pre(run_bash("md_pre", workflow))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_node_helper_encodes_and_wraps(tmp_path):
    lines = shipped_lines("reusable-nodejs-coverage.yaml", guard.JS_MD)
    for form, check in (("mdCode", check_code), ("mdPre", check_pre)):
        script = tmp_path / f"{form}.js"
        script.write_text(lines + f"\nprocess.stdout.write({form}(process.argv[2]));\n", encoding="utf-8")
        check(subprocess.run(["node", str(script), HOSTILE], capture_output=True, text=True, check=True).stdout)


def python_helpers(source: str) -> dict:
    namespace: dict = {}
    exec("import re\n" + source, namespace)  # noqa: S102 -- the guard's own constant
    return namespace


@pytest.mark.parametrize("script", ["docs_freshness", "branch_protection_audit"])
def test_the_scripts_ship_the_python_helper_unchanged(script):
    assert guard.PY_MD in (SCRIPTS / f"{script}.py").read_text(encoding="utf-8")
    module = load(script)
    check_code(module.md_code(HOSTILE))
    check_pre(module.md_pre(HOSTILE))


def test_the_python_helper_encodes_and_wraps():
    helpers = python_helpers(guard.PY_MD)
    check_code(helpers["md_code"](HOSTILE))
    check_pre(helpers["md_pre"](HOSTILE))


def test_the_three_languages_agree():
    helpers = python_helpers(guard.PY_MD)
    assert run_bash("md_code") == helpers["md_code"](HOSTILE)
    assert run_bash("md_pre") == helpers["md_pre"](HOSTILE) + "\n"


def test_an_empty_value_still_wraps():
    helpers = python_helpers(guard.PY_MD)
    assert helpers["md_code"]("") == "<code></code>"
    assert helpers["md_pre"]("") == "<pre>\n</pre>"
