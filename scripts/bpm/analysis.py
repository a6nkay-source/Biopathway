"""The five analyses. Each returns a models.Analysis and never raises on a
source outage: failures are recorded in Analysis.source_status / warnings.

Design rule: an Edge is only created from a database record that states the
relationship (KEGG relation, KEGG/Reactome reaction, Reactome membership,
STRING association, UniProt feature, ClinVar assertion). PubMed search hits
are listed as reading material and never become edges.
"""

from __future__ import annotations

import difflib
import re
from collections import deque

from . import evidence as ev
from .http import HttpClient, SourceError
from .integrations import KeggClient, NcbiClient, ReactomeClient, StringClient, UniProtClient
from .integrations.kegg import is_pathway_id, normalise_pathway_id, pathway_url
from .integrations.reactome import url_for as reactome_url
from .integrations.stringdb import network_url
from .models import Analysis, Citation, Edge, Node, Statement

KEGG_ORG = {9606: "hsa", 10090: "mmu", 10116: "rno", 7955: "dre", 7227: "dme",
            6239: "cel", 559292: "sce"}
REACTOME_SPECIES = {9606: "Homo sapiens", 10090: "Mus musculus", 10116: "Rattus norvegicus",
                    7955: "Danio rerio", 7227: "Drosophila melanogaster",
                    6239: "Caenorhabditis elegans", 559292: "Saccharomyces cerevisiae"}
UNIPROT_ACC = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})(-\d+)?$")
REACTOME_ID = re.compile(r"^R-[A-Z]{3}-\d+$")
STOPWORDS = {"pathway", "pathways", "signaling", "signalling", "the", "of", "and", "in",
             "cascade", "process", "metabolism", "biological"}


class Context:
    """Clients plus organism settings, shared by all analyses in one run."""

    def __init__(self, http: HttpClient | None = None, taxid: int = 9606, use_kegg: bool = True):
        self.http = http or HttpClient()
        self.taxid = taxid
        self.org = KEGG_ORG.get(taxid)
        self.species = REACTOME_SPECIES.get(taxid, "Homo sapiens")
        self.ncbi = NcbiClient(self.http)
        self.uniprot = UniProtClient(self.http)
        self.reactome = ReactomeClient(self.http)
        self.string = StringClient(self.http)
        self.kegg = KeggClient(self.http)
        self.use_kegg = use_kegg and self.org is not None
        self._kegg_names: dict | None = None

    def kegg_names(self, a: Analysis) -> dict:
        if self._kegg_names is None:
            rows = attempt(a, "KEGG", lambda: self.kegg.list_pathways(self.org), None)
            if rows is None:
                return {}
            self._kegg_names = {r["id"]: r["name"] for r in rows}
        return self._kegg_names


def attempt(a: Analysis, label: str, fn, default=None):
    try:
        result = fn()
    except SourceError as exc:
        a.fail(label, exc.message)
        return default
    a.ok(label)
    return result


def _start(ctx: Context, kind: str, query: str) -> tuple[Analysis, int]:
    a = Analysis(kind, query)
    if not ctx.use_kegg:
        a.source_status["KEGG"] = "not queried (disabled or organism not mapped)"
    return a, len(ctx.http.log)


def _finish(ctx: Context, a: Analysis, log_start: int) -> Analysis:
    a.requests = ctx.http.log[log_start:]
    return a


# ------------------------------------------------------------- citations
def cite_gene(g):
    return Citation("NCBI Gene", g["gene_id"], g["url"], f"{g['symbol']}: {g['description']}")


def cite_uniprot(p):
    return Citation("UniProt", p["accession"], p["url"], f"{p['symbol']}: {p['protein_name']}")


def cite_kegg(pid, name=""):
    return Citation("KEGG", pid, pathway_url(pid), name)


def cite_reactome(st, name=""):
    return Citation("Reactome", st, reactome_url(st), name)


def cite_string(a, b, taxid):
    return Citation("STRING", f"{a}--{b}", network_url([a, b], taxid), f"STRING association {a}-{b}")


def cite_pmid(pmid, title=""):
    return Citation("PubMed", f"PMID:{pmid}", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", title)


def cite_clinvar(rec):
    return Citation("ClinVar", rec["accession"] or rec["uid"], rec["url"], rec["title"])


# --------------------------------------------------------- name matching
def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def rank_names(query: str, items: list[dict], boost_ids: set | None = None) -> list[dict]:
    """Rank {id,name} items against free text. Returns items with a 'match' score.

    Score = fraction of query tokens found in the name (+0.25 when the item
    contains every focus gene, +0.5 for an exact name). Items under 0.5 are
    dropped: a weak lexical match is not a resolution.
    """
    q = _tokens(query)
    if not q:
        return []
    out = []
    for item in items:
        name_tokens = set(_tokens(item["name"]))
        hit = sum(1 for t in q if t in name_tokens) / len(q)
        if hit == 0:
            continue
        score = hit
        if item["name"].strip().lower() == query.strip().lower():
            score += 0.5
        if boost_ids and item["id"] in boost_ids:
            score += 0.25
        score += 0.01 * difflib.SequenceMatcher(None, query.lower(), item["name"].lower()).ratio()
        if hit >= 0.5:
            out.append(dict(item, match=round(score, 3)))
    return sorted(out, key=lambda x: -x["match"])


# --------------------------------------------------------- gene resolution
def resolve_gene(ctx: Context, a: Analysis, query: str) -> dict | None:
    q = query.strip()
    protein = None
    symbol = q
    if UNIPROT_ACC.match(q):
        protein = attempt(a, "UniProt", lambda: ctx.uniprot.get_protein(q))
        if protein and protein["symbol"]:
            symbol = protein["symbol"]
    gene = attempt(a, "NCBI Gene", lambda: ctx.ncbi.find_gene(symbol, ctx.taxid))
    if gene:
        symbol = gene["symbol"]
    if protein is None:
        protein = attempt(a, "UniProt", lambda: ctx.uniprot.find_protein(symbol, ctx.taxid))
    if gene is None and protein is None:
        a.warnings.append(f"Could not resolve '{q}' in NCBI Gene or UniProt for taxon {ctx.taxid}.")
        return None
    gene_id = gene["gene_id"] if gene else ((protein or {}).get("xrefs", {}).get("GeneID") or [None])[0]
    if gene and gene["matched_by"] == "alias":
        a.warnings.append(f"'{q}' was matched to {symbol} through an alias, not an official "
                          "symbol; confirm this is the intended gene.")
    if protein and not protein["reviewed"]:
        a.warnings.append(f"{symbol}: only an unreviewed (TrEMBL) UniProt entry was found.")
    a.resolved[symbol] = {
        "input": q, "symbol": symbol, "ncbi_gene_id": gene_id,
        "name": (gene or {}).get("description") or (protein or {}).get("protein_name", ""),
        "location": (gene or {}).get("map_location", ""),
        "aliases": (gene or {}).get("aliases", []),
        "uniprot": (protein or {}).get("accession"),
        "uniprot_reviewed": (protein or {}).get("reviewed"),
    }
    return {"symbol": symbol, "gene_id": gene_id, "gene": gene, "protein": protein}


def _strip_pubmed_refs(text: str) -> str:
    text = re.sub(r"\s*\((?:PubMed|By similarity|Ref\.)[^()]*\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _short(text: str, limit: int = 700) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def add_function_statements(a: Analysis, rec: dict) -> None:
    sym, p, g = rec["symbol"], rec["protein"], rec["gene"]
    if p and p["functions"]:
        for f in p["functions"][:2]:
            level, why = ev.classify_eco(f["evidences"], p["reviewed"])
            pmids = [x["id"] for x in f["evidences"] if x.get("source") == "PubMed"][:4]
            a.statements.append(Statement(
                f"{sym} function (UniProt {p['accession']}, {why}): {_short(_strip_pubmed_refs(f['text']))}",
                level, [cite_uniprot(p)] + [cite_pmid(i) for i in pmids], "Function"))
    elif g and g.get("summary"):
        a.statements.append(Statement(f"{sym} (NCBI RefSeq summary): {_short(g['summary'])}",
                                      ev.CURATED, [cite_gene(g)], "Function"))
    if p and p["go_bp"]:
        by_level: dict[str, list[str]] = {}
        for term in p["go_bp"]:
            level, _ = ev.classify_go(term["evidence"])
            by_level.setdefault(level, []).append(term["term"])
        for level in ev.LEVELS:
            terms = by_level.get(level)
            if terms:
                shown = ", ".join(terms[:12]) + (f" (+{len(terms) - 12} more)" if len(terms) > 12 else "")
                a.statements.append(Statement(f"{sym} GO biological process annotations: {shown}",
                                              level, [cite_uniprot(p)], "Biological process"))


def add_string_edges(ctx: Context, a: Analysis, rows: list[dict]) -> None:
    for r in rows:
        level, why = ev.classify_string(r["scores"])
        for name in (r["a"], r["b"]):
            a.add_node(Node(name, name, "gene"))
        a.add_edge(Edge(r["a"], r["b"], "association", level, directed=False, detail=why,
                        citations=[cite_string(r["a"], r["b"], ctx.taxid)],
                        scores={"combined": r["scores"]["score"], "experiments": r["scores"]["escore"],
                                "databases": r["scores"]["dscore"], "textmining": r["scores"]["tscore"]}))
    if rows:
        a.notes.append("STRING edges are undirected functional associations scored per evidence "
                       "channel. They do not establish direct physical binding, direction or "
                       "activating/inhibiting effect.")


def add_literature(ctx: Context, a: Analysis, term: str, retmax: int = 5, basis: str = "PubMed search") -> None:
    recs = attempt(a, "PubMed", lambda: ctx.ncbi.pubmed_search(term, retmax), [])
    for r in recs or []:
        a.literature.append(dict(r, basis=f"{basis}: {term}", evidence=ev.LITERATURE))


def add_cited_literature(ctx: Context, a: Analysis, pmids: list[str], basis: str, limit: int = 5) -> None:
    if not pmids:
        return
    recs = attempt(a, "PubMed", lambda: ctx.ncbi.pubmed_summaries(pmids[:limit]), [])
    for r in recs or []:
        a.literature.append(dict(r, basis=basis, evidence=ev.CURATED))


# ============================================================== 1. GENE
def analyze_gene(ctx: Context, queries: list[str], partners: int = 15) -> Analysis:
    a, start = _start(ctx, "gene", ", ".join(queries))
    recs = [r for r in (resolve_gene(ctx, a, q) for q in queries) if r]
    if not recs:
        return _finish(ctx, a, start)
    names = ctx.kegg_names(a) if ctx.use_kegg else {}
    kegg_sets = []
    for rec in recs:
        sym = rec["symbol"]
        a.add_node(Node(sym, sym, "gene", focus=True,
                        xrefs={"ncbi_gene": rec["gene_id"], "uniprot": (rec["protein"] or {}).get("accession")}))
        add_function_statements(a, rec)
        if rec["protein"]:
            for p in attempt(a, "Reactome", lambda: ctx.reactome.pathways_for_uniprot(
                    rec["protein"]["accession"], ctx.taxid), []) or []:
                a.pathways.append({"source": "Reactome", "gene": sym, "id": p["id"], "name": p["name"],
                                   "url": p["url"], "evidence": ev.classify_reactome(p["inferred"])[0]})
        if ctx.use_kegg and rec["gene_id"]:
            pids = attempt(a, "KEGG", lambda: ctx.kegg.gene_pathways(rec["gene_id"], ctx.org), []) or []
            kegg_sets.append(set(pids))
            for pid in pids:
                a.pathways.append({"source": "KEGG", "gene": sym, "id": pid, "name": names.get(pid, pid),
                                   "url": pathway_url(pid), "evidence": ev.CURATED})
    symbols = [r["symbol"] for r in recs]
    if len(symbols) == 1:
        rows = attempt(a, "STRING", lambda: ctx.string.partners(symbols[0], ctx.taxid, partners), [])
        add_literature(ctx, a, f"{symbols[0]}[tiab] AND review[pt]", 5)
    else:
        rows = attempt(a, "STRING", lambda: ctx.string.network(symbols, ctx.taxid), [])
        add_literature(ctx, a, " AND ".join(f"{s}[tiab]" for s in symbols), 5)
        if len(kegg_sets) == len(symbols) and kegg_sets:
            shared = sorted(set.intersection(*kegg_sets))
            if shared:
                a.notes.append("KEGG maps containing all queried genes: " +
                               "; ".join(f"{p} {names.get(p, '')}".strip() for p in shared[:12]) +
                               ". Run `pathway <id> --genes ...` to reconstruct the directed relations.")
    add_string_edges(ctx, a, rows or [])
    a.diagram_note = ("Undirected STRING functional-association network around the queried gene(s); "
                      "line colour = evidence class. For directed signalling use the pathway analysis.")
    return _finish(ctx, a, start)


# =========================================================== 2. PATHWAY
_REL_MAIN = [("inhibition", "inhibition"), ("repression", "inhibition"),
             ("activation", "activation"), ("expression", "expression"),
             ("binding/association", "binding"), ("dissociation", "dissociation"),
             ("state change", "state change"), ("missing interaction", "missing interaction"),
             ("indirect effect", "indirect effect")]
_MODIFIERS = {"phosphorylation": "+p", "dephosphorylation": "-p", "ubiquitination": "+u",
              "glycosylation": "+g", "methylation": "+m"}


def _relation_from_subtypes(subtypes: list[str]) -> tuple[str, list[str]]:
    mods = [_MODIFIERS[s] for s in subtypes if s in _MODIFIERS]
    for name, rel in _REL_MAIN:
        if name in subtypes:
            return rel, mods
    named = [s for s in subtypes if s in _MODIFIERS]
    if named:   # e.g. KGML 'phosphorylation' with no activation/inhibition subtype
        return named[0], mods[1:]
    return "relation", mods


def _fmt_members(symbols: list[str], focus: set) -> str:
    ordered = sorted(symbols, key=lambda s: (s not in focus, symbols.index(s)))
    shown = "/".join(ordered[:3])
    return shown + (f" (+{len(ordered) - 3})" if len(ordered) > 3 else "")


def resolve_kegg_pathway(ctx: Context, a: Analysis, query: str, focus_ids: list[str]) -> str | None:
    if is_pathway_id(query):
        return normalise_pathway_id(query, ctx.org)
    names = ctx.kegg_names(a)
    if not names:
        return None
    boost = None
    if focus_ids:
        sets = [set(attempt(a, "KEGG", lambda g=g: ctx.kegg.gene_pathways(g, ctx.org), []) or [])
                for g in focus_ids]
        boost = set.intersection(*sets) if sets else None
    ranked = rank_names(query, [{"id": k, "name": v} for k, v in names.items()], boost)
    if not ranked:
        a.warnings.append(f"No KEGG {ctx.org} pathway name matches '{query}'. Pass a KEGG id instead.")
        return None
    if len(ranked) > 1:
        a.notes.append("KEGG name candidates (best first): " + "; ".join(
            f"{r['id']} {r['name']} (score {r['match']})" for r in ranked[:5]) +
            ". Re-run with an explicit id if the chosen map is not the intended one.")
    return ranked[0]["id"]


def _all_shortest_paths(adj: dict, src: str, dst: str, max_len: int = 8) -> list[list[str]]:
    parents: dict[str, list[str]] = {src: []}
    depth = {src: 0}
    queue = deque([src])
    while queue:
        node = queue.popleft()
        if node == dst or depth[node] >= max_len:
            continue
        for nxt in adj.get(node, ()):
            if nxt not in depth:
                depth[nxt] = depth[node] + 1
                parents[nxt] = [node]
                queue.append(nxt)
            elif depth[nxt] == depth[node] + 1:
                parents[nxt].append(node)
    if dst not in depth:
        return []
    paths: list[list[str]] = []

    def walk(node, acc):
        if len(paths) >= 20:
            return
        if node == src:
            paths.append([src] + acc[::-1])
            return
        for p in parents[node]:
            walk(p, acc + [node])
    walk(dst, [])
    return paths


def kegg_signalling_graph(ctx: Context, a: Analysis, pid: str, focus: dict, hops: int = 1) -> None:
    """Reconstruct directed relations from a KEGG map (KGML) into `a`.

    focus: symbol -> NCBI gene id. With >= 2 focus genes the diagram keeps every
    shortest directed route between them; with one, its `hops` neighbourhood.
    """
    info = attempt(a, "KEGG", lambda: ctx.kegg.pathway_info(pid))
    kg = attempt(a, "KEGG", lambda: ctx.kegg.kgml(pid))
    if not info or not kg:
        a.warnings.append(f"KEGG map {pid} could not be retrieved; no KEGG relations were reconstructed.")
        return
    title = info["name"] or kg["title"]
    a.pathways.append({"source": "KEGG", "id": pid, "name": title, "url": pathway_url(pid),
                       "evidence": ev.CURATED, "class": info["class"]})
    symbol_of = info["genes"]
    focus_syms = set(focus)
    focus_ids = {str(v) for v in focus.values() if v}
    # Symbol fallback when NCBI was unavailable: use KEGG's own gene table.
    for sym in focus_syms:
        if not focus.get(sym):
            focus_ids |= {gid for gid, s in symbol_of.items() if s.upper() == sym.upper()}
    entries = kg["entries"]
    cpd_ids = [n.split(":")[1] for e in entries.values() if e["type"] == "compound"
               for n in e["names"] if ":" in n]
    cpd_names = attempt(a, "KEGG", lambda: ctx.kegg.compound_names(cpd_ids), {}) or {} if cpd_ids else {}

    node_of: dict[str, str | None] = {}

    def gene_ids(e):
        return [n.split(":")[1] for n in e["names"] if n.startswith(f"{ctx.org}:")]

    def entry_node(eid: str):
        if eid in node_of:
            return node_of[eid]
        e = entries.get(eid)
        nid = None
        if e is None:
            pass
        elif e["type"] == "gene":
            ids = gene_ids(e)
            if ids:
                syms = [symbol_of.get(i, i) for i in ids]
                nid = "g:" + "+".join(sorted(ids))
                a.add_node(Node(nid, _fmt_members(syms, focus_syms), "gene",
                                xrefs={"kegg_genes": [f"{ctx.org}:{i}" for i in ids], "members": syms},
                                focus=bool(focus_ids & set(ids))))
        elif e["type"] == "group":
            parts = [entry_node(c) for c in e["components"]]
            parts = [p for p in parts if p]
            if parts:
                nid = "cx:" + "|".join(sorted(parts))
                labels = [a.nodes[p].label for p in parts]
                members = [m for p in parts for m in a.nodes[p].xrefs.get("members", [])]
                kg_genes = [g for p in parts for g in a.nodes[p].xrefs.get("kegg_genes", [])]
                a.add_node(Node(nid, ":".join(labels), "complex",
                                xrefs={"components": parts, "members": members, "kegg_genes": kg_genes},
                                focus=any(a.nodes[p].focus for p in parts)))
        elif e["type"] == "compound":
            cid = e["names"][0].split(":")[-1] if e["names"] else eid
            nid = f"c:{cid}"
            a.add_node(Node(nid, cpd_names.get(cid, e["label"] or cid), "compound", xrefs={"kegg": cid}))
        elif e["type"] == "map":
            label = e["label"]
            if label and not label.startswith("TITLE:"):
                nid = "map:" + (e["names"][0].replace("path:", "") if e["names"] else eid)
                a.add_node(Node(nid, label, "pathway", xrefs={"kegg": nid[4:]}))
        node_of[eid] = nid
        return nid

    all_edges: list[Edge] = []
    for r in kg["relations"]:
        if r["type"] == "ECrel":
            continue
        src, dst = entry_node(r["entry1"]), entry_node(r["entry2"])
        if not src or not dst or src == dst:
            continue
        if r["type"] == "maplink":
            rel, mods = "pathway link", []
        else:
            rel, mods = _relation_from_subtypes(r["subtypes"])
        via = [cpd_names.get((entries.get(c, {}).get("names") or ["x:"])[0].split(":")[-1], "")
               for c in r["compound_entries"]]
        mods += [f"via {v}" for v in via if v]
        level, why = ev.classify_kegg(r["subtypes"])
        undirected_rel = rel in ("binding", "dissociation")
        all_edges.append(Edge(src, dst, rel, level, modifiers=mods, directed=not undirected_rel,
                              indirect=("indirect effect" in r["subtypes"] or rel == "pathway link"),
                              detail=f"{why}; KGML {r['type']} [{', '.join(r['subtypes']) or 'no subtype'}]",
                              citations=[cite_kegg(pid, title)]))
    # KGML lists some gene entries that take part in no relation; they still count for membership.
    for eid, e in entries.items():
        if e["type"] == "gene" and focus_ids & set(gene_ids(e)):
            entry_node(eid)

    sym_nodes: dict[str, set] = {}
    for sym in sorted(focus_syms):
        gid = f"{ctx.org}:{focus.get(sym)}"
        hits = {n.id for n in a.nodes.values() if n.kind in ("gene", "complex")
                and (sym in n.xrefs.get("members", []) or gid in n.xrefs.get("kegg_genes", []))}
        if hits:
            sym_nodes[sym] = hits
        else:
            a.warnings.append(f"{sym} is not drawn in KEGG map {pid}; it is not part of this "
                              "reconstruction (absence from a map is not evidence of no role).")

    # Binding/dissociation are symmetric in KGML, so they are traversable both ways.
    adj: dict[str, set] = {}
    undirected: dict[str, set] = {}
    for e in all_edges:
        adj.setdefault(e.source, set()).add(e.target)
        if not e.directed:
            adj.setdefault(e.target, set()).add(e.source)
        undirected.setdefault(e.source, set()).add(e.target)
        undirected.setdefault(e.target, set()).add(e.source)

    def edge_between(u, v):
        for e in all_edges:
            if (e.source, e.target) == (u, v) or (not e.directed and (e.target, e.source) == (u, v)):
                return e
        return None

    selected: list[Edge] = []
    syms = sorted(sym_nodes)
    if len(syms) >= 2:
        keep: set[int] = set()
        missing = []
        for s_sym in syms:
            for t_sym in syms:
                if s_sym == t_sym:
                    continue
                sources, targets = sym_nodes[s_sym], sym_nodes[t_sym] - sym_nodes[s_sym]
                if not targets:
                    continue
                graph = {k: set(v) for k, v in adj.items()}
                graph["__S__"] = set(sources)
                for t in targets:
                    graph.setdefault(t, set()).add("__T__")
                paths = [p[1:-1] for p in _all_shortest_paths(graph, "__S__", "__T__", 10)]
                paths = [p for p in paths if len(p) >= 2]
                if not paths:
                    missing.append(f"{s_sym} -> {t_sym}")
                    continue
                for path in paths:
                    for u, v in zip(path, path[1:]):
                        e = edge_between(u, v)
                        if e is not None:
                            keep.add(id(e))
                path = paths[0]
                steps = []
                for u, v in zip(path, path[1:]):
                    e = edge_between(u, v)
                    rel = (" ".join([e.relation] + e.modifiers) + ("" if e.directed else ", undirected")) if e else "?"
                    steps.append(f"-[{rel}]-> {a.nodes[v].label}")
                a.statements.append(Statement(
                    f"{s_sym} to {t_sym}, shortest directed route in KEGG {pid} ({title}): "
                    f"{a.nodes[path[0]].label} " + " ".join(steps) +
                    (f" ({len(paths)} equally short routes; all are drawn)" if len(paths) > 1 else "") +
                    ". Each step is a KEGG-drawn relation; a route is a curated summary and may skip "
                    "intermediates.", ev.CURATED, [cite_kegg(pid, title)], "Mechanism"))
        selected = [e for e in all_edges if id(e) in keep]
        if missing:
            a.notes.append("No directed KEGG route for: " + "; ".join(missing[:10]) +
                           ". This reflects the map's drawing, not proof that no regulation exists.")
    if len(syms) == 1 or (len(syms) >= 2 and not selected):
        centre = set().union(*(sym_nodes[s] for s in syms))
        seen = set(centre)
        frontier = set(centre)
        for _ in range(max(1, hops)):
            frontier = {n for f in frontier for n in undirected.get(f, ())} - seen
            seen |= frontier
        selected = [e for e in all_edges if e.source in seen and e.target in seen
                    and ({e.source, e.target} & centre or hops > 1)]
    elif not syms:
        selected = all_edges
    for e in selected:
        a.add_edge(e)
    used = {e.source for e in a.edges} | {e.target for e in a.edges}
    covered = {m for nid in used for m in a.nodes[nid].xrefs.get("members", [])}
    for nid in list(a.nodes):
        node = a.nodes[nid]
        if nid in used:
            continue
        if not node.focus or (set(node.xrefs.get("members", [])) & focus_syms & covered):
            del a.nodes[nid]
    a.notes.append(f"KEGG {pid} contains {len(all_edges)} reconstructable relations; "
                   f"{len(a.edges)} are kept for this question.")
    add_cited_literature(ctx, a, info["pmids"], f"reference of KEGG {pid}")


def analyze_pathway(ctx: Context, query: str, genes: list[str] = (), hops: int = 1) -> Analysis:
    a, start = _start(ctx, "pathway", query + (f" | genes: {', '.join(genes)}" if genes else ""))
    recs = [r for r in (resolve_gene(ctx, a, g) for g in genes) if r]
    if REACTOME_ID.match(query.strip()) or not ctx.use_kegg:
        if not ctx.use_kegg and not REACTOME_ID.match(query.strip()):
            a.notes.append("KEGG disabled: falling back to a Reactome reconstruction.")
        _finish(ctx, a, start)
        return analyze_process(ctx, query, genes, _analysis=a, _start_index=start)
    focus = {r["symbol"]: r["gene_id"] for r in recs}
    pid = resolve_kegg_pathway(ctx, a, query, [g for g in focus.values() if g])
    if pid:
        kegg_signalling_graph(ctx, a, pid, focus, hops)
    # Reactome cross-reference: the focus genes' own Reactome pathways matching the query.
    for r in recs:
        if not r["protein"]:
            continue
        rows = attempt(a, "Reactome", lambda: ctx.reactome.pathways_for_uniprot(
            r["protein"]["accession"], ctx.taxid), []) or []
        for p in rank_names(query, rows)[:5]:
            a.pathways.append({"source": "Reactome", "gene": r["symbol"], "id": p["id"],
                               "name": p["name"], "url": p["url"],
                               "evidence": ev.classify_reactome(p["inferred"])[0]})
    if recs:
        add_literature(ctx, a, " AND ".join(f"{r['symbol']}[tiab]" for r in recs[:3]) +
                       f" AND ({' OR '.join(_tokens(query)) or query})", 5)
    a.diagram_note = ("Directed relations redrawn from the KEGG map (KGML). Arrow = activation, "
                      "x = inhibition, dashed = expression/indirect. Multi-gene boxes are paralog "
                      "groups that KEGG draws as one node.")
    return _finish(ctx, a, start)


# =========================================================== 3. PROCESS
def resolve_reactome(ctx: Context, a: Analysis, query: str) -> dict | None:
    q = query.strip()
    if REACTOME_ID.match(q):
        d = attempt(a, "Reactome", lambda: ctx.reactome.detail(q))
        if not d:
            a.warnings.append(f"Reactome has no record {q}.")
        return d
    hits = attempt(a, "Reactome", lambda: ctx.reactome.search_pathways(q, ctx.species), []) or []
    if not hits:
        a.warnings.append(f"Reactome search found no {ctx.species} pathway for '{q}'.")
        return None
    exact = [h for h in hits if h["name"].lower() == q.lower()]
    best = (exact or hits)[0]
    if len(hits) > 1:
        a.notes.append("Reactome candidates: " + "; ".join(f"{h['id']} {h['name']}" for h in hits[:5]) + ".")
    return attempt(a, "Reactome", lambda: ctx.reactome.detail(best["id"]))


def analyze_process(ctx: Context, query: str, genes: list[str] = (), max_reactions: int = 15,
                    _analysis: Analysis | None = None, _start_index: int | None = None) -> Analysis:
    if _analysis is None:
        a, start = _start(ctx, "process", query + (f" | genes: {', '.join(genes)}" if genes else ""))
        recs = [r for r in (resolve_gene(ctx, a, g) for g in genes) if r]
    else:
        a, start = _analysis, _start_index
        a.kind = "process"
        recs = [{"symbol": s, "gene_id": v["ncbi_gene_id"],
                 "protein": {"accession": v["uniprot"]} if v.get("uniprot") else None}
                for s, v in a.resolved.items()]
    root = resolve_reactome(ctx, a, query)
    if root:
        rid, rname = root["id"], root["name"]
        root_level, root_why = ev.classify_reactome(root["inferred"])
        a.add_node(Node(rid, rname, "pathway", xrefs={"reactome": rid}))
        a.pathways.append({"source": "Reactome", "id": rid, "name": rname, "url": root["url"],
                           "evidence": root_level})
        if root.get("summary"):
            a.statements.append(Statement(f"{rname} (Reactome summary): {_short(root['summary'], 600)}",
                                          root_level, [cite_reactome(rid, rname)], "Process overview"))
        children = [c for c in root["children"] if c["type"] == "Pathway"]
        for c in children:
            a.add_node(Node(c["id"], c["name"], "pathway", xrefs={"reactome": c["id"]}))
            lvl, why = ev.classify_reactome(c["inferred"])
            a.add_edge(Edge(rid, c["id"], "contains", lvl, detail=why, citations=[cite_reactome(rid, rname)]))
        n_reactions = sum(1 for c in root["children"] if c["type"] != "Pathway")
        if n_reactions:
            a.notes.append(f"{rname} also has {n_reactions} reactions directly under it (not drawn).")

        descendants = attempt(a, "Reactome", lambda: ctx.reactome.contained_events(rid), []) or []
        desc_ids = {e["id"] for e in descendants}
        child_desc: dict[str, set] = {}
        for r in recs:
            sym = r["symbol"]
            a.add_node(Node(sym, sym, "gene", focus=True))
            if not r.get("protein"):
                a.warnings.append(f"{sym}: no UniProt accession, so Reactome membership could not be checked.")
                continue
            gp = attempt(a, "Reactome", lambda: ctx.reactome.pathways_for_uniprot(
                r["protein"]["accession"], ctx.taxid), []) or []
            inside = [p for p in gp if p["id"] in desc_ids or p["id"] == rid]
            outside = [p for p in gp if p not in inside]
            for p in (inside + outside)[:25]:
                a.pathways.append({"source": "Reactome", "gene": sym, "id": p["id"], "name": p["name"],
                                   "url": p["url"], "evidence": ev.classify_reactome(p["inferred"])[0],
                                   "note": f"inside {rid}" if p in inside else "outside this process"})
            if outside:
                a.notes.append(f"{sym} has {len(outside)} Reactome pathways outside {rname} (listed in "
                               "section 3). Roles there are not part of this process reconstruction.")
            if not inside:
                a.warnings.append(f"Reactome does not place {sym} inside {rname} ({rid}). Any link "
                                  f"between {sym} and this process is not supported by Reactome curation.")
                continue
            for p in inside[:8]:
                a.add_node(Node(p["id"], p["name"], "pathway", xrefs={"reactome": p["id"]}))
                lvl, why = ev.classify_reactome(p["inferred"])
                a.add_edge(Edge(sym, p["id"], "participates in", lvl, detail=why,
                                citations=[cite_reactome(p["id"], p["name"])]))
                if p["id"] == rid or any(p["id"] == c["id"] for c in children):
                    continue
                parent = None
                for c in children:
                    if c["id"] not in child_desc:
                        child_desc[c["id"]] = {e["id"] for e in attempt(
                            a, "Reactome", lambda c=c: ctx.reactome.contained_events(c["id"]), []) or []}
                    if p["id"] in child_desc[c["id"]]:
                        parent = c
                        break
                anc = parent["id"] if parent else rid
                a.add_edge(Edge(anc, p["id"], "contains", ev.CURATED, indirect=True,
                                detail="Reactome hierarchy; intermediate sub-pathways omitted",
                                citations=[cite_reactome(anc)]))
            if len(inside) > 8:
                a.notes.append(f"{sym} participates in {len(inside)} sub-pathways of {rname}; 8 drawn.")
            pat = re.compile(rf"(?<![A-Za-z0-9]){re.escape(sym)}(?![A-Za-z0-9])")
            reactions = [e for e in descendants if e["type"] != "Pathway" and pat.search(e["name"])]
            for e in reactions[:max_reactions]:
                lvl, why = ev.classify_reactome(e["inferred"])
                a.statements.append(Statement(f"Reactome event {e['id']}: {e['name']}", lvl,
                                              [cite_reactome(e["id"], e["name"])], f"Mechanism ({sym})"))
            if len(reactions) > max_reactions:
                a.notes.append(f"{len(reactions)} Reactome events in {rname} name {sym}; "
                               f"{max_reactions} are listed.")
        add_cited_literature(ctx, a, root.get("pmids", []), f"reference of Reactome {rid}")
    # KEGG cross-reference
    if ctx.use_kegg:
        names = ctx.kegg_names(a)
        for k in rank_names(query, [{"id": i, "name": n} for i, n in names.items()])[:3]:
            entry = {"source": "KEGG", "id": k["id"], "name": k["name"], "url": pathway_url(k["id"]),
                     "evidence": ev.CURATED, "match": k["match"]}
            for r in recs:
                if r.get("gene_id"):
                    members = attempt(a, "KEGG", lambda r=r: ctx.kegg.gene_pathways(r["gene_id"], ctx.org), []) or []
                    entry.setdefault("contains", {})[r["symbol"]] = k["id"] in members
            a.pathways.append(entry)
    if recs:
        add_literature(ctx, a, " AND ".join(f"{r['symbol']}[tiab]" for r in recs[:3]) +
                       f" AND {query}[tiab]", 5)
    a.diagram_note = ("Reactome hierarchy: process -> sub-pathways, and the curated sub-pathways "
                      "each queried gene participates in. Dashed 'contains' skips intermediate levels.")
    return _finish(ctx, a, start)


# ========================================================= 4. METABOLIC
def analyze_metabolic(ctx: Context, query: str, module: str | None = None,
                      genes: list[str] = ()) -> Analysis:
    a, start = _start(ctx, "metabolic", query + (f" | module {module}" if module else ""))
    if not ctx.use_kegg:
        a.warnings.append("Metabolic reconstruction needs KEGG reaction data, which is disabled. "
                          "Use `process` for a Reactome hierarchy instead.")
        return _finish(ctx, a, start)
    recs = [r for r in (resolve_gene(ctx, a, g) for g in genes) if r]
    pid = resolve_kegg_pathway(ctx, a, query, [])
    if not pid:
        return _finish(ctx, a, start)
    info = attempt(a, "KEGG", lambda: ctx.kegg.pathway_info(pid))
    kg = attempt(a, "KEGG", lambda: ctx.kegg.kgml(pid))
    if not info or not kg:
        a.warnings.append(f"KEGG map {pid} could not be retrieved.")
        return _finish(ctx, a, start)
    title = info["name"]
    a.pathways.append({"source": "KEGG", "id": pid, "name": title, "url": pathway_url(pid),
                       "evidence": ev.CURATED, "class": info["class"]})
    if "metabolism" not in info["class"].lower():
        a.warnings.append(f"{pid} is classed '{info['class']}', not metabolism; reaction data may be sparse.")
    if info["modules"] and not module:
        a.notes.append("KEGG modules on this map (use --module to restrict to one route): " +
                       "; ".join(info["modules"][:8]))

    rxn_enzymes: dict[str, set] = {}
    for e in kg["entries"].values():
        if e["type"] == "gene" and e["reactions"]:
            syms = [info["genes"].get(n.split(":")[1], n) for n in e["names"] if n.startswith(f"{ctx.org}:")]
            for rid in e["reactions"]:
                rxn_enzymes.setdefault(rid, set()).update(syms)
    reversible = {rid: r["reversible"] for r in kg["reactions"] for rid in r["ids"]}

    if module:
        mod = attempt(a, "KEGG", lambda: ctx.kegg.module(module.replace(f"{ctx.org}_", "")))
        if not mod:
            a.warnings.append(f"KEGG module {module} not found.")
            return _finish(ctx, a, start)
        steps = mod["reactions"]
        a.pathways.append({"source": "KEGG", "id": mod["id"], "name": mod["name"], "url": mod["url"],
                           "evidence": ev.CURATED})
        cite = Citation("KEGG", mod["id"], mod["url"], mod["name"])
    else:
        steps = [{"ids": r["ids"], "substrates": r["substrates"], "products": r["products"]}
                 for r in kg["reactions"]]
        cite = cite_kegg(pid, title)
    cpds = {c for s in steps for c in s["substrates"] + s["products"]}
    names = attempt(a, "KEGG", lambda: ctx.kegg.compound_names(sorted(cpds)), {}) or {}
    focus_syms = {r["symbol"] for r in recs}
    catalysed_by_focus: dict[str, list] = {}
    for s in steps:
        enzymes = sorted(set().union(*[rxn_enzymes.get(r, set()) for r in s["ids"]]))
        rev = any(reversible.get(r, False) for r in s["ids"])
        for c in s["substrates"] + s["products"]:
            a.add_node(Node(f"c:{c}", names.get(c, c), "compound", xrefs={"kegg": c}))
        for sub in s["substrates"]:
            for prod in s["products"]:
                mods = ([_fmt_members(enzymes, focus_syms)] if enzymes else ["enzyme not mapped in this organism"])
                a.add_edge(Edge(f"c:{sub}", f"c:{prod}", "conversion", ev.CURATED,
                                modifiers=mods + (["reversible"] if rev else []),
                                detail=f"KEGG reaction(s) {', '.join(s['ids'])}; enzymes from KGML gene entries",
                                citations=[cite]))
        for f in focus_syms & set(enzymes):
            catalysed_by_focus.setdefault(f, []).append(
                f"{' + '.join(names.get(c, c) for c in s['substrates'])} -> "
                f"{' + '.join(names.get(c, c) for c in s['products'])} ({', '.join(s['ids'])})")
        if not enzymes:
            a.notes.append(f"No {ctx.org} enzyme is linked to reaction(s) {', '.join(s['ids'])} on this map.")
    for f in focus_syms:
        if f in catalysed_by_focus:
            a.statements.append(Statement(f"{f} is mapped by KEGG as an enzyme for: " +
                                          "; ".join(catalysed_by_focus[f]), ev.CURATED, [cite], "Enzymes"))
        else:
            a.warnings.append(f"{f} is not linked to any drawn reaction of {pid}"
                              + (f"/{module}" if module else "") + ".")
    if module and steps:
        first, last = steps[0]["substrates"][0], steps[-1]["products"][-1]
        a.statements.append(Statement(
            f"KEGG module {cite.id} ({cite.title}) runs {names.get(first, first)} -> "
            f"{names.get(last, last)} in {len(steps)} reaction steps (definition: {mod['definition']}).",
            ev.CURATED, [cite], "Mechanism"))
    hits = attempt(a, "Reactome", lambda: ctx.reactome.search_pathways(query, ctx.species, 3), []) or []
    for h in hits:
        a.pathways.append({"source": "Reactome", "id": h["id"], "name": h["name"], "url": h["url"],
                           "evidence": ev.CURATED})
    add_cited_literature(ctx, a, info["pmids"], f"reference of KEGG {pid}")
    a.diagram_note = ("Metabolite flow from KEGG reaction records: node = compound, edge label = "
                      "enzyme gene(s) KEGG assigns to that reaction in this organism.")
    return _finish(ctx, a, start)


# ========================================================== 5. MUTATION
AA3 = {"Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E",
       "Gly": "G", "His": "H", "Ile": "I", "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F",
       "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V", "Ter": "*", "Sec": "U"}
AA1 = {v: k for k, v in AA3.items()}
_POINT = re.compile(r"^(?:p\.)?\(?([A-Z][a-z]{2}|[A-Z])(\d+)([A-Z][a-z]{2}|[A-Z*X=]|fs\*?\d*|fs)\)?$")
_RANGE = re.compile(r"^(?:p\.)?([A-Z][a-z]{0,2})(\d+)(?:_([A-Z][a-z]{0,2})(\d+))?(del|dup|ins\w*|delins\w*)$")


def parse_protein_change(text: str) -> dict | None:
    t = text.strip().replace(" ", "")
    m = _POINT.match(t)
    if m:
        ref, pos, alt = m.groups()
        ref1 = AA3.get(ref, ref if len(ref) == 1 else None)
        if alt.startswith("fs"):
            alt1, kind = "fs", "frameshift"
        else:
            alt1 = AA3.get(alt, alt if len(alt) == 1 else None)
            alt1 = "*" if alt1 == "X" else alt1
            kind = "nonsense" if alt1 == "*" else "synonymous" if alt1 in ("=", ref1) else "missense"
        if ref1 and alt1:
            pos = int(pos)
            one = f"{ref1}{pos}{alt1}"
            three = f"{AA1.get(ref1, ref1)}{pos}{'fs' if alt1 == 'fs' else AA1.get(alt1, alt1)}"
            return {"ref": ref1, "start": pos, "end": pos, "alt": alt1, "kind": kind,
                    "one_letter": one, "three_letter": three, "hgvs_p": f"p.{three}"}
    m = _RANGE.match(t)
    if m:
        r1, p1, r2, p2, op = m.groups()
        start, end = int(p1), int(p2 or p1)
        return {"ref": AA3.get(r1, r1), "start": start, "end": end, "alt": op, "kind": "in-frame " + op[:3],
                "one_letter": t.replace("p.", ""), "three_letter": t.replace("p.", ""), "hgvs_p": "p." + t.replace("p.", "")}
    return None


def analyze_mutation(ctx: Context, gene: str, change: str) -> Analysis:
    a, start = _start(ctx, "mutation", f"{gene} {change}")
    rec = resolve_gene(ctx, a, gene)
    if not rec:
        return _finish(ctx, a, start)
    sym = rec["symbol"]
    var = parse_protein_change(change)
    vid = f"var:{sym}:{change}"
    a.add_node(Node(sym, sym, "gene", focus=True))
    if var is None:
        a.warnings.append(f"'{change}' is not a recognised protein-level change (expected e.g. R175H, "
                          "p.Arg175His, G12D, E746_A750del). Only a ClinVar text search was run.")
        a.add_node(Node(vid, f"{sym} {change}", "variant", focus=True))
    else:
        a.resolved["variant"] = var
        vid = f"var:{sym}:{var['one_letter']}"
        a.add_node(Node(vid, f"{sym} p.{var['one_letter']}", "variant", focus=True, xrefs={"hgvs_p": var["hgvs_p"]}))
    a.add_edge(Edge(vid, sym, "alters", ev.CURATED, detail="variant is defined on this gene's product",
                    citations=[cite_gene(rec["gene"])] if rec["gene"] else []))

    p = rec["protein"]
    if p and var:
        data = attempt(a, "UniProt", lambda: ctx.uniprot.features(p["accession"]))
        if data:
            seq = data["sequence"]
            pos, ref = var["start"], var["ref"]
            if pos > len(seq):
                a.warnings.append(f"Position {pos} is beyond the {len(seq)}-residue canonical {p['accession']} "
                                  "sequence; the change may use a different isoform's numbering.")
            elif ref and len(ref) == 1 and seq[pos - 1] != ref:
                a.warnings.append(f"Canonical {p['accession']} has {seq[pos - 1]} at position {pos}, not {ref}. "
                                  "The change may refer to another isoform or be mis-specified; "
                                  "feature overlaps below may not apply.")
            else:
                a.statements.append(Statement(
                    f"Reference residue check: {p['accession']} position {pos} is {seq[pos - 1]}, matching the input.",
                    ev.CURATED, [cite_uniprot(p)], "Identifiers"))
            region_types = {"Domain", "Region", "DNA binding", "Zinc finger", "Motif"}
            site_types = {"Binding site", "Active site", "Modified residue"}
            for f in data["features"]:
                overlaps = f["start"] <= var["end"] and f["end"] >= var["start"]
                if not overlaps:
                    continue
                level, why = ev.classify_eco(f["evidences"], p["reviewed"])
                pmids = [x["id"] for x in f["evidences"] if x.get("source") == "PubMed"][:3]
                cites = [cite_uniprot(p)] + [cite_pmid(i) for i in pmids]
                loc = f"{f['start']}-{f['end']}" if f["start"] != f["end"] else str(f["start"])
                if f["type"] in region_types:
                    name = f["description"] or f["type"]
                    rid = f"reg:{f['type']}:{loc}"
                    a.add_node(Node(rid, f"{name} ({loc})", "region"))
                    a.add_edge(Edge(vid, rid, "located in", level, detail=why, citations=cites))
                    a.statements.append(Statement(f"Position {var['start']} lies in UniProt {f['type'].lower()} "
                                                  f"'{name}' ({loc}).", level, cites, "Structural context"))
                elif f["type"] in site_types:
                    what = f["ligand"] or f["description"] or f["type"]
                    a.statements.append(Statement(f"UniProt {f['type'].lower()} at {loc}: {what}. The variant "
                                                  "overlaps this site; any effect on it is not established "
                                                  "by this overlap alone.", level, cites, "Structural context"))
                elif f["type"] == "Natural variant":
                    same = var["alt"] in f["alternatives"]
                    a.statements.append(Statement(
                        f"UniProt natural variant {f['feature_id'] or ''} {f['original']}{loc}"
                        f"{'/'.join(f['alternatives'])}{' (same substitution)' if same else ' (different substitution at this position)'}: "
                        f"{_strip_pubmed_refs(f['description']) or 'no description'}",
                        level, cites, "Reported variant effects" if same else "Other variants at this position"))
                elif f["type"] == "Mutagenesis":
                    same = var["alt"] in f["alternatives"]
                    a.statements.append(Statement(
                        f"UniProt mutagenesis {f['original']}{loc}{'/'.join(f['alternatives'])}"
                        f"{' (same substitution)' if same else ''}: {_strip_pubmed_refs(f['description'])}",
                        level, cites, "Reported variant effects" if same else "Other variants at this position"))
    elif not p:
        a.warnings.append(f"No UniProt entry for {sym}; structural context could not be checked.")

    terms = [change] if var is None else list(dict.fromkeys([var["one_letter"], var["three_letter"]]))
    clin = attempt(a, "ClinVar", lambda: ctx.ncbi.clinvar_search(sym, terms), []) or []
    if var:
        clin = [c for c in clin if var["one_letter"] in c["protein_change"]
                or var["hgvs_p"] in c["title"] or f"({var['hgvs_p']})" in c["title"]]
    clin = [c for c in clin if not c["genes"] or sym in c["genes"]]
    single = [c for c in clin if c["variant_type"] in ("single nucleotide variant", "Deletion",
                                                        "Insertion", "Indel", "Duplication", "Microsatellite")]
    for c in (single or clin)[:4]:
        for label, block in (("germline", c["germline"]), ("oncogenicity", c["oncogenicity"]),
                             ("clinical impact", c["clinical_impact"])):
            if not block["classification"]:
                continue
            level, why = ev.classify_clinvar(block["review_status"])
            conds = block["conditions"][:4]
            a.statements.append(Statement(
                f"ClinVar {c['accession']} ({c['title']}) {label} classification: {block['classification']}"
                f"{' for ' + '; '.join(conds) if conds else ''} [{why}; last evaluated {block['last_evaluated'] or 'n/a'}]. "
                "This is a clinical association, not a mechanism.",
                level, [cite_clinvar(c)], "Clinical assertions"))
            for cond in conds[:3]:
                cid = f"dz:{cond}"
                a.add_node(Node(cid, cond, "condition"))
                a.add_edge(Edge(vid, cid, f"{label}: {block['classification']}", level, detail=why,
                                citations=[cite_clinvar(c)]))
    if not clin:
        a.notes.append(f"ClinVar returned no record for {sym} {change}.")
    if ctx.use_kegg and rec["gene_id"]:
        names = ctx.kegg_names(a)
        pids = attempt(a, "KEGG", lambda: ctx.kegg.gene_pathways(rec["gene_id"], ctx.org), []) or []
        signalling = [pid for pid in pids if not pid[len(ctx.org):].startswith(("05", "01"))]
        for pid in pids:
            a.pathways.append({"source": "KEGG", "gene": sym, "id": pid, "name": names.get(pid, pid),
                               "url": pathway_url(pid), "evidence": ev.CURATED})
        for pid in signalling[:6]:
            a.add_node(Node(f"map:{pid}", names.get(pid, pid), "pathway"))
            a.add_edge(Edge(sym, f"map:{pid}", "member of", ev.CURATED, detail="KEGG gene-pathway link",
                            citations=[cite_kegg(pid, names.get(pid, ""))]))
        if len(signalling) > 6:
            a.notes.append(f"{sym} is in {len(signalling)} KEGG signalling/process maps; 6 drawn.")
    add_literature(ctx, a, f"{sym}[tiab] AND ({' OR '.join(terms)})", 5)
    a.notes.append("Pathway membership is that of the wild-type gene. Whether this variant gains, "
                   "loses or alters a pathway function is only stated where a cited record says so.")
    a.diagram_note = "Variant -> gene, the UniProt regions it falls in, ClinVar conditions, and the gene's KEGG maps."
    return _finish(ctx, a, start)
