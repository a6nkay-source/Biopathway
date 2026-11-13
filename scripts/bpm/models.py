"""Plain data containers shared by every analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Citation:
    """A pointer to the exact record a claim came from."""
    source: str          # "KEGG", "Reactome", "STRING", "UniProt", "NCBI Gene", "PubMed", "ClinVar"
    id: str              # stable identifier inside that source
    url: str
    title: str = ""

    def key(self) -> tuple:
        return (self.source, self.id)


@dataclass
class Node:
    id: str
    label: str
    kind: str = "gene"   # gene | complex | compound | pathway | variant | process
    xrefs: dict = field(default_factory=dict)
    focus: bool = False


@dataclass
class Edge:
    source: str
    target: str
    relation: str                 # activation, inhibition, expression, binding, association, conversion ...
    evidence: str                 # one of evidence.LEVELS
    directed: bool = True
    modifiers: list = field(default_factory=list)   # e.g. ["phosphorylation"]
    indirect: bool = False
    detail: str = ""              # human-readable rationale for the evidence label
    citations: list = field(default_factory=list)
    scores: dict = field(default_factory=dict)

    def key(self) -> tuple:
        ends = (self.source, self.target) if self.directed else tuple(sorted((self.source, self.target)))
        return ends + (self.relation, self.directed)


@dataclass
class Statement:
    """One mechanistic or descriptive claim, always carrying its evidence label."""
    text: str
    evidence: str
    citations: list = field(default_factory=list)
    section: str = "Mechanism"


@dataclass
class Analysis:
    kind: str
    query: str
    resolved: dict = field(default_factory=dict)
    nodes: dict = field(default_factory=dict)        # id -> Node
    edges: list = field(default_factory=list)
    statements: list = field(default_factory=list)
    pathways: list = field(default_factory=list)     # dicts: source,id,name,url,match
    literature: list = field(default_factory=list)   # dicts: pmid,title,journal,year,url
    warnings: list = field(default_factory=list)
    source_status: dict = field(default_factory=dict)  # source -> "ok" | "failed: ..." | "not queried"
    notes: list = field(default_factory=list)
    requests: list = field(default_factory=list)
    diagram_note: str = ""

    def add_node(self, node: Node) -> Node:
        existing = self.nodes.get(node.id)
        if existing:
            existing.focus = existing.focus or node.focus
            existing.xrefs.update(node.xrefs)
            return existing
        self.nodes[node.id] = node
        return node

    def add_edge(self, edge: Edge) -> None:
        for existing in self.edges:
            if existing.key() == edge.key():
                for m in edge.modifiers:
                    if m not in existing.modifiers:
                        existing.modifiers.append(m)
                for c in edge.citations:
                    if c not in existing.citations:
                        existing.citations.append(c)
                return
        self.edges.append(edge)

    def ok(self, source: str) -> None:
        if not str(self.source_status.get(source, "")).startswith("failed"):
            self.source_status[source] = "ok"

    def fail(self, source: str, message: str) -> None:
        self.source_status[source] = f"failed: {message}"
        self.warnings.append(f"{source} unavailable; results from it are missing ({message}).")

    def citations(self) -> list:
        seen, out = set(), []
        pools = [c for e in self.edges for c in e.citations] + \
                [c for s in self.statements for c in s.citations]
        for c in pools:
            if c.key() not in seen:
                seen.add(c.key())
                out.append(c)
        return out

    def to_dict(self) -> dict:
        data = asdict(self)
        data["nodes"] = [asdict(n) for n in self.nodes.values()]
        data["citations"] = [asdict(c) for c in self.citations()]
        return data


def first(items, default: Optional[object] = None):
    for item in items:
        return item
    return default
