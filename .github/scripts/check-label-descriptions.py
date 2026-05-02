#!/usr/bin/env python3
"""Validate that label descriptions in commons-settings.yml stay within
GitHub's 100-character limit.

Exceeding the limit causes the GitHub label API to reject the request
with HTTP 422 ("description is too long"); the Probot Settings App
swallows that error silently and the rest of the sync continues, so the
offending label never appears in the live repo. Discovered while closing
issue #331; see `.github/settings.yml` header comment and the auto-memory
`reference_label_portfolio_gaps.md` for the full context.
"""

import sys
from pathlib import Path

import yaml

LIMIT = 100


def check(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text()) or {}
    errors: list[str] = []
    for label in data.get("labels", []):
        desc = label.get("description") or ""
        if len(desc) > LIMIT:
            errors.append(
                f"  {path}: label '{label.get('name')}' description is "
                f"{len(desc)} chars (max {LIMIT})"
            )
    return errors


def main(argv: list[str]) -> int:
    errors: list[str] = []
    for arg in argv[1:]:
        errors.extend(check(Path(arg)))
    if errors:
        print(
            "Label descriptions over GitHub's 100-character limit "
            "(would silently skip during Probot sync, see issue #331):",
            file=sys.stderr,
        )
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
