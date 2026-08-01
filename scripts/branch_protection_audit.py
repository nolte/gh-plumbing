#!/usr/bin/env python3
"""Compare declared branch protection against what GitHub actually enforces.

Branch protection declared in `.github/settings.yml` is frequently not applied.
The declaration looks correct, the Probot Settings App reports nothing, and the
protection is absent. Nobody notices until a merge that should have been
blocked goes through -- see issue #387.

The defining property of that fault is invisibility: no error, no log, no
failed check. This script makes it visible, and fails when declared protection
is missing so a scheduled run cannot pass silently.

It reports *per declared context* rather than diffing sets, because the
interesting case in practice is a partial application: `gh-plumbing` declares
three required contexts and GitHub enforces one.

Reads only. Requires a token with `repo` scope (administration read) for every
repository surveyed; repositories it cannot read are reported as such rather
than skipped, since an unreadable repository is indistinguishable from an
unprotected one otherwise.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
COMMONS_REPO = "nolte/gh-plumbing"
COMMONS_PATH = ".github/commons-settings.yml"


class Forbidden(Exception):
    """The token may not read this resource."""


def api(path: str, token: str):
    """GET a JSON endpoint.

    Returns None on 404. Raises Forbidden on 403 so a permission gap is never
    mistaken for an absent protection rule -- with a token that cannot read
    administration, every repository would otherwise look unprotected, which is
    the most dangerous possible false negative for this script.
    """
    req = urllib.request.Request(
        f"{API}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gh-plumbing-branch-protection-audit",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code == 403:
            raise Forbidden(path) from exc
        if exc.code == 401:
            raise SystemExit(
                "::error::the token was rejected (401). A scheduled audit that "
                "cannot authenticate must fail loudly, not report an empty "
                "portfolio as healthy."
            )
        raise


def read_yaml_file(repo: str, path: str, token: str):
    """Fetch and parse a YAML file from a repository's default branch."""
    payload = api(f"repos/{repo}/contents/{path}", token)
    if payload is None:
        return None
    import yaml  # imported late so --help works without the dependency

    return yaml.safe_load(base64.b64decode(payload["content"]).decode())


def declared_contexts(settings, commons, branch: str):
    """Resolve the contexts a repository declares for one branch.

    The Probot Settings App merges `branches:` entries by `name`, so a per-repo
    entry overrides the commons entry of the same name field by field.
    """
    def contexts_from(doc):
        if not isinstance(doc, dict):
            return None
        for entry in doc.get("branches") or []:
            if entry.get("name") != branch:
                continue
            checks = (entry.get("protection") or {}).get("required_status_checks")
            if checks is None:
                continue
            return list(checks.get("contexts") or [])
        return None

    own = contexts_from(settings)
    if own is not None:
        return own
    # Only fall through to the commons when the repository extends them.
    if settings and settings.get("_extends"):
        return contexts_from(commons) or []
    return []


def audit_repo(repo: str, branch: str, commons, token: str) -> dict:
    result = {"repo": repo, "branch": branch, "notes": []}

    try:
        settings = read_yaml_file(repo, ".github/settings.yml", token)
    except Forbidden:
        result["status"] = "unreadable"
        result["notes"].append("the token may not read this repository's contents")
        return result
    if settings is None:
        result["status"] = "no-settings"
        result["notes"].append("no .github/settings.yml")
        return result

    result["extends"] = settings.get("_extends") or "(none)"
    declared = declared_contexts(settings, commons, branch)
    result["declared"] = declared

    try:
        protection = api(f"repos/{repo}/branches/{branch}/protection", token)
    except Forbidden:
        result["status"] = "unreadable"
        result["live"] = []
        result["notes"].append(
            "the token may not read branch protection here; this is NOT evidence "
            "that the branch is unprotected"
        )
        return result
    if protection is None:
        result["status"] = "unprotected" if declared else "ok"
        result["live"] = []
        if declared:
            result["notes"].append(
                f"{len(declared)} context(s) declared, branch has no protection at all"
            )
        return result

    checks = protection.get("required_status_checks") or {}
    live = list(checks.get("contexts") or [])
    result["live"] = live
    result["strict"] = checks.get("strict")
    result["enforce_admins"] = (protection.get("enforce_admins") or {}).get("enabled")
    result["restrictions"] = "present" if protection.get("restrictions") else "null"

    # Distinguish "the commons were applied and something was dropped" from
    # "the commons were never applied". The commons declare enforce_admins and
    # strict for develop; a repository that extends them and reports neither is
    # a different fault from one that reports both and is missing a context.
    if settings.get("_extends") and isinstance(commons, dict):
        for entry in commons.get("branches") or []:
            if entry.get("name") != branch:
                continue
            wanted = entry.get("protection") or {}
            if wanted.get("enforce_admins") and not result["enforce_admins"]:
                result["notes"].append(
                    "extends the commons but `enforce_admins` is not enforced -- "
                    "the commons block looks unapplied, not merely incomplete"
                )
            break

    missing = [c for c in declared if c not in live]
    extra = [c for c in live if c not in declared]
    result["missing"] = missing
    result["extra"] = extra

    if missing:
        result["status"] = "drift"
        result["notes"].append(f"declared but not enforced: {', '.join(missing)}")
        # The observation from #387: on gh-plumbing the only context that
        # applied was the first declared one. Flag the pattern so a second
        # sample either confirms it or kills it.
        if declared and live and declared[0] in live and all(
            c not in live for c in declared[1:]
        ):
            result["notes"].append(
                "only the FIRST declared context is enforced -- matches the "
                "gh-plumbing pattern"
            )
    else:
        result["status"] = "ok"
    if extra:
        result["notes"].append(f"enforced but not declared: {', '.join(extra)}")
    return result


def render(results: list[dict]) -> str:
    order = {"drift": 0, "unprotected": 1, "unreadable": 2, "no-settings": 3, "ok": 4}
    results = sorted(results, key=lambda r: (order.get(r["status"], 9), r["repo"]))

    lines = ["# Branch protection: declared versus enforced", ""]
    drift = [r for r in results if r["status"] in ("drift", "unprotected", "unreadable")]
    lines.append(
        f"**{len(drift)} of {len(results)}** surveyed repositories do not enforce "
        "what they declare, or could not be read."
    )
    lines.append("")
    lines.append("| Repository | Branch | Declared | Enforced | Status |")
    lines.append("|---|---|---|---:|---|")
    for r in results:
        lines.append(
            f"| `{r['repo']}` | `{r['branch']}` | {len(r.get('declared', []))} "
            f"| {len(r.get('live', []))} | {r['status']} |"
        )

    detail = [r for r in results if r["notes"]]
    if detail:
        lines += ["", "## Detail", ""]
        for r in detail:
            lines.append(f"### `{r['repo']}`")
            lines.append("")
            for note in r["notes"]:
                lines.append(f"- {note}")
            if r.get("declared"):
                lines.append(f"- declared: `{'`, `'.join(r['declared'])}`")
            if r.get("live"):
                lines.append(f"- enforced: `{'`, `'.join(r['live'])}`")
            if r.get("restrictions"):
                lines.append(
                    f"- `restrictions`: {r['restrictions']}, "
                    f"`enforce_admins`: {r.get('enforce_admins')}, "
                    f"`strict`: {r.get('strict')}"
                )
            lines.append(f"- `_extends`: `{r.get('extends', '(unknown)')}`")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repos", nargs="*", help="owner/name; default: every non-archived nolte repo")
    parser.add_argument("--branch", default="develop")
    parser.add_argument("--owner", default="nolte")
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="report drift without failing; for an initial survey, not for the schedule",
    )
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("::error::GH_TOKEN or GITHUB_TOKEN must be set", file=sys.stderr)
        return 2

    repos = args.repos
    if not repos:
        repos = []
        page = 1
        while True:
            batch = api(f"users/{args.owner}/repos?per_page=100&page={page}", token) or []
            if not batch:
                break
            repos += [
                r["full_name"]
                for r in batch
                # Forks carry upstream's configuration and would drown the
                # signal; archived repositories cannot be fixed.
                if not r["archived"] and not r["fork"]
            ]
            page += 1

    commons = read_yaml_file(COMMONS_REPO, COMMONS_PATH, token)

    results = [audit_repo(repo, args.branch, commons, token) for repo in repos]
    report = render(results)
    print(report)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")

    drift = [r for r in results if r["status"] in ("drift", "unprotected", "unreadable")]
    if drift and not args.exit_zero:
        print(
            f"::error::{len(drift)} repositories do not enforce their declared "
            "branch protection",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
