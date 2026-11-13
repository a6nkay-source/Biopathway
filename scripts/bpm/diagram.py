"""Mermaid and Graphviz DOT rendering of an Analysis graph.

Visual grammar (identical in both formats):
  solid arrow      activation / conversion / membership (directed)
  x / tee head     inhibition
  dashed           expression, indirect effect, or computationally predicted
  no arrowhead     undirected association (STRING)
  line colour      evidence class (legend emitted with every diagram)
"""

from __future__ import annotations

import shutil
import subprocess

from . import evidence as ev
from .models import Analysis, Edge

COLOR = {ev.EXPERIMENTAL: "#1b7837", ev.CURATED: "#2166ac", ev.PREDICTED: "#e08214",
         ev.LITERATURE: "#762a83", ev.HYPOTHETICAL: "#878787"}
_RANK = {lvl: i for i, lvl in enumerate(ev.LEVELS)}


def select_edges(a: Analysis, max_edges: int) -> list[Edge]:
    """Keep the edges most relevant to the question when a graph is too big to read."""
    focus = {n.id for n in a.nodes.values() if n.focus}
    ranked = sorted(enumerate(a.edges), key=lambda ie: (
        not ({ie[1].source, ie[1].target} & focus), _RANK[ie[1].evidence],
        -float(ie[1].scores.get("combined", 0) or 0), ie[0]))
    keep = {i for i, _ in ranked[:max_edges]}
    return [e for i, e in enumerate(a.edges) if i in keep]


def _dashed(e: Edge) -> bool:
    return e.indirect or e.relation in ("expression", "indirect effect", "missing interaction") \
        or e.evidence in (ev.PREDICTED, ev.HYPOTHETICAL, ev.LITERATURE)


def edge_label(e: Edge, with_evidence: bool = True) -> str:
    parts = [e.relation] + [m for m in e.modifiers if m]
    label = " ".join(parts)
    if with_evidence:
        label += f" · {ev.SHORT[e.evidence]}"
    return label


def _mm(text: str) -> str:
    return (text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")
            .replace("|", "#124;"))


_MM_SHAPE = {"gene": ('["', '"]'), "complex": ('[["', '"]]'), "compound": ('(["', '"])'),
             "pathway": ('{{"', '"}}'), "variant": ('>"', '"]'), "region": ('("', '")'),
             "condition": ('[/"', '"/]'), "process": ('("', '")')}


def mermaid(a: Analysis, max_edges: int = 50, direction: str = "LR") -> str:
    edges = select_edges(a, max_edges)
    used = {e.source for e in edges} | {e.target for e in edges}
    nodes = [n for n in a.nodes.values() if n.id in used or n.focus]
    ids = {n.id: f"n{i}" for i, n in enumerate(nodes)}
    lines = [f"flowchart {direction}"]
    for n in nodes:
        o, c = _MM_SHAPE.get(n.kind, ('["', '"]'))
        lines.append(f"    {ids[n.id]}{o}{_mm(n.label)}{c}")
    styles = []
    for i, e in enumerate(edges):
        s, t = ids[e.source], ids[e.target]
        label = _mm(edge_label(e))
        if not e.directed:
            arrow = "-.-" if _dashed(e) else "---"
        elif e.relation == "inhibition":
            arrow = "-.-x" if _dashed(e) else "--x"
        else:
            arrow = "-.->" if _dashed(e) else "-->"
        lines.append(f'    {s} {arrow}|"{label}"| {t}')
        styles.append(f"    linkStyle {i} stroke:{COLOR[e.evidence]},stroke-width:2px")
    lines += styles
    lines += ["    classDef focus fill:#fff3bf,stroke:#b8860b,stroke-width:3px",
              "    classDef compound fill:#e6f4ea,stroke:#3c8d5a",
              "    classDef pathway fill:#e8eaf6,stroke:#3f51b5",
              "    classDef variant fill:#fde2e1,stroke:#c0392b,stroke-width:2px",
              "    classDef condition fill:#f3e5f5,stroke:#8e24aa",
              "    classDef region fill:#f1f3f4,stroke:#5f6368"]
    for kind in ("compound", "pathway", "variant", "condition", "region"):
        members = [ids[n.id] for n in nodes if n.kind == kind and not n.focus]
        if members:
            lines.append(f"    class {','.join(members)} {kind}")
    focus = [ids[n.id] for n in nodes if n.focus]
    if focus:
        lines.append(f"    class {','.join(focus)} focus")
    return "\n".join(lines)


def _dq(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


_DOT_SHAPE = {"gene": "box", "complex": "box3d", "compound": "ellipse", "pathway": "hexagon",
              "variant": "cds", "region": "note", "condition": "parallelogram", "process": "oval"}
_DOT_FILL = {"gene": "#ffffff", "complex": "#ffffff", "compound": "#e6f4ea", "pathway": "#e8eaf6",
             "variant": "#fde2e1", "region": "#f1f3f4", "condition": "#f3e5f5", "process": "#ffffff"}


def dot(a: Analysis, max_edges: int = 50, rankdir: str = "LR") -> str:
    edges = select_edges(a, max_edges)
    used = {e.source for e in edges} | {e.target for e in edges}
    nodes = [n for n in a.nodes.values() if n.id in used or n.focus]
    ids = {n.id: f"n{i}" for i, n in enumerate(nodes)}
    out = ["digraph BioPathway {", f'  rankdir={rankdir}; splines=true; nodesep=0.35;',
           '  node [fontname="Helvetica", fontsize=11, style="filled"];',
           '  edge [fontname="Helvetica", fontsize=9];',
           f'  labelloc="t"; label="{_dq(a.kind + ": " + a.query)}";']
    for n in nodes:
        extra = ', penwidth=3, color="#b8860b", fillcolor="#fff3bf"' if n.focus else \
            f', fillcolor="{_DOT_FILL.get(n.kind, "#ffffff")}"'
        out.append(f'  {ids[n.id]} [label="{_dq(n.label)}", shape={_DOT_SHAPE.get(n.kind, "box")}{extra}];')
    for e in edges:
        attrs = [f'label="{_dq(edge_label(e))}"', f'color="{COLOR[e.evidence]}"',
                 f'fontcolor="{COLOR[e.evidence]}"', "penwidth=1.6"]
        if not e.directed:
            attrs.append("dir=none")
        elif e.relation == "inhibition":
            attrs.append("arrowhead=tee")
        if _dashed(e):
            attrs.append("style=dashed")
        out.append(f"  {ids[e.source]} -> {ids[e.target]} [{', '.join(attrs)}];")
    legend = "".join(f'<TR><TD BGCOLOR="{COLOR[l]}" WIDTH="18"></TD><TD ALIGN="LEFT">{ev.SHORT[l]} = {l}</TD></TR>'
                     for l in ev.LEVELS)
    out.append(f'  legend [shape=plaintext, style="", label=<<TABLE BORDER="0" CELLSPACING="2">'
               f'<TR><TD COLSPAN="2"><B>Evidence</B></TD></TR>{legend}</TABLE>>];')
    out.append("}")
    return "\n".join(out)


def legend_markdown() -> str:
    rows = ["| Line colour | Code | Evidence class |", "|---|---|---|"]
    names = {ev.EXPERIMENTAL: "green", ev.CURATED: "blue", ev.PREDICTED: "orange",
             ev.LITERATURE: "purple", ev.HYPOTHETICAL: "grey"}
    rows += [f"| {names[l]} | {ev.SHORT[l]} | {l} |" for l in ev.LEVELS]
    rows.append("\nSolid arrow = activation/conversion/membership; `x` head = inhibition; "
                "dashed = expression, indirect or non-curated; no head = undirected association.")
    return "\n".join(rows)


def render_with_graphviz(dot_source: str, out_path: str, fmt: str = "svg") -> bool:
    """Render DOT if Graphviz is installed. Returns False (never raises) if it is not."""
    exe = shutil.which("dot")
    if not exe:
        return False
    try:
        subprocess.run([exe, f"-T{fmt}", "-o", out_path], input=dot_source.encode(),
                       check=True, capture_output=True, timeout=60)
        return True
    except (subprocess.SubprocessError, OSError):
        return False
