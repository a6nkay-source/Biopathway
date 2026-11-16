#!/usr/bin/env python3
"""BioPathway Mapper command line.

Examples
  python3 scripts/bpm_cli.py gene TP53
  python3 scripts/bpm_cli.py gene EGFR KRAS BRAF
  python3 scripts/bpm_cli.py pathway "MAPK signaling" --genes EGFR,MAPK1
  python3 scripts/bpm_cli.py pathway hsa04151 --genes PIK3CA,AKT1,MTOR
  python3 scripts/bpm_cli.py process apoptosis --genes TP53
  python3 scripts/bpm_cli.py metabolic glycolysis --module M00001
  python3 scripts/bpm_cli.py mutation KRAS G12D --out ./kras_g12d
  python3 scripts/bpm_cli.py literature glycolysis --genes BRCA1

Standard library only (Python >= 3.9). Exit codes: 0 ok, 2 nothing resolved,
3 every queried source failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bpm import analysis as an  # noqa: E402
from bpm.diagram import dot, mermaid, render_with_graphviz  # noqa: E402
from bpm.http import HttpClient  # noqa: E402
from bpm.report import render_markdown  # noqa: E402


def _genes(text: str) -> list[str]:
    return [g.strip() for g in (text or "").replace(";", ",").split(",") if g.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bpm", description="Evidence-traceable pathway mapping.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--taxid", type=int, default=9606, help="NCBI taxonomy id (default 9606, human)")
    common.add_argument("--format", choices=["md", "json", "mermaid", "dot"], default="md")
    common.add_argument("--out", help="directory to write report.md, analysis.json, diagram.mmd, diagram.dot")
    common.add_argument("--max-edges", type=int, default=50, help="edges drawn in the diagram")
    common.add_argument("--no-kegg", action="store_true",
                        help="do not call KEGG (its API is free for academic use only)")
    common.add_argument("--offline", action="store_true", help="answer from cache only")
    common.add_argument("--no-cache", action="store_true")
    common.add_argument("--cache-dir", help="default ~/.cache/biopathway-mapper or $BPM_CACHE_DIR")
    common.add_argument("--cache-ttl-days", type=float, default=7)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gene", parents=[common], help="gene/protein identity, function, pathways, interactors")
    g.add_argument("genes", nargs="+", help="gene symbols or UniProt accessions")
    g.add_argument("--partners", type=int, default=15)

    pw = sub.add_parser("pathway", parents=[common], help="directed signalling relations from KEGG")
    pw.add_argument("query", help="pathway name, KEGG id (hsa04010) or Reactome id (R-HSA-...)")
    pw.add_argument("--genes", default="", help="comma-separated focus genes")
    pw.add_argument("--hops", type=int, default=1, help="neighbourhood size for a single focus gene")

    pr = sub.add_parser("process", parents=[common], help="biological process via the Reactome hierarchy")
    pr.add_argument("query", help="process name or Reactome id")
    pr.add_argument("--genes", default="")

    me = sub.add_parser("metabolic", parents=[common], help="metabolite flow from KEGG reactions")
    me.add_argument("query", help="pathway name or KEGG id (hsa00010)")
    me.add_argument("--module", help="restrict to a KEGG module, e.g. M00001")
    me.add_argument("--genes", default="")

    li = sub.add_parser("literature", parents=[common],
                        help="primary studies and reviews with abstracts, to read and judge")
    li.add_argument("query", nargs="?", default="", help="topic, e.g. 'glycolysis'")
    li.add_argument("--genes", default="")
    li.add_argument("--pmids", default="", help="comma-separated PMIDs to fetch directly")
    li.add_argument("--max", type=int, default=8, help="primary studies to retrieve (default 8)")

    tl = sub.add_parser("tool", help="any BioPathway 2.0 operation as JSON (same as the MCP server / Explorer API)")
    tl.add_argument("op", help="compare_mutation | perturb_pathway | structures | expression | enrichment | "
                               "pathway_graph | interaction_graph | node_info | literature | ...")
    tl.add_argument("params", nargs="*", help="key=value pairs, e.g. gene=KRAS change=G12D pathway='MAPK signaling'")
    tl.add_argument("--offline", action="store_true")
    tl.add_argument("--no-kegg", action="store_true")
    tl.add_argument("--taxid", type=int, default=9606)

    mu = sub.add_parser("mutation", parents=[common], help="protein variant in structural/clinical/pathway context")
    mu.add_argument("gene")
    mu.add_argument("change", help="e.g. R175H, p.Arg175His, G12D, E746_A750del")
    return p


def run(args) -> "an.Analysis":
    if args.no_kegg or os.environ.get("BPM_DISABLE_KEGG") == "1":
        args.no_kegg = True
    http = HttpClient(cache_dir=Path(args.cache_dir) if args.cache_dir else None,
                      cache_ttl=args.cache_ttl_days * 86400, use_cache=not args.no_cache,
                      offline=args.offline)
    ctx = an.Context(http, taxid=args.taxid, use_kegg=not args.no_kegg)
    if args.command == "gene":
        return an.analyze_gene(ctx, args.genes, args.partners)
    if args.command == "pathway":
        return an.analyze_pathway(ctx, args.query, _genes(args.genes), args.hops)
    if args.command == "process":
        return an.analyze_process(ctx, args.query, _genes(args.genes))
    if args.command == "metabolic":
        return an.analyze_metabolic(ctx, args.query, args.module, _genes(args.genes))
    if args.command == "literature":
        return an.analyze_literature(ctx, args.query, _genes(args.genes), _genes(args.pmids), args.max)
    return an.analyze_mutation(ctx, args.gene, args.change)


def run_tool(args) -> int:
    from bpm.service import Service
    params = {}
    for kv in args.params:
        if "=" not in kv:
            print(f"bad parameter '{kv}' (expected key=value)", file=sys.stderr)
            return 2
        k, v = kv.split("=", 1)
        params[k] = v
    svc = Service(HttpClient(offline=args.offline), taxid=args.taxid,
                  use_kegg=not (args.no_kegg or os.environ.get("BPM_DISABLE_KEGG") == "1"))
    try:
        data = svc.call(args.op, params)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}. Operations: {', '.join(sorted(svc.ops()))}", file=sys.stderr)
        return 2
    print(data["markdown"] if args.op == "report" else json.dumps(data, indent=1, default=str))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "tool":
        return run_tool(args)
    a = run(args)
    md = render_markdown(a, args.max_edges)
    mmd = mermaid(a, args.max_edges)
    dt = dot(a, args.max_edges)
    data = json.dumps(a.to_dict(), indent=2, default=str)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text(md)
        (out / "analysis.json").write_text(data)
        (out / "diagram.mmd").write_text(mmd)
        (out / "diagram.dot").write_text(dt)
        rendered = render_with_graphviz(dt, str(out / "diagram.svg"))
        print(f"Wrote {out}/report.md, analysis.json, diagram.mmd, diagram.dot"
              + (", diagram.svg" if rendered else " (install Graphviz to also get diagram.svg)"),
              file=sys.stderr)
    print({"md": md, "json": data, "mermaid": mmd, "dot": dt}[args.format])
    statuses = [s for s in a.source_status.values() if not s.startswith("not queried")]
    if statuses and all(s.startswith("failed") for s in statuses):
        return 3
    if not a.resolved and not a.edges and not a.pathways and not a.literature:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
