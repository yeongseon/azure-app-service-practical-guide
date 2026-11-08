import argparse
import contextlib
import importlib.util
import io
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import build_doc_graph as graph

FILESYSTEM_PRIMITIVES = {
    "pathlib.Path": (
        "rglob", "glob", "iterdir", "exists", "is_dir", "is_file", "is_symlink", "stat", "open", "read_text",
        "read_bytes", "mkdir", "touch", "write_text", "write_bytes", "unlink", "rmdir", "rename", "replace", "chmod",
        "symlink_to",
    ),
    "os": (
        "listdir", "scandir", "walk", "stat", "access", "mkdir", "makedirs", "remove", "unlink", "rmdir", "removedirs",
        "rename", "renames", "replace", "chmod", "utime", "symlink", "link", "truncate", "open",
    ),
    "shutil": ("copy", "copy2", "copyfile", "copytree", "move", "rmtree"),
    "tempfile": ("TemporaryDirectory", "mkdtemp", "mkstemp", "NamedTemporaryFile"),
    "glob": ("glob", "iglob"),
    "io": ("open",),
    "builtins": ("open",),
}


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
            # argparse looks for translation catalogs with os.stat; a fixed locale keeps that lookup out of the mocks
            patch.dict(os.environ, {"LANGUAGE": "", "LC_ALL": "C"}),
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

    def test_main_writes_both_graphs_when_slug_types_differ(self) -> None:
        self.page("troubleshooting/a.md", "slug: 123")
        self.page("troubleshooting/b.md", "slug: '123'")
        self.page("troubleshooting/c.md", "slug: 1.5")

        documents = graph.scan_documents()
        status = graph.main()

        self.assertEqual(set(documents), {123, "123", 1.5})
        self.assertEqual(status, 0)
        self.assertEqual(sorted(path.name for path in self.output.iterdir()),
                         ["core-knowledge.json", "troubleshooting-map.json"])
        for path in self.output.iterdir():
            elements = json.loads(path.read_text(encoding="utf-8"))["elements"]
            self.assertEqual({element["data"]["id"] for element in elements},
                             {123, "123", 1.5})

    def test_main_reports_collisions_when_slug_types_differ(self) -> None:
        paths = [
            self.page("z.md", "slug: '123'"),
            self.page("b.md", "slug: 123"),
            self.page("a.md", "slug: 123"),
            self.page("c.md", "slug: '123'"),
        ]
        collisions = ((123, ("a.md", "b.md")), ("123", ("c.md", "z.md")))

        for order in (paths, list(reversed(paths))):
            with self.subTest(order=[path.name for path in order]):
                with patch.object(Path, "rglob", return_value=iter(order)):
                    with self.assertRaises(graph.SlugCollisionError) as raised:
                        graph.scan_documents()
                self.assertEqual(raised.exception.collisions, collisions)
                self.stderr.seek(0)
                self.stderr.truncate()
                with patch.object(Path, "rglob", return_value=iter(order)):
                    status = graph.main()
                self.assertEqual(status, 1)
                report = self.stderr.getvalue()
                self.assertIn("  Slug 123:\n    a.md\n    b.md\n"
                              "  Slug '123':\n    c.md\n    z.md\n", report)
                self.assertIn("2 shared slugs, 4 files affected", report)

    def test_scan_skips_excluded_paths_and_missing_frontmatter(self) -> None:
        self.page("visible.md", "slug: shared")
        for relative in ("_hidden/a.md", ".hidden/b.md", "nested/_skip/c.md",
                         "nested/.skip/d.md", "nested/_file.md", "nested/.file.md"):
            self.page(relative, "slug: shared")
        (self.docs / "shared.md").write_text("# No frontmatter\n", encoding="utf-8")

        documents = graph.scan_documents()

        self.assertEqual({slug: doc["file"] for slug, doc in documents.items()},
                         {"shared": "visible.md"})

    def reference_parser(self) -> argparse.ArgumentParser:
        return argparse.ArgumentParser(prog="build_doc_graph.py", description="Build documentation graphs")

    def clear_output(self) -> None:
        for stream in (self.stdout, self.stderr):
            stream.seek(0)
            stream.truncate()

    def forbid_filesystem(self, stack: contextlib.ExitStack) -> dict[str, MagicMock]:
        mocks = {
            f"{module}.{name}": MagicMock(side_effect=AssertionError(f"{module}.{name} was called"))
            for module, names in FILESYSTEM_PRIMITIVES.items()
            for name in names
        }
        for target, mock in mocks.items():
            stack.enter_context(patch(target, mock))
        # resolve() only normalises a path but calls stat() on Python 3.11 and 3.12
        stack.enter_context(patch.object(Path, "resolve", lambda path, strict=False: path))
        return mocks

    def assert_untouched(self, mocks: dict[str, MagicMock]) -> None:
        self.assertEqual({name: mock.mock_calls for name, mock in mocks.items()}, {name: [] for name in mocks})

    def run_main_untouched(self, *argv: str) -> tuple[object, dict[str, MagicMock]]:
        mocks = {
            "DOCS_DIR": MagicMock(spec=Path),
            "OUTPUT_DIR": MagicMock(spec=Path),
            "sys.stdin": MagicMock(spec=io.TextIOBase),
        }
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", ["build_doc_graph.py", *argv]))
            stack.enter_context(patch.object(sys, "stdin", mocks["sys.stdin"]))
            stack.enter_context(patch.object(logging.root, "handlers", []))
            stack.enter_context(patch.object(logging.root, "level", logging.WARNING))
            stack.enter_context(patch.object(graph, "DOCS_DIR", mocks["DOCS_DIR"]))
            stack.enter_context(patch.object(graph, "OUTPUT_DIR", mocks["OUTPUT_DIR"]))
            mocks["scan_documents"] = stack.enter_context(patch.object(graph, "scan_documents"))
            mocks.update(self.forbid_filesystem(stack))
            with self.assertRaises(SystemExit) as raised:
                graph.main()
        return raised.exception.code, mocks

    def test_main_rejects_unrecognized_arguments_before_any_scan(self) -> None:
        usage = self.reference_parser().format_usage()
        for args in (
            ("--learning-paths",),
            ("--no-such-option",),
            ("--no-such-option", "--learning-paths"),
            ("--learning-paths", "--no-such-option"),
            ("--learning-paths", "@no-such-argument-file.txt"),
        ):
            with self.subTest(args=args):
                self.clear_output()

                code, untouched = self.run_main_untouched(*args)

                self.assertEqual(code, 2)
                self.assertEqual(
                    self.stderr.getvalue(),
                    f"{usage}build_doc_graph.py: error: unrecognized arguments: {' '.join(args)}\n",
                )
                self.assertEqual(self.stdout.getvalue(), "")
                self.assert_untouched(untouched)

    def test_main_help_exits_without_scanning_and_prints_only_the_help_text(self) -> None:
        help_text = self.reference_parser().format_help()
        for argv in (
            ("--help",),
            ("-h",),
            ("--help", "--learning-paths"),
            ("--learning-paths", "--help"),
            ("--learning-paths=yes", "--help"),
            ("--no-such-option", "-h"),
            ("-h", "--no-such-option"),
            ("@no-such-argument-file.txt", "--help"),
        ):
            with self.subTest(argv=argv):
                self.clear_output()

                code, untouched = self.run_main_untouched(*argv)

                self.assertEqual(code, 0)
                self.assertEqual(self.stdout.getvalue(), help_text)
                self.assertEqual(self.stderr.getvalue(), "")
                self.assert_untouched(untouched)

    def test_importing_the_module_reads_no_documents_and_no_input(self) -> None:
        spec = importlib.util.spec_from_file_location("build_doc_graph_fresh", graph.__file__)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        stdin = MagicMock(spec=io.TextIOBase)
        with contextlib.ExitStack() as stack:
            mocks = {"sys.stdin": stdin, **self.forbid_filesystem(stack)}
            stack.enter_context(patch.object(sys, "stdin", stdin))
            spec.loader.exec_module(module)

        self.assert_untouched(mocks)
        self.assertEqual((self.stdout.getvalue(), self.stderr.getvalue()), ("", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
