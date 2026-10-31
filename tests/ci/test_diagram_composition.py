"""Stdlib mutation tests against the independently authored grammar fences."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import random
import re
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
            (("extensions", "ingress-pe", "containers", 1, "members"), ["ghost"], "missing member ghost"),
            (("extensions", "ingress-pe", "containers", 1, "members"), ["vnet_in"], "container cycle"),
            (("extensions", "ingress-pe", "containers", 1, "members"), [], "missing members"),
            (("diagrams", 1, "layout", "link_length", "arm"), True, "expected int"),
            (("diagrams", 1, "layout", "title_padding", "vnet_in"), -1, "nonnegative"),
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
        def shared_parent(raw):
            raw["extensions"]["ingress-pe"]["containers"][0]["members"].append("private_endpoint")
        def conflicting_extension(raw):
            raw["extensions"]["extra"] = {"nodes": [], "containers": [], "replace_edges": {"request": []}}
            raw["diagrams"][1]["extensions"].append("extra")
        cases = [
            (unknown_replacement, "unknown edge"), (missing_overlay_edge, "unknown edge"),
            (missing_overlay_node, "overlay targets missing node"), (shared_parent, "multiple parents"),
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
                                        env={**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONDONTWRITEBYTECODE": "1"},
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
        # Given: a temporary root, canonical metadata and one drifting body.
        for newline in ("\n", "\r\n"):
            with tempfile.TemporaryDirectory() as directory:
                # Use the real spec path and mirror its page in this disposable root.
                nested = Path(directory) / RAW["diagrams"][0]["page"]
                nested.parent.mkdir(parents=True)
                original = PAGE.read_text(encoding="utf-8").replace("\n", newline).encode()
                nested.write_bytes(original.replace(("```mermaid" + newline + "flowchart TD").encode(), ("```mermaid" + newline + "flowchart LR").encode(), 1))
                # When: read-only check fails, then write repairs only the enrolled span.
                failed = run_cli(directory, "--check")
                self.assertEqual(failed.returncode, 1)
                self.assertIn(RAW["diagrams"][0]["id"].encode(), failed.stderr)
                self.assertNotIn(b"Traceback", failed.stderr)
                self.assertIn(b"flowchart LR", nested.read_bytes())
                self.assertEqual(run_cli(directory, "--write").returncode, 0)
                # Then: every other byte, including CRLF and hand-written adapters, survives.
                self.assertEqual(nested.read_bytes(), original)
                stamp = nested.stat().st_mtime_ns
                self.assertEqual(run_cli(directory, "--write").returncode, 0)
                self.assertEqual(nested.stat().st_mtime_ns, stamp)
                self.assertEqual(run_cli(directory, "--check").returncode, 0)

    def test_noncanonical_closing_delimiters_are_refused_and_outside_text_survives(self):
        # Given: bodies that Markdown closes early with a delimiter the fence pattern does not recognise.
        original = PAGE.read_text(encoding="utf-8")
        for closer in ("````", "``` ", "   ```"):
            with self.subTest(closer=closer), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / RAW["diagrams"][0]["page"]
                target.parent.mkdir(parents=True)
                attack = original.replace("```mermaid\nflowchart TD", f"```mermaid\nflowchart TD\n{closer}\nOUTSIDE_SENTINEL", 1)
                target.write_text(attack, encoding="utf-8", newline="\n")
                # When: the CLI is asked to write and to check.
                results = [run_cli(directory, mode) for mode in ("--write", "--check")]
                # Then: both refuse with a diagnostic and no byte changes, so the text after the delimiter survives.
                self.assertEqual([r.returncode for r in results], [1, 1])
                self.assertIn(b"noncanonical closing delimiter", results[0].stderr)
                self.assertEqual(target.read_text(encoding="utf-8"), attack)

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
