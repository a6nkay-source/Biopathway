"""Structured payloads for the BioPathway Explorer and the MCP server.

Everything here is built from the existing analyses; nothing introduces a
relationship that a database record does not state. Graphs are Cytoscape.js
element lists so the frontend can render them directly.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import asdict

from . import analysis as an
from . import evidence as ev
from .http import SourceError
from .integrations.expression import ExpressionClient, geo_datasets
from .integrations.structures import StructureClient
from .models import Analysis, Edge, Node

SIGN = {"activation": "+", "expression": "+", "inhibition": "-", "repression": "-",
        "conversion": "+", "phosphorylation": "0", "binding": "0", "association": "0"}
PHOSPHO = ("+p", "phosphorylation")


# ------------------------------------------------------------ Cytoscape
def edge_id(e: Edge) -> str:
    return f"{e.source}__{e.relation}__{e.target}"


def node_element(n: Node) -> dict:
    return {"data": {"id": n.id, "label": n.label, "kind": n.kind, "focus": n.focus,
                     "members": n.xrefs.get("members", []), "xrefs": _jsonable(n.xrefs)}}


def edge_element(e: Edge) -> dict:
    mods = [m for m in e.modifiers if m]
    return {"data": {
        "id": edge_id(e), "source": e.source, "target": e.target,
        "relation": e.relation, "sign": SIGN.get(e.relation, "0"),
        "evidence": e.evidence, "evidenceCode": ev.SHORT[e.evidence],
        "directed": e.directed, "indirect": e.indirect, "modifiers": mods,
        "phospho": any(m in PHOSPHO for m in mods) or e.relation == "phosphorylation",
        "suspect": "direction suspect" in mods,
        "detail": e.detail, "scores": e.scores,
        "citations": [asdict(c) for c in e.citations]}}


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]
    return x if isinstance(x, (str, int, float, bool)) or x is None else str(x)


def payload(a: Analysis) -> dict:
    """Common envelope: graph elements plus the report's evidence context."""
    return {
        "kind": a.kind, "query": a.query, "resolved": a.resolved,
        "elements": {"nodes": [node_element(n) for n in a.nodes.values()],
                     "edges": [edge_element(e) for e in a.edges]},
        "focus": [n.id for n in a.nodes.values() if n.focus],
        "statements": [{"text": s.text, "evidence": s.evidence, "code": ev.SHORT[s.evidence],
                        "section": s.section, "citations": [asdict(c) for c in s.citations]}
                       for s in a.statements],
        "pathways": a.pathways, "literature": a.literature, "warnings": list(dict.fromkeys(a.warnings)),
        "notes": list(dict.fromkeys(a.notes)), "source_status": a.source_status,
        "citations": [asdict(c) for c in a.citations()], "diagram_note": a.diagram_note,
        "retrieved": sorted(r["retrieved_at"] for r in a.requests if r.get("retrieved_at"))[-1:]}


# ------------------------------------------------------------- graphs
def pathway_graph(ctx, query: str, genes: list[str] = (), hops: int = 1) -> dict:
    a = an.analyze_pathway(ctx, query, list(genes), hops)
    out = payload(a)
    full = a.extras.get("kegg_full")
    if full:
        out["full"] = {"pathway": full["pathway"], "title": full["title"],
                       "nodes": [node_element(n) for n in full["nodes"]],
                       "edges": [edge_element(e) for e in full["edges"]]}
    return out


def interaction_graph(ctx, genes: list[str], partners: int = 15) -> dict:
    return payload(an.analyze_gene(ctx, list(genes), partners))


def metabolic_graph(ctx, query: str, module: str | None = None, genes: list[str] = ()) -> dict:
    return payload(an.analyze_metabolic(ctx, query, module, list(genes)))


def process_graph(ctx, query: str, genes: list[str] = ()) -> dict:
    return payload(an.analyze_process(ctx, query, list(genes)))


def literature(ctx, query: str, genes: list[str] = (), pmids: list[str] = (), max_results: int = 8) -> dict:
    from .litmine import mine
    a = an.analyze_literature(ctx, query, list(genes), list(pmids), max_results)
    out = payload(a)
    symbols = [v["symbol"] for k, v in a.resolved.items() if k != "variant"] or list(genes)
    out["mining"] = mine(a.literature, symbols, query)
    return out


# ---------------------------------------------------------- node detail
def node_info(ctx, symbol: str) -> dict:
    """Everything the information panel shows for one gene/protein."""
    a = an.analyze_gene(ctx, [symbol], partners=10)
    out = {"symbol": symbol, "resolved": a.resolved.get(symbol) or next(iter(a.resolved.values()), None),
           "function": [], "go": [], "pathways": a.pathways[:40], "partners": [],
           "warnings": list(dict.fromkeys(a.warnings)), "source_status": a.source_status,
           "literature": a.literature[:5]}
    for s in a.statements:
        item = {"text": s.text, "evidence": s.evidence, "code": ev.SHORT[s.evidence],
                "citations": [asdict(c) for c in s.citations]}
        (out["function"] if s.section == "Function" else out["go"]).append(item)
    for e in a.edges:
        other = e.target if e.source == symbol else e.source
        out["partners"].append({"symbol": other, "evidence": e.evidence, "code": ev.SHORT[e.evidence],
                                "basis": e.detail, "scores": e.scores,
                                "citations": [asdict(c) for c in e.citations]})
    return out


# ------------------------------------------------------ mutation compare
def _members(node: dict) -> set:
    d = node["data"]
    return set(d.get("members") or []) | {d["label"]} | set(re.split(r"[/:]", d["label"]))


def compare_mutation(ctx, gene: str, change: str, pathway: str, genes: list[str] = ()) -> dict:
    """Normal pathway graph vs the same graph annotated with *documented* variant changes.

    Edge annotations come only from Reactome disease events in which the
    variant entity (or a curated set it is a confirmed member of) takes part,
    mapped to graph edges through the participant genes of the event's normal
    counterpart. Without such records the mutant graph equals the normal graph
    except for the highlighted variant node.
    """
    normal = pathway_graph(ctx, pathway, [gene] + [g for g in genes if g != gene])
    mut = an.analyze_mutation(ctx, gene, change)
    var = mut.resolved.get("variant")
    sym = next((v["symbol"] for k, v in mut.resolved.items() if k != "variant"), gene)
    out = {"gene": sym, "change": change, "variant": var, "normal": normal,
           "variant_statements": [s for s in payload(mut)["statements"]
                                  if s["section"] not in ("Identifiers",)],
           "reactome": {"entities": [], "sets": [], "pathways": []}, "changes": [],
           "overlay": {"edges": {}, "nodes": {}}, "downstream": [], "warnings": list(mut.warnings),
           "source_status": {**normal["source_status"], **mut.source_status}}
    short = var["one_letter"] if var else change
    nodes = normal.get("full", normal["elements"])["nodes"] if normal.get("full") else normal["elements"]["nodes"]
    edges = normal.get("full", normal["elements"])["edges"] if normal.get("full") else normal["elements"]["edges"]
    by_id = {n["data"]["id"]: n for n in nodes}
    gene_nodes = {n["data"]["id"] for n in nodes if sym in _members(n)}
    for nid in gene_nodes:
        box = by_id[nid]["data"].get("members") or []
        out["overlay"]["nodes"][nid] = {"status": "mutated", "label": f"{sym} p.{short}",
                                        "box_note": (f"{sym} is one of {len(box)} paralogs KEGG draws in this box; "
                                                     "the variant applies to "
                                                     f"{sym} only") if len(box) > 1 else ""}

    try:
        entities = ctx.reactome.variant_entities(sym, short, ctx.species)
    except SourceError as exc:
        out["warnings"].append(f"Reactome unavailable for variant lookup ({exc.message}).")
        entities = []
    out["reactome"]["entities"] = entities
    if not entities:
        out["warnings"].append(f"Reactome has no disease entity named '{sym} {short}'. No curated "
                               "pathway-level change is drawn; the mutant panel only marks the gene.")
    event_ids, seen_pw, event_pathway = [], set(), {}
    for ent in entities:
        sets = ctx.reactome.sets_containing(ent["id"])
        out["reactome"]["sets"].extend(sets)
        for pw in ctx.reactome.lowest_pathways(ent["id"], ctx.taxid):
            if pw["id"] in seen_pw:
                continue
            seen_pw.add(pw["id"])
            out["reactome"]["pathways"].append(pw)
            for e in ctx.reactome.contained_events(pw["id"]):
                if e["type"] != "Pathway" and e["id"] not in event_ids:
                    event_ids.append(e["id"])
                    event_pathway[e["id"]] = pw["name"]
    weak_sets = [s for s in out["reactome"]["sets"] if s["relation"] == "hasCandidate"]
    for eid in event_ids[:40]:
        d = ctx.reactome.event_detail(eid)
        if not d:
            continue
        failed = d["type"] == "FailedReaction"
        genes_here = ctx.reactome.participant_genes(d["normal"]["id"] if (failed and d["normal"]) else eid)
        # Events whose name names *another* gene's mutants need a co-occurring mutation (e.g. BRAF).
        context = f"{d['name']} | {event_pathway.get(eid, '')}"
        found = re.findall(r"\b([A-Z][A-Z0-9]{1,9}) mutants?\b", context) + \
            re.findall(r"kinase[- ]inactive ([A-Z][A-Z0-9]{1,9})", context, re.I)
        other_mut = sorted({g for g in found if g not in (sym, "RAS", sym[:3]) and not sym.startswith(g)})
        level = ev.PREDICTED if (d["inferred"] or weak_sets) else ev.CURATED
        hit_edges = []
        for e in edges:
            s, t = by_id.get(e["data"]["source"]), by_id.get(e["data"]["target"])
            if not s or not t:
                continue
            sm, tm = _members(s), _members(t)
            touches_var = e["data"]["source"] in gene_nodes or e["data"]["target"] in gene_nodes
            other = tm if e["data"]["source"] in gene_nodes else sm
            if touches_var and (other & set(genes_here)) and not (other == {sym}):
                hit_edges.append(e["data"]["id"])
        if failed:
            status = "impaired in mutant"
        elif other_mut:
            status = f"requires co-occurring {'/'.join(other_mut)} mutation"
        else:
            status = "mutant participates; no change from normal documented"
        if not failed:
            hit_edges = []   # only FailedReactions are drawn as edge changes
        change_rec = {"event": d["id"], "name": d["name"], "type": d["type"], "pathway": event_pathway.get(eid, ""),
                      "status": status,
                      "normal": d["normal"], "evidence": level, "code": ev.SHORT[level],
                      "summary": an._short(d["summary"], 500), "pmids": d["pmids"][:6],
                      "participant_genes": genes_here, "edges": hit_edges, "url": d["url"]}
        out["changes"].append(change_rec)
        for eid2 in hit_edges:
            slot = out["overlay"]["edges"].setdefault(eid2, {"status": "impaired in mutant", "events": []})
            slot["events"].append({"id": d["id"], "name": d["name"]})
        if failed and not hit_edges:
            for nid in gene_nodes:
                out["overlay"]["nodes"][nid].setdefault("impaired", []).append(d["name"])
    if weak_sets:
        out["warnings"].append("The variant is only a *candidate* member of some Reactome sets; "
                               "changes derived from them are labelled predicted.")
    out["downstream"] = sorted(reachable_from(gene_nodes, edges))
    out["notes"] = [
        "Only Reactome FailedReactions for this exact variant entity are drawn as changes ('impaired'), "
        "mapped through the participants of their normal reaction. Other disease events are listed "
        "as context: the mutant takes part, but no change from normal is documented, or a second "
        "mutation is required.",
        "Downstream nodes are graph-reachable from the mutated node. Reachability is a structural "
        "statement, not a measurement of signalling in cells.",
        "Effects differ between variants of the same residue (e.g. G12C vs G12D); nothing here is "
        "transferred from another variant."]
    return out


# ------------------------------------------------------- perturbation
def _adjacency(edges: list[dict], removed: set = frozenset(), cut: set = frozenset()) -> dict:
    """Deterministic adjacency (neighbours in edge-id order), matching explorer/src/lib/graph.ts.

    Edges flagged 'direction suspect' are not traversed: a route through a probably
    mis-encoded relation is not evidence of reachability."""
    adj: dict = {}
    for e in sorted(edges, key=lambda x: x["data"]["id"]):
        d = e["data"]
        if d["id"] in cut or d["source"] in removed or d["target"] in removed or d.get("suspect"):
            continue
        adj.setdefault(d["source"], []).append(d["target"])
        if not d.get("directed", True):
            adj.setdefault(d["target"], []).append(d["source"])
    return adj


def reachable_from(sources, edges, removed=frozenset(), cut=frozenset()) -> set:
    adj = _adjacency(edges, set(removed), set(cut))
    seen = {s for s in sources if s not in removed}
    q = deque(seen)
    while q:
        n = q.popleft()
        for m in adj.get(n, ()):
            if m not in seen:
                seen.add(m)
                q.append(m)
    return seen - set(sources)


def _shortest(adj: dict, src: str, dst: str) -> list[str]:
    prev = {src: None}
    q = deque([src])
    while q:
        n = q.popleft()
        if n == dst:
            break
        for m in adj.get(n, ()):
            if m not in prev:
                prev[m] = n
                q.append(m)
    if dst not in prev:
        return []
    path, cur = [], dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1]


def path_sign(path: list[str], edges: list[dict]) -> str:
    """Product of edge signs along a path: '+', '-', or '?' when any step is unsigned."""
    sign = 1
    for u, v in zip(path, path[1:]):
        e = next((x["data"] for x in edges if x["data"]["source"] == u and x["data"]["target"] == v), None) or \
            next((x["data"] for x in edges if not x["data"].get("directed", True)
                  and x["data"]["source"] == v and x["data"]["target"] == u), None)
        s = (e or {}).get("sign", "0")
        if s == "0":
            return "?"
        sign *= -1 if s == "-" else 1
    return "+" if sign > 0 else "-"


def perturb(elements: dict, sources: list[str], remove_nodes: list[str] = (),
            inhibit_edges: list[str] = ()) -> dict:
    """Graph connectivity before/after removing nodes or cutting (inhibiting) edges."""
    edges = elements["edges"]
    removed, cut = set(remove_nodes), set(inhibit_edges)
    before = reachable_from(sources, edges)
    after = reachable_from(sources, edges, removed, cut)
    lost = sorted(before - after - removed)
    adj0, adj1 = _adjacency(edges), _adjacency(edges, removed, cut)
    influence_lost = []
    for n in lost:
        p0 = next((pp for pp in (_shortest(adj0, s, n) for s in sources) if pp), [])
        influence_lost.append({"node": n, "net_sign": path_sign(p0, edges), "route": p0})
    def uses_change(path):
        if any(x in removed for x in path):
            return True
        ids = {(e["data"]["source"], e["data"]["target"]): e["data"]["id"] for e in edges}
        return any(ids.get((u, v)) in cut or ids.get((v, u)) in cut for u, v in zip(path, path[1:]))

    rerouted = []
    for n in sorted(after):
        for s in sources:
            p0, p1 = _shortest(adj0, s, n), _shortest(adj1, s, n)
            if p0 and p1 and uses_change(p0):
                rerouted.append({"source": s, "target": n, "original": p0, "alternative": p1,
                                 "sign_original": path_sign(p0, edges), "sign_alternative": path_sign(p1, edges)})
                break
    return {"sources": sources, "removed": sorted(removed), "inhibited_edges": sorted(cut),
            "reachable_before": sorted(before), "reachable_after": sorted(after),
            "unreachable": lost, "influence_lost": influence_lost, "rerouted": rerouted,
            "caveat": ("Connectivity on a curated map is a computational hypothesis. 'Unreachable' means the "
                       "source's influence no longer propagates along drawn relations; it does not mean the node "
                       "switches off. Removing an inhibitor (net sign '-') would usually relieve inhibition. "
                       "Compensation, unmapped routes, dosage and kinetics are not modelled.")}


# ----------------------------------------------------------- structures
def structures(ctx, query: str, pdb_limit: int = 8) -> dict:
    a = Analysis("structures", query)
    rec = an.resolve_gene(ctx, a, query)
    if not rec or not rec.get("protein"):
        return {"query": query, "warnings": a.warnings + ["No UniProt entry; structures need an accession."],
                "source_status": a.source_status}
    acc = rec["protein"]["accession"]
    sc = StructureClient(ctx.http)
    out = {"query": query, "symbol": rec["symbol"], "accession": acc,
           "protein_name": rec["protein"]["protein_name"], "warnings": list(a.warnings),
           "source_status": dict(a.source_status), "predicted": None, "experimental": [],
           "experimental_total": 0, "features": [], "pathways": []}
    try:
        out["predicted"] = sc.alphafold(acc)
        out["source_status"]["AlphaFold DB"] = "ok"
    except SourceError as exc:
        out["source_status"]["AlphaFold DB"] = f"failed: {exc.message}"
    try:
        pdb = sc.pdb_entries(acc, pdb_limit)
        out["experimental"], out["experimental_total"] = pdb["entries"], pdb["total"]
        out["source_status"]["RCSB PDB"] = "ok"
    except SourceError as exc:
        out["source_status"]["RCSB PDB"] = f"failed: {exc.message}"
    try:
        feats = ctx.uniprot.features(acc)
        keep = {"Domain", "Region", "DNA binding", "Zinc finger", "Motif", "Binding site", "Active site",
                "Modified residue", "Natural variant", "Mutagenesis"}
        for f in feats["features"]:
            if f["type"] not in keep:
                continue
            level, why = ev.classify_eco(f["evidences"], rec["protein"]["reviewed"])
            out["features"].append({"type": f["type"], "start": f["start"], "end": f["end"],
                                    "description": f["description"] or f["ligand"], "ligand": f["ligand"],
                                    "evidence": level, "code": ev.SHORT[level], "basis": why,
                                    "alternatives": f["alternatives"], "original": f["original"]})
        out["sequence_length"] = len(feats["sequence"])
    except SourceError as exc:
        out["warnings"].append(f"UniProt features unavailable ({exc.message}).")
    try:
        out["pathways"] = [dict(p, source="Reactome") for p in
                           ctx.reactome.pathways_for_uniprot(acc, ctx.taxid)[:15]]
    except SourceError:
        pass
    out["notes"] = ["AlphaFold models are computational predictions; colour by pLDDT shows per-residue "
                    "confidence (<50 very low, 50-70 low, 70-90 confident, >90 very high).",
                    "PDB entries are experimental; residues are mapped to UniProt numbering through SIFTS "
                    "so domain and site overlays line up. Unmapped residues are drawn grey.",
                    "A structure may contain only a fragment, a mutant, or a complex; check the title."]
    return out


def structure_coords(ctx, kind: str, ident: str, accession: str) -> dict:
    return StructureClient(ctx.http).ca_trace(kind, ident, accession)


# ----------------------------------------------------------- expression
def expression(ctx, symbol: str, context: str = "") -> dict:
    xc = ExpressionClient(ctx.http)
    out = {"symbol": symbol, "gtex": None, "hpa": None, "geo": None, "source_status": {}}
    for key, label, fn in (("gtex", "GTEx", lambda: xc.gtex_tissues(symbol)),
                           ("hpa", "Human Protein Atlas", lambda: xc.hpa_specificity(symbol)),
                           ("geo", "GEO", lambda: geo_datasets(ctx.ncbi, symbol, context))):
        try:
            out[key] = fn()
            out["source_status"][label] = "ok" if out[key] else "no record"
        except SourceError as exc:
            out["source_status"][label] = f"failed: {exc.message}"
    out["notes"] = ["Expression shows a gene is transcribed in a tissue or cell type. It does not show "
                    "that a pathway is active there, and RNA levels do not equal protein activity.",
                    "GEO entries are datasets for follow-up analysis, not findings."]
    return out


# ------------------------------------------------------ cross-pathway
def enrichment(ctx, genes: list[str]) -> dict:
    out = {"genes": genes, "reactome": None, "kegg_shared": [], "source_status": {}}
    try:
        out["reactome"] = ctx.reactome.overrepresentation(genes)
        out["source_status"]["Reactome AnalysisService"] = "ok"
    except SourceError as exc:
        out["source_status"]["Reactome AnalysisService"] = f"failed: {exc.message}"
    if ctx.use_kegg:
        a = Analysis("enrichment", ",".join(genes))
        names = ctx.kegg_names(a)
        member: dict = {}
        for g in genes:
            rec = an.resolve_gene(ctx, a, g)
            if rec and rec.get("gene_id"):
                for pid in an.attempt(a, "KEGG", lambda r=rec: ctx.kegg.gene_pathways(r["gene_id"], ctx.org), []) or []:
                    member.setdefault(pid, []).append(rec["symbol"])
        out["kegg_shared"] = sorted(({"id": p, "name": names.get(p, p), "genes": gs, "count": len(gs)}
                                     for p, gs in member.items() if len(gs) > 1),
                                    key=lambda r: (-r["count"], r["id"]))[:30]
        out["source_status"].update(a.source_status)
    else:
        out["source_status"]["KEGG"] = "not queried (disabled)"
    out["notes"] = ["Reactome p-values come from its over-representation test against all human genes; "
                    "they indicate shared annotation, not co-regulation.",
                    "KEGG 'shared maps' counts genes drawn on the same map, not interactions between them."]
    return out
