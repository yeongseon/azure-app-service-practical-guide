"""Stdlib mutation tests against the independently authored grammar fences."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

guard = importlib.import_module("test_diagram_topology_grammar")

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/diagram_compose.py"
MODULE = importlib.util.spec_from_file_location("diagram_compose", SCRIPT)
assert MODULE is not None and MODULE.loader is not None
composer = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(composer)
RAW = json.loads((ROOT / "scripts/diagram_composition.json").read_text(encoding="utf-8"))
PAGE = ROOT / RAW["diagrams"][0]["page"]
CLI = ("import importlib.util, pathlib, sys; "
       f"s=importlib.util.spec_from_file_location('c', {str(SCRIPT)!r}); "
       "c=importlib.util.module_from_spec(s); s.loader.exec_module(c); "
       "c.ROOT=pathlib.Path(sys.argv[1]); sys.exit(c.main(sys.argv[2:]))")
LIMITED_CLI = ("import resource, signal; signal.signal(signal.SIGXFSZ, signal.SIG_IGN); "
               "resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024)); ") + CLI


def run_cli(root, *args):
    return subprocess.run([sys.executable, "-c", CLI, str(root), *args], capture_output=True)


def shuffled(value):
    match value:
        case dict():
            keys = list(value)
            random.Random(283).shuffle(keys)
            return {key: shuffled(value[key]) for key in keys}
        case list():
            return [shuffled(item) for item in value]
        case _:
            return value


class CompositionTests(unittest.TestCase):
    def test_single_defects_raise_their_own_diagnostic(self):
        # Given: one changed field or record per case, without a generated oracle.
        cases = [
            (("base", "edges", 0, "to"), "ghost", "undeclared node"),
            (("extensions", "ingress-pe", "replace_edges", "request", 0, "to"), "ghost", "undeclared node"),
            (("overlays", "egress-failure", "replace_edges", "dns_lookup", 0, "to"), "ghost", "undeclared node"),
            (("base", "nodes", 1, "id"), "control_plane", "duplicate node/container id"),
            (("base", "edges", 1, "id"), "arm", "duplicate edge id"),
            (("diagrams", 1, "id"), RAW["diagrams"][0]["id"], "duplicate diagram id"),
            (("extensions", "ingress-pe", "nodes", 0, "id"), "client", "duplicate node/container id"),
            (("extensions", "ingress-pe", "containers", 0, "id"), "dns", "duplicate node/container id"),
            (("base", "nodes", 0, "component"), "alien", "unknown component"),
            (("diagrams", 1, "extensions"), ["alien"], "unknown extension"),
            (("diagrams", 3, "overlay"), "alien", "unknown overlay"),
            (("overlays", "egress-failure", "type"), "normal", "unsupported value"),
            (("overlays", "egress-failure", "callout", "lines"), ["scenario"], "missing disclaimer"),
            (("overlays", "egress-failure", "callout", "edge_label"), "[Configured] note", "missing claim prefix"),
            (("base", "nodes", 0, "label"), "[Observed] fact", "reserved [Observed]"),
            (("overlays", "egress-failure", "replace_edges", "dns_lookup", 0, "label"), "[Configured] lookup", "missing claim prefix"),
            (("base", "edges", 0, "style"), "fault", "missing claim prefix"),
            (("schema_version",), 2, "unsupported schema_version"),
            (("schema_version",), True, "expected int"),
            (("grammar_version",), 2, "unsupported grammar_version"),
            (("base", "nodes"), {}, "expected array"),
            (("diagrams", 0, "genre"), "sequence", "sequence/decision/state stay hand-written"),
            (("diagrams", 0, "page"), "docs/page\x00.md", "control, line-separator or lone surrogate"),
            (("diagrams", 0, "page"), "../outside.md", "repo-root relative"),
            (("diagrams", 0, "page"), "/etc/outside.md", "repo-root relative"),
            (("base", "nodes", 0, "label"), "two\rlines", "control, line-separator or lone surrogate"),
            (("base", "nodes", 0, "label"), "two\u2028lines", "control, line-separator or lone surrogate"),
            (("base", "nodes", 0, "label"), "lone\ud800surrogate", "control, line-separator or lone surrogate"),
            (("extensions", "ingress-pe", "containers", 1, "members"), ["ghost"], "missing member ghost"),
            (("extensions", "ingress-pe", "containers", 1, "members"), ["vnet_in"], "container cycle"),
            (("extensions", "ingress-pe", "containers", 1, "members"), [], "missing members"),
            (("diagrams", 1, "layout", "link_length", "arm"), True, "expected int"),
            (("diagrams", 1, "layout", "title_padding", "vnet_in"), -1, "between 0 and 100"),
            (("diagrams", 1, "layout", "title_padding", "vnet_in"), 101, "between 0 and 100"),
            (("diagrams", 1, "layout", "link_length", "arm"), 0, "between 1 and 100"),
            (("diagrams", 1, "layout", "link_length", "arm"), 2**63, "between 1 and 100"),
            (("diagrams", 1, "layout", "link_length", "ghost"), 2, "unknown or non-dotted edge"),
            (("diagrams", 1, "layout", "title_padding", "ghost"), 2, "unknown container"),
            (("base", "nodes", 0, "label"), 'x"]\nflowchart LR', "raw Mermaid"),
        ]
        for path, value, diagnostic in cases:
            with self.subTest(path=path, value=value):
                raw = copy.deepcopy(RAW)
                target = raw
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                # When / Then: validation names this defect, not merely a failure.
                with self.assertRaisesRegex(composer.CompositionError, re.escape(diagnostic)):
                    composer.parse_spec(raw)

    def test_mapping_and_missing_field_defects(self):
        # Given: mutations that add, remove or rename a single mapping entry.
        def unknown_replacement(raw):
            mapping = raw["extensions"]["ingress-pe"]["replace_edges"]
            mapping["ghost"] = mapping.pop("request")
        def missing_overlay_edge(raw):
            mapping = raw["overlays"]["egress-failure"]["replace_edges"]
            mapping["ghost"] = mapping.pop("dns_lookup")
        def missing_overlay_node(raw):
            mapping = raw["overlays"]["egress-failure"]["nodes"]
            mapping["ghost"] = mapping.pop("dns_out")
        def deep_nesting(raw):
            names = ["vnet_in", "subnet_pe"] + [f"level{i}" for i in range(7)]
            members = names[1:] + ["private_endpoint"]
            raw["extensions"]["ingress-pe"]["containers"] = [
                {"id": name, "component": "vnet" if index == 0 else "subnet", "title": "Nested", "tag": "[x]", "members": [member]}
                for index, (name, member) in enumerate(zip(names, members))]
        def shared_parent(raw):
            raw["extensions"]["ingress-pe"]["containers"][0]["members"].append("private_endpoint")
        def conflicting_extension(raw):
            raw["extensions"]["extra"] = {"nodes": [], "containers": [], "replace_edges": {"request": []}}
            raw["diagrams"][1]["extensions"].append("extra")
        cases = [
            (unknown_replacement, "unknown edge"), (missing_overlay_edge, "unknown edge"),
            (missing_overlay_node, "overlay targets missing node"), (shared_parent, "multiple parents"),
            (deep_nesting, "container nesting deeper than 8 levels"),
            (conflicting_extension, "two extensions replace the same edge"),
            (lambda r: r.update(extra=1), "unknown keys"),
            (lambda r: r["overlays"]["egress-failure"]["callout"].pop("anchor"), "missing anchor"),
            (lambda r: r["overlays"]["egress-failure"].pop("callout"), "missing callout"),
        ]
        for mutate, diagnostic in cases:
            with self.subTest(defect=diagnostic):
                raw = copy.deepcopy(RAW)
                mutate(raw)
                # When / Then: each independently malformed model is rejected.
                with self.assertRaisesRegex(composer.CompositionError, diagnostic):
                    composer.parse_spec(raw)

    def test_duplicate_json_keys_are_rejected(self):
        # Given / When / Then: duplicate keys at any depth cannot silently overwrite.
        with self.assertRaisesRegex(composer.CompositionError, "duplicate JSON key: id"):
            composer.decode('{"base": {"id": "one", "id": "two"}}')
        with self.assertRaisesRegex(composer.CompositionError, "invalid JSON constant"):
            composer.decode('{"schema_version": NaN}')
        with mock.patch.object(composer.json, "loads", side_effect=RecursionError), self.assertRaisesRegex(composer.CompositionError, "nesting too deep"):
            composer.decode("[]")
        with mock.patch.object(composer.json, "loads", side_effect=ValueError("Exceeds the limit (4300 digits)")), self.assertRaisesRegex(composer.CompositionError, "number out of range"):
            composer.decode("[]")

    def test_committed_bodies_and_guard_round_trip(self):
        # Given: exactly four enrolled bodies from the working-tree oracle.
        spec = composer.parse_spec(RAW)
        fences = dict(guard.FENCE.findall(PAGE.read_text(encoding="utf-8")))
        self.assertEqual(set(fences) & {d.id for d in spec.diagrams}, set(guard.APP_SERVICE))
        for diagram in spec.diagrams:
            with self.subTest(diagram=diagram.id):
                # When: composition serializes the shared model.
                body = composer.compose(spec, diagram)
                # Then: bytes match and the independent guard accepts the result.
                self.assertEqual(body.encode(), fences[diagram.id].encode())
                self.assertIsNotNone(composer.GENERATED_BODY.fullmatch(body))
                self.assertEqual(guard.fixture_problems(diagram.id, body, guard.parse_fixture(body)), [])

    def test_determinism_across_repetition_key_order_and_hash_seeds(self):
        # Given: the same records with shuffled object keys (arrays retain order).
        specs = [composer.parse_spec(RAW), composer.parse_spec(shuffled(RAW))]
        expected = [composer.compose(specs[0], d) for d in specs[0].diagrams]
        # When / Then: repeated calls and independent hash seeds preserve every byte.
        for spec in specs:
            self.assertEqual([composer.compose(spec, d) for d in spec.diagrams], expected)
        for seed in (0, 1, 42):
            for diagram, body in zip(specs[0].diagrams, expected):
                result = subprocess.run([sys.executable, str(SCRIPT), "--print", diagram.id],
                                        env={**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-16-le"},
                                        capture_output=True, check=True)
                self.assertEqual(result.stdout, body.encode())

    def test_indices_follow_combination_and_fault_insertion(self):
        # Given: both extensions, then a further fault edge at a replacement position.
        for inserted, indices in ((False, {7, 11, 12}), (True, {7, 8, 12, 13})):
            raw = copy.deepcopy(RAW)
            raw["diagrams"][3]["extensions"].insert(0, "ingress-pe")
            if inserted:
                raw["overlays"]["egress-failure"]["replace_edges"]["dns_lookup"].append(
                    {"id": "another_fault", "from": "app_runtime", "to": "storage_db",
                     "style": "fault", "label": "[FAULT / Inferred] competing failure"})
            # When: emission computes indices from the final edge sequence.
            spec = composer.parse_spec(raw)
            parsed = guard.parse_fixture(composer.compose(spec, spec.diagrams[3]))
            # Then: exact expected lists include the shifted callout edge.
            self.assertEqual(parsed["linkstyle"], indices)
            self.assertEqual({i for i, e in enumerate(parsed["edges"]) if e[1] == "==>"}, indices)

    def test_new_extension_copies_no_base_data(self):
        # Given: one new dependency and an in-place path replacement, no base copy.
        raw = copy.deepcopy(RAW)
        raw["extensions"]["secrets"] = {
            "nodes": [{"id": "key_vault", "component": "key-vault", "label": "Secrets: vault", "class": "baseNeutral"}],
            "containers": [], "replace_edges": {"storage": [
                {"id": "vault", "from": "app_runtime", "to": "key_vault", "style": "solid", "label": "[Configured] HTTPS secrets"}]}}
        raw["diagrams"][0]["extensions"] = ["secrets"]
        # When: the unchanged composer consumes the new extension.
        spec = composer.parse_spec(raw)
        parsed = guard.parse_fixture(composer.compose(spec, spec.diagrams[0]))
        # Then: the new cylinder and edge coexist with every shared base node.
        self.assertEqual(set(parsed["labels"]), set(guard.BASE_NODES) | {"key_vault"})
        self.assertIn(("app_runtime", "-->", "[Configured] HTTPS secrets", "key_vault"), parsed["edges"])

    def test_drift_metadata_and_adjacency_diagnostics(self):
        # Given: independent single-defect edits to the real page.
        spec = composer.parse_spec(RAW)
        entries = tuple((d, composer.compose(spec, d)) for d in spec.diagrams)
        original = PAGE.read_text(encoding="utf-8")
        identifier = spec.diagrams[0].id
        cases = [
            (original.replace("```mermaid\nflowchart TD", "```mermaid\nflowchart LR", 1), identifier + ": committed fence drift"),
            (original.replace("<!-- diagram-id: " + identifier, "<!-- diagram-id: missing", 1), identifier + ": missing"),
            (original.replace("-->\n```mermaid", "-->\n\n```mermaid", 1), identifier + ": missing"),
            (original.replace("- id: " + identifier, "- id: topology-grammar-v1-appservice-missing", 1), "frontmatter diagram ids differ"),
            (original.replace(spec.diagrams[0].sources[0], "https://example.com/source", 1), identifier + ": frontmatter sources differ"),
        ]
        for mutated, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                # When / Then: checking the temporary page reports the targeted defect.
                with tempfile.TemporaryDirectory() as directory:
                    page = Path(directory) / "page.md"
                    page.write_bytes(mutated.encode())
                    with self.assertRaisesRegex(composer.CompositionError, re.escape(diagnostic)):
                        composer.page_result(page.read_bytes().decode(), entries)

    def test_cli_write_is_span_only_idempotent_and_crlf_preserving(self):
        # Given: a temporary root and three drifting bodies that shrink, grow and keep their length.
        for newline in ("\n", "\r\n"):
            with tempfile.TemporaryDirectory() as directory:
                nested = Path(directory) / RAW["diagrams"][0]["page"]
                nested.parent.mkdir(parents=True)
                original = PAGE.read_text(encoding="utf-8").replace("\n", newline)
                ids = [d["id"] for d in RAW["diagrams"][:3]]
                title = f"    accTitle: {RAW['diagrams'][0]['accTitle']}{newline}"
                self.assertEqual(original.count(title), 1)
                header = f"<!-- diagram-id: {ids[1]} -->{newline}```mermaid{newline}flowchart TD"
                same = f"<!-- diagram-id: {ids[2]} -->{newline}```mermaid{newline}flowchart "
                self.assertIn(header, original)
                drifted = original.replace(title, "", 1).replace(header, f'{header}{newline}    extra["x"]', 1).replace(same + "TD", same + "BT", 1)
                self.assertEqual(len({original, drifted}), 2)
                nested.write_bytes(drifted.encode())
                nested.chmod(0o640)
                mode = stat.S_IMODE(nested.stat().st_mode)
                # When: read-only check fails, then write repairs only the enrolled spans.
                failed = run_cli(directory, "--check")
                self.assertEqual(failed.returncode, 1)
                self.assertIn(ids[0].encode(), failed.stderr)
                self.assertNotIn(b"Traceback", failed.stderr)
                self.assertEqual(nested.read_bytes(), drifted.encode())
                self.assertEqual(run_cli(directory, "--write").returncode, 0)
                # Then: every other byte, including CRLF and hand-written adapters, survives, the file keeps its
                # permissions and the replacement leaves no temporary file behind.
                self.assertEqual(nested.read_bytes(), original.encode())
                self.assertEqual(stat.S_IMODE(nested.stat().st_mode), mode)
                self.assertEqual([entry.name for entry in nested.parent.iterdir()], [nested.name])
                stamp = nested.stat().st_mtime_ns
                self.assertEqual(run_cli(directory, "--write").returncode, 0)
                self.assertEqual(nested.stat().st_mtime_ns, stamp)
                self.assertEqual(run_cli(directory, "--check").returncode, 0)

    def test_a_write_that_fails_part_way_leaves_the_page_byte_identical(self):
        # Given: a drifting page and a process that may not create a file larger than 1 KiB, so the write fails part way.
        if importlib.util.find_spec("resource") is None:
            self.skipTest("resource limits are unavailable")
        drifted = PAGE.read_bytes().replace(b"```mermaid\nflowchart TD", b"```mermaid\nflowchart LR", 1)
        self.assertGreater(len(drifted), 4096)
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / RAW["diagrams"][0]["page"]
            page.parent.mkdir(parents=True)
            page.write_bytes(drifted)
            # When: --write replaces the page.
            result = subprocess.run([sys.executable, "-c", LIMITED_CLI, directory, "--write"], capture_output=True)
            # Then: one handled line, every byte of the page kept and no temporary file left behind.
            self.assertEqual(result.returncode, 1)
            self.assertEqual(len(result.stderr.splitlines()), 1)
            self.assertNotIn(b"Traceback", result.stderr)
            self.assertEqual(page.read_bytes(), drifted)
            self.assertEqual([entry.name for entry in page.parent.iterdir()], [page.name])

    def test_a_diagnostic_is_one_line_whatever_text_it_quotes(self):
        # Given: a spec whose duplicate key holds a line break of some kind; the diagnostic quotes it before any text rule runs.
        for key in ("x\rY", "x\u2028Y", "x\x85Y", "x\ud800Y"):
            with self.subTest(key=key):
                raw = f"{{{json.dumps(key)}: 1, {json.dumps(key)}: 2}}"
                stderr = io.StringIO()
                # When: the CLI loads it.
                with mock.patch.object(composer, "load_spec", side_effect=lambda: composer.decode(raw)), contextlib.redirect_stderr(stderr):
                    code = composer.main(["--check"])
                # Then: it exits 1 with exactly one line that names the defect.
                self.assertEqual(code, 1)
                self.assertEqual(len(stderr.getvalue().splitlines()), 1)
                self.assertIn("duplicate JSON key", stderr.getvalue())

    def test_an_empty_print_identifier_is_refused_and_not_read_as_a_check(self):
        # When: --print is given an empty identifier.
        result = run_cli(ROOT, "--print", "")
        # Then: it is an unknown diagram, not a silent check that passes.
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"unknown diagram", result.stderr)

    def test_early_closing_lines_are_refused_and_outside_text_survives(self):
        # Given: bodies that Markdown closes early, or that merely look like fence syntax; the text after each
        # line is indented, so only that line can make the body unacceptable.
        original = PAGE.read_text(encoding="utf-8")
        opening = "```mermaid\nflowchart TD"
        shape, drift, cr = b"not shaped like a generated one", b"committed fence drift", b"bare carriage return"
        cases = [("four backticks", opening + "\n````\n    OUTSIDE_SENTINEL", shape, drift),
                 ("trailing space", opening + "\n``` \n    OUTSIDE_SENTINEL", shape, drift),
                 ("three-space indent", opening + "\n   ```\n    OUTSIDE_SENTINEL", shape, drift),
                 ("tildes", opening + "\n~~~\n    OUTSIDE_SENTINEL", shape, drift),
                 ("closer instead of the header", "```mermaid\n````\n    flowchart TD", shape, drift),
                 ("bare carriage return", opening + "\n```\r    OUTSIDE_SENTINEL", cr, cr)]
        for label, replacement, write_diagnostic, check_diagnostic in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / RAW["diagrams"][0]["page"]
                target.parent.mkdir(parents=True)
                attack = original.replace(opening, replacement, 1).encode("utf-8")
                target.write_bytes(attack)
                # When: the CLI is asked to write and to check.
                written, checked = run_cli(directory, "--write"), run_cli(directory, "--check")
                # Then: both refuse with their own diagnostic and no byte changes, so the text after the line survives.
                self.assertEqual([written.returncode, checked.returncode], [1, 1])
                self.assertIn(write_diagnostic, written.stderr)
                self.assertIn(check_diagnostic, checked.stderr)
                self.assertEqual(target.read_bytes(), attack)

    def test_a_deleted_closing_delimiter_cannot_swallow_the_text_after_the_fence(self):
        # Given: the last enrolled fence has lost its closing line, so the fence pattern runs into the following text.
        original = PAGE.read_text(encoding="utf-8")
        last = RAW["diagrams"][-1]["id"]
        match = next(m for m in composer.FENCE.finditer(original) if m.group(1) == last)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / RAW["diagrams"][0]["page"]
            target.parent.mkdir(parents=True)
            attack = (original[:match.end(2)] + original[match.end(0):]).encode("utf-8")
            target.write_bytes(attack)
            # When: the CLI is asked to write.
            result = run_cli(directory, "--write")
            # Then: it refuses and every byte of the text after the fence survives.
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"not shaped like a generated one", result.stderr)
            self.assertEqual(target.read_bytes(), attack)

    def test_a_page_symlinked_outside_the_root_is_refused(self):
        # Given: an enrolled page that is a symlink to a drifting file outside the root.
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "outside.md"
            external.write_text(PAGE.read_text(encoding="utf-8").replace("```mermaid\nflowchart TD", "```mermaid\nflowchart LR", 1), encoding="utf-8", newline="\n")
            link = Path(directory) / RAW["diagrams"][0]["page"]
            link.parent.mkdir(parents=True)
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable")
            before = external.read_bytes()
            # When: the CLI is asked to write and to check.
            results = [run_cli(directory, mode) for mode in ("--write", "--check")]
            # Then: both refuse and the external file is untouched.
            self.assertEqual([r.returncode for r in results], [1, 1])
            self.assertIn(b"resolves outside the repository", results[0].stderr)
            self.assertEqual(external.read_bytes(), before)

    def test_a_page_hard_linked_to_a_file_outside_the_root_is_not_written(self):
        # Given: an enrolled page that is a hard link to a drifting file outside the root.
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "outside.md"
            external.write_bytes(PAGE.read_bytes().replace(b"```mermaid\nflowchart TD", b"```mermaid\nflowchart LR", 1))
            link = Path(directory) / RAW["diagrams"][0]["page"]
            link.parent.mkdir(parents=True)
            try:
                os.link(external, link)
            except (OSError, NotImplementedError):
                self.skipTest("hard links are unavailable")
            before = external.read_bytes()
            # When: the CLI is asked to write.
            result = run_cli(directory, "--write")
            # Then: it refuses before any byte is written, so the file shared with the outside is untouched.
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"more than one hard link", result.stderr)
            self.assertEqual(external.read_bytes(), before)

    def test_two_spellings_of_one_page_are_planned_together(self):
        # Given: two enrolled diagrams that spell one page path differently, both drifting.
        raw = copy.deepcopy(RAW)
        raw["diagrams"][1]["page"] = raw["diagrams"][1]["page"].replace("docs/", "docs/./", 1)
        spec = composer.parse_spec(raw)
        original = PAGE.read_text(encoding="utf-8")
        drifted = original
        for diagram in spec.diagrams[:2]:
            marker = f"<!-- diagram-id: {diagram.id} -->\n```mermaid\nflowchart TD"
            self.assertIn(marker, drifted)
            drifted = drifted.replace(marker, marker.replace("flowchart TD", "flowchart LR"), 1)
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / RAW["diagrams"][0]["page"]
            page.parent.mkdir(parents=True)
            page.write_bytes(drifted.encode("utf-8"))
            # When: --write plans the file once, not once per spelling.
            with mock.patch.object(composer, "ROOT", Path(directory)), mock.patch.object(composer, "load_spec", return_value=spec), contextlib.redirect_stdout(io.StringIO()):
                code = composer.main(["--write"])
            # Then: one write repairs both fences instead of the second plan undoing the first.
            self.assertEqual(code, 0)
            self.assertEqual(page.read_bytes(), original.encode("utf-8"))

    def test_a_page_that_is_not_a_regular_file_is_a_diagnostic(self):
        # Given: an enrolled page path that is a directory.
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / RAW["diagrams"][0]["page"]).mkdir(parents=True)
            # When / Then: the CLI reports one handled line before it reads anything.
            result = run_cli(directory, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"not a regular file", result.stderr)

    def test_a_symlink_loop_is_a_diagnostic_not_a_traceback(self):
        # Given: an enrolled page that is a symlink to itself.
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / RAW["diagrams"][0]["page"]
            link.parent.mkdir(parents=True)
            try:
                link.symlink_to(link.name)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable")
            # When / Then: the CLI reports one handled line on every supported Python version.
            result = run_cli(directory, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(b"Traceback", result.stderr)

    def test_normal_path_rejects_a_claimed_fault(self):
        # Given: one fault record on the base's normal path.
        raw = copy.deepcopy(RAW)
        raw["base"]["edges"][0] = {**raw["base"]["edges"][0], "style": "fault", "label": "[FAULT / Illustrative] broken"}
        # When / Then: a normal diagram cannot silently acquire failure semantics.
        with self.assertRaisesRegex(composer.CompositionError, "normal path cannot contain fault"):
            composer.parse_spec(raw)

    def test_other_drawable_vocabulary_shapes_need_no_passthrough(self):
        # Given: unused drawable vocabulary entries, expressed as semantic records.
        raw = copy.deepcopy(RAW)
        additions = [("firewall_nva", "firewall-nva"), ("key_vault", "key-vault")]
        raw["base"]["nodes"] += [{"id": name, "component": component, "label": name, "class": "baseNeutral"} for name, component in additions]
        # When: the same emitter serializes the extended base.
        spec = composer.parse_spec(raw)
        body = composer.compose(spec, spec.diagrams[0])
        # Then: the independent grammar parser recognizes both shape declarations.
        self.assertEqual(set(guard.parse_fixture(body)["labels"]), set(guard.BASE_NODES) | {n for n, _ in additions})

    def test_stats_are_derived_from_the_spec_and_the_committed_fences(self):
        # Given: the counts the evaluation quotes, computed independently from the raw records and the page.
        fences = dict(guard.FENCE.findall(PAGE.read_text(encoding="utf-8")))
        # When: the composer reports its own counts.
        counts = composer.stats(composer.parse_spec(RAW))
        # Then: both agree, so the quoted numbers cannot drift from the files.
        self.assertEqual(counts["nodes"], len(RAW["base"]["nodes"]) + sum(len(e["nodes"]) for e in RAW["extensions"].values()))
        self.assertEqual(counts["inline_nonblank_lines"], {i: len(fences[i].splitlines()) for i in counts["inline_nonblank_lines"]})

    def test_empty_replacement_removes_an_edge_in_place(self):
        # Given: a test-only extension that removes one base edge.
        raw = copy.deepcopy(RAW)
        raw["extensions"]["omit"] = {"nodes": [], "containers": [], "replace_edges": {"storage": []}}
        raw["diagrams"][0]["extensions"] = ["omit"]
        # When: the extension is applied without copying base records.
        spec = composer.parse_spec(raw)
        edges = guard.parse_fixture(composer.compose(spec, spec.diagrams[0]))["edges"]
        # Then: only the selected edge disappears and survivor order is unchanged.
        original = guard.parse_fixture(dict(guard.FENCE.findall(PAGE.read_text(encoding="utf-8")))[guard.BASELINE])["edges"]
        self.assertEqual(edges, original[:5] + original[6:])


if __name__ == "__main__":
    unittest.main()
