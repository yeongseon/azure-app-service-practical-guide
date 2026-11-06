import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import build_doc_graph as graph


class GraphGenerationTests(unittest.TestCase):
    root: Path = Path()
    docs: Path = Path()
    output: Path = Path()
    stdout: io.StringIO = io.StringIO()
    stderr: io.StringIO = io.StringIO()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.output = self.root / "output"
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        for context in (
            patch.object(graph, "DOCS_DIR", self.docs),
            patch.object(graph, "OUTPUT_DIR", self.output),
            patch.object(sys, "argv", ["build_doc_graph.py"]),
            contextlib.redirect_stdout(self.stdout),
            contextlib.redirect_stderr(self.stderr),
        ):
            contexts.enter_context(context)

    def page(self, relative: str, metadata: str = "title: Fixture") -> Path:
        path = self.docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{metadata}\n---\n", encoding="utf-8")
        return path

    def test_scan_rejects_explicit_slug_when_directories_differ(self) -> None:
        self.page("first/a.md", "slug: shared")
        self.page("second/b.md", "slug: shared")

        with self.assertRaises(ValueError) as raised:
            graph.scan_documents()

        assert isinstance(raised.exception, graph.SlugCollisionError)
        self.assertEqual(raised.exception.collisions, (
            ("shared", ("first/a.md", "second/b.md")),
        ))

    def test_scan_rejects_equal_stems_when_slugs_absent(self) -> None:
        self.page("first/shared.md")
        self.page("second/shared.md")

        with self.assertRaises(ValueError) as raised:
            graph.scan_documents()

        assert isinstance(raised.exception, graph.SlugCollisionError)
        self.assertEqual(raised.exception.collisions, (
            ("shared", ("first/shared.md", "second/shared.md")),
        ))

    def test_scan_rejects_explicit_slug_when_it_matches_fallback(self) -> None:
        self.page("first/a.md", "slug: shared")
        self.page("second/shared.md")

        with self.assertRaises(ValueError) as raised:
            graph.scan_documents()

        assert isinstance(raised.exception, graph.SlugCollisionError)
        self.assertEqual(raised.exception.collisions, (
            ("shared", ("first/a.md", "second/shared.md")),
        ))

    def test_main_reports_every_collision_when_iteration_is_reversed(self) -> None:
        paths = [
            self.page("z/third.md", "slug: zeta"),
            self.page("a/second.md", "slug: alpha"),
            self.page("b/first.md", "slug: alpha"),
            self.page("c/fourth.md", "slug: zeta"),
            self.page("d/fifth.md", "slug: alpha"),
        ]
        reports = []

        for order in (paths, list(reversed(paths))):
            self.stderr.seek(0)
            self.stderr.truncate()
            with patch.object(Path, "rglob", return_value=iter(order)):
                status = graph.main()
            self.assertEqual(status, 1)
            report = self.stderr.getvalue()
            tokens = ["'alpha'", "a/second.md", "b/first.md", "d/fifth.md",
                      "'zeta'", "c/fourth.md", "z/third.md"]
            positions = [report.index(token) for token in tokens]
            self.assertEqual(positions, sorted(positions))
            self.assertIn("2 shared slugs, 5 files affected", report)
            reports.append(report)

        self.assertEqual(reports[0], reports[1])

    def test_main_creates_nothing_when_slugs_collide(self) -> None:
        self.page("a.md", "slug: shared")
        self.page("b.md", "slug: shared")

        status = graph.main()

        self.assertEqual((status, self.output.exists()), (1, False))
        self.assertEqual(list(self.root.rglob("*.json")), [])

    def test_main_preserves_existing_outputs_when_slugs_collide(self) -> None:
        self.page("a.md", "slug: shared")
        self.page("b.md", "slug: shared")
        self.output.mkdir()
        original = b'{"existing": true}\n'
        files = [self.output / name for name in (
            "core-knowledge.json", "troubleshooting-map.json",
        )]
        for path in files:
            path.write_bytes(original)

        status = graph.main()

        self.assertEqual((status, [path.read_bytes() for path in files]),
                         (1, [original, original]))

    def test_main_writes_both_graphs_when_slugs_are_unique(self) -> None:
        self.page("troubleshooting/a.md", "slug: alpha\nrelated: [beta]")
        self.page("troubleshooting/b.md", "slug: beta")

        status = graph.main() or 0

        self.assertEqual(status, 0)
        self.assertEqual(sorted(path.name for path in self.output.iterdir()),
                         ["core-knowledge.json", "troubleshooting-map.json"])
        for path in self.output.iterdir():
            elements = json.loads(path.read_text(encoding="utf-8"))["elements"]
            self.assertEqual({element["data"]["id"] for element in elements
                              if "id" in element["data"]}, {"alpha", "beta"})
            self.assertIn({"data": {"source": "alpha", "target": "beta",
                                    "type": "related"}}, elements)

    def test_scan_skips_excluded_paths_and_missing_frontmatter(self) -> None:
        self.page("visible.md", "slug: shared")
        for relative in ("_hidden/a.md", ".hidden/b.md", "nested/_skip/c.md",
                         "nested/.skip/d.md", "nested/_file.md", "nested/.file.md"):
            self.page(relative, "slug: shared")
        (self.docs / "shared.md").write_text("# No frontmatter\n", encoding="utf-8")

        documents = graph.scan_documents()

        self.assertEqual({slug: doc["file"] for slug, doc in documents.items()},
                         {"shared": "visible.md"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
