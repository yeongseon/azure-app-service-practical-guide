#!/usr/bin/env python3
"""Generate content validation status dashboard from frontmatter metadata.

Scans all non-tutorial markdown files for content_validation frontmatter and
generates a dashboard page showing verification status of core claims.

Usage:
    python3 scripts/generate_content_validation_status.py
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# Sections to scan for content_validation metadata. The scope is intentionally
# limited to factual-claim pages per AGENTS.md §Text Content Validation.
SCAN_SECTIONS = [
    "platform",
    "best-practices",
    "operations",
    "troubleshooting",
]

# Subpaths under SCAN_SECTIONS that do NOT require content_validation because
# they are navigation, reference-lookup, or lab-evidence pages.
EXCLUDED_SUBPATHS = (
    "troubleshooting/kql",
    "troubleshooting/lab-guides",
)

# Tautological claim marker - rejects placeholder claims such as
# "This page uses Microsoft Learn as the primary source basis ..."
TAUTOLOGICAL_CLAIM_MARKER = "primary source basis"

# Status icons
ICON_VERIFIED = "✅ Verified"
ICON_PENDING = "⚠️ Pending Review"
ICON_UNVERIFIED = "➖ Unverified"
ICON_NO_META = "❓ No Metadata"


def parse_frontmatter(filepath: Path) -> dict[str, Any] | None:
    """Extract YAML frontmatter from a markdown file."""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


def get_section_from_path(filepath: Path, docs_dir: Path) -> str:
    """Extract section name from file path."""
    rel = filepath.relative_to(docs_dir)
    parts = rel.parts
    if len(parts) > 0:
        return parts[0]
    return "unknown"


def scan_documents(docs_dir: Path) -> list[dict[str, Any]]:
    """Scan all documents and extract validation metadata."""
    documents = []

    for section in SCAN_SECTIONS:
        section_dir = docs_dir / section
        if not section_dir.exists():
            continue

        for md_file in section_dir.rglob("*.md"):
            if md_file.name == "index.md":
                continue
            rel_path = md_file.relative_to(docs_dir)
            if any(str(rel_path).startswith(prefix) for prefix in EXCLUDED_SUBPATHS):
                continue

            frontmatter = parse_frontmatter(md_file)

            doc_info = {
                "filepath": md_file,
                "rel_path": str(rel_path),
                "section": get_section_from_path(md_file, docs_dir),
                "filename": md_file.stem,
                "title": md_file.stem.replace("-", " ").title(),
                "has_content_sources": False,
                "has_content_validation": False,
                "validation_status": "no_metadata",
                "core_claims_count": 0,
                "verified_claims_count": 0,
                "tautological_claims_count": 0,
                "last_reviewed": None,
            }

            if frontmatter and isinstance(frontmatter, dict):
                if "content_sources" in frontmatter:
                    doc_info["has_content_sources"] = True

                cv = frontmatter.get("content_validation", {})
                if cv and isinstance(cv, dict):
                    doc_info["has_content_validation"] = True
                    doc_info["validation_status"] = cv.get("status", "unverified")
                    doc_info["last_reviewed"] = cv.get("last_reviewed")

                    claims = cv.get("core_claims", [])
                    if isinstance(claims, list):
                        doc_info["core_claims_count"] = len(claims)
                        doc_info["verified_claims_count"] = sum(
                            1
                            for c in claims
                            if isinstance(c, dict) and c.get("verified", False)
                        )
                        doc_info["tautological_claims_count"] = sum(
                            1
                            for c in claims
                            if isinstance(c, dict)
                            and isinstance(c.get("claim"), str)
                            and TAUTOLOGICAL_CLAIM_MARKER in c["claim"]
                        )

            documents.append(doc_info)

    return documents


def get_status_icon(status: str) -> str:
    """Return icon for validation status."""
    mapping = {
        "verified": ICON_VERIFIED,
        "pending_review": ICON_PENDING,
        "unverified": ICON_UNVERIFIED,
        "no_metadata": ICON_NO_META,
    }
    return mapping.get(status, ICON_NO_META)


def count_mermaid_diagrams(docs_dir: Path) -> int:
    """Count Mermaid code blocks across the docs tree."""
    count = 0
    for md_file in docs_dir.rglob("*.md"):
        rel_path = md_file.relative_to(docs_dir)
        if any(part.startswith("_") or part.startswith(".") for part in rel_path.parts):
            continue

        text = md_file.read_text(encoding="utf-8")
        count += len(re.findall(r"^```mermaid\s*$", text, re.MULTILINE))
    return count


def generate_dashboard(
    documents: list[dict[str, Any]], docs_dir: Path, today: date
) -> str:
    """Generate the markdown dashboard content."""
    # Compute stats
    total = len(documents)
    verified = sum(1 for d in documents if d["validation_status"] == "verified")
    pending = sum(1 for d in documents if d["validation_status"] == "pending_review")
    unverified = sum(1 for d in documents if d["validation_status"] == "unverified")
    no_meta = sum(1 for d in documents if d["validation_status"] == "no_metadata")
    has_sources = sum(1 for d in documents if d["has_content_sources"])

    diagram_count = count_mermaid_diagrams(docs_dir)

    lines: list[str] = []
    lines.append("---")
    lines.append("content_sources:")
    lines.append("  - type: self-generated")
    lines.append(
        "    justification: Auto-generated dashboard tracking content validation status"
    )
    lines.append("---")
    lines.append("")
    lines.append("# Content Validation Status")
    lines.append("")
    lines.append(
        "This page tracks the source validation status of all documentation content. "
        "All content must be traceable to official Microsoft Learn documentation."
    )
    lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append("")
    lines.append(f"*Generated: {today.isoformat()}*")
    lines.append("")
    lines.append(
        "| Content Type | Total | Verified | Pending | Unverified | No Metadata |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(
        f"| Mermaid Diagrams | {diagram_count} | {diagram_count} | 0 | 0 | 0 |"
    )
    lines.append(
        f"| Text Documents | {total} | {verified} | {pending} | {unverified} | {no_meta} |"
    )
    lines.append("")

    # Status explanation
    if verified == total and total > 0:
        lines.append('!!! success "All Content Verified"')
        lines.append(
            "    All text documents have verified Microsoft Learn sources for core claims."
        )
    elif no_meta > 0:
        lines.append('!!! warning "Validation In Progress"')
        lines.append(
            f"    {no_meta} documents need `content_validation` metadata added."
        )
    lines.append("")

    # Mermaid pie chart
    lines.append("<!-- diagram-id: content-validation-status-pie -->")
    lines.append("```mermaid")
    lines.append("pie title Document Validation Status")
    if verified > 0:
        lines.append(f'    "Verified" : {verified}')
    if pending > 0:
        lines.append(f'    "Pending Review" : {pending}')
    if unverified > 0:
        lines.append(f'    "Unverified" : {unverified}')
    if no_meta > 0:
        lines.append(f'    "No Metadata" : {no_meta}')
    lines.append("```")
    lines.append("")

    # Group by section
    by_section: dict[str, list[dict[str, Any]]] = {}
    for d in documents:
        section = d["section"]
        by_section.setdefault(section, []).append(d)

    lines.append("## By Section")
    lines.append("")

    section_order = ["platform", "best-practices", "operations", "troubleshooting"]

    for section in section_order:
        if section not in by_section:
            continue

        section_docs = by_section[section]
        section_display = section.replace("-", " ").title()

        lines.append(f"### {section_display}")
        lines.append("")
        lines.append("| Document | Has Sources | Status | Claims | Last Reviewed |")
        lines.append("|---|---|---|---|---|")

        section_docs.sort(key=lambda d: d["filename"])

        for d in section_docs:
            doc_link = f"[{d['title']}](../{d['rel_path']})"
            has_sources = "✅" if d["has_content_sources"] else "❌"
            status = get_status_icon(d["validation_status"])

            if d["core_claims_count"] > 0:
                claims = f"{d['verified_claims_count']}/{d['core_claims_count']}"
            else:
                claims = "—"

            last_reviewed = d["last_reviewed"] if d["last_reviewed"] else "—"

            lines.append(
                f"| {doc_link} | {has_sources} | {status} | {claims} | {last_reviewed} |"
            )

        lines.append("")

    # Validation categories
    lines.append("## Validation Categories")
    lines.append("")
    lines.append("### Source Types")
    lines.append("")
    lines.append("| Type | Description | Allowed? |")
    lines.append("|---|---|---|")
    lines.append(
        "| `mslearn` | Content directly from or based on Microsoft Learn | Yes |"
    )
    lines.append(
        "| `mslearn-adapted` | Microsoft Learn content adapted for this guide | Yes, with source URL |"
    )
    lines.append(
        "| `self-generated` | Original content created for this guide | Requires justification |"
    )
    lines.append("| `community` | From community sources | Not for core content |")
    lines.append("| `unknown` | Source not documented | Must be validated |")
    lines.append("")

    lines.append("### Validation Status")
    lines.append("")
    lines.append("| Status | Description |")
    lines.append("|---|---|")
    lines.append("| `verified` | All core claims traced to Microsoft Learn sources |")
    lines.append(
        "| `pending_review` | Document exists but claims need source verification |"
    )
    lines.append("| `unverified` | New document, no validation performed |")
    lines.append("")

    # How to add validation
    lines.append("## How to Add Validation")
    lines.append("")
    lines.append("Add a `content_validation` block to your document's frontmatter:")
    lines.append("")
    lines.append("```yaml")
    lines.append("---")
    lines.append("content_sources:")
    lines.append("  - type: mslearn-adapted")
    lines.append("    url: https://learn.microsoft.com/azure/app-service/...")
    lines.append("content_validation:")
    lines.append("  status: verified")
    lines.append("  last_reviewed: 2026-04-12")
    lines.append("  reviewer: ai-agent")
    lines.append("  core_claims:")
    lines.append('    - claim: "App Service supports VNet integration"')
    lines.append(
        "      source: https://learn.microsoft.com/azure/app-service/overview-vnet-integration"
    )
    lines.append("      verified: true")
    lines.append("---")
    lines.append("```")
    lines.append("")
    lines.append("Then regenerate this page:")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/generate_content_validation_status.py")
    lines.append("```")
    lines.append("")

    # See Also
    lines.append("## See Also")
    lines.append("")
    lines.append("- [CLI Cheatsheet](cli-cheatsheet.md)")
    lines.append("- [Platform Limits](platform-limits.md)")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate content validation status dashboard"
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Path to docs directory (default: docs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reference/content-validation-status.md"),
        help="Output file path",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    docs_dir = project_root / args.docs_dir
    output_path = project_root / args.output

    if not docs_dir.exists():
        print(f"Error: docs directory not found: {docs_dir}")
        raise SystemExit(1)

    documents = scan_documents(docs_dir)

    tautological_docs = [d for d in documents if d["tautological_claims_count"] > 0]
    if tautological_docs:
        print(
            f"ERROR: {len(tautological_docs)} document(s) contain tautological "
            f"placeholder claims (text containing '{TAUTOLOGICAL_CLAIM_MARKER}').",
            file=sys.stderr,
        )
        print(
            "Tautological claims are forbidden by AGENTS.md \u00a7Text Content "
            "Validation. Replace them with verifiable factual assertions or "
            "remove the content_validation block via:",
            file=sys.stderr,
        )
        print(
            "  python3 scripts/remove_tautological_validation.py --apply",
            file=sys.stderr,
        )
        print("Offending files:", file=sys.stderr)
        for d in tautological_docs:
            print(
                f"  - {d['rel_path']} "
                f"({d['tautological_claims_count']}/{d['core_claims_count']} claims)",
                file=sys.stderr,
            )
        raise SystemExit(1)

    today = date.today()
    dashboard = generate_dashboard(documents, docs_dir, today)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dashboard, encoding="utf-8")

    verified = sum(1 for d in documents if d["validation_status"] == "verified")
    print(
        f"Scanned {len(documents)} documents, "
        f"{verified} verified, "
        f"generated {output_path}"
    )


if __name__ == "__main__":
    main()
