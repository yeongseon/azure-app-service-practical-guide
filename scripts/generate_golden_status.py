#!/usr/bin/env python3
"""Generate the Golden Status dashboard: one scorecard for every quality gate.

This repository enforces its contract through two dozen independent checks
spread across five GitHub Actions workflows -- documentation validators,
reference-application builds, and infrastructure template builds. Each one
reports in isolation, so no single place answers "is this repository currently
golden?". This generator runs every gate, records the outcome, and renders
:data:`OUTPUT_REL` as a single canonical scorecard.

Three regions of the rendered page are deliberately distinguished:

* **Gate results** -- depend on repository content, and on which toolchains the
  machine running the generator happens to have. Fenced by ``results`` markers.
* **Gate inventory** -- fully deterministic, derived from :data:`GATES`. Fenced
  by ``inventory`` markers.
* **Provenance** -- the source revision and generation date, outside both
  fences because they change on every run by design.

``--check`` is the CI contract. It verifies three things, none of which any
other job checks:

1. **Registry completeness** -- every validator script in the repository is
   either registered in :data:`GATES` or excluded in :data:`NON_GATE_SCRIPTS`
   with a written reason.
2. **Inventory freshness** -- the committed inventory table matches the
   registry.
3. **Status freshness** -- for gates marked :attr:`Gate.verified_in_ci`, the
   committed pass/fail status matches a fresh run. Only gate *status* is
   compared, not the detail counts, so adding a documentation page does not
   force a regeneration while a gate flipping red still fails the build.

Usage:
    python3 scripts/generate_golden_status.py
    python3 scripts/generate_golden_status.py --include-network
    python3 scripts/generate_golden_status.py --strict
    python3 scripts/generate_golden_status.py --gate KEY
    python3 scripts/generate_golden_status.py --check
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lib.yaml_style import dump_frontmatter

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_REL = "docs/meta/golden-status.md"
DIAGRAM_ID = "golden-status-gate-outcomes-pie"

INVENTORY_MARKER = "golden-status:inventory"
RESULTS_MARKER = "golden-status:results"

BLOCKING = "blocking"
ADVISORY = "advisory"
UNWIRED = "unwired"

SEVERITY_LABEL = {
    BLOCKING: "Blocking",
    ADVISORY: "Advisory",
    UNWIRED: "Not in CI",
}

PASS = "✅ Pass"
FAIL = "❌ Fail"
WARN = "⚠️ Warn"
SKIPPED = "➖ Skipped"

CONTENT_SOURCES_WORKFLOW = ".github/workflows/validate-content-sources.yml"
REPETITION_WORKFLOW = ".github/workflows/validate-repetition.yml"
VISUAL_WORKFLOW = ".github/workflows/validate-visual-content.yml"
GOLDEN_STATUS_WORKFLOW = ".github/workflows/validate-golden-status.yml"
APP_INFRA_WORKFLOW = ".github/workflows/app-infra-ci.yml"


@dataclass(frozen=True)
class Binding:
    """One workflow job that enforces a gate.

    A gate can have several: the doctest batch below is split across six jobs
    in CI, and collapsing that to a single job name would misstate which job
    actually fails when a doctest breaks.
    """

    job: str
    workflow: str


# Scripts whose doctests CI executes, and the job that executes each one. Kept
# as pairs so the inventory can state the real bindings instead of attributing
# the whole batch to one job.
DOCTEST_BINDINGS: tuple[tuple[str, Binding], ...] = (
    (
        "scripts/lib/content_scope.py",
        Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),
    ),
    (
        "scripts/validate_content_sources.py",
        Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),
    ),
    (
        "scripts/validate_cli_explanations.py",
        Binding("Validate CLI Explanation Tables", CONTENT_SOURCES_WORKFLOW),
    ),
    ("scripts/validate_pii.py", Binding("Validate PII", CONTENT_SOURCES_WORKFLOW)),
    (
        "scripts/detect_repetition.py",
        Binding("Validate Documentation Repetition", REPETITION_WORKFLOW),
    ),
    (
        "scripts/validate_doc_quality.py",
        Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),
    ),
    (
        "scripts/validate_visual_content.py",
        Binding("Validate Visual Content (advisory)", VISUAL_WORKFLOW),
    ),
    (
        "scripts/generate_golden_status.py",
        Binding("Validate Golden Status", GOLDEN_STATUS_WORKFLOW),
    ),
)
DOCTEST_TARGETS = tuple(target for target, _ in DOCTEST_BINDINGS)

# Mirrors the "Audit existing diagram IDs" workflow step: every Mermaid fence
# must be preceded by a diagram-id comment, so the two counts must match.
DIAGRAM_ID_PARITY_SHELL = """
set -u
blocks=$(grep -r '```mermaid' docs/ --include='*.md' | wc -l)
ids=$(grep -r '<!-- diagram-id:' docs/ --include='*.md' | wc -l)
echo "mermaid blocks: $blocks"
echo "diagram-id comments: $ids"
test "$blocks" -eq "$ids"
"""

SHELL_SYNTAX_SHELL = (
    "find apps labs scripts -type f -name '*.sh' -print0 | xargs -0 -r bash -n"
)
SHELLCHECK_SHELL = (
    "find apps labs scripts -type f -name '*.sh' -print0 | xargs -0 -r shellcheck"
)
NODE_AUDIT_SHELL = (
    "cd apps/nodejs && npm audit --package-lock-only --omit=dev --audit-level=moderate"
)
NODE_TEST_SHELL = "cd apps/nodejs && npm test"
NODE_PROD_INSTALL_SHELL = "cd apps/nodejs && npm ci --omit=dev --dry-run"

BICEP_BUILD_SHELL = """
set -eu
count=0
while IFS= read -r file; do
  # </dev/null stops `az` from consuming the file list on stdin. Without it the
  # loop silently stops after the first template.
  az bicep build --file "${file}" --stdout >/dev/null </dev/null
  count=$((count + 1))
done < <(find apps labs -type f -name '*.bicep' -print | sort)
echo "Bicep templates built: ${count}"
"""


@dataclass(frozen=True)
class Gate:
    """One runnable quality gate plus the metadata rendered into the inventory.

    ``argv`` is what this generator executes; ``display`` is what a human runs.
    They differ only where the generator needs a throwaway artifact directory,
    so ``display`` defaults to ``argv``.
    """

    key: str
    name: str
    enforces: str
    argv: tuple[str, ...]
    severity: str
    covers: tuple[str, ...] = ()
    bindings: tuple[Binding, ...] = ()
    note: str = ""
    summary_keys: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    network: bool = False
    superset: bool = False
    verified_in_ci: bool = False
    display: str = ""
    quiet_detail: str = "Exit code 0, no output."

    @property
    def command(self) -> str:
        """Human-runnable form of this gate's command.

        >>> Gate("k", "N", "e", ("{python}", "scripts/x.py"), BLOCKING).command
        'python3 scripts/x.py'
        >>> Gate("k", "N", "e", ("bash",), BLOCKING, display="make lint").command
        'make lint'
        """
        return self.display or " ".join(self.argv).replace("{python}", "python3")


GATES: tuple[Gate, ...] = (
    Gate(
        key="doctests",
        name="Validator doctests",
        enforces="Executable specs inside the validators themselves still pass.",
        argv=("{python}", "-m", "doctest", *DOCTEST_TARGETS),
        severity=BLOCKING,
        bindings=tuple(dict.fromkeys(binding for _, binding in DOCTEST_BINDINGS)),
        note="CI runs these doctests one module per job; the dashboard runs them as one batch.",
        display="python3 -m doctest " + " ".join(DOCTEST_TARGETS),
        quiet_detail=f"{len(DOCTEST_TARGETS)} modules checked, every doctest passed.",
        verified_in_ci=True,
    ),
    Gate(
        key="mermaid-format",
        name="Mermaid format",
        enforces="Mermaid fences are unindented and correctly delimited.",
        argv=("{python}", "scripts/validate_mermaid_format.py"),
        severity=BLOCKING,
        covers=("scripts/validate_mermaid_format.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("Files checked:", "Files with errors:"),
        verified_in_ci=True,
    ),
    Gate(
        key="mermaid-syntax",
        name="Mermaid syntax",
        enforces="Every diagram parses as valid Mermaid.",
        argv=("{python}", "scripts/validate_mermaid_syntax.py"),
        severity=BLOCKING,
        covers=("scripts/validate_mermaid_syntax.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("Diagrams checked:", "Errors found:"),
        verified_in_ci=True,
    ),
    Gate(
        key="content-sources",
        name="Content sources",
        enforces="Pages with Mermaid carry content_sources metadata with a valid source type.",
        argv=("{python}", "scripts/validate_content_sources.py"),
        severity=BLOCKING,
        covers=("scripts/validate_content_sources.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("Files with mermaid:", "Validation errors:"),
        verified_in_ci=True,
    ),
    Gate(
        key="content-sources-schema",
        name="Content sources schema",
        enforces="content_sources blocks use the canonical mapping shape, not the legacy list form.",
        argv=("{python}", "scripts/normalize_content_sources_schema.py", "--check"),
        severity=BLOCKING,
        covers=("scripts/normalize_content_sources_schema.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("Files with content_sources schema drift:", "Parse errors:"),
        verified_in_ci=True,
    ),
    Gate(
        key="diagram-id-parity",
        name="Diagram ID parity",
        enforces="Mermaid fence count equals diagram-id comment count across docs/.",
        argv=("bash", "-c", DIAGRAM_ID_PARITY_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("mermaid blocks:", "diagram-id comments:"),
        note=(
            "An inline shell step with no standalone script, so the dashboard re-runs the "
            "same comparison through its own --gate entry point."
        ),
        display="python3 scripts/generate_golden_status.py --gate diagram-id-parity",
        verified_in_ci=True,
    ),
    Gate(
        key="cli-explanations",
        name="CLI explanation tables",
        enforces="Every az CLI fence has an explanation table, and Markdown tables in docs/ and repository-root contracts end with a blank line.",
        argv=("{python}", "scripts/validate_cli_explanations.py"),
        severity=BLOCKING,
        covers=("scripts/validate_cli_explanations.py",),
        bindings=(Binding("Validate CLI Explanation Tables", CONTENT_SOURCES_WORKFLOW),),
        verified_in_ci=True,
    ),
    Gate(
        key="doc-quality",
        name="Document quality",
        enforces="Canonical section templates, tail sections, long CLI flags, and masked identifiers.",
        argv=("{python}", "scripts/validate_doc_quality.py", "--all"),
        severity=BLOCKING,
        covers=("scripts/validate_doc_quality.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        note=(
            "CI blocks on changed files only. The dashboard runs --all, so findings here may "
            "include historical debt and cannot be mapped onto the changed-only CI scope."
        ),
        superset=True,
        verified_in_ci=True,
    ),
    Gate(
        key="yaml-frontmatter",
        name="Frontmatter YAML style",
        enforces="Frontmatter matches the canonical ruamel.yaml serialization.",
        argv=("{python}", "scripts/normalize_yaml_frontmatter.py", "--check"),
        severity=BLOCKING,
        covers=("scripts/normalize_yaml_frontmatter.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("Files with style drift:", "Parse errors:"),
        verified_in_ci=True,
    ),
    Gate(
        key="mslearn-locale",
        name="Microsoft Learn locale",
        enforces="Every learn.microsoft.com URL carries the en-us locale prefix.",
        argv=("{python}", "scripts/normalize_mslearn_locale.py", "--check"),
        severity=BLOCKING,
        covers=("scripts/normalize_mslearn_locale.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        summary_keys=("Files with locale drift:",),
        verified_in_ci=True,
    ),
    Gate(
        key="mslearn-urls",
        name="Microsoft Learn URL reachability",
        enforces="Cited Microsoft Learn URLs still resolve and have not been redirected away.",
        argv=("{python}", "scripts/validate_mslearn_urls.py"),
        severity=ADVISORY,
        covers=("scripts/validate_mslearn_urls.py",),
        bindings=(Binding("Validate MSLearn URLs", CONTENT_SOURCES_WORKFLOW),),
        note="Network gate. CI runs it on push to main with continue-on-error to avoid rate limits.",
        network=True,
    ),
    Gate(
        key="lab-pii",
        name="Lab artifact PII",
        enforces="Lab scripts and templates carry no real UUIDs, emails, hostnames, or public IPs.",
        argv=("{python}", "scripts/scan_lab_pii.py"),
        severity=BLOCKING,
        covers=("scripts/scan_lab_pii.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        verified_in_ci=True,
    ),
    Gate(
        key="pii",
        name="Documentation PII",
        enforces="No leaked subscription, tenant, or object IDs and no real email addresses in docs/.",
        argv=("{python}", "scripts/validate_pii.py"),
        severity=BLOCKING,
        covers=("scripts/validate_pii.py",),
        bindings=(Binding("Validate PII", CONTENT_SOURCES_WORKFLOW),),
        note=(
            "CI blocks on changed Markdown only. The dashboard scans the full documentation "
            "tree, so findings here may include historical debt that CI does not fail on."
        ),
        superset=True,
        verified_in_ci=True,
    ),
    Gate(
        key="repetition",
        name="Documentation repetition",
        enforces="No known scaffold marker is repeated within a single page.",
        argv=("{python}", "scripts/detect_repetition.py", "docs"),
        severity=BLOCKING,
        covers=("scripts/detect_repetition.py",),
        bindings=(Binding("Validate Documentation Repetition", REPETITION_WORKFLOW),),
        note="Marker hits are errors; other repeated prose is reported as a non-blocking warning.",
        verified_in_ci=True,
    ),
    Gate(
        key="visual-content",
        name="Visual content coverage",
        enforces="Factual-claim pages carry at least one diagram, screenshot, or image.",
        argv=("{python}", "scripts/validate_visual_content.py", "--all"),
        severity=ADVISORY,
        covers=("scripts/validate_visual_content.py",),
        bindings=(Binding("Validate Visual Content (advisory)", VISUAL_WORKFLOW),),
        note="Advisory by design; it always exits 0 and reports coverage as a tracked metric.",
        verified_in_ci=True,
    ),
    Gate(
        key="frontmatter",
        name="Frontmatter schema",
        enforces="Valid doc_type and section values, unique slugs, resolvable relationships, content_validation placement.",
        argv=("{python}", "tools/validate_frontmatter.py"),
        severity=BLOCKING,
        covers=("tools/validate_frontmatter.py",),
        bindings=(Binding("Validate Content Source Metadata", CONTENT_SOURCES_WORKFLOW),),
        note="Unresolved relationship slugs are warnings, so only hard schema errors fail the job.",
        summary_keys=("Checked ", "Found "),
        verified_in_ci=True,
    ),
    Gate(
        key="mkdocs-strict",
        name="MkDocs strict build",
        enforces="The site builds with no broken internal links and no navigation warnings.",
        argv=("{python}", "-m", "mkdocs", "build", "--strict", "--site-dir", "{tmpsite}"),
        severity=BLOCKING,
        bindings=(Binding("Build Documentation", CONTENT_SOURCES_WORKFLOW),),
        note=(
            "Builds into a temporary directory so a local `mkdocs serve` is left alone. Needs the "
            "full docs toolchain, so the Validate Golden Status job does not re-verify it."
        ),
        requires=("py:mkdocs",),
        summary_keys=("WARNING", "ERROR", "Aborted with"),
        quiet_detail="Site built with no strict-mode warnings.",
        display="mkdocs build --strict",
    ),
    Gate(
        key="shell-syntax",
        name="Shell script syntax",
        enforces="Every tracked .sh file under apps/, labs/, and scripts/ parses.",
        argv=("bash", "-c", SHELL_SYNTAX_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Shell Scripts", APP_INFRA_WORKFLOW),),
        quiet_detail="All shell scripts parse.",
        display=f'bash -c "{SHELL_SYNTAX_SHELL}"',
    ),
    Gate(
        key="shellcheck",
        name="ShellCheck",
        enforces="Shell scripts pass ShellCheck static analysis.",
        argv=("bash", "-c", SHELLCHECK_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Shell Scripts", APP_INFRA_WORKFLOW),),
        requires=("exe:shellcheck",),
        quiet_detail="ShellCheck reported no findings.",
        display=f'bash -c "{SHELLCHECK_SHELL}"',
    ),
    Gate(
        key="nodejs-audit",
        name="Node.js dependency audit",
        enforces="The Express reference app has no moderate-or-worse production advisories.",
        argv=("bash", "-c", NODE_AUDIT_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Node.js App", APP_INFRA_WORKFLOW),),
        note=(
            "--package-lock-only audits the lockfile, so the result cannot be skewed by a "
            "stale node_modules. CI audits the tree it just installed, which is equivalent."
        ),
        requires=("exe:npm", "path:apps/nodejs/package-lock.json"),
        summary_keys=("severity vulnerabilit", "found 0 vulnerabilities", "npm error"),
        quiet_detail="Audit produced no recognizable summary line.",
        display=NODE_AUDIT_SHELL,
    ),
    Gate(
        key="nodejs-tests",
        name="Node.js app tests",
        enforces="The Express reference app test suite passes.",
        argv=("bash", "-c", NODE_TEST_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Node.js App", APP_INFRA_WORKFLOW),),
        note="Needs `npm ci` in apps/nodejs first; the dashboard never installs dependencies.",
        requires=("exe:npm", "path:apps/nodejs/node_modules"),
        display=NODE_TEST_SHELL,
        summary_keys=("tests ", "pass ", "fail "),
    ),
    Gate(
        key="nodejs-prod-install",
        name="Node.js production install",
        enforces="The Express reference app's production dependency tree resolves from its lockfile.",
        argv=("bash", "-c", NODE_PROD_INSTALL_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Node.js App", APP_INFRA_WORKFLOW),),
        note="Dry run, so it resolves from the lockfile without writing node_modules.",
        requires=("exe:npm", "path:apps/nodejs/package-lock.json"),
        display=NODE_PROD_INSTALL_SHELL,
        summary_keys=("npm error",),
        quiet_detail="Production tree resolved from the lockfile.",
    ),
    Gate(
        key="python-app-compile",
        name="Python app compile",
        enforces="The Flask reference app and its tests compile.",
        argv=(
            "{python}",
            "-m",
            "compileall",
            "-q",
            "apps/python-flask/src",
            "apps/python-flask/tests",
        ),
        severity=BLOCKING,
        bindings=(Binding("Python Flask App", APP_INFRA_WORKFLOW),),
        quiet_detail="All modules compiled.",
        verified_in_ci=True,
    ),
    Gate(
        key="python-app-tests",
        name="Python app tests",
        enforces="The Flask reference app pytest suite passes.",
        argv=("{python}", "-m", "pytest", "apps/python-flask/tests"),
        severity=BLOCKING,
        bindings=(Binding("Python Flask App", APP_INFRA_WORKFLOW),),
        note="Needs apps/python-flask/requirements-dev.txt installed into the running interpreter.",
        requires=("py:pytest", "py:flask"),
        summary_keys=("collected ", "failed", "error"),
    ),
    Gate(
        key="dotnet-build",
        name=".NET app build",
        enforces="The ASP.NET Core reference project builds.",
        argv=("dotnet", "build", "apps/dotnet-aspnetcore/GuideApi/GuideApi.csproj"),
        severity=BLOCKING,
        bindings=(Binding("ASP.NET Core App", APP_INFRA_WORKFLOW),),
        requires=("exe:dotnet",),
    ),
    Gate(
        key="java-tests",
        name="Java app tests",
        enforces="The Spring Boot reference app Maven test phase passes.",
        argv=("mvn", "-q", "-f", "apps/java-springboot/pom.xml", "test"),
        severity=BLOCKING,
        bindings=(Binding("Java Spring Boot App", APP_INFRA_WORKFLOW),),
        requires=("exe:mvn",),
        quiet_detail="Maven test phase completed.",
    ),
    Gate(
        key="bicep-build",
        name="Bicep template build",
        enforces="Every .bicep file under apps/ and labs/ compiles to ARM JSON.",
        argv=("bash", "-c", BICEP_BUILD_SHELL),
        severity=BLOCKING,
        bindings=(Binding("Bicep Templates", APP_INFRA_WORKFLOW),),
        requires=("exe:az",),
        note=(
            "Both this gate and the workflow step redirect stdin per template; without that, "
            "`az` consumes the file list and the loop stops after the first file."
        ),
        summary_keys=("Bicep templates built:",),
        display="az bicep build over every .bicep file under apps/ and labs/",
    ),
)

# Scripts under scripts/ and tools/ that match the validator naming patterns but
# are deliberately not gates. Every entry needs a reason so the exclusion list
# stays reviewable rather than becoming a dumping ground.
NON_GATE_SCRIPTS: dict[str, str] = {
    "scripts/generate_golden_status.py": "This generator.",
    "scripts/generate_content_validation_status.py": "Dashboard generator, not a validator.",
    "scripts/generate_validation_status.py": "Dashboard generator, not a validator.",
    "scripts/remove_out_of_scope_validation.py": "One-shot remediation fixer.",
    "scripts/remove_tautological_validation.py": "One-shot remediation fixer.",
    "tools/build_doc_graph.py": "Knowledge-graph generator, not a validator.",
}

SCRIPT_ROOTS = ("scripts", "tools")
SCRIPT_PREFIXES = ("validate_", "detect_", "normalize_", "scan_", "generate_", "remove_")
SCRIPT_EXTRA_CANDIDATES = ("tools/build_doc_graph.py",)
SCRIPT_SKIP_PARTS = ("__pycache__", "node_modules", ".venv")

_GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(r"(?<![:.\w])(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}(?![:.\w])")
_AZURE_HOST_RE = re.compile(
    r"\b[A-Za-z0-9-]+\.(?:scm\.)?(?:azurewebsites\.net|onmicrosoft\.com|"
    r"blob\.core\.windows\.net|vault\.azure\.net)\b"
)
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}\b")


def scrub(text: str) -> str:
    """Redact identifier-shaped tokens before gate output is echoed onto the page.

    A validator that prints an offending value would otherwise publish the very
    thing it flagged, so everything reaching the rendered page passes through
    here. This reduces that risk substantially but is **not** a complete PII
    scanner -- it only knows the shapes below. A gate whose output could contain
    anything else should define ``summary_keys`` so that only known summary
    lines are ever published.

    >>> scrub("found 11111111-2222-3333-4444-555555555555 in file")
    'found REDACTED-GUID in file'
    >>> scrub("Private IP address: 10.20.2.4")
    'Private IP address: REDACTED-IP'
    >>> scrub("contact someone@microsoft.com now")
    'contact REDACTED-EMAIL now'
    >>> scrub("host myapp.azurewebsites.net down")
    'host REDACTED-HOST down'
    >>> scrub("Files checked: 231")
    'Files checked: 231'
    """
    text = _GUID_RE.sub("REDACTED-GUID", text)
    text = _EMAIL_RE.sub("REDACTED-EMAIL", text)
    text = _AZURE_HOST_RE.sub("REDACTED-HOST", text)
    text = _IPV4_RE.sub("REDACTED-IP", text)
    text = _IPV6_RE.sub("REDACTED-IP", text)
    return _LONG_TOKEN_RE.sub("REDACTED-TOKEN", text)


def summarize(output: str, summary_keys: tuple[str, ...] = (), limit: int = 180) -> str:
    """Condense gate output into one scrubbed, table-safe cell.

    With ``summary_keys`` the last line containing each key is kept, in key
    order -- validators that end with an indented detail block need this
    because their final line is not the interesting one:

    >>> out = "Summary:\\n  Files scanned: 231\\n  Files with style drift: 0\\n"
    >>> summarize(out, ("Files with style drift:",))
    'Files with style drift: 0'

    Keys that match nothing yield an empty summary, so callers can substitute a
    stable "nothing to report" string instead of echoing a noisy final line:

    >>> summarize("INFO - Documentation built in 25.22 seconds", ("Aborted with",))
    ''

    Without keys the last non-empty line wins, and internal whitespace runs are
    collapsed so log-style padding does not bloat the cell:

    >>> summarize("checking\\n\\nINFO    -  Built in 3s\\n")
    'INFO - Built in 3s'

    Pipe characters would break the surrounding Markdown table, so they are
    escaped, and empty output yields an empty summary:

    >>> summarize("a | b")
    'a \\\\| b'
    >>> summarize("   \\n")
    ''
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return ""
    if summary_keys:
        picked = []
        for key in summary_keys:
            matches = [line for line in lines if key in line]
            if matches:
                picked.append(matches[-1])
        if not picked:
            return ""
        lines = picked
    else:
        lines = lines[-1:]
    text = re.sub(r"\s+", " ", scrub(" · ".join(lines))).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text.replace("|", "\\|")


# Boundaries sit where no registered gate actually lands: the fast gates finish
# well under a second, the slow ones take tens of seconds, and only the Bicep
# build exceeds two minutes. Tighter buckets flip on network jitter alone and
# churn the committed page.
DURATION_BUCKETS = ((10.0, "< 10s"), (120.0, "10-120s"))


def duration_bucket(seconds: float) -> str:
    """Bucket a gate's runtime so regeneration does not churn the committed page.

    Exact timings differ on every run, which would make the generated file
    produce a diff even when nothing about the repository changed.

    >>> duration_bucket(0.12)
    '< 10s'
    >>> duration_bucket(1.4)
    '< 10s'
    >>> duration_bucket(25.7)
    '10-120s'
    >>> duration_bucket(200.0)
    '> 120s'
    """
    for threshold, label in DURATION_BUCKETS:
        if seconds < threshold:
            return label
    return "> 120s"


def missing_requirement(requirement: str) -> str:
    """Return a human explanation if ``requirement`` is unmet, else an empty string.

    Three forms are supported so a gate can state exactly what the machine needs
    before its result means anything:

    >>> missing_requirement("exe:definitely-not-a-real-binary")
    'executable `definitely-not-a-real-binary` is not on PATH'
    >>> missing_requirement("py:not_a_real_module_xyz")
    'Python module `not_a_real_module_xyz` is not importable'
    >>> missing_requirement("path:no/such/file")
    '`no/such/file` does not exist'
    >>> missing_requirement("py:re")
    ''
    >>> missing_requirement("path:")
    Traceback (most recent call last):
    ValueError: requirement has an empty value: 'path:'
    """
    kind, _, value = requirement.partition(":")
    if not value:
        raise ValueError(f"requirement has an empty value: {requirement!r}")
    if kind == "exe":
        return "" if shutil.which(value) else f"executable `{value}` is not on PATH"
    if kind == "py":
        found = importlib.util.find_spec(value) is not None
        return "" if found else f"Python module `{value}` is not importable"
    if kind == "path":
        return "" if (ROOT / value).exists() else f"`{value}` does not exist"
    raise ValueError(f"unknown requirement form: {requirement!r}")


@dataclass
class Result:
    gate: Gate
    status: str
    detail: str
    seconds: float


def build_argv(gate: Gate, tmpsite: str) -> list[str]:
    """Resolve a gate's argv template against the current interpreter and temp dir."""
    return [
        part.replace("{python}", sys.executable).replace("{tmpsite}", tmpsite)
        for part in gate.argv
    ]


def needs_temp_site(gate: Gate) -> bool:
    """True when a gate writes build artifacts and needs a throwaway directory.

    >>> needs_temp_site(Gate("k", "N", "e", ("mkdocs", "--site-dir", "{tmpsite}"), BLOCKING))
    True
    >>> needs_temp_site(Gate("k", "N", "e", ("{python}", "x.py"), BLOCKING))
    False
    """
    return any("{tmpsite}" in part for part in gate.argv)


def skip_reason(gate: Gate, *, include_network: bool) -> str:
    """Return why a gate cannot run here, or an empty string if it can.

    The text is rendered both as a Detail cell and inside a Known Gaps bullet,
    so it reads as a standalone reason without a leading label.

    >>> skip_reason(Gate("k", "N", "e", ("x",), ADVISORY, network=True),
    ...             include_network=False)
    'Network gate; re-run with --include-network.'
    >>> skip_reason(Gate("k", "N", "e", ("x",), BLOCKING,
    ...                  requires=("exe:definitely-not-real",)), include_network=False)
    'Executable `definitely-not-real` is not on PATH.'
    >>> skip_reason(Gate("k", "N", "e", ("x",), BLOCKING), include_network=False)
    ''
    """
    if gate.network and not include_network:
        return "Network gate; re-run with --include-network."
    unmet = [message for r in gate.requires if (message := missing_requirement(r))]
    if not unmet:
        return ""
    joined = "; ".join(unmet)
    return joined[0].upper() + joined[1:] + "."


def execute(gate: Gate) -> tuple[str, int, float]:
    """Run a gate's command, returning combined output, exit code, and duration."""
    tmpsite = (
        tempfile.mkdtemp(prefix="golden-status-site-") if needs_temp_site(gate) else ""
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            build_argv(gate, tmpsite),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        output, code = completed.stdout + completed.stderr, completed.returncode
    except subprocess.TimeoutExpired:
        output, code = "Gate timed out after 1800 seconds.", 124
    except OSError as exc:
        output, code = f"Gate could not be executed: {exc}", 127
    finally:
        if tmpsite:
            shutil.rmtree(tmpsite, ignore_errors=True)
    return output, code, time.perf_counter() - started


def classify(gate: Gate, code: int) -> str:
    """Map an exit code to a status.

    A ``superset`` gate runs a wider scope than its CI job does, so a finding
    here does not mean CI would fail; it is reported as a warning, never a
    failure:

    >>> wide = Gate("k", "N", "e", ("x",), BLOCKING, superset=True)
    >>> classify(wide, 1)
    '⚠️ Warn'
    >>> classify(Gate("k", "N", "e", ("x",), BLOCKING), 1)
    '❌ Fail'
    >>> classify(Gate("k", "N", "e", ("x",), ADVISORY), 1)
    '⚠️ Warn'
    >>> classify(Gate("k", "N", "e", ("x",), BLOCKING), 0)
    '✅ Pass'
    """
    if code == 0:
        return PASS
    if gate.severity == BLOCKING and not gate.superset:
        return FAIL
    return WARN


def run_gate(gate: Gate, *, include_network: bool) -> Result:
    """Execute one gate, or record why it could not run here."""
    reason = skip_reason(gate, include_network=include_network)
    if reason:
        return Result(gate, SKIPPED, reason, 0.0)
    output, code, elapsed = execute(gate)
    detail = summarize(output, gate.summary_keys) or gate.quiet_detail
    return Result(gate, classify(gate, code), detail, elapsed)


def discovered_scripts() -> list[str]:
    """Every script under scripts/ and tools/ that looks like a gate candidate.

    Recursive, so a validator nested in a subpackage cannot hide from the
    completeness check. Candidates are files whose name starts with one of
    :data:`SCRIPT_PREFIXES`, plus the explicit :data:`SCRIPT_EXTRA_CANDIDATES`.
    """
    found: list[str] = []
    for root in SCRIPT_ROOTS:
        for path in sorted((ROOT / root).rglob("*.py")):
            if any(part in SCRIPT_SKIP_PARTS for part in path.parts):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if path.name.startswith(SCRIPT_PREFIXES) or rel in SCRIPT_EXTRA_CANDIDATES:
                found.append(rel)
    return found


def registry_problems() -> list[str]:
    """Report every way the registry can disagree with the repository.

    This is the anti-drift contract: adding a validator without registering it
    here is a CI failure, so the dashboard cannot silently under-report.
    """
    problems: list[str] = []
    seen_keys: set[str] = set()
    seen_names: set[str] = set()
    owner: dict[str, str] = {}

    for gate in GATES:
        if gate.key in seen_keys:
            problems.append(f"duplicate gate key {gate.key!r}")
        seen_keys.add(gate.key)
        if gate.name in seen_names:
            problems.append(
                f"duplicate gate name {gate.name!r}; names key the results table"
            )
        seen_names.add(gate.name)
        if gate.severity not in SEVERITY_LABEL:
            problems.append(f"gate {gate.key!r} has unknown severity {gate.severity!r}")
        elif bool(gate.bindings) != (gate.severity != UNWIRED):
            problems.append(
                f"gate {gate.key!r} is {SEVERITY_LABEL[gate.severity]!r} with "
                f"{len(gate.bindings)} workflow binding(s); 'Not in CI' means zero "
                f"bindings and every other severity means at least one"
            )
        if gate.severity == UNWIRED and gate.verified_in_ci:
            problems.append(
                f"gate {gate.key!r} is 'Not in CI' but sets verified_in_ci, which would "
                f"make the Validate Golden Status job execute it and contradict its severity"
            )
        for requirement in gate.requires:
            try:
                missing_requirement(requirement)
            except ValueError as exc:
                problems.append(f"gate {gate.key!r}: {exc}")
        for binding in gate.bindings:
            if not (ROOT / binding.workflow).exists():
                problems.append(
                    f"gate {gate.key!r} points at {binding.workflow}, which does not exist"
                )
        for path in gate.covers:
            if path in owner:
                problems.append(
                    f"{path} is claimed by both {owner[path]!r} and {gate.key!r}"
                )
            owner[path] = gate.key

    problems += [
        f"{path} is excluded from the registry without a reason"
        for path, reason in NON_GATE_SCRIPTS.items()
        if not reason.strip()
    ]

    accounted = set(owner) | set(NON_GATE_SCRIPTS)
    problems += [
        f"{rel} is not covered by GATES and not listed in NON_GATE_SCRIPTS"
        for rel in discovered_scripts()
        if rel not in accounted
    ]
    problems += [
        f"{rel} is registered but no longer exists"
        for rel in sorted(accounted)
        if not (ROOT / rel).exists()
    ]
    return problems


def marked_region(text: str, marker: str) -> str | None:
    """Return the text fenced by ``<!-- marker:start -->`` / ``:end``, or None.

    >>> doc = "a\\n<!-- m:start -->\\nBODY\\n<!-- m:end -->\\nb\\n"
    >>> marked_region(doc, "m")
    'BODY'
    >>> marked_region("no markers here", "m") is None
    True
    """
    pattern = re.compile(
        rf"<!--\s*{re.escape(marker)}:start\s*-->\n(.*?)\n<!--\s*{re.escape(marker)}:end\s*-->",
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def parse_statuses(results_table: str) -> dict[str, str]:
    """Map gate name to status from a rendered Gate Results table.

    Header and separator rows are skipped so only real gate rows are returned:

    >>> table = (
    ...     "| Gate | Severity | Status | Detail | Time |\\n"
    ...     "| --- | --- | --- | --- | --- |\\n"
    ...     "| Mermaid syntax | Blocking | OK | fine | < 1s |"
    ... )
    >>> parse_statuses(table)
    {'Mermaid syntax': 'OK'}
    """
    statuses: dict[str, str] = {}
    for line in results_table.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in {"Gate", "---"}:
            continue
        statuses[cells[0]] = cells[2]
    return statuses


def render_inventory() -> str:
    """Render the deterministic gate inventory table."""
    lines = [
        "| Gate | Enforces | Severity | Command | Enforced by |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gate in GATES:
        enforced = (
            "<br>".join(f"`{b.job}` — `{Path(b.workflow).name}`" for b in gate.bindings)
            or "— *(no workflow step)*"
        )
        lines.append(
            f"| {gate.name} | {gate.enforces} | {SEVERITY_LABEL[gate.severity]} "
            f"| `{gate.command}` | {enforced} |"
        )
    return "\n".join(lines)


def render_results(results: list[Result]) -> str:
    """Render the Gate Results table."""
    lines = [
        "| Gate | Severity | Status | Detail | Time |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.gate.name} | {SEVERITY_LABEL[result.gate.severity]} "
            f"| {result.status} | {result.detail} | {duration_bucket(result.seconds)} |"
        )
    return "\n".join(lines)


def render_frontmatter() -> str:
    """Build canonical frontmatter for the dashboard page.

    ``docs/meta/`` is out of ``content_validation`` scope, so that block is
    deliberately absent; adding it would fail ``tools/validate_frontmatter.py``.
    ``last_reviewed`` is absent too, because stamping today's date would make
    the file churn on every calendar day rather than on real change.
    """
    data = {
        "title": "Golden Status",
        "slug": "golden-status",
        "doc_type": "reference",
        "section": "meta",
        "topics": ["quality-gates", "ci", "documentation-standards"],
        "products": ["azure-app-service"],
        "summary": (
            "Single scorecard aggregating every quality gate in this repository, with "
            "the CI job that enforces each one."
        ),
        "status": "stable",
        "content_sources": {
            "diagrams": [
                {
                    "id": DIAGRAM_ID,
                    "type": "pie",
                    "source": "self-generated",
                    "justification": (
                        "Auto-generated from the exit codes of this repository's own "
                        "quality gates; it describes repository state, not Azure behavior."
                    ),
                }
            ]
        },
    }
    return f"---\n{dump_frontmatter(data)}---\n"


def render_pie(results: list[Result]) -> list[str]:
    counts = {
        "Pass": sum(1 for r in results if r.status == PASS),
        "Fail": sum(1 for r in results if r.status == FAIL),
        "Warn": sum(1 for r in results if r.status == WARN),
        "Skipped": sum(1 for r in results if r.status == SKIPPED),
    }
    lines = [
        f"<!-- diagram-id: {DIAGRAM_ID} -->",
        "```mermaid",
        "pie title Quality Gate Outcomes",
    ]
    lines += [f'    "{label}" : {count}' for label, count in counts.items() if count]
    lines.append("```")
    return lines


def render_gaps(results: list[Result]) -> list[str]:
    """One bullet per gate that is not a clean, CI-enforced pass."""
    gaps = []
    for result in results:
        gate = result.gate
        if gate.severity == UNWIRED:
            gaps.append(
                f"- **{gate.name}** is not wired into any workflow, so its findings never "
                f"reach a pull request. Snapshot result: {result.status} — {result.detail}"
            )
        elif result.status == FAIL:
            gaps.append(
                f"- **{gate.name}** is blocking and failed in this snapshot: {result.detail}"
            )
        elif result.status == WARN:
            gaps.append(
                f"- **{gate.name}** reported findings that its CI job does not fail on: "
                f"{result.detail}"
            )
        elif result.status == SKIPPED:
            gaps.append(f"- **{gate.name}** did not run here: {result.detail}")
    return gaps or ["- No gaps. Every registered gate is wired into CI and passing."]


def render_verdict(results: list[Result]) -> list[str]:
    """Render the headline verdict admonition.

    The wording deliberately never asserts that GitHub Actions is green: these
    are locally executed results for the gates this machine could run, not the
    status of any CI run.

    >>> ok = Gate("k", "Name", "e", ("x",), BLOCKING)
    >>> render_verdict([Result(ok, PASS, "", 0.0)])[0]
    '!!! success "Golden"'
    >>> render_verdict([Result(ok, FAIL, "", 0.0)])[0]
    '!!! failure "Not golden"'
    >>> render_verdict([Result(ok, SKIPPED, "", 0.0)])[0]
    '!!! warning "Blocking gates pass, with gaps"'
    """
    failures = sum(1 for r in results if r.status == FAIL)
    gaps = sum(
        1
        for r in results
        if r.status in {FAIL, WARN, SKIPPED} or r.gate.severity == UNWIRED
    )
    if failures:
        return [
            '!!! failure "Not golden"',
            f"    {failures} blocking gate(s) failed in this snapshot. Review the Gate "
            "Results table before merging anything.",
        ]
    if gaps:
        return [
            '!!! warning "Blocking gates pass, with gaps"',
            f"    No blocking gate failed in this snapshot, but {gaps} gate(s) reported "
            "findings, are unwired from CI, or could not run on the machine that generated "
            "this page. See Known Gaps.",
        ]
    return [
        '!!! success "Golden"',
        "    Every registered gate is wired into CI and passed in this snapshot with no "
        "findings.",
    ]


def source_revision() -> str:
    """Describe the tree the gates ran against, flagging uncommitted changes."""

    def git(*args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return completed.stdout.strip()

    revision = git("rev-parse", "--short", "HEAD") or "unknown"
    if git("status", "--porcelain"):
        revision += " plus uncommitted working-tree changes"
    return revision


def render_page(results: list[Result], today: date) -> str:
    counts = [
        ("Registered gates", len(results)),
        (PASS, sum(1 for r in results if r.status == PASS)),
        (FAIL, sum(1 for r in results if r.status == FAIL)),
        (WARN, sum(1 for r in results if r.status == WARN)),
        (SKIPPED, sum(1 for r in results if r.status == SKIPPED)),
    ]
    verified = sum(1 for r in results if r.gate.verified_in_ci)

    lines = [render_frontmatter().rstrip("\n"), ""]
    lines += [
        "# Golden Status",
        "",
        "Every quality gate in this repository, its most recently recorded result, and the "
        "CI job that enforces it. The page exists because the gates are spread across five "
        "workflows and report in isolation, which makes repository-wide health hard to read.",
        "",
        "## Summary",
        "",
        f"*Snapshot of `{source_revision()}`, generated {today.isoformat()}.*",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines += [f"| {label} | {count} |" for label, count in counts]
    lines += [""]
    lines += render_verdict(results)
    lines += [""]
    lines += render_pie(results)
    lines += [
        "",
        "## Gate Results",
        "",
        "These are locally executed results, not GitHub Actions statuses. **Skipped** means "
        "the machine that generated this page lacked the toolchain the gate needs. **Warn** "
        "means the gate reported findings its CI job would not fail on, either because the "
        f"job is advisory or because the dashboard runs a wider scope than CI does. {verified} "
        f"of {len(results)} gates are re-run and compared by the `Validate Golden Status` job, "
        "so a flip to **Fail** cannot sit here unnoticed.",
        "",
        f"<!-- {RESULTS_MARKER}:start -->",
        render_results(results),
        "",
        f"<!-- {RESULTS_MARKER}:end -->",
        "",
        "## Gate Inventory",
        "",
        "Generated from the `GATES` registry in `scripts/generate_golden_status.py`. CI "
        "fails if a candidate validator script matching the registry discovery rules has no "
        "entry here, so this table cannot silently fall behind.",
        "",
        f"<!-- {INVENTORY_MARKER}:start -->",
        render_inventory(),
        "",
        f"<!-- {INVENTORY_MARKER}:end -->",
        "",
        "### Invocation notes",
        "",
        "| Gate | Note |",
        "| --- | --- |",
    ]
    lines += [f"| {g.name} | {g.note} |" for g in GATES if g.note]
    lines += ["", "## Known Gaps", ""]
    lines += render_gaps(results)
    lines += [
        "",
        "## How to Regenerate",
        "",
        "```bash",
        "python3 scripts/generate_golden_status.py",
        "python3 scripts/generate_golden_status.py --include-network",
        "python3 scripts/generate_golden_status.py --strict",
        "python3 scripts/generate_golden_status.py --check",
        "python3 scripts/generate_golden_status.py --gate mermaid-syntax",
        "```",
        "",
        "| Invocation | Purpose |",
        "| --- | --- |",
        "| *(no flags)* | Run every gate this machine can run and rewrite this page. |",
        "| `--include-network` | Also run gates that make outbound HTTP requests. |",
        "| `--strict` | Exit non-zero when a blocking gate fails. |",
        "| `--check` | Registry completeness, inventory freshness, and status freshness. This is what CI runs. |",
        "| `--gate KEY` | Run one gate, stream its raw output, and exit with its code. |",
        "",
        "## See Also",
        "",
        "- [Documentation Taxonomy](taxonomy.md)",
        "- [Content Validation Status](../reference/content-validation-status.md)",
        "- [Tutorial Validation Status](../reference/validation-status.md)",
        "- [Contributing Guide](../contributing/index.md)",
        "",
        "## Sources",
        "",
        "- [AGENTS.md — Quality Gates & Verification](https://github.com/yeongseon/azure-app-service-practical-guide/blob/main/AGENTS.md)",
        "- [Series epic: documentation repetition gate](https://github.com/yeongseon/azure-container-apps-practical-guide/issues/376)",
        "- [Series epic: PII detection gate](https://github.com/yeongseon/azure-container-apps-practical-guide/issues/384)",
        "- [Series epic: visual content gate](https://github.com/yeongseon/azure-container-apps-practical-guide/issues/391)",
        "",
    ]
    return "\n".join(lines)


def status_problems(page: str) -> list[str]:
    """Re-run the CI-verifiable gates and report any status that drifted.

    Only gate *status* is compared. Detail cells carry file counts that change
    whenever a page is added, and forcing a regeneration for that would put a
    dashboard diff in every documentation pull request.
    """
    committed = marked_region(page, RESULTS_MARKER)
    if committed is None:
        return [f"{OUTPUT_REL} has no {RESULTS_MARKER} markers"]
    recorded = parse_statuses(committed)
    problems = []
    for gate in GATES:
        if not gate.verified_in_ci:
            continue
        fresh = run_gate(gate, include_network=False).status
        was = recorded.get(gate.name)
        if was is None:
            problems.append(f"{gate.name!r} is missing from the committed results table")
        elif was != fresh:
            problems.append(
                f"{gate.name!r} is recorded as {was} but currently runs {fresh}"
            )
    return problems


def check_mode() -> int:
    """Registry completeness, inventory freshness, and status freshness."""
    problems = registry_problems()
    output = ROOT / OUTPUT_REL
    if not output.exists():
        problems.append(f"{OUTPUT_REL} does not exist")
    else:
        page = output.read_text(encoding="utf-8")
        committed = marked_region(page, INVENTORY_MARKER)
        if committed is None:
            problems.append(f"{OUTPUT_REL} has no {INVENTORY_MARKER} markers")
        elif committed != render_inventory():
            problems.append(f"{OUTPUT_REL} inventory does not match the GATES registry")
        problems += status_problems(page)

    if problems:
        print("Golden status check failed:")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nRegenerate with `python3 scripts/generate_golden_status.py` "
            "and commit the result."
        )
        return 1
    verified = sum(1 for g in GATES if g.verified_in_ci)
    print(
        f"Golden status check passed: {len(GATES)} gates registered, inventory current, "
        f"{verified} gate statuses re-verified."
    )
    return 0


def run_single(key: str, *, include_network: bool) -> int:
    """Run one gate by key, stream its raw output, and return its shell exit code."""
    matches = [gate for gate in GATES if gate.key == key]
    if not matches:
        print(f"Unknown gate {key!r}. Known gates: {', '.join(g.key for g in GATES)}")
        return 2
    gate = matches[0]
    reason = skip_reason(gate, include_network=include_network)
    if reason:
        print(f"{gate.name}: {reason}")
        return 3
    output, code, _elapsed = execute(gate)
    print(output, end="" if output.endswith("\n") else "\n")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify registry completeness, inventory freshness, and status freshness.",
    )
    parser.add_argument(
        "--gate",
        metavar="KEY",
        help="Run a single gate by key and exit with its code.",
    )
    parser.add_argument(
        "--include-network",
        action="store_true",
        help="Also run gates that make outbound HTTP requests.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a blocking gate fails.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(OUTPUT_REL),
        help=f"Output path relative to the repository root (default: {OUTPUT_REL}).",
    )
    args = parser.parse_args()

    if args.check:
        return check_mode()
    if args.gate:
        return run_single(args.gate, include_network=args.include_network)

    problems = registry_problems()
    if problems:
        print("Refusing to generate: the gate registry is out of date.")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    results = []
    for gate in GATES:
        result = run_gate(gate, include_network=args.include_network)
        results.append(result)
        print(f"{result.status}  {gate.name} ({duration_bucket(result.seconds)})")

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_page(results, date.today()), encoding="utf-8")

    failures = [r for r in results if r.status == FAIL]
    print(f"\nWrote {args.output}: {len(results)} gates, {len(failures)} failure(s).")
    return 1 if failures and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
