#!/usr/bin/env python3
"""
Build documentation graph JSON from markdown frontmatter.

Scans docs/ for markdown files with frontmatter, extracts relationships,
and generates Cytoscape.js-compatible JSON graph data.
Exits 1 without writing output when document slugs collide.

Usage:
    python tools/build_doc_graph.py [--learning-paths]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

DOCS_DIR = Path(__file__).parent.parent / "docs"
OUTPUT_DIR = DOCS_DIR / "assets" / "graph"

DOC_TYPES = {
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

EDGE_TYPES = {
    "prerequisite",
    "related",
    "used_in",
    "deep_dive_for",
    "troubleshooting_for",
    "validated_by_lab",
    "investigated_with_kql",
}


class SlugCollisionError(ValueError):
    def __init__(self, collisions: tuple[tuple[str, tuple[str, ...]], ...]) -> None:
        self.collisions = collisions
        super().__init__()

    def __str__(self) -> str:
        lines = ["Error: document slug collisions (paths relative to docs/):"]
        for slug, paths in self.collisions:
            lines.append(f"  Slug {slug!r}:")
            lines.extend(f"    {path}" for path in paths)
        affected = sum(len(paths) for _, paths in self.collisions)
        lines.append(f"Total: {len(self.collisions)} shared slugs, {affected} files affected.")
        lines.append(
            "Give each listed file a unique frontmatter slug, or ask the maintainer "
            "to decide the node key. No graph files were written."
        )
        return "\n".join(lines)


def parse_frontmatter(file_path: Path) -> dict[str, Any] | None:
    """Extract YAML frontmatter from a markdown file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return None

    if not content.startswith("---"):
        return None

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    try:
        frontmatter = yaml.safe_load(match.group(1))
        if not isinstance(frontmatter, dict):
            return None
        return frontmatter
    except yaml.YAMLError as e:
        print(f"  Warning: Invalid YAML in {file_path}: {e}", file=sys.stderr)
        return None


def get_relative_href(file_path: Path, base_url: str = "") -> str:
    """Convert file path to relative URL for documentation site."""
    rel_path = file_path.relative_to(DOCS_DIR)
    href = str(rel_path).replace("\\", "/")
    if href.endswith(".md"):
        href = href[:-3] + "/"
    if href.endswith("/index/"):
        href = href[:-7] + "/"
    elif href == "index/":
        href = ""
    return base_url + href


def scan_documents() -> dict[str, dict[str, Any]]:
    """Scan all markdown files and extract frontmatter."""
    documents: dict[str, dict[str, Any]] = {}
    slug_paths: dict[str, list[str]] = {}

    for md_file in DOCS_DIR.rglob("*.md"):
        rel_path = md_file.relative_to(DOCS_DIR)
        if any(part.startswith("_") or part.startswith(".") for part in rel_path.parts):
            continue

        frontmatter = parse_frontmatter(md_file)
        if not frontmatter:
            continue

        slug = frontmatter.get("slug")
        if not slug:
            slug = md_file.stem

        slug_paths.setdefault(slug, []).append(rel_path.as_posix())
        if slug in documents:
            continue

        documents[slug] = {
            "file": str(rel_path),
            "href": get_relative_href(md_file),
            "frontmatter": frontmatter,
        }

    collisions = tuple(
        (slug, tuple(sorted(paths)))
        for slug, paths in sorted(slug_paths.items(), key=lambda item: (
            str(item[0]), type(item[0]).__name__, repr(item[0]),
        ))
        if len(paths) > 1
    )
    if collisions:
        raise SlugCollisionError(collisions)
    return documents


def build_core_knowledge_graph(documents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the core knowledge graph from document relationships."""
    nodes = []
    edges = []
    seen_edges = set()

    for slug, doc in documents.items():
        fm = doc["frontmatter"]

        node = {
            "data": {
                "id": slug,
                "label": fm.get("title", slug),
                "type": fm.get("doc_type", "concept"),
                "section": fm.get("section", ""),
                "href": doc["href"],
                "topics": fm.get("topics", []),
                "products": fm.get("products", []),
            }
        }
        nodes.append(node)

        for rel_type, edge_type, reverse in [
            ("related", "related", False),
            ("prerequisites", "prerequisite", True),
            ("used_in", "used_in", False),
            ("deep_dive_for", "deep_dive_for", False),
            ("troubleshooting_for", "troubleshooting_for", False),
        ]:
            targets = fm.get(rel_type, [])
            if isinstance(targets, str):
                targets = [targets]

            for target in targets:
                if target not in documents:
                    continue

                if reverse:
                    source, dest = target, slug
                else:
                    source, dest = slug, target

                edge_key = f"{source}->{dest}:{edge_type}"
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                edges.append(
                    {"data": {"source": source, "target": dest, "type": edge_type}}
                )

    return {"elements": nodes + [{"data": e["data"]} for e in edges]}


def build_troubleshooting_map(documents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build a focused troubleshooting graph."""
    ts_sections = {"troubleshooting", "playbook", "lab", "kql", "map"}
    ts_docs = {
        slug: doc
        for slug, doc in documents.items()
        if doc["frontmatter"].get("section") in ts_sections
        or doc["frontmatter"].get("doc_type") in {"playbook", "lab", "kql", "map"}
        or "troubleshooting" in doc["file"]
    }

    nodes = []
    edges = []
    seen_edges = set()

    for slug, doc in ts_docs.items():
        fm = doc["frontmatter"]

        category = "other"
        file_path = doc["file"].lower()
        if "startup" in file_path or "availability" in file_path:
            category = "startup"
        elif "performance" in file_path or "memory" in file_path or "5xx" in file_path:
            category = "performance"
        elif "network" in file_path or "dns" in file_path or "snat" in file_path:
            category = "network"

        node = {
            "data": {
                "id": slug,
                "label": fm.get("title", slug),
                "type": fm.get("doc_type", "playbook"),
                "category": category,
                "href": doc["href"],
                "topics": fm.get("topics", []),
                "evidence": fm.get("evidence", []),
            }
        }
        nodes.append(node)

        for rel_type, edge_type, reverse in [
            ("related", "related", False),
            ("prerequisites", "prerequisite", True),
            ("used_in", "used_in", False),
            ("validated_by_lab", "validated_by_lab", False),
            ("investigated_with_kql", "investigated_with_kql", False),
        ]:
            targets = fm.get(rel_type, [])
            if isinstance(targets, str):
                targets = [targets]

            for target in targets:
                if target not in ts_docs:
                    continue

                if reverse:
                    source, dest = target, slug
                else:
                    source, dest = slug, target

                edge_key = f"{source}->{dest}:{edge_type}"
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                edges.append(
                    {"data": {"source": source, "target": dest, "type": edge_type}}
                )

    return {"elements": nodes + [{"data": e["data"]} for e in edges]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build documentation graphs")
    parser.add_argument(
        "--learning-paths", action="store_true", help="Include learning path graphs"
    )
    args = parser.parse_args()

    print("Scanning documents...")
    try:
        documents = scan_documents()
    except SlugCollisionError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"  Found {len(documents)} documents with frontmatter")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building core knowledge graph...")
    core_graph = build_core_knowledge_graph(documents)
    core_path = OUTPUT_DIR / "core-knowledge.json"
    core_path.write_text(
        json.dumps(core_graph, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"  Wrote {core_path} ({len(core_graph['elements'])} elements)")

    print("Building troubleshooting map...")
    ts_graph = build_troubleshooting_map(documents)
    ts_path = OUTPUT_DIR / "troubleshooting-map.json"
    ts_path.write_text(json.dumps(ts_graph, indent=2, sort_keys=True), encoding="utf-8")
    print(f"  Wrote {ts_path} ({len(ts_graph['elements'])} elements)")

    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
