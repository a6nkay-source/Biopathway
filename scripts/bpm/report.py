"""Markdown report: the evidence-traceable deliverable Claude builds its answer from."""

from __future__ import annotations

from collections import Counter, OrderedDict

from . import evidence as ev
from .diagram import edge_label, legend_markdown, mermaid
from .models import Analysis


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(a: Analysis, max_edges: int = 50, max_rows: int = 60) -> str:
    cites = a.citations()
    num = {c.key(): i + 1 for i, c in enumerate(cites)}

    def refs(items) -> str:
        ids = sorted({num[c.key()] for c in items if c.key() in num})
        return " ".join(f"[{i}]" for i in ids)

    out = [f"# BioPathway Mapper: {a.kind} analysis", "", f"**Query:** `{a.query}`", ""]

    out += ["## 1. Input and resolved identifiers", ""]
    genes = {k: v for k, v in a.resolved.items() if k != "variant"}
    if genes:
        out += ["| Input | Symbol | NCBI Gene | UniProt | Name | Location |", "|---|---|---|---|---|---|"]
        for v in genes.values():
            up = v.get("uniprot") or "—"
            if v.get("uniprot") and v.get("uniprot_reviewed") is False:
                up += " (unreviewed)"
            out.append(f"| {_cell(v['input'])} | {v['symbol']} | {v.get('ncbi_gene_id') or '—'} | {up} | "
                       f"{_cell(v.get('name', ''))} | {v.get('location') or '—'} |")
    else:
        out.append("No gene identifiers were resolved for this query.")
    if "variant" in a.resolved:
        v = a.resolved["variant"]
        out += ["", f"Variant parsed as **{v['hgvs_p']}** ({v['one_letter']}; {v['kind']}, "
                f"residue {v['start']}{'' if v['start'] == v['end'] else '-' + str(v['end'])})."]
    out.append("")

    out += ["## 2. Data source status", "", "| Source | Status |", "|---|---|"]
    for src, status in sorted(a.source_status.items()):
        out.append(f"| {src} | {_cell(status)} |")
    n_req = len(a.requests)
    cached = sum(1 for r in a.requests if r.get("cached"))
    stale = sum(1 for r in a.requests if r.get("stale"))
    out += ["", f"{n_req} API requests ({cached} served from cache"
            + (f", {stale} from an expired cache entry after a live failure" if stale else "") + ").", ""]

    if a.warnings:
        out += ["## Warnings", ""] + [f"- {w}" for w in dict.fromkeys(a.warnings)] + [""]

    out += ["## 3. Pathway context", ""]
    if a.pathways:
        out += ["| Source | ID | Name | Gene | Evidence | Note |", "|---|---|---|---|---|---|"]
        for p in a.pathways[:max_rows]:
            note = p.get("note", "")
            if "match" in p:
                note += f"name match {p['match']}"
            if p.get("contains"):
                note += (" " if note else "") + ", ".join(
                    f"{g}: {'in map' if v else 'not in map'}" for g, v in p["contains"].items())
            out.append(f"| {p['source']} | [{p['id']}]({p['url']}) | {_cell(p['name'])} | "
                       f"{p.get('gene', '')} | {ev.SHORT[p['evidence']]} | {_cell(note)} |")
        if len(a.pathways) > max_rows:
            out.append(f"\n{len(a.pathways) - max_rows} more in the JSON output.")
    else:
        out.append("No pathway records were retrieved.")
    out.append("")

    out += ["## 4. Reconstructed molecular relationships", ""]
    if a.edges:
        counts = Counter(e.evidence for e in a.edges)
        out.append("Evidence mix: " + ", ".join(f"{ev.SHORT[l]} {counts[l]}" for l in ev.LEVELS if counts[l]) + "")
        out += ["", "| From | Relation | To | Evidence | Basis | Refs |", "|---|---|---|---|---|---|"]
        for e in a.edges[:max_rows]:
            arrow = "—" if not e.directed else "→"
            out.append(f"| {_cell(a.nodes[e.source].label)} | {arrow} {_cell(edge_label(e, False))} | "
                       f"{_cell(a.nodes[e.target].label)} | {ev.SHORT[e.evidence]} | {_cell(e.detail)} | "
                       f"{refs(e.citations)} |")
        if len(a.edges) > max_rows:
            out.append(f"\n{len(a.edges) - max_rows} more relationships in the JSON output.")
    else:
        out.append("No relationships could be reconstructed from the retrieved records.")
    out.append("")

    out += ["## 5. Evidence-labelled statements", ""]
    if a.statements:
        sections: "OrderedDict[str, list]" = OrderedDict()
        for s in a.statements:
            sections.setdefault(s.section, []).append(s)
        for name, items in sections.items():
            out += [f"### {name}", ""]
            for s in items:
                out.append(f"- **[{ev.SHORT[s.evidence]}]** {s.text} {refs(s.citations)}")
            out.append("")
    else:
        out += ["No statements were generated.", ""]

    out += ["## 6. Pathway diagram", ""]
    if a.diagram_note:
        out += [a.diagram_note, ""]
    if a.edges:
        if len(a.edges) > max_edges:
            out += [f"Showing the {max_edges} most relevant of {len(a.edges)} relationships "
                    "(focus genes first, then strongest evidence).", ""]
        out += ["```mermaid", mermaid(a, max_edges), "```", "", legend_markdown(), ""]
    else:
        out += ["No diagram: there are no supported relationships to draw.", ""]

    if a.notes:
        out += ["## 7. Interpretation notes and limits", ""] + [f"- {n}" for n in dict.fromkeys(a.notes)] + [""]

    if a.literature:
        out += ["## 8. Literature", "",
                "CUR rows are references cited by the curated pathway record; LIT rows are search hits "
                "offered for reading and were not used to draw any relationship.", ""]
        seen = set()
        for r in a.literature:
            if r["pmid"] in seen:
                continue
            seen.add(r["pmid"])
            out.append(f"- **[{ev.SHORT[r['evidence']]}]** {r.get('first_author', '')} ({r.get('year', '')}). "
                       f"{r['title']} *{r.get('journal', '')}*. [PMID:{r['pmid']}]({r['url']}) — {r['basis']}")
        out.append("")

    out += ["## Sources", ""]
    for c in cites:
        title = f" — {c.title}" if c.title else ""
        out.append(f"{num[c.key()]}. {c.source} {c.id}{_cell(title)}. <{c.url}>")
    if not cites:
        out.append("No sources were cited.")
    out.append("")
    stamps = sorted(r["retrieved_at"] for r in a.requests if r.get("retrieved_at"))
    if stamps:
        out.append(f"Records retrieved between {stamps[0]} and {stamps[-1]} (UTC). Databases are "
                   "updated continually; re-run to refresh.")
    return "\n".join(out)
