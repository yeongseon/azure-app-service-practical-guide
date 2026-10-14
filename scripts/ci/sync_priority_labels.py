"""Synchronize only versioned priority labels without deleting unrelated labels."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Final

EXPECTED_NAMES: Final = (
    "priority:critical",
    "priority:high",
    "priority:medium",
    "priority:low",
)
DEFAULT_DEFINITIONS: Final = Path(".github/priority-labels.json")


@dataclass(frozen=True, slots=True)
class LabelOperation:
    """One non-destructive label change derived from the versioned definitions."""

    name: str
    description: str
    color: str
    action: str


def load_definitions(path: Path) -> dict[str, tuple[str, str]]:
    """Parse the committed priority-label definitions at the CLI boundary."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or tuple(raw) != EXPECTED_NAMES:
        raise ValueError("Definitions must contain the four ordered priority:* labels.")
    result: dict[str, tuple[str, str]] = {}
    for name, definition in raw.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            raise ValueError("Priority-label definitions must map names to color and description.")
        color = definition.get("color")
        description = definition.get("description")
        if not isinstance(color, str) or not isinstance(description, str):
            raise ValueError("Priority-label definitions must provide text color and description.")
        result[name] = (color, description)
    return result


def plan(definitions: dict[str, tuple[str, str]], existing: dict[str, tuple[str, str]]) -> tuple[LabelOperation, ...]:
    """Plan creates and description updates; intentionally never plan deletions."""
    operations: list[LabelOperation] = []
    for name, (color, description) in definitions.items():
        if name not in existing:
            operations.append(LabelOperation(name, description, color, "create"))
        elif existing[name] != (color, description):
            operations.append(LabelOperation(name, description, color, "edit"))
    return tuple(operations)


def existing_labels(repository: str) -> dict[str, tuple[str, str]]:
    """Read the repository labels through the GitHub CLI without mutation."""
    result = subprocess.run(
        ["gh", "label", "list", "--repo", repository, "--limit", "100", "--json", "name,color,description"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    labels = json.loads(result.stdout)
    if not isinstance(labels, list):
        raise ValueError("GitHub returned invalid label data.")
    result: dict[str, tuple[str, str]] = {}
    for item in labels:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        color = item.get("color")
        description = item.get("description")
        if isinstance(name, str) and isinstance(color, str) and (isinstance(description, str) or description is None):
            result[name] = (color, description or "")
    return result


def apply(repository: str, operations: tuple[LabelOperation, ...]) -> None:
    """Apply the already-planned scoped changes; unrelated labels remain untouched."""
    for operation in operations:
        command = ["gh", "label", operation.action, operation.name, "--repo", repository, "--description", operation.description, "--color", operation.color]
        if operation.action == "edit":
            command.append("--name")
            command.append(operation.name)
        subprocess.run(command, check=True)


def main() -> int:
    """Report drift by default and mutate labels only after explicit --apply."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/repository")
    parser.add_argument("--definitions", type=Path, default=DEFAULT_DEFINITIONS)
    parser.add_argument("--check", action="store_true", help="Read labels and fail when definitions are not synchronized.")
    parser.add_argument("--apply", action="store_true", help="Create or update only priority:* labels; never deletes labels.")
    arguments = parser.parse_args()
    if arguments.check == arguments.apply:
        parser.error("Specify exactly one of --check or --apply.")
    operations = plan(load_definitions(arguments.definitions), existing_labels(arguments.repo))
    if not operations:
        print("Priority labels conform. No labels were deleted.")
        return 0
    for operation in operations:
        print(f"{operation.action}: {operation.name}")
    if arguments.check:
        return 1
    apply(arguments.repo, operations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
