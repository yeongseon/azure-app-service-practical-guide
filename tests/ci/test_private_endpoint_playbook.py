"""Small content regressions for the private endpoint / access restriction playbook.

These tests check selected invariants only. They never contact Azure: the
configuration commands are validated as text against a strict read-only
allowlist, not executed, and no test proves any causal claim in the prose.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PE = ROOT / "docs/troubleshooting/playbooks/private-endpoint-access-restrictions.md"
SCM = ROOT / "docs/troubleshooting/playbooks/scm-access-dns-and-http-failures.md"
NETWORKING = ROOT / "docs/operations/networking.md"
SECTIONS = (
    "1. Summary", "2. Common Misreadings", "3. Competing Hypotheses",
    "4. What to Check First", "5. Evidence to Collect",
    "6. Validation and Disproof by Hypothesis", "7. Likely Root Cause Patterns",
    "8. Immediate Mitigations", "9. Prevention", "See Also", "Sources",
)
# The ONLY shell on the page: two read-only reads, compared as exact logical lines.
# Slot variation is described in prose, so the fence itself never needs to change.
APPROVED_COMMANDS = (
    'az resource show --ids "$APP_RESOURCE_ID" --api-version 2024-11-01 --output json',
    'az webapp config access-restriction show --resource-group "$RG" --name "$APP_NAME" --output json',
)
# The retired rule of thumb "a private endpoint never closes default-endpoint access".
NEVER_CLOSES = re.compile(
    r"(?:\*{0,2}not\*{0,2}|n't|never)\s+automatically\s+(?:disabl\w*|block\w*)[^.\n]{0,40}public(?:\s+inbound)?\s+(?:endpoint|access)"
    r"|public(?:\s+inbound)?\s+endpoint\s+(?:is|are)\s+not\s+automatically\s+disabled"
    r"|public\s+endpoint\s+remains\s+reachable\s+until",
    re.IGNORECASE,
)
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)")
ALLOWED_FENCE_LANGUAGES = {"mermaid", "kusto", "bash"}


def fences(text: str) -> list[tuple[str, str]]:
    """Return (language, body) for every fenced block, backtick or tilde, any info string."""
    found: list[tuple[str, str]] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        opening = FENCE_OPEN.match(lines[index])
        if opening:
            marker, language = opening.group(1), opening.group(2).lower()
            body: list[str] = []
            index += 1
            while index < len(lines) and not re.match(rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\s*$", lines[index]):
                body.append(lines[index])
                index += 1
            found.append((language, "\n".join(body)))
        index += 1
    return found


def first_bash_fence(text: str) -> str:
    for language, body in fences(text):
        if language == "bash":
            return body
    raise AssertionError("no bash fence")


#: Line shapes this page's body is allowed to contain outside its fences.
BODY_LINE_SHAPES = (
    ("blank", re.compile(r"^\s*$")),
    ("heading", re.compile(r"^#{1,6} \S")),
    ("table row", re.compile(r"^\|")),
    ("list item", re.compile(r"^(?:[-*] |\d+\. )\S")),
    ("diagram comment", re.compile(r"^<!-- diagram-id: [a-z0-9-]+ -->\s*$")),
    ("paragraph", re.compile(r"^[A-Za-z0-9*`\[(\"'_]")),
)


def hidden_code_blocks(page: str) -> list[str]:
    """Fail closed on any body line that is not one of the allowed plain shapes.

    Python-Markdown renders indented text, fences nested in an admonition, list
    or blockquote, and raw <pre> as copyable code, and new forms keep turning
    up. Rather than enumerate them, accept only the six shapes this body
    actually uses; anything else (blockquote, raw HTML, indentation, an
    admonition, a Setext underline) is reported. Inline code is ordinary
    paragraph text and is untouched. Frontmatter (YAML) is excluded. This is a
    deliberately page-specific restriction, not a general Markdown linter.
    """
    body = page.split("\n---\n", 1)[1] if page.startswith("---\n") else page
    problems: list[str] = []
    marker: str | None = None
    for number, line in enumerate(body.split("\n"), 1):
        if marker is not None:
            if re.match(rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\s*$", line):
                marker = None
            continue
        opening = FENCE_OPEN.match(line)
        if opening:
            marker = opening.group(1)
            if line not in EXACT_FENCE_OPENERS:
                # An info string after the language is expanded by the macros plugin and
                # Markdown extensions, so a body comparison cannot protect what it injects.
                problems.append(f"body line {number}: fence opener must be exactly one of {sorted(EXACT_FENCE_OPENERS)}")
            continue
        runs = re.findall(r"`+", line)
        if any(len(run) != 1 for run in runs) or len(runs) % 2:
            # Only balanced single backticks are accepted, so the code-span stripping below is sound.
            problems.append(f"body line {number}: ambiguous backtick structure")
        elif not any(shape.match(line) for _, shape in BODY_LINE_SHAPES):
            problems.append(f"body line {number}: unexpected line shape {line[:40]!r}")
        elif EXPANSION_SYNTAX.search(line):
            problems.append(f"body line {number}: expansion syntax or escaped backtick")
        elif not line.startswith("<!-- diagram-id") and raw_html_in_text(line):
            # Raw HTML (pre, a display:block code element, ...) can hide inside an otherwise
            # allowed shape such as a paragraph, list item or table cell.
            problems.append(f"body line {number}: raw HTML tag in an allowed line")
    return problems


#: Exact approved bodies of the page's non-shell fences. Anything else, including a
#: fence whose label is right but whose content is not, is rejected: the stack renders
#: every fence as copyable text, and snippet or macro directives expand inside them.
APPROVED_FENCE_BODIES = {
    "mermaid": (
        "flowchart TD",
        "A[Identify client, hostname, app or slot and attempt] --> B{Actual path established?}",
        "B -->|No| C[Collect client DNS, route and connection evidence]",
        "B -->|Yes| D{Private endpoint or default endpoint?}",
        "D -->|Private endpoint| E[Check approval, DNS, route and applicable network policies]",
        "E --> F[Site access restrictions are not evaluated]",
        "D -->|Default endpoint| G{Effective publicNetworkAccess permits this path?}",
        "G -->|No| H[App access denied; an Allow rule cannot override it]",
        "G -->|Yes| I[Evaluate main or SCM rules and unmatched action]",
        "F --> J[Check TLS, identity and application response separately]",
        "I --> J",
    ),
    "kusto": (
        "let TargetResourceId = '<resource-id>';",
        "let TargetHost = '<app-or-scm-hostname>';",
        "let StartUtc = datetime(2026-01-20T09:00:00Z);",
        "let EndUtc = datetime(2026-01-20T10:00:00Z);",
        "AppServiceIPSecAuditLogs",
        "| where _ResourceId =~ TargetResourceId",
        "| where TimeGenerated >= StartUtc and TimeGenerated < EndUtc",
        "| where CsHost =~ TargetHost",
        "| project TimeGenerated, CsHost, CIp, Result, Details, ServiceEndpoint",
        "| order by TimeGenerated asc",
    ),
}

#: Expansion syntaxes of the configured stack (macros plugin delimiters, Jinja, snippets,
#: attr_list braces) and escaped backticks, which defeat inline-code detection. The page
#: uses none of them outside its fences, so any occurrence is reported instead of parsed.
EXACT_FENCE_OPENERS = {"```mermaid", "```bash", "```kusto"}
EXPANSION_SYNTAX = re.compile(r"\[\[|\]\]|%\]|\{|\}|--8<--|\\`")


def fence_body_problems(blocks: list[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    for language in APPROVED_FENCE_BODIES:
        bodies = [body for lang, body in blocks if lang == language]
        if len(bodies) != 1:
            problems.append(f"expected exactly one {language} fence, found {len(bodies)}")
        elif tuple(logical_lines(bodies[0])) != APPROVED_FENCE_BODIES[language]:
            problems.append(f"the {language} fence differs from its approved body")
    return problems


def raw_html_in_text(line: str) -> bool:
    """True when a body line carries an HTML tag outside inline code spans."""
    return bool(re.search(r"<\s*[A-Za-z/!]", re.sub(r"`[^`]*`", "", line)))


def frontmatter_problems(page: str) -> list[str]:
    """The theme renders some frontmatter (the title) as raw HTML, so it is not outside the surface.

    Plain text only: reject raw HTML tags and the stack's expansion syntax anywhere in it.
    """
    lines = page.split("\n")
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return ["page has no closed YAML frontmatter"]
    frontmatter = "\n".join(lines[1:lines.index("---", 1)])
    problems = []
    if re.search(r"<\s*[A-Za-z/!]", frontmatter):
        problems.append("frontmatter contains a raw HTML tag")
    if EXPANSION_SYNTAX.search(frontmatter):
        problems.append("frontmatter contains expansion syntax")
    # YAML decodes escapes only inside double-quoted scalars, and the decoded value (for example
    # a title written as \x3cpre\x3e) reaches the theme as raw HTML after the source checks above.
    # The repository's CI installs no YAML parser, so fail closed instead of decoding.
    if re.search(r'[\\"]', frontmatter):
        problems.append("frontmatter uses a backslash or a double-quoted scalar, which can decode to HTML")
    if re.search(r"(?m)(?:^|[:\s\-\[,])[!&*]\S", frontmatter):
        problems.append("frontmatter uses a YAML tag, anchor or alias")
    return problems


def logical_lines(script: str) -> list[str]:
    """Join backslash continuations and collapse whitespace; drop blank lines."""
    joined = script.replace("\\\n", " ")
    return [" ".join(line.split()) for line in joined.split("\n") if line.strip()]


def unapproved_configuration(page: str) -> list[str]:
    """Explain every way the page's shell differs from the two approved commands.

    Deliberately not a shell parser: any extra fence, line, operator, redirect,
    positional argument or missing flag changes a logical line and is reported.
    """
    front = frontmatter_problems(page)
    if front:
        return front
    hidden = hidden_code_blocks(page)
    if hidden:
        return hidden
    blocks = fences(page)
    other = sorted({language for language, _ in blocks} - ALLOWED_FENCE_LANGUAGES)
    if other:
        return [f"unexpected fenced code languages: {other}"]
    content = fence_body_problems(blocks)
    if content:
        return content
    shell = [body for language, body in blocks if language == "bash"]
    if len(shell) != 1:
        return [f"expected exactly one bash fence, found {len(shell)}"]
    actual = tuple(logical_lines(shell[0]))
    if actual == APPROVED_COMMANDS:
        return []
    return [f"unapproved shell line: {line!r}" for line in actual if line not in APPROVED_COMMANDS] or [
        f"approved commands missing or reordered: {actual!r}"
    ]


class PrivateEndpointPlaybookTests(unittest.TestCase):
    def test_numbered_sections_in_order(self) -> None:
        self.assertEqual(re.findall(r"^## (.+)$", PE.read_text(), re.MULTILINE), list(SECTIONS))

    def test_execution_and_causality_boundaries_present(self) -> None:
        text = PE.read_text()
        for token in ("NOT_RUN", "NOT_TESTED", "INCONCLUSIVE", "NOT_MET"):
            self.assertIn(token, text)
        self.assertNotIn("last_tested:", text)
        self.assertNotIn("captured_at:", text)

    def test_page_is_reachable_from_navigation_and_playbook_index(self) -> None:
        nav = (ROOT / "mkdocs.yml").read_text()
        index = (ROOT / "docs/troubleshooting/playbooks/index.md").read_text()
        self.assertIn("troubleshooting/playbooks/" + PE.name, nav)
        self.assertIn(f"]({PE.name})", index)

    def test_fences_balanced_and_one_diagram_with_matching_id(self) -> None:
        text = PE.read_text()
        self.assertEqual(len(re.findall(r"^```", text, re.MULTILINE)) % 2, 0)
        ids = re.findall(r"<!-- diagram-id: ([a-z0-9-]+) -->", text)
        self.assertEqual(len(ids), 1)
        self.assertIn(f"- id: {ids[0]}", text)
        self.assertIn("```mermaid\nflowchart TD\n", text)

    def test_policy_matrix_keeps_distinct_boundaries(self) -> None:
        rows: dict[tuple[str, str, str], str] = {}
        for line in PE.read_text().splitlines():
            cells = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] in {"Private endpoint", "Default endpoint"}:
                key = (cells[0], cells[1], cells[2])
                self.assertNotIn(key, rows, f"duplicate matrix row {key}")
                rows[key] = cells[3]
        expected = {
            ("Private endpoint", "Any publicNetworkAccess value", "Any main/SCM site rules"): "not evaluated for this traffic",
            ("Default endpoint", "Disabled", "Even a matching Allow"): "BLOCKED at app access",
            ("Default endpoint", "Enabled", "No match; default unset; zero configured rules"): "Implicit ALLOW",
            ("Default endpoint", "Enabled", "No match; default unset; one or more configured rules"): "Implicit DENY",
            ("Default endpoint", "null; no PE exists", "Evaluate applicable site rules"): "default ENABLED",
            ("Default endpoint", "null; PE exists", "Any site rule"): "default DISABLED",
        }
        for key, token in expected.items():
            with self.subTest(row=key):
                self.assertIn(key, rows)
                self.assertIn(token, rows[key])
        self.assertIn("does not guarantee HTTP 200", PE.read_text())

    def test_main_and_scm_controls_are_assessed_separately(self) -> None:
        text = PE.read_text()
        for posture in ("Public-only, main", "Public-only, SCM", "Private-only, main", "Private-only, SCM"):
            self.assertIn(f"| {posture} |", text)
        self.assertIn("Mixed: private deployment, SCM", text)

    def test_missing_property_is_never_projected_into_a_null(self) -> None:
        text = PE.read_text()
        self.assertIn("An absent property is UNKNOWN, not a verified JSON null", text)
        # A --query projection can fabricate a null for a field that was never returned.
        self.assertNotIn("--query", first_bash_fence(text))

    def test_audit_keeps_scope_and_missing_evidence_limits(self) -> None:
        text = PE.read_text()
        for token in (
            "AppServiceIPSecAuditLogs", "_ResourceId =~ TargetResourceId",
            "CsHost =~ TargetHost", "TimeGenerated >= StartUtc and TimeGenerated < EndUtc",
            "project TimeGenerated, CsHost, CIp, Result, Details, ServiceEndpoint",
            "excluding the unmatched rule", "No rows is not proof of no denial",
            "privateEndpointNetworkPolicies", "scmIpSecurityRestrictionsUseMain",
        ):
            self.assertIn(token, text)
        self.assertNotIn("ScSubStatus", text)

    def test_configuration_shell_is_exactly_the_two_approved_read_only_commands(self) -> None:
        self.assertEqual(unapproved_configuration(PE.read_text()), [])

    def test_exact_form_check_rejects_every_known_bypass(self) -> None:
        # Given: the real page and its single fence body.
        page = PE.read_text()
        body = first_bash_fence(page)
        mutations = {
            "semicolon append": body + "; az webapp stop",
            "single newline append": body + "\naz webapp stop",
            "blank-line append": body + "\n\naz webapp stop --name x",
            "adjacent and-and": body + "&&az webapp stop",
            "attached redirect": body.replace("--output json", "--output json>out.txt", 1),
            "pipe": body + " | tee out.txt",
            "command substitution": body.replace("$RG", "$(az account show)", 1),
            "extra positional": body.replace("az resource show", "az resource show extra", 1),
            "missing api-version": body.replace("  --api-version 2024-11-01 \\\n", "", 1),
            "changed verb": body.replace("resource show", "resource delete", 1),
            "dropped command": body.split("\n\n")[0],
        }

        for name, mutated in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutated, body)
                # When / Then: the exact-form check reports a difference.
                self.assertTrue(unapproved_configuration(page.replace(body, mutated, 1)), name)

        # And: code forms the fence parser cannot see are rejected (fail closed).
        for name, extra in {
            "admonition-nested fence": '\n!!! warning "Extra"\n\n    ```bash\n    az webapp stop\n    ```\n',
            "list-nested fence": "\n1. Step\n\n    ```bash\n    az webapp stop\n    ```\n",
            "indented code block": "\n\n    az webapp stop\n",
            "tab-indented code block": "\n\n\taz webapp stop\n",
            "raw pre block": "\n<pre><code>az webapp stop</code></pre>\n",
            "blockquote fence": "\n> ```bash\n> az webapp stop\n> ```\n",
            "blockquote tilde fence": "\n> ~~~bash\n> az webapp stop\n> ~~~\n",
            "blockquote indented code": "\n>     az webapp stop\n",
            "nested blockquote fence": "\n>> ```bash\n>> az webapp stop\n>> ```\n",
            "raw script": "\n<script>alert(1)</script>\n",
            "pre inside a table cell": "\n| a | <pre>az webapp stop</pre> |\n",
            "kusto-labelled shell": "\n```kusto\naz webapp stop --resource-group demo --name demo\n```\n",
            "unequal backtick runs hiding pre": "\nExample: ``x`<pre>az webapp stop --name demo</pre>`\n",
            "double-backtick span": "\nExample: ``az webapp stop``\n",
            "odd backtick count": "\nExample: `az webapp stop\n",
            "second kusto fence": "\n```kusto\nlet x = 1;\n```\n",
            "kusto curl after a let": "\n```kusto\nlet x = 1; curl -X DELETE https://example.com\n```\n",
            "mermaid bare rm": "\n```mermaid\nrm -rf /tmp/demo\n```\n",
            "macro fence expression": '\n[[[ "\\n```sh\\nrm -rf /tmp/demo\\n```\\n" ]]]\n',
            "jinja statement": "\n{% include 'x' %}\n",
            "snippet outside a fence": '\n--8<-- "labs/snat-exhaustion/cleanup.sh"\n',
            "attr_list display:block": '\n- `az webapp stop --name demo`{: style="display:block;white-space:pre"}\n',
            "attr_list in a table cell": '\n| a | `az webapp stop`{: style="display:block" } |\n',
            "escaped backticks around html": "\nExample: \\`<pre><code>az webapp stop --name demo</code></pre>\\`\n",
            "kusto-labelled shell after a query line": "\n```kusto\nlet X = 1;\naz webapp delete --name demo\n```\n",
            "mermaid-labelled shell": "\n```mermaid\nflowchart TD\naz webapp stop --name demo\n```\n",
            "display:block code in a paragraph": '\nExample: <code style="display:block;white-space:pre">az webapp stop --name demo<br>az webapp delete --name demo</code>\n',
            "span in a list item": "\n- step <span style=\"display:block\">az webapp stop</span>\n",
            "div in a table cell": "\n| a | <div>az webapp stop</div> |\n",
            "pre inside a list item": "\n- step <pre>az webapp stop</pre>\n",
            "admonition": '\n!!! note "x"\n    text\n',
        }.items():
            with self.subTest(hidden=name):
                self.assertTrue(unapproved_configuration(page + extra), name)

        # Opener lines and frontmatter are part of the rendered surface (macros expand in
        # an opener's info string; the theme renders the title as raw HTML).
        bash_opener = page.replace("```bash\n", '```bash [[[ "\\naz webapp stop --name demo\\n" ]]]\n', 1)
        for name, mutated in {
            "macro in the bash opener": bash_opener,
            "info string on the mermaid opener": page.replace("```mermaid\n", "```mermaid title=x\n", 1),
            "trailing-space opener": page.replace("```bash\n", "```bash \n", 1),
            "html in the frontmatter title": page.replace("title: Private Endpoint and Access Restriction Decisions", "title: '<pre><code>az webapp stop --name demo</code></pre>'", 1),
            "macro in the frontmatter": page.replace("slug: private-endpoint-access-restrictions", 'slug: [[[ "x" ]]]', 1),
            "yaml hex escapes decoding to html": page.replace("title: Private Endpoint and Access Restriction Decisions", 'title: "\\x3c/title\\x3e\\x3cpre\\x3e\\x3ccode\\x3eaz webapp stop --name demo\\naz webapp delete --name demo\\x3c/code\\x3e\\x3c/pre\\x3e"', 1),
            "yaml unicode escape": page.replace("title: Private Endpoint and Access Restriction Decisions", 'title: "\\u003cpre\\u003eaz webapp stop\\u003c/pre\\u003e"', 1),
            "double-quoted title": page.replace("title: Private Endpoint and Access Restriction Decisions", 'title: "Private Endpoint"', 1),
            "yaml tag": page.replace("slug: private-endpoint-access-restrictions", "slug: !!str x", 1),
            "yaml anchor": page.replace("slug: private-endpoint-access-restrictions", "slug: &a x", 1),
        }.items():
            with self.subTest(surface=name):
                self.assertNotEqual(mutated, page, name)
                self.assertTrue(unapproved_configuration(mutated), name)

        # Inline code is legitimate and must not trip the guard.
        self.assertEqual(unapproved_configuration(page + "\nUse `az webapp stop` only as a quoted example.\n"), [])

        # And: an extra fence in ANY syntax Python-Markdown renders as code is rejected.
        for name, extra in {
            "second bash fence": "\n```bash\naz webapp stop\n```\n",
            "trailing-space info string": "\n```bash \naz webapp stop\n```\n",
            "tilde fence": "\n~~~bash\naz webapp stop\n~~~\n",
            "sh fence": "\n```sh\naz webapp stop\n```\n",
            "untagged fence": "\n```\naz webapp stop\n```\n",
            "longer backtick fence": "\n````bash\naz webapp stop\n````\n",
        }.items():
            with self.subTest(extra_fence=name):
                self.assertTrue(unapproved_configuration(page + extra), name)
        self.assertTrue(unapproved_configuration(page.replace(body, "", 1).replace("```bash\n\n```", "")))

    @unittest.skipUnless(shutil.which("bash"), "bash required for syntax checks")
    def test_configuration_script_parses(self) -> None:
        subprocess.run(["bash", "-n"], input=first_bash_fence(PE.read_text()), text=True, check=True, capture_output=True)

    def test_pages_link_in_both_directions(self) -> None:
        self.assertIn(f"]({SCM.name})", PE.read_text())
        self.assertIn(f"]({PE.name})", SCM.read_text())

    def test_no_page_says_a_private_endpoint_never_closes_default_access(self) -> None:
        # Given: the sentences that previously shipped on three pages.
        for old in (
            "Creating a Private Endpoint does not automatically block the public endpoint.",
            "The public inbound endpoint is not automatically disabled.",
            "Adding a private endpoint does not automatically disable the public endpoint;",
            "Creating a Private Endpoint assigns a private IP but does **not** automatically disable the public endpoint.",
            "!!! warning \"Private Endpoint does not automatically block public access\"",
            "After creating a Private Endpoint, the public endpoint remains reachable until you disable public network access",
        ):
            self.assertTrue(NEVER_CLOSES.search(old), old)

        # When: every page under docs/ is scanned.
        offenders = [
            f"{path.relative_to(ROOT)}:{number}"
            for path in sorted((ROOT / "docs").rglob("*.md"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if NEVER_CLOSES.search(line)
        ]

        # Then: none remains; raw publicNetworkAccess plus PE existence decides.
        self.assertEqual(offenders, [])

    def test_networking_page_no_longer_treats_configuration_as_reachability(self) -> None:
        text = NETWORKING.read_text()
        self.assertNotIn("proves the app is reachable from the entire internet", text)
        self.assertNotIn("HTTP response is `200` from the in-network client", text)
        self.assertIn("../troubleshooting/playbooks/private-endpoint-access-restrictions.md", text)


if __name__ == "__main__":
    unittest.main()
