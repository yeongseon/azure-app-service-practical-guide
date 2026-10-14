"""Validate a GitHub pull_request event without network calls or mutations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

TYPES = "feat|fix|docs|test|perf|refactor|ci|build|chore|style|revert"
TITLE = re.compile(rf"^({TYPES})(\([a-z0-9][a-z0-9._/,-]*\))?!?: \S(?:.*[^.\s])?$")
PRIORITIES = {"priority:" + name for name in ("critical", "high", "medium", "low")}
SECTIONS = ["Summary", "Changes", "Type of Change", "Validation", "Checklist", "Related Issues"]
FOREIGN_ISSUE_REFERENCE = re.compile(r"\b[\w.-]+/[\w.-]+#[1-9][0-9]*\b")


def headings(body: str) -> list[str]:
    result, fence, details = [], "", 0
    for line in body.splitlines():
        token = re.match(r"^\s*(`{3,}|~{3,})", line)
        if token:
            char = token[1][0]
            fence = "" if fence == char else (char if not fence else fence)
            continue
        if fence:
            continue
        details += line.lower().count("<details")
        if not details and line.startswith("## "):
            result.append(line[3:].strip())
        details = max(0, details - line.lower().count("</details>"))
    return result


def validate(pr: dict[str, object]) -> list[str]:
    errors = []
    title = pr.get("title", "")
    body = pr.get("body", "")
    if not isinstance(title, str) or not isinstance(body, str):
        return ["The pull request title and body must be text."]
    if not TITLE.fullmatch(title) or re.search(r"\(#\d+\)$", title):
        errors.append("Use a Conventional Commit title without a trailing issue number or period.")
    raw_labels = pr.get("labels", [])
    if not isinstance(raw_labels, list):
        return [*errors, "Pull request labels must be an array."]
    labels = [v["name"] if isinstance(v, dict) and isinstance(v.get("name"), str) else v for v in raw_labels]
    if not all(isinstance(label, str) for label in labels):
        return [*errors, "Pull request labels must have text names."]
    priorities = [v for v in labels if v.startswith("priority:")]
    if len(priorities) != 1 or priorities[0] not in PRIORITIES:
        errors.append("Apply exactly one priority:critical/high/medium/low label.")
    if headings(body) != SECTIONS:
        errors.append("Required ordered sections: " + " / ".join(SECTIONS))
    related = body.rsplit("## Related Issues", 1)[-1]
    if FOREIGN_ISSUE_REFERENCE.search(related):
        errors.append("Related Issues must not contain foreign owner/repository#N references.")
    if not re.search(r"(?im)^\s*(Closes|Fixes|Resolves|Refs) #[1-9][0-9]*\b", related):
        errors.append("Link a local issue; use Refs with remaining scope for partial work.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", type=Path)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    if not isinstance(event.get("pull_request"), dict):
        raise ValueError("Expected a pull_request event")
    errors = validate(event["pull_request"])
    print("\n".join(errors) if errors else "PR metadata conforms. This check does not certify test or Azure results.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
