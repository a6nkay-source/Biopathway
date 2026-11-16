"""One operation table shared by the HTTP API (Explorer) and the MCP server.

Each operation takes a plain dict of parameters and returns JSON-serialisable
data. Adding an operation here exposes it to both front ends.
"""

from __future__ import annotations

import threading

from . import analysis as an
from . import explorer as ex
from .http import HttpClient
from .report import render_markdown

_LOCK = threading.Lock()   # the backend is single-user; serialising keeps rate limits and cache simple


def _list(v) -> list[str]:
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


def _int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _resolve_labels(elements: dict, names: list[str]) -> list[str]:
    """Map gene symbols / node labels to node ids (KEGG boxes match any member)."""
    out = []
    for name in names:
        for n in elements["nodes"]:
            d = n["data"]
            if name == d["id"] or name.upper() == d["label"].upper() or name.upper() in {m.upper() for m in d.get("members") or []}:
                out.append(d["id"])
    return list(dict.fromkeys(out))


def _resolve_edges(elements: dict, specs: list[str]) -> list[str]:
    """'A->B' (gene symbols or labels) -> edge ids."""
    out = []
    for spec in specs:
        if "->" not in spec:
            if any(e["data"]["id"] == spec for e in elements["edges"]):
                out.append(spec)
            continue
        a, b = [x.strip() for x in spec.split("->", 1)]
        src, dst = set(_resolve_labels(elements, [a])), set(_resolve_labels(elements, [b]))
        out += [e["data"]["id"] for e in elements["edges"]
                if e["data"]["source"] in src and e["data"]["target"] in dst]
    return list(dict.fromkeys(out))


class Service:
    def __init__(self, http: HttpClient | None = None, taxid: int = 9606, use_kegg: bool = True):
        self.ctx = an.Context(http or HttpClient(), taxid=taxid, use_kegg=use_kegg)

    # Every op: (handler, description, parameter schema) — schemas feed the MCP tool list.
    def ops(self) -> dict:
        S = {"type": "string"}
        L = {"type": "array", "items": {"type": "string"}}
        return {
            "report": (self.report, "Run a BioPathway analysis and return its evidence-labelled Markdown report "
                       "(kind: gene|pathway|process|metabolic|mutation|literature).",
                       {"kind": S, "query": S, "genes": L, "change": S, "module": S, "pmids": L}, ["kind"]),
            "pathway_graph": (lambda p: ex.pathway_graph(self.ctx, p["query"], _list(p.get("genes")), _int(p.get("hops"), 1)),
                              "Directed KEGG pathway graph (Cytoscape elements) with evidence on every edge, plus the full map for expansion.",
                              {"query": S, "genes": L, "hops": {"type": "integer"}}, ["query"]),
            "interaction_graph": (lambda p: ex.interaction_graph(self.ctx, _list(p.get("genes")), _int(p.get("partners"), 15)),
                                  "STRING functional-association network (undirected) with per-channel evidence.",
                                  {"genes": L, "partners": {"type": "integer"}}, ["genes"]),
            "metabolic_graph": (lambda p: ex.metabolic_graph(self.ctx, p["query"], p.get("module") or None, _list(p.get("genes"))),
                                "Metabolite-flow graph from KEGG reactions with enzyme genes.",
                                {"query": S, "module": S, "genes": L}, ["query"]),
            "process_graph": (lambda p: ex.process_graph(self.ctx, p["query"], _list(p.get("genes"))),
                              "Reactome process hierarchy with the sub-pathways and events of the queried genes.",
                              {"query": S, "genes": L}, ["query"]),
            "node_info": (lambda p: ex.node_info(self.ctx, p["symbol"]),
                          "Gene/protein detail: identifiers, function (with evidence codes), GO processes, pathways, interaction partners.",
                          {"symbol": S}, ["symbol"]),
            "compare_mutation": (lambda p: ex.compare_mutation(self.ctx, p["gene"], p["change"], p.get("pathway") or "MAPK signaling", _list(p.get("genes"))),
                                 "Normal pathway graph vs the same graph annotated only with documented variant changes (Reactome disease events, UniProt, ClinVar).",
                                 {"gene": S, "change": S, "pathway": S, "genes": L}, ["gene", "change"]),
            "perturb_pathway": (self.perturb,
                                "Remove nodes or inhibit edges in a KEGG pathway graph and report which nodes become unreachable from the source and which re-route. Computational hypothesis only.",
                                {"query": S, "genes": L, "source": S, "remove": L, "inhibit": L}, ["query", "source"]),
            "structures": (lambda p: ex.structures(self.ctx, p["query"], _int(p.get("limit"), 8)),
                           "AlphaFold (predicted) and RCSB PDB (experimental) structures for a protein, with UniProt domain and site annotations.",
                           {"query": S, "limit": {"type": "integer"}}, ["query"]),
            "structure_coords": (lambda p: ex.structure_coords(self.ctx, p["kind"], p.get("id", ""), p["accession"]),
                                 "C-alpha trace of an AlphaFold model (kind=alphafold) or PDB entry (kind=pdb, id=XXXX) in UniProt numbering.",
                                 {"kind": S, "id": S, "accession": S}, ["kind", "accession"]),
            "expression": (lambda p: ex.expression(self.ctx, p["symbol"], p.get("context", "")),
                           "Tissue (GTEx median TPM) and cell-type (Human Protein Atlas) expression context plus GEO datasets.",
                           {"symbol": S, "context": S}, ["symbol"]),
            "enrichment": (lambda p: ex.enrichment(self.ctx, _list(p.get("genes"))),
                           "Cross-pathway analysis for a gene set: Reactome over-representation and shared KEGG maps.",
                           {"genes": L}, ["genes"]),
            "literature": (lambda p: ex.literature(self.ctx, p.get("query", ""), _list(p.get("genes")), _list(p.get("pmids")), _int(p.get("max"), 8)),
                           "Primary studies and reviews with abstracts, plus keyword-extracted methods, systems, candidate conflicts and gaps.",
                           {"query": S, "genes": L, "pmids": L, "max": {"type": "integer"}}, []),
        }

    def call(self, op: str, params: dict):
        ops = self.ops()
        if op not in ops:
            raise KeyError(f"unknown operation '{op}'")
        handler, _, _, required = ops[op]
        missing = [r for r in required if not params.get(r)]
        if missing:
            raise ValueError(f"missing parameter(s): {', '.join(missing)}")
        with _LOCK:
            try:
                return handler(params)
            finally:
                if len(self.ctx.http.log) > 5000:
                    del self.ctx.http.log[:-1000]

    def report(self, p: dict) -> dict:
        kind, q, genes = p["kind"], p.get("query", ""), _list(p.get("genes"))
        if kind == "gene":
            a = an.analyze_gene(self.ctx, genes or [q])
        elif kind == "pathway":
            a = an.analyze_pathway(self.ctx, q, genes)
        elif kind == "process":
            a = an.analyze_process(self.ctx, q, genes)
        elif kind == "metabolic":
            a = an.analyze_metabolic(self.ctx, q, p.get("module") or None, genes)
        elif kind == "mutation":
            a = an.analyze_mutation(self.ctx, q or (genes[0] if genes else ""), p.get("change", ""))
        elif kind == "literature":
            a = an.analyze_literature(self.ctx, q, genes, _list(p.get("pmids")))
        else:
            raise ValueError(f"unknown kind '{kind}'")
        return {"markdown": render_markdown(a), "source_status": a.source_status}

    def perturb(self, p: dict) -> dict:
        g = ex.pathway_graph(self.ctx, p["query"], _list(p.get("genes")) or [p["source"]])
        elements = g.get("full") or g["elements"]
        sources = _resolve_labels(elements, [p["source"]])
        if not sources:
            raise ValueError(f"source '{p['source']}' is not drawn on this map")
        res = ex.perturb(elements, sources, _resolve_labels(elements, _list(p.get("remove"))),
                         _resolve_edges(elements, _list(p.get("inhibit"))))
        label = {n["data"]["id"]: n["data"]["label"] for n in elements["nodes"]}
        for k in ("sources", "removed", "reachable_before", "reachable_after", "unreachable"):
            res[k] = [label.get(x, x) for x in res[k]]
        for r in res["influence_lost"]:
            r["node"] = label.get(r["node"], r["node"])
            r["route"] = [label.get(x, x) for x in r["route"]]
        for r in res["rerouted"]:
            for k in ("original", "alternative"):
                r[k] = [label.get(x, x) for x in r[k]]
            r["source"], r["target"] = label.get(r["source"], r["source"]), label.get(r["target"], r["target"])
        res["pathway"] = g.get("full", {}).get("pathway")
        return res
