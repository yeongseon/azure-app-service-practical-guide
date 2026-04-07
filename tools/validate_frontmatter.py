#!/usr/bin/env python3
"""
Validate frontmatter in documentation files.

Checks for:
- Required fields present
- Valid doc_type values
- Slug uniqueness
- Related/prerequisite targets exist
- Proper YAML formatting

Usage:
    python tools/validate_frontmatter.py [--fix]
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

DOCS_DIR = Path(__file__).parent.parent / "docs"

VALID_DOC_TYPES = {
    "concept",
    "best_practice",
    "tutorial",
    "operation",
    "playbook",
    "reference",
    "lab",
    "map",
    "kql",
}

VALID_SECTIONS = {
    "platform",
    "best-practices",
    "language-guides",
    "operations",
    "troubleshooting",
    "reference",
    "visualization",
    "meta",
    "start-here",
}

REQUIRED_FIELDS = {"title", "slug", "doc_type"}
RECOMMENDED_FIELDS = {"summary", "topics", "products"}

RELATIONSHIP_FIELDS = {
    "related",
    "prerequisites",
    "used_in",
    "deep_dive_for",
    "troubleshooting_for",
    "validated_by_lab",
    "investigated_with_kql",
}


class ValidationError:
    def __init__(self, file: Path, field: str, message: str, severity: str = "error"):
        self.file = file
        self.field = field
        self.message = message
        self.severity = severity

    def __str__(self):
        prefix = "ERROR" if self.severity == "error" else "WARNING"
        rel_path = self.file.relative_to(DOCS_DIR)
        return f"[{prefix}] {rel_path}: {self.field} - {self.message}"


def parse_frontmatter(file_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Extract YAML frontmatter and return it with any parse error."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return None, f"Could not read file: {e}"

    if not content.startswith("---"):
        return None, None

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None, "Malformed frontmatter delimiters"

    try:
        frontmatter = yaml.safe_load(match.group(1))
        if not isinstance(frontmatter, dict):
            return None, "Frontmatter is not a dictionary"
        return frontmatter, None
    except yaml.YAMLError as e:
        return None, f"Invalid YAML: {e}"


def validate_file(file_path: Path, all_slugs: set[str]) -> list[ValidationError]:
    """Validate a single file's frontmatter."""
    errors = []

    frontmatter, parse_error = parse_frontmatter(file_path)

    if parse_error:
        errors.append(ValidationError(file_path, "frontmatter", parse_error))
        return errors

    if frontmatter is None:
        return errors

    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            errors.append(
                ValidationError(file_path, field, f"Missing required field: {field}")
            )

    for field in RECOMMENDED_FIELDS:
        if field not in frontmatter:
            errors.append(
                ValidationError(
                    file_path,
                    field,
                    f"Missing recommended field: {field}",
                    severity="warning",
                )
            )

    doc_type = frontmatter.get("doc_type")
    if doc_type and doc_type not in VALID_DOC_TYPES:
        errors.append(
            ValidationError(
                file_path,
                "doc_type",
                f"Invalid doc_type '{doc_type}'. Valid types: {', '.join(sorted(VALID_DOC_TYPES))}",
            )
        )

    section = frontmatter.get("section")
    if section and section not in VALID_SECTIONS:
        errors.append(
            ValidationError(
                file_path, "section", f"Unknown section '{section}'", severity="warning"
            )
        )

    for rel_field in RELATIONSHIP_FIELDS:
        targets = frontmatter.get(rel_field, [])
        if isinstance(targets, str):
            targets = [targets]

        for target in targets:
            if target not in all_slugs:
                errors.append(
                    ValidationError(
                        file_path,
                        rel_field,
                        f"Reference to unknown slug: '{target}'",
                        severity="warning",
                    )
                )

    return errors


def collect_slugs(docs_dir: Path) -> tuple[set[str], dict[str, list[Path]]]:
    """Collect all slugs and detect duplicates."""
    slugs: set[str] = set()
    slug_files: dict[str, list[Path]] = {}

    for md_file in docs_dir.rglob("*.md"):
        rel_path = md_file.relative_to(docs_dir)
        if any(part.startswith("_") or part.startswith(".") for part in rel_path.parts):
            continue

        frontmatter, _ = parse_frontmatter(md_file)
        if not frontmatter:
            continue

        slug = frontmatter.get("slug", md_file.stem)
        slugs.add(slug)

        if slug not in slug_files:
            slug_files[slug] = []
        slug_files[slug].append(md_file)

    return slugs, slug_files


def main():
    parser = argparse.ArgumentParser(description="Validate documentation frontmatter")
    parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix issues (not implemented)"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    args = parser.parse_args()

    print("Collecting slugs...")
    all_slugs, slug_files = collect_slugs(DOCS_DIR)
    print(f"  Found {len(all_slugs)} unique slugs")

    all_errors: list[ValidationError] = []

    for slug, files in slug_files.items():
        if len(files) > 1:
            for f in files:
                all_errors.append(
                    ValidationError(
                        f,
                        "slug",
                        f"Duplicate slug '{slug}' also found in: {', '.join(str(p.relative_to(DOCS_DIR)) for p in files if p != f)}",
                    )
                )

    print("Validating files...")
    files_checked = 0
    for md_file in DOCS_DIR.rglob("*.md"):
        rel_path = md_file.relative_to(DOCS_DIR)
        if any(part.startswith("_") or part.startswith(".") for part in rel_path.parts):
            continue

        errors = validate_file(md_file, all_slugs)
        all_errors.extend(errors)
        files_checked += 1

    print(f"  Checked {files_checked} files")

    error_count = sum(1 for e in all_errors if e.severity == "error")
    warning_count = sum(1 for e in all_errors if e.severity == "warning")

    if all_errors:
        print(f"\nFound {error_count} errors, {warning_count} warnings:\n")

        errors_sorted = sorted(
            all_errors, key=lambda e: (e.severity != "error", str(e.file))
        )
        for error in errors_sorted:
            print(f"  {error}")
    else:
        print("\nNo issues found!")

    if args.strict:
        sys.exit(1 if (error_count + warning_count) > 0 else 0)
    else:
        sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()
