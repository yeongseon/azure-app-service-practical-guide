"""Compose the App Service topology fixtures from one spec (prototype for #283).

Run from the repository root:
    python scripts/diagram_compose.py --check      compare the composed bodies and sources with the page
    python scripts/diagram_compose.py --write      rewrite only the enrolled fence bodies
    python scripts/diagram_compose.py --print ID   print one composed body
    python scripts/diagram_compose.py --stats      print the counts used by the evaluation
"""
import argparse
import json
from pathlib import Path
import re
import sys
from typing import Callable, Final, Literal, NamedTuple, NoReturn, TypeVar

JSON = str | int | float | bool | None | list["JSON"] | dict[str, "JSON"]
Role = Literal["baseNeutral", "focusActive", "bandMuted", "stateFault"]
Style = Literal["solid", "dotted", "fault"]


class CompositionError(Exception):
    """A diagnostic at the spec or page boundary, never a programming error."""
    def __init__(self, diagnostic: str):
        self.diagnostic = diagnostic
        super().__init__(diagnostic)


class Node(NamedTuple):
    id: str
    component: str
    label: str
    role: Role


class Edge(NamedTuple):
    id: str
    source: str
    target: str
    style: Style
    label: str


class Container(NamedTuple):
    id: str
    component: Literal["vnet", "subnet"]
    title: str
    tag: str
    members: tuple[str, ...]


class Base(NamedTuple):
    id: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


class Extension(NamedTuple):
    nodes: tuple[Node, ...]
    containers: tuple[Container, ...]
    replace_edges: dict[str, tuple[Edge, ...]]


class Override(NamedTuple):
    label: str | None = None
    role: Role | None = None


class Callout(NamedTuple):
    id: str
    anchor: str
    edge_label: str
    lines: tuple[str, ...]


class Overlay(NamedTuple):
    type: Literal["failure"]
    nodes: dict[str, Override]
    replace_edges: dict[str, tuple[Edge, ...]]
    callout: Callout


class Layout(NamedTuple):
    link_length: dict[str, int]
    title_padding: dict[str, int]


class Diagram(NamedTuple):
    id: str
    page: str
    genre: Literal["topology"]
    accTitle: str
    accDescr: str
    base: str
    extensions: tuple[str, ...]
    overlay: str | None
    sources: tuple[str, ...]
    layout: Layout


class Spec(NamedTuple):
    schema_version: int
    grammar_version: int
    base: Base
    extensions: dict[str, Extension]
    overlays: dict[str, Overlay]
    diagrams: tuple[Diagram, ...]


SHAPES: Final = {
    "client": ('(["', '"])'), "dns": ('{{"', '"}}'),
    "ingress": ('["', '"]'), "app-runtime": ('["', '"]'),
    "control-plane": ('["', '"]'), "identity": ('{{"', '"}}'),
    "private-endpoint": ('[["', '"]]'), "vnet-integration": ('[["', '"]]'),
    "key-vault": ('[("', '")]'), "storage-db": ('[("', '")]'),
    "telemetry": ('>"', '"]'), "firewall-nva": ('[/"', '"/]'),
}
CALLOUT_SHAPE: Final = ('["', '"]')
FAULT_PREFIXES: Final = ("[FAULT / Illustrative] ", "[FAULT / Inferred] ")
CLAIM_PREFIXES: Final = ("[Configured] ", "[Illustrative] ", "[Inferred] ")
PALETTE: Final = {
    "baseNeutral": "fill:#f2f4f8,stroke:#707e93,stroke-width:1.5px,color:#14202e;",
    "focusActive": "fill:#e6f0fd,stroke:#287ce4,stroke-width:2.5px,color:#14202e;",
    "bandMuted": "fill:#ffffff,stroke:#707e93,stroke-width:1.5px,stroke-dasharray:4 3,color:#14202e;",
    "stateFault": "fill:#fdebee,stroke:#da495d,stroke-width:3px,color:#86172a;",
    "netBox": "fill:transparent,stroke:#287ce4,stroke-width:2px,stroke-dasharray:6 3;",
}
FENCE: Final = re.compile(r"^<!-- diagram-id: ([a-z0-9-]+) -->\r?\n```mermaid\r?\n(.*?)\r?\n```(?=\r?$)", re.M | re.S)
ROOT: Final = Path(__file__).resolve().parents[1]
SPEC_PATH: Final = ROOT / "scripts/diagram_composition.json"
T = TypeVar("T")


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise CompositionError(diagnostic)


def assert_never(value: NoReturn) -> NoReturn:
    raise AssertionError(f"unreachable variant: {value!r}")


def non_json(value: str) -> NoReturn:
    raise CompositionError(f"invalid JSON constant: {value}")


def unique(pairs: list[tuple[str, JSON]]) -> dict[str, JSON]:
    result: dict[str, JSON] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(text: str) -> JSON:
    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=non_json)
    except json.JSONDecodeError as error:
        raise CompositionError(f"invalid JSON: {error.msg}") from error


def mapping(raw: JSON) -> dict[str, JSON]:
    if not isinstance(raw, dict):
        raise CompositionError("expected object")
    return raw


def record(raw: JSON, fields: str) -> dict[str, JSON]:
    value = mapping(raw)
    required = set(fields.split())
    require(not value.keys() - required, f"unknown keys {sorted(value.keys() - required)}")
    require(not required - value.keys(), f"missing {' '.join(sorted(required - value.keys()))}")
    return value


def text(raw: JSON) -> str:
    if not isinstance(raw, str):
        raise CompositionError("expected str")
    require(bool(raw.strip()), "empty text")
    require("[Observed]" not in raw and "/ Observed]" not in raw, "reserved [Observed]")
    require(not re.search(r'["\r\n`|]|<(?!br/>)|&nbsp;', raw), "raw Mermaid or layout text")
    return raw


def integer(raw: JSON) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise CompositionError("expected int")
    return raw


def sequence(raw: JSON, parse: Callable[[JSON], T]) -> tuple[T, ...]:
    if not isinstance(raw, list):
        raise CompositionError("expected array")
    return tuple(parse(value) for value in raw)


def table(raw: JSON, parse: Callable[[JSON], T]) -> dict[str, T]:
    return {text(key): parse(value) for key, value in mapping(raw).items()}


def role(raw: JSON) -> Role:
    match text(raw):
        case "baseNeutral" | "focusActive" | "bandMuted" | "stateFault" as value:
            return value
        case value:
            raise CompositionError(f"unsupported class: {value}")


def node(raw: JSON) -> Node:
    r = record(raw, "id component label class")
    component = text(r["component"])
    require(component in SHAPES, f"unknown component or non-node component: {component}")
    return Node(text(r["id"]), component, text(r["label"]), role(r["class"]))


def edge(raw: JSON) -> Edge:
    r = record(raw, "id from to style label")
    match text(r["style"]):
        case "solid" | "dotted" | "fault" as style:
            return Edge(text(r["id"]), text(r["from"]), text(r["to"]), style, text(r["label"]))
        case value:
            raise CompositionError(f"unsupported style: {value}")


def container(raw: JSON) -> Container:
    r = record(raw, "id component title tag members")
    match text(r["component"]):
        case "vnet" | "subnet" as component:
            return Container(text(r["id"]), component, text(r["title"]), text(r["tag"]), sequence(r["members"], text))
        case value:
            raise CompositionError(f"unsupported container component: {value}")


def extension(raw: JSON) -> Extension:
    r = record(raw, "nodes containers replace_edges")
    return Extension(sequence(r["nodes"], node), sequence(r["containers"], container), table(r["replace_edges"], lambda v: sequence(v, edge)))


def override(raw: JSON) -> Override:
    r = mapping(raw)
    require(bool(r) and not r.keys() - {"label", "class"}, "unknown keys or empty node override")
    return Override(text(r["label"]) if "label" in r else None, role(r["class"]) if "class" in r else None)


def overlay(raw: JSON) -> Overlay:
    r = record(raw, "type nodes replace_edges callout")
    require(text(r["type"]) == "failure", "unsupported value for overlay type")
    c = record(r["callout"], "id anchor edge_label lines")
    callout = Callout(text(c["id"]), text(c["anchor"]), text(c["edge_label"]), sequence(c["lines"], text))
    return Overlay("failure", table(r["nodes"], override), table(r["replace_edges"], lambda v: sequence(v, edge)), callout)


def parse_diagram(raw: JSON) -> Diagram:
    r = record(raw, "id page genre accTitle accDescr base extensions overlay sources layout")
    require(text(r["genre"]) == "topology", "sequence/decision/state stay hand-written; genre must be topology")
    layout = record(r["layout"], "link_length title_padding")
    return Diagram(text(r["id"]), text(r["page"]), "topology", text(r["accTitle"]), text(r["accDescr"]), text(r["base"]),
                   sequence(r["extensions"], text), None if r["overlay"] is None else text(r["overlay"]), sequence(r["sources"], text),
                   Layout(table(layout["link_length"], integer), table(layout["title_padding"], integer)))


def parse_spec(raw: JSON) -> Spec:
    r = record(raw, "schema_version grammar_version base extensions overlays diagrams")
    b = record(r["base"], "id nodes edges")
    base = Base(text(b["id"]), sequence(b["nodes"], node), sequence(b["edges"], edge))
    spec = Spec(integer(r["schema_version"]), integer(r["grammar_version"]), base, table(r["extensions"], extension),
                table(r["overlays"], overlay), sequence(r["diagrams"], parse_diagram))
    for field in ("schema_version", "grammar_version"):
        require(getattr(spec, field) == 1, f"unsupported {field}")
    require(bool(spec.diagrams), "missing diagrams")
    require(len({d.id for d in spec.diagrams}) == len(spec.diagrams), "duplicate diagram id")
    for diagram in spec.diagrams:
        require(bool(re.fullmatch(r"[a-z0-9-]+", diagram.id)), f"invalid diagram id: {diagram.id}")
        require(not Path(diagram.page).is_absolute() and ".." not in Path(diagram.page).parts, "page must be repo-root relative")
        graph(spec, diagram)
    return spec


def load_spec(path: Path = SPEC_PATH) -> Spec:
    return parse_spec(decode(path.read_text(encoding="utf-8")))


def replace_edges(edges: tuple[Edge, ...], replacements: dict[str, tuple[Edge, ...]]) -> tuple[Edge, ...]:
    unknown = replacements.keys() - {e.id for e in edges}
    require(not unknown, "replace_edges: unknown edge " + str(sorted(unknown)))
    return tuple(new for edge in edges for new in replacements.get(edge.id, (edge,)))


def graph(spec: Spec, diagram: Diagram) -> tuple[tuple[Node, ...], tuple[Container, ...], tuple[Edge, ...]]:
    """Apply ordered extensions and failure changes without mutating the authored model."""
    require(diagram.base == spec.base.id, f"unknown base: {diagram.base}")
    nodes, edges, containers = spec.base.nodes, spec.base.edges, ()
    require(len(nodes) == len({n.id for n in nodes}), "duplicate node/container id")
    require(len(edges) == len({e.id for e in edges}), "duplicate edge id")
    for edge in edges:
        require(edge.source in {n.id for n in nodes} and edge.target in {n.id for n in nodes}, f"base edge {edge.id}: undeclared node")
    replaced: set[str] = set()
    for name in diagram.extensions:
        require(name in spec.extensions, f"unknown extension: {name}")
        extension = spec.extensions[name]
        require(not replaced & extension.replace_edges.keys(), "two extensions replace the same edge")
        replaced.update(extension.replace_edges)
        nodes += extension.nodes
        containers += extension.containers
        edges = replace_edges(edges, extension.replace_edges)
    if diagram.overlay is not None:
        require(diagram.overlay in spec.overlays, f"unknown overlay: {diagram.overlay}")
        overlay = spec.overlays[diagram.overlay]
        require(not overlay.nodes.keys() - {n.id for n in nodes}, "overlay targets missing node")
        nodes = tuple(n._replace(label=o.label or n.label, role=o.role or n.role) if (o := overlay.nodes.get(n.id)) else n for n in nodes)
        before = edges
        edges = replace_edges(edges, overlay.replace_edges)
        callout = overlay.callout
        require("[Illustrative scenario - not a measurement]" in callout.lines, "callout missing disclaimer")
        nodes += (Node(callout.id, "callout", "<br/>".join(callout.lines), "stateFault"),)
        # Place the annotation after the final replacement span, not by a numeric index.
        last = max((i for i, e in enumerate(before) if e.id in overlay.replace_edges), default=len(before) - 1)
        position = sum(len(overlay.replace_edges.get(e.id, (e,))) for e in before[:last + 1])
        annotation = Edge(callout.id, callout.anchor, callout.id, "fault", callout.edge_label)
        edges = edges[:position] + (annotation,) + edges[position:]
        require(any(e.style == "fault" for e in edges if e.id != callout.id), "failure overlay has no broken normal path")
    ids = [item.id for item in (*nodes, *containers)]
    require(len(ids) == len(set(ids)), "duplicate node/container id")
    require(len(edges) == len({e.id for e in edges}), "duplicate edge id")
    for identifier in (*ids, *(e.id for e in edges)):
        require(bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", identifier)), f"invalid graph id: {identifier}")
    for edge in edges:
        require(edge.source in {n.id for n in nodes} and edge.target in {n.id for n in nodes}, f"edge {edge.id}: undeclared node")
        prefixes = FAULT_PREFIXES if edge.style == "fault" else CLAIM_PREFIXES
        require(edge.label.startswith(prefixes), f"edge {edge.id}: missing claim prefix for {edge.style}")
        require(diagram.overlay is not None or edge.style != "fault", "normal path cannot contain fault edges")
    parents: dict[str, str] = {}
    for container in containers:
        require(bool(container.members), f"container {container.id}: missing members")
        for member in container.members:
            require(member in ids, f"container {container.id}: missing member {member}")
            require(member not in parents, f"container member {member}: multiple parents")
            parents[member] = container.id
    for identifier in parents:
        seen: set[str] = set()
        current = identifier
        while current in parents:
            require(current not in seen, f"container cycle: {identifier}")
            seen.add(current)
            current = parents[current]
    for key, value in diagram.layout.link_length.items():
        require(any(e.id == key and e.style == "dotted" for e in edges), f"link_length: unknown or non-dotted edge {key}")
        require(value >= 1, "link_length must be positive")
    for key, value in diagram.layout.title_padding.items():
        require(key in {c.id for c in containers}, f"title_padding: unknown container {key}")
        require(value >= 0, "title_padding must be nonnegative")
    return nodes, containers, edges


def compose(spec: Spec, diagram: Diagram) -> str:
    nodes, containers, edges = graph(spec, diagram)
    members = {m for c in containers for m in c.members}
    lookup = {item.id: item for item in (*nodes, *containers)}
    lines = ["flowchart TD", f"    accTitle: {diagram.accTitle}", f"    accDescr: {diagram.accDescr}"]
    def emit(identifier: str, depth: int) -> None:
        item, indent = lookup[identifier], "    " * depth
        match item:
            case Node():
                opening, closing = CALLOUT_SHAPE if item.component == "callout" else SHAPES[item.component]
                lines.append(f"{indent}{item.id}{opening}{item.label}{closing}")
            case Container():
                padding = "&nbsp;" * diagram.layout.title_padding.get(item.id, 0)
                title = f"{item.title} {padding} {item.tag}" if padding else f"{item.title} {item.tag}"
                lines.append(f'{indent}subgraph {item.id}["{title}"]')
                for member in item.members:
                    emit(member, depth + 1)
                lines.append(indent + "end")
            case unreachable:
                assert_never(unreachable)
    for item in (*nodes, *containers):
        if item.id not in members:
            emit(item.id, 1)
    for edge in edges:
        arrow = {"solid": "-->", "fault": "==>", "dotted": "-" + "." * diagram.layout.link_length.get(edge.id, 1) + "->"}[edge.style]
        lines.append(f'    {edge.source} {arrow}|"{edge.label}"| {edge.target}')
    classes = {role: [n.id for n in nodes if n.role == role] for role in PALETTE}
    classes["netBox"] = [c.id for c in containers]
    lines += [f"    classDef {role} {definition}" for role, definition in PALETTE.items() if classes[role]]
    lines += [f"    class {','.join(ids)} {role};" for role, ids in classes.items() if ids]
    faults = [str(i) for i, edge in enumerate(edges) if edge.style == "fault"]
    if faults:
        lines.append(f"    linkStyle {','.join(faults)} stroke:#da495d,stroke-width:3px;")
    return "\n".join(lines)


def page_result(text: str, entries: tuple[tuple[Diagram, str], ...], write: bool = False) -> str:
    """Validate metadata and spans first; return a byte-preserving replacement plan."""
    normalized = text.replace("\r\n", "\n")
    head = re.match(r"\A---\n(.*?)\n---\n", normalized, re.S)
    if head is None:
        raise CompositionError("missing canonical frontmatter")
    metadata = dict(re.findall(r"^    - id: ([a-z0-9-]+)\n(.*?)(?=^    - id:|\Z)", head.group(1), re.M | re.S))
    require({d.id for d, _ in entries} <= metadata.keys(), "frontmatter diagram ids differ")
    for diagram, _ in entries:
        source = re.search(r"^      based_on: \[(.*?)\]$", metadata[diagram.id], re.M)
        require(source is not None and tuple(source.group(1).split(", ")) == diagram.sources, f"{diagram.id}: frontmatter sources differ")
    spans = []
    for diagram, body in entries:
        matches = [m for m in FENCE.finditer(text) if m.group(1) == diagram.id]
        require(len(matches) == 1, f"{diagram.id}: missing or duplicate committed fence")
        match = matches[0]
        require(write or match.group(2).replace("\r\n", "\n") == body, f"{diagram.id}: committed fence drift")
        newline = "\r\n" if "\r\n" in match.group(0) else "\n"
        spans.append((match.start(2), match.end(2), body.replace("\n", newline)))
    result = text
    for start, end, body in sorted(spans, reverse=True):
        result = result[:start] + body + result[end:]
    return result


def nonblank_lines(content: str) -> int:
    return sum(bool(line.strip()) for line in content.splitlines())


def stats(spec: Spec) -> dict[str, JSON]:
    fragments = tuple(spec.extensions.values())
    replacements = [f.replace_edges for f in (*fragments, *spec.overlays.values())]
    inline: dict[str, JSON] = {}
    for d in spec.diagrams:
        page = (ROOT / d.page).read_text(encoding="utf-8")
        bodies = [m.group(2) for m in FENCE.finditer(page) if m.group(1) == d.id]
        require(len(bodies) == 1, f"{d.id}: missing or duplicate committed fence")
        inline[d.id] = nonblank_lines(bodies[0])
    files = {"spec": SPEC_PATH, "generator": Path(__file__), "test": ROOT / "tests/ci/test_diagram_composition.py"}
    return {
        **{f"{name}_nonblank_lines": nonblank_lines(path.read_text(encoding="utf-8")) for name, path in files.items()},
        "nodes": len(spec.base.nodes) + sum(len(f.nodes) for f in fragments),
        "containers": sum(len(f.containers) for f in fragments),
        "edges": len(spec.base.edges) + sum(len(es) for r in replacements for es in r.values()),
        "replacements": sum(len(r) for r in replacements),
        "overrides": sum(len(o.nodes) for o in spec.overlays.values()),
        "callouts": len(spec.overlays),
        "layout_hints": sum(len(d.layout.link_length) + len(d.layout.title_padding) for d in spec.diagrams),
        "inline_nonblank_lines": inline,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("check", "write", "stats"):
        modes.add_argument("--" + mode, action="store_true")
    modes.add_argument("--print", dest="identifier", metavar="ID")
    args = parser.parse_args(argv)
    try:
        spec = load_spec()
        outputs = tuple((d, compose(spec, d)) for d in spec.diagrams)
        if args.identifier:
            require(args.identifier in {d.id for d in spec.diagrams}, f"unknown diagram: {args.identifier}")
            sys.stdout.write(next(body for d, body in outputs if d.id == args.identifier))
        elif args.stats:
            print(json.dumps(stats(spec), indent=2))
        else:
            plans = []
            for page in sorted({d.page for d in spec.diagrams}):
                path = ROOT / page
                text = path.read_bytes().decode("utf-8")
                result = page_result(text, tuple((d, b) for d, b in outputs if d.page == page), args.write)
                plans.append((path, text, result))
            changed = [(path, result) for path, text, result in plans if result != text]
            if args.write:
                for path, result in changed:
                    path.write_bytes(result.encode("utf-8"))
                print(f"diagram composition: wrote {len(changed)} page(s)")
            else:
                print(f"diagram composition: check passed ({len(outputs)} diagrams)")
        return 0
    except (CompositionError, OSError, UnicodeError) as error:
        print(str(error).replace("\n", " "), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
