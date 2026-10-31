"""Offline guard for the Azure topology visual grammar page (grammar v1).

The page is a contract other guides will adopt, so the promises that can be
checked mechanically are tested here: section order, the component and claim-level
vocabularies, fixture structure (orientation, accessible names, no bidirectional
arrows, a claim prefix on every visible edge, no unrecognized source lines),
identical base nodes across the four App Service variants, factual containment
(VNet > subnet > NIC with each NIC in the subnet its role names, DNS zones outside,
NAT/UDR/NSG as subnet tags and never as nodes), the required fault edges and
their link styles, and the evidence-honesty rule that an illustrative fixture
never uses the `[Observed]` claim level.

This is a static check of text and Mermaid source. It renders nothing and says
nothing about visual quality, title clearance, layout stability or live Azure
behavior. It is not a Mermaid parser: it accepts a line by a recognized shape or
prefix (so a malformed `class` line still passes) and rejects any other line, and
an extra `end` or a label that is true only in a diagram is not detected.
Accessible names are checked for presence and non-empty text on the same line,
DNS zones and NAT/UDR/NSG are identified by node id prefix or by label text, and
a NIC's subnet by the start of its visible subnet title. Edge purposes are
checked only for DNS lookups not being solid `-->` arrows (a thick `==>` lookup
passes). Link styles are checked only for index membership, a non-white color
and a width of at least 2px (a transparent or zero-opacity override passes).
Colors and contrast are not checked otherwise (the page's tables are reviewed,
not computed here). Each mutation test asserts the diagnostic of the rule it
targets, so a rule that stops firing is reported even if another rule still
fails.
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
    "client", "dns", "vnet", "subnet", "nsg-udr", "nat-gateway", "firewall-nva", "ingress",
    "private-endpoint", "vnet-integration", "app-runtime", "identity", "key-vault",
    "storage-db", "telemetry", "control-plane",
)
CLAIM_LEVELS = ("[Configured]", "[Illustrative]", "[Inferred]", "[Observed]")
EDGE_PREFIXES = ("[Configured] ", "[Illustrative] ", "[Inferred] ", "[FAULT / Illustrative] ", "[FAULT / Inferred] ")
BASE_NODES = ("control_plane", "client", "ingress", "app_runtime", "identity", "storage_db", "telemetry")
NIC_SUBNET_TITLES = {
    "vnet_integration": "Subnet: VNet integration",
    "private_endpoint": "Subnet: private endpoints",
    "pe_storage": "Subnet: private endpoints",
}
BASELINE, INGRESS_PE, EGRESS, OVERLAY = (
    "topology-grammar-v1-appservice-baseline",
    "topology-grammar-v1-appservice-ingress-pe",
    "topology-grammar-v1-appservice-egress-vnet",
    "topology-grammar-v1-appservice-fault-overlay",
)
FUNCTIONS, CONTAINER_APPS = "topology-grammar-v1-adapter-functions", "topology-grammar-v1-adapter-container-apps"
APP_SERVICE = (BASELINE, INGRESS_PE, EGRESS, OVERLAY)
FIXTURES = APP_SERVICE + (FUNCTIONS, CONTAINER_APPS)
REFUTED_PHRASES = (
    "bypasses access restriction",  # Learn: the rules "aren't evaluated" for private endpoint traffic
    "standalone resource",  # Learn only says a private DNS zone is linked to virtual networks
    "guarantees invariant",  # dagre gives no stability guarantee
)

FENCE = re.compile(r"<!-- diagram-id: ([a-z0-9-]+) -->\n```mermaid\n(.*?)\n```", re.S)
NODE = re.compile(r'^\s*(\w+)\s*(?:\[\[|\[\(|\(\[|\{\{|\[/|\[|\(|>)\s*"(.*)"\s*(?:\]\]|\)\]|\]\)|\}\}|/\]|\]|\))\s*$')
EDGE = re.compile(r'^\s*(\w+)\s+(-\.+->|-{2,}>|={2,}>|~~~)\s*(?:\|"(.*?)"\|\s*)?(\w+)\s*$')
SUBGRAPH = re.compile(r'^\s*subgraph\s+(\w+)(?:\[\s*"(.*)"\s*\])?\s*$')
LINKSTYLE = re.compile(r"^\s*linkStyle\s+([\d,\s]+?)\s+\S.*;?\s*$")
SIZE_IN_TITLE = re.compile(r"/\d{2}\b")
KNOWN_LINE = re.compile(r"^\s*(flowchart TD|accTitle:|accDescr:|classDef |class |linkStyle |%%|end\s*$|$)")


def section(text, start, end):
    """Return the text between two level-two headings (empty if either is missing)."""
    first = text.find(start)
    last = text.find(end, first + 1) if first >= 0 else -1
    return text[first:last] if first >= 0 and last > first else ""


def parse_fixture(code):
    """Return labels, declaration order, edges, link styles and subgraph structure of one fence."""
    fixture = {"labels": {}, "order": [], "edges": [], "container": {}, "parent": {}, "title": {}, "linkstyle": set(), "linkstyle_lines": [], "unparsed": []}
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
        elif LINKSTYLE.match(raw):
            fixture["linkstyle"] |= {int(i) for i in re.findall(r"\d+", LINKSTYLE.match(raw).group(1))}
            fixture["linkstyle_lines"].append(raw.strip())
        elif not KNOWN_LINE.match(raw):
            fixture["unparsed"].append(raw.strip())
    return fixture


def chain_matches(chain, kinds):
    """True when the innermost containers start with the given id prefixes, outermost first."""
    return len(chain) >= len(kinds) and all(c.startswith(k) for c, k in zip(chain[-len(kinds):], kinds))


def fixture_problems(name, code, fixture):
    """Problems found in a single Mermaid fixture."""
    problems = []
    first = next((line for line in code.splitlines() if line.strip()), "")
    if first.strip() != "flowchart TD":
        problems.append(f"{name}: must start with 'flowchart TD' (orientation rule), found {first.strip()!r}")
    for keyword in ("accTitle:", "accDescr:"):
        if keyword not in code:
            problems.append(f"{name}: missing {keyword}")
        elif not re.search(rf"^[ \t]*{keyword}[ \t]*\S", code, re.M):  # horizontal space only: an empty name must not borrow the next line
            problems.append(f"{name}: empty {keyword}")
    if "<-->" in code:
        problems.append(f"{name}: unconstrained bidirectional arrow")
    if "[Observed]" in code or "/ Observed]" in code:
        problems.append(f"{name}: fixture uses the reserved [Observed] claim level")
    problems.extend(f"{name}: unparsed line {line!r}" for line in fixture["unparsed"])
    for node, containers in fixture["container"].items():
        if node.startswith("dns") and containers:
            problems.append(f"{name}: DNS zone node {node} drawn inside container {containers[-1]}")
        if node.startswith(("nsg", "nat", "udr")):
            problems.append(f"{name}: {node} must be a subnet tag, not a node (UDR, NSG and NAT Gateway are not hops)")
    for node, label in fixture["labels"].items():
        if re.search(r"\b(?:NAT|UDR|NSG)\b", label):
            problems.append(f"{name}: node {node} label names NAT/UDR/NSG, which belong in subnet tags")
        if "Private DNS zone" in label and fixture["container"][node]:
            problems.append(f"{name}: Private DNS zone node {node} drawn inside container {fixture['container'][node][-1]}")
    for owner, title in fixture["title"].items():
        if SIZE_IN_TITLE.search(title):
            problems.append(f"{name}: container {owner} carries a subnet size in its title: {title!r}")
    for source, arrow, label, target in fixture["edges"]:
        if source.startswith("dns") and target != "fault_note":  # a callout anchor is an annotation, not a lookup
            problems.append(f"{name}: edge starts at DNS zone node {source} (lookups end at the zone)")
        for end in (source, target):
            if end not in fixture["labels"]:
                problems.append(f"{name}: edge {source} -> {target} references undeclared node {end}")
        if target.startswith("dns") and arrow.startswith("--"):
            problems.append(f"{name}: DNS lookup arrows must be dotted, found a solid arrow to {target}")
        if arrow == "~~~" and label:
            problems.append(f"{name}: invisible layout anchor {source} ~~~ {target} must not carry a label")
        if arrow != "~~~" and not label.startswith(EDGE_PREFIXES):
            problems.append(f"{name}: edge {source} -> {target} lacks a claim prefix: {label!r}")
    return problems


def containment_problems(parsed):
    """VNet > subnet > NIC and environment containment per fixture."""
    problems = []
    rules = {
        INGRESS_PE: {"private_endpoint": ("vnet", "subnet")},
        EGRESS: {"vnet_integration": ("vnet", "subnet"), "pe_storage": ("vnet", "subnet")},
        OVERLAY: {"vnet_integration": ("vnet", "subnet"), "pe_storage": ("vnet", "subnet")},
        FUNCTIONS: {"vnet_integration": ("vnet", "subnet"), "pe_storage": ("vnet", "subnet")},
        CONTAINER_APPS: {"ingress": ("vnet", "subnet", "aca"), "app_runtime": ("vnet", "subnet", "aca")},
    }
    for fixture_id, nodes in rules.items():
        fixture = parsed.get(fixture_id)
        if fixture is None:
            continue
        for node, kinds in nodes.items():
            chain = fixture["container"].get(node, ())
            if not chain_matches(chain, kinds):
                problems.append(f"{fixture_id}: {node} must sit inside {' > '.join(kinds)} containers, found {chain}")
                continue
            expected_title = NIC_SUBNET_TITLES.get(node)
            actual_title = fixture["title"].get(chain[-1], "")
            if expected_title and not actual_title.startswith(expected_title):
                problems.append(f"{fixture_id}: {node} must sit in a subnet titled {expected_title!r}, found {actual_title!r}")
        if {"vnet_integration", "pe_storage"} <= set(nodes):
            subnets = {fixture["container"].get(n, ("",))[-1] for n in ("vnet_integration", "pe_storage")}
            if len(subnets) != 2:
                problems.append(f"{fixture_id}: the integration subnet and the private-endpoint subnet must differ")
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
    problems.extend(f"missing fixture {missing}" for missing in FIXTURES if missing not in parsed)
    problems.extend(containment_problems(parsed))

    variants = [parsed[i] for i in APP_SERVICE if i in parsed]
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
        overlay_code, overlay = dict(fences)[OVERLAY], parsed[OVERLAY]
        if "[FAULT / Illustrative]" not in overlay_code or "Illustrative scenario" not in overlay_code:
            problems.append("fault overlay is not labelled as an illustrative scenario")
        fault_edges = [(s, t) for s, a, _, t in overlay["edges"] if a.startswith("=")]
        for pair in (("vnet_integration", "storage_db"), ("app_runtime", "dns_out"), ("dns_out", "fault_note")):
            if pair not in fault_edges:
                problems.append(f"fault overlay is missing the required fault edge {pair[0]} -> {pair[1]}")
        for source, target in fault_edges:
            if target == "storage_db" and source != "vnet_integration":
                problems.append(f"fault overlay: failing arrow into storage_db starts at {source}, not vnet_integration")
        for line in overlay["linkstyle_lines"]:
            color = re.search(r"stroke:(#[0-9a-fA-F]{3,8})", line)
            width = re.search(r"stroke-width:(\d+(?:\.\d+)?)px", line)
            if not color or color.group(1).lower() in ("#fff", "#ffffff") or not width or float(width.group(1)) < 2:
                problems.append("fault overlay: linkStyle must use a visible stroke color and a width of at least 2px")
        thick = {i for i, (_, a, _, _) in enumerate(overlay["edges"]) if a.startswith("=")}
        if overlay["linkstyle"] != thick:
            problems.append(f"fault overlay: linkStyle indices {sorted(overlay['linkstyle'])} do not match the thick edges {sorted(thick)}")

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

    def edit_fixture(self, fixture_id, edit):
        """Apply an edit inside one named Mermaid fence only (prose also mentions these tokens)."""
        match = next(m for m in FENCE.finditer(self.text) if m.group(1) == fixture_id)
        return self.text[:match.start(2)] + edit(match.group(2)) + self.text[match.end(2):]

    def replace_in(self, fixture_id, old, new):
        def edit(code):
            self.assertIn(old, code, f"{fixture_id} no longer contains {old!r}; update the mutation")
            return code.replace(old, new, 1)
        return self.edit_fixture(fixture_id, edit)

    def test_the_committed_page_satisfies_every_rule(self):
        # Given: the committed grammar page.
        # When: every mechanical rule runs against it.
        problems = grammar_problems(self.text)

        # Then: nothing is reported.
        self.assertEqual(problems, [])

    def test_all_six_fixtures_are_present_and_registered(self):
        # Given: the committed page.
        fences = {diagram_id for diagram_id, _ in FENCE.findall(self.text)}

        # When / Then: the scan is not vacuous.
        self.assertEqual(fences, set(FIXTURES))

    def test_the_vocabulary_separates_policy_nat_and_routed_hops(self):
        # Given: the component vocabulary.
        vocabulary = section(self.text, "\n## 4. Component Vocabulary", "\n## 5. ")

        # When / Then: UDR/NSG and NAT Gateway are subnet tags and only a firewall/NVA is a node.
        self.assertRegex(vocabulary, r"`nsg-udr`.*never a node")
        self.assertRegex(vocabulary, r"`nat-gateway`.*never a node or a UDR target")
        self.assertRegex(vocabulary, r"`firewall-nva`.*`firewall_nva`")

    def test_each_rule_fires_its_own_diagnostic(self):
        # Given: single-defect mutations of the committed page and the diagnostic each must raise.
        def drop_block(diagram_id):
            return re.sub(rf"<!-- diagram-id: {diagram_id} -->\n```mermaid\n.*?\n```\n", "", self.text, flags=re.S)

        def move_runtime_into_subnet(code):
            line = next(l for l in code.splitlines() if l.strip().startswith("app_runtime["))
            code = code.replace(line + "\n", "", 1)
            header = next(l for l in code.splitlines() if "subgraph subnet_int[" in l)
            return code.replace(header, header + "\n" + line, 1)

        def unwrap_pe_subnet(code):
            header = next(l for l in code.splitlines() if "subgraph subnet_pe[" in l)
            code = code.replace(header + "\n", "", 1)
            at = code.index("        end\n", code.index("private_endpoint"))
            return code[:at] + code[at + len("        end\n"):]

        def swap_headings():
            a, b = "\n## 5. Edge and Legend Contract\n", "\n## 6. Visual System\n"
            return self.text.replace(a, "\n@@\n", 1).replace(b, a, 1).replace("\n@@\n", b, 1)

        def drop_line(fixture_id, marker):
            return self.edit_fixture(fixture_id, lambda code: "\n".join(l for l in code.splitlines() if marker not in l))

        def dns_into_container(code):
            header = next(l for l in code.splitlines() if "subgraph vnet_in[" in l)
            return code.replace(header, header + '\n        dns_x{{"Zone"}}', 1)

        def swap_nic_declarations(code):
            lines = code.splitlines()
            first = next(i for i, l in enumerate(lines) if l.strip().startswith("vnet_integration[["))
            second = next(i for i, l in enumerate(lines) if l.strip().startswith("pe_storage[["))
            lines[first], lines[second] = lines[second], lines[first]
            return "\n".join(lines)

        def swap_subnet_titles(code):
            integration = re.search(r'subgraph subnet_int\["([^"]*)"\]', code).group(1)
            endpoint = re.search(r'subgraph subnet_pe_out\["([^"]*)"\]', code).group(1)
            return code.replace(integration, "@@", 1).replace(endpoint, integration, 1).replace("@@", endpoint, 1)

        mutations = {
            "orientation": (self.replace_in(BASELINE, "flowchart TD", "flowchart LR"), "must start with 'flowchart TD'"),
            "bidirectional arrow": (self.replace_in(BASELINE, "flowchart TD", "flowchart TD\n    a <--> b"), "bidirectional arrow"),
            "reserved claim level": (self.replace_in(BASELINE, "[Configured]", "[Observed]"), "reserved [Observed] claim level"),
            "dns lookup from the zone": (self.replace_in(INGRESS_PE, "flowchart TD", 'flowchart TD\n    dns -.->|"[Configured] x"| ingress'), "edge starts at DNS zone node"),
            "dns inside a container": (self.edit_fixture(INGRESS_PE, dns_into_container), "DNS zone node dns_x drawn inside container vnet_in"),
            "nat node": (self.replace_in(EGRESS, "flowchart TD", 'flowchart TD\n    nat_x["n"]'), "must be a subnet tag, not a node"),
            "layout-only edge": (self.replace_in(INGRESS_PE, "flowchart TD", 'flowchart TD\n    ingress -.->|"layout only"| app_runtime'), "lacks a claim prefix"),
            "missing accessible name": (self.replace_in(BASELINE, "accTitle:", "accTit:"), "missing accTitle:"),
            "unrecognized source line": (self.replace_in(BASELINE, "flowchart TD", "flowchart TD\n    foo bar baz"), "unparsed line"),
            "size in a container title": (self.replace_in(INGRESS_PE, 'subgraph vnet_in["Customer VNet', 'subgraph vnet_in["Customer VNet /27'), "carries a subnet size"),
            "private endpoint outside its subnet": (self.edit_fixture(INGRESS_PE, unwrap_pe_subnet), "private_endpoint must sit inside vnet > subnet"),
            "NICs swapped between the two subnets": (self.edit_fixture(EGRESS, swap_nic_declarations), "vnet_integration must sit in a subnet titled 'Subnet: VNet integration'"),
            "subnet titles swapped": (self.edit_fixture(OVERLAY, swap_subnet_titles), "pe_storage must sit in a subnet titled 'Subnet: private endpoints'"),
            "runtime inside a customer container": (self.edit_fixture(EGRESS, move_runtime_into_subnet), "app_runtime is drawn inside a customer container"),
            "base node label drift": (self.replace_in(EGRESS, 'client(["', 'client(["X '), "base node client has different labels"),
            "control plane edge drift": (self.replace_in(OVERLAY, "[Configured] SCM deploy", "[Configured] SCM deploy 2"), "control_plane edges differ"),
            "fault arrow from the wrong node": (self.replace_in(OVERLAY, 'vnet_integration ==>|"[FAULT / Illustrative] 3."| storage_db', 'app_runtime ==>|"[FAULT / Illustrative] 3."| storage_db'), "starts at app_runtime, not vnet_integration"),
            "fault arrow removed": (drop_line(OVERLAY, '[FAULT / Illustrative] 3."'), "missing the required fault edge vnet_integration -> storage_db"),
            "fault link style removed": (drop_line(OVERLAY, "linkStyle"), "linkStyle indices"),
            "fixture removed": (drop_block(CONTAINER_APPS), f"missing fixture {CONTAINER_APPS}"),
            "metadata mismatch": (self.text.replace("- id: " + FUNCTIONS, "- id: topology-grammar-v1-adapter-xx", 1), "ids differ or repeat"),
            "heading missing": (self.text.replace("\n## 7. Progressive Views\n", "\n## 7. Views\n", 1), "missing heading '## 7. Progressive Views'"),
            "heading out of order": (swap_headings(), "level-two headings are out of order"),
            "empty accessible title": (self.edit_fixture(BASELINE, lambda code: re.sub(r"accTitle:.*", "accTitle:", code, count=1)), "empty accTitle:"),
            "edge to an undeclared node": (self.replace_in(INGRESS_PE, "flowchart TD", 'flowchart TD\n    ingress -.->|"[Configured] x"| ghost_node'), "references undeclared node ghost_node"),
            "NAT named in a node label": (self.replace_in(EGRESS, 'identity{{"Identity: Microsoft Entra ID', 'identity{{"Identity: NAT Entra ID'), "label names NAT/UDR/NSG"),
            "solid DNS lookup": (self.replace_in(INGRESS_PE, 'client -..->|"[Configured] 1. DNS lookup returns PE private IP"| dns', 'client -->|"[Configured] 1. DNS lookup returns PE private IP"| dns'), "DNS lookup arrows must be dotted"),
            "invisible fault link style": (self.replace_in(OVERLAY, "linkStyle 5,9,10 stroke:#da495d,stroke-width:3px", "linkStyle 5,9,10 stroke:#ffffff,stroke-width:0px"), "linkStyle must use a visible stroke color"),
            "learn locale": (self.text.replace("learn.microsoft.com/en-us/", "learn.microsoft.com/", 1), "lacks the /en-us/ locale"),
            "refuted claim": (self.text + "\nPrivate Endpoint traffic bypasses access restriction rules.\n", "contains a refuted claim"),
            "image": (self.text + "\n![x](a.png)\n", "references or embeds an image"),
            "oversized page": (self.text + "\n" * (MAX_LINES + 1), "budget is"),
        }

        # When / Then: each mutation changes the page and raises the diagnostic of the rule it targets.
        for name, (mutated, expected) in mutations.items():
            with self.subTest(defect=name):
                self.assertNotEqual(mutated, self.text, "the mutation did not change the page")
                problems = "\n".join(grammar_problems(mutated))
                self.assertTrue(problems, f"{name} went undetected")
                self.assertIn(expected, problems, f"{name} was not reported by its own rule")

    def test_anchor_labels_and_zone_placement_are_enforced_on_synthetic_fixtures(self):
        # Given: tiny fixtures that isolate rules the full-page mutations cannot target cleanly.
        inside = 'flowchart TD\n    accTitle: t\n    accDescr: d\n    subgraph v["VNet"]\n        dns{{"Zone"}}\n    end\n'
        anchored = 'flowchart TD\n    accTitle: t\n    accDescr: d\n    a["A"]\n    b["B"]\n    a ~~~|"x"| b\n'

        # When: each is checked on its own.
        inside_problems = fixture_problems("f", inside, parse_fixture(inside))
        anchored_problems = fixture_problems("f", anchored, parse_fixture(anchored))

        # Then: the diagnostics name the violated rule.
        self.assertTrue(any("DNS zone node dns drawn inside container v" in p for p in inside_problems), inside_problems)
        self.assertTrue(any("invisible layout anchor" in p for p in anchored_problems), anchored_problems)


if __name__ == "__main__":
    unittest.main()
