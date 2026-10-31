"""Offline guard for the Azure topology visual grammar page (grammar v1).

The page is a contract other guides will adopt, so the promises that can be
checked mechanically are tested here: section order, the component and claim-level
vocabularies, fixture structure (orientation, accessible names, no bidirectional
arrows, stable base nodes across the four App Service variants, factual
containment, no layout-only semantic edges) and the evidence-honesty rule that an
illustrative fixture never uses the `[Observed]` claim level.

This is a static check of text and Mermaid source. It renders nothing and says
nothing about visual quality, layout stability or live Azure behavior.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "reference" / "diagram-topology-grammar.md"
MAX_LINES = 450

HEADINGS = (
    "## 1. Status and Scope",
    "## 2. Reading Order and Layout Regions",
    "## 3. Resource and Responsibility Boundaries",
    "## 4. Component Vocabulary",
    "## 5. Edge and Legend Contract",
    "## 6. Visual System",
    "## 7. Progressive Views",
    "## 8. Reference Fixtures (App Service)",
    "## 9. Service Adapters",
    "## 10. Exceptions and Limits",
    "## 11. Source and Accuracy",
    "## See Also",
    "## Sources",
)
VOCABULARY = (
    "client", "dns", "vnet", "subnet", "nsg-udr", "ingress", "private-endpoint",
    "vnet-integration", "nat-firewall", "app-runtime", "identity", "key-vault",
    "storage-db", "telemetry", "control-plane",
)
CLAIM_LEVELS = ("[Configured]", "[Illustrative]", "[Inferred]", "[Observed]")
BASE_NODES = ("control_plane", "client", "ingress", "app_runtime", "identity", "storage_db", "telemetry")
APP_SERVICE = (
    "topology-grammar-v1-appservice-baseline",
    "topology-grammar-v1-appservice-ingress-pe",
    "topology-grammar-v1-appservice-egress-vnet",
    "topology-grammar-v1-appservice-fault-overlay",
)
REFUTED_PHRASES = (
    "bypasses access restriction",  # Learn: the rules "aren't evaluated" for private endpoint traffic
    "standalone resource",  # Learn only says a private DNS zone is linked to virtual networks
    "guarantees invariant",  # dagre gives no stability guarantee
)

FENCE = re.compile(r"<!-- diagram-id: ([a-z0-9-]+) -->\n```mermaid\n(.*?)\n```", re.S)
NODE = re.compile(r'^\s*(\w+)\s*(?:\[\[|\[\(|\(\[|\{\{|\[/|\[|\(|>)\s*"(.*)"\s*(?:\]\]|\)\]|\]\)|\}\}|/\]|\]|\))\s*$')
EDGE = re.compile(r'^\s*(\w+)\s+(-\.+->|-{2,}>|={2,}>|~~~)\s*(?:\|"(.*?)"\|\s*)?(\w+)\s*$')
SUBGRAPH = re.compile(r'^\s*subgraph\s+(\w+)(?:\[\s*"(.*)"\s*\])?\s*$')
SIZE_IN_TITLE = re.compile(r"/\d{2}\b")


def section(text, start, end):
    """Return the text between two level-two headings (empty if either is missing)."""
    first = text.find(start)
    last = text.find(end, first + 1) if first >= 0 else -1
    return text[first:last] if first >= 0 and last > first else ""


def parse_fixture(code):
    """Return nodes, edges, declaration order and subgraph structure of one fence."""
    fixture = {"labels": {}, "order": [], "edges": [], "container": {}, "parent": {}, "title": {}}
    stack = []
    for raw in code.splitlines():
        match = SUBGRAPH.match(raw)
        if match:
            name = match.group(1)
            fixture["parent"][name] = stack[-1] if stack else None
            fixture["title"][name] = match.group(2) or name
            stack.append(name)
        elif raw.strip() == "end":
            if stack:
                stack.pop()
        elif NODE.match(raw):
            name, label = NODE.match(raw).groups()
            fixture["labels"][name] = label
            fixture["order"].append(name)
            fixture["container"][name] = tuple(stack)
        elif EDGE.match(raw):
            source, arrow, label, target = EDGE.match(raw).groups()
            fixture["edges"].append((source, arrow, label or "", target))
    return fixture


def fixture_problems(name, code, fixture):
    """Problems found in a single Mermaid fixture."""
    problems = []
    first = next((line for line in code.splitlines() if line.strip()), "")
    if first.strip() != "flowchart TD":
        problems.append(f"{name}: must start with 'flowchart TD' (orientation rule), found {first.strip()!r}")
    for keyword in ("accTitle:", "accDescr:"):
        if keyword not in code:
            problems.append(f"{name}: missing {keyword}")
    if "<-->" in code:
        problems.append(f"{name}: unconstrained bidirectional arrow")
    if "[Observed]" in code or "/ Observed]" in code:
        problems.append(f"{name}: fixture uses the reserved [Observed] claim level")
    for node, containers in fixture["container"].items():
        if node.startswith("dns") and containers:
            problems.append(f"{name}: DNS zone node {node} drawn inside container {containers[-1]}")
    for title_owner, title in fixture["title"].items():
        if SIZE_IN_TITLE.search(title):
            problems.append(f"{name}: container {title_owner} carries a subnet size in its title: {title!r}")
    for source, _, _, target in fixture["edges"]:
        if source.startswith("dns"):
            problems.append(f"{name}: edge starts at DNS zone node {source} (lookups end at the zone)")
    visible = [edge for edge in fixture["edges"] if edge[1] != "~~~"]
    for node in fixture["labels"]:
        if node.startswith("nsg") and any(e[3] == node for e in visible) and any(e[0] == node for e in visible):
            problems.append(f"{name}: policy node {node} is drawn as a hop in the request chain")
    return problems


def grammar_problems(text):
    """Return human-readable problems for the whole page."""
    problems = []
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        problems.append(f"page has {len(lines)} lines; budget is {MAX_LINES}")

    head = text.split("---", 2)[1] if text.startswith("---") else ""
    for required in ("slug: diagram-topology-grammar", "doc_type: reference", "section: reference"):
        if required not in head:
            problems.append(f"frontmatter lacks {required!r}")
    declared = re.findall(r"^\s+- id: ([a-z0-9-]+)\s*$", head, re.M)

    positions = [text.find(f"\n{heading}\n") for heading in HEADINGS]
    for heading, position in zip(HEADINGS, positions):
        if position < 0:
            problems.append(f"missing heading {heading!r}")
    present = [p for p in positions if p >= 0]
    if present != sorted(present):
        problems.append("level-two headings are out of order")
    if "grammar v1" not in text or "Proposed" not in text:
        problems.append("page does not state 'grammar v1' and its 'Proposed' status")

    vocabulary = section(text, "\n## 4. Component Vocabulary", "\n## 5. ")
    for identifier in VOCABULARY:
        if not re.search(rf"^\|\s*`{re.escape(identifier)}`\s*\|", vocabulary, re.M):
            problems.append(f"component vocabulary lacks {identifier!r}")
    claims = section(text, "\n## 5. Edge and Legend Contract", "\n## 6. ")
    for level in CLAIM_LEVELS:
        if level not in claims:
            problems.append(f"claim-level vocabulary lacks {level}")

    fences = FENCE.findall(text)
    if len(fences) != text.count("```mermaid"):
        problems.append("a Mermaid fence is not directly preceded by its diagram-id comment")
    ids = [diagram_id for diagram_id, _ in fences]
    if len(set(ids)) != len(ids) or sorted(ids) != sorted(declared):
        problems.append("diagram-id comments and content_sources.diagrams[] ids differ or repeat")
    parsed = {}
    for diagram_id, code in fences:
        parsed[diagram_id] = parse_fixture(code)
        problems.extend(fixture_problems(diagram_id, code, parsed[diagram_id]))

    variants = [parsed[i] for i in APP_SERVICE if i in parsed]
    for missing in (i for i in APP_SERVICE if i not in parsed):
        problems.append(f"missing App Service fixture {missing}")
    if len(variants) == len(APP_SERVICE):
        base_order = [[n for n in v["order"] if n in BASE_NODES] for v in variants]
        if any(order != base_order[0] for order in base_order) or set(base_order[0]) != set(BASE_NODES):
            problems.append(f"base nodes are not declared once, in the same order, in all four variants: {base_order}")
        for node in BASE_NODES:
            if len({v["labels"].get(node) for v in variants}) != 1:
                problems.append(f"base node {node} has different labels across the variants")
        plane = [frozenset((label, target) for source, _, label, target in v["edges"] if source == "control_plane")
                 for v in variants]
        if any(edges != plane[0] for edges in plane) or not plane[0]:
            problems.append("control_plane edges differ in label or target across the variants")
        for node in ("ingress", "app_runtime"):
            for diagram_id, v in zip(APP_SERVICE, variants):
                if v["container"].get(node):
                    problems.append(f"{diagram_id}: {node} is drawn inside a customer container")
        for diagram_id in APP_SERVICE[1:3]:
            nested = [c for c, p in parsed[diagram_id]["parent"].items() if p]
            if not nested:
                problems.append(f"{diagram_id}: no subnet container nested inside the VNet container")
        overlay_code = dict(fences)[APP_SERVICE[3]]
        if "[FAULT / Illustrative]" not in overlay_code or "Illustrative scenario" not in overlay_code:
            problems.append("fault overlay is not labelled as an illustrative scenario")
        for source, arrow, _, target in parsed[APP_SERVICE[3]]["edges"]:
            if arrow.startswith("=") and target == "storage_db" and source != "vnet_integration":
                problems.append(f"fault overlay: failing arrow into storage_db starts at {source}, not vnet_integration")

    if re.search(r"https://learn\.microsoft\.com/(?!en-us/)", text):
        problems.append("a Microsoft Learn URL lacks the /en-us/ locale")
    if re.search(r"!\[|\.(?:png|svg|webp)\b", text, re.I):
        problems.append("page references or embeds an image")
    for phrase in REFUTED_PHRASES:
        if phrase in text:
            problems.append(f"contains a refuted claim: {phrase!r}")
    return problems


class TopologyGrammarPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_the_committed_page_satisfies_every_rule(self):
        # Given: the committed grammar page.
        # When: every mechanical rule runs against it.
        problems = grammar_problems(self.text)

        # Then: nothing is reported.
        self.assertEqual(problems, [])

    def test_a_vacuous_scan_is_impossible(self):
        # Given: the committed page.
        fences = FENCE.findall(self.text)

        # When / Then: it carries the four App Service fixtures it is checked on.
        self.assertTrue(set(APP_SERVICE) <= {diagram_id for diagram_id, _ in fences})

    def mutate_first_fixture(self, old, new):
        """Apply one edit inside the first Mermaid fence only (prose also mentions these tokens)."""
        code = FENCE.search(self.text).group(2)
        return self.text.replace(code, code.replace(old, new, 1), 1)

    def test_each_rule_can_fail(self):
        # Given: single-defect mutations of the committed page.
        first_subgraph = re.search(r"^( *)subgraph .*$", self.text, re.M)
        fixture = self.mutate_first_fixture
        mutations = {
            "orientation": fixture("flowchart TD", "flowchart LR"),
            "bidirectional arrow": fixture("flowchart TD", "flowchart TD\n    a <--> b"),
            "reserved claim level": fixture("[Configured]", "[Observed]"),
            "dns lookup that starts at the zone": fixture("flowchart TD", 'flowchart TD\n    dns_x -.->|"x"| ingress'),
            "dns inside a container": self.text.replace(
                first_subgraph.group(0), first_subgraph.group(0) + "\n" + first_subgraph.group(1) + '    dns_x{{"d"}}', 1),
            "policy node as a hop": fixture(
                "flowchart TD", 'flowchart TD\n    nsg_x["n"]\n    a -->|"x"| nsg_x\n    nsg_x -->|"y"| b'),
            "missing accessible name": fixture("accTitle:", "accTit:"),
            "label drift in one variant": fixture('client(["', 'client(["X '),
            "learn locale": self.text.replace("learn.microsoft.com/en-us/", "learn.microsoft.com/", 1),
            "refuted claim": self.text + "\nPrivate Endpoint traffic bypasses access restriction rules.\n",
            "image": self.text + "\n![x](a.png)\n",
            "oversized page": self.text + "\n" * (MAX_LINES + 1),
        }

        # When / Then: every mutation is reported.
        for name, mutated in mutations.items():
            with self.subTest(defect=name):
                self.assertNotEqual(mutated, self.text, "the mutation did not change the page")
                self.assertTrue(grammar_problems(mutated), f"{name} went undetected")


if __name__ == "__main__":
    unittest.main()
