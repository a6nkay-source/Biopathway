#!/usr/bin/env python3
"""Bundle the six reference scenarios as static JSON for the Explorer's demo mode.

    python3 scripts/export_explorer_data.py            # live APIs (cached)
    python3 scripts/export_explorer_data.py --offline  # cache only

Writes explorer/public/data/<key>.json plus index.json. Each file is exactly
what the HTTP API returns for the same request, so the frontend uses one code
path for live and bundled data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bpm.http import HttpClient  # noqa: E402
from bpm.service import Service  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "explorer" / "public" / "data"

SCENARIOS = [
    {"id": "tp53-apoptosis", "title": "TP53 and apoptosis", "view": "pathway",
     "summary": "KEGG p53 signalling: how p53 drives PUMA, NOXA, BAX and the caspase cascade.",
     "request": ["pathway_graph", {"query": "hsa04115", "genes": "TP53,BBC3,PMAIP1,BAX,CASP3"}]},
    {"id": "brca1-dna-repair", "title": "BRCA1 and DNA repair", "view": "process",
     "summary": "Reactome DNA repair hierarchy and the curated sub-pathways BRCA1 takes part in.",
     "request": ["process_graph", {"query": "DNA repair", "genes": "BRCA1"}]},
    {"id": "egfr-mapk", "title": "EGFR to ERK (MAPK)", "view": "pathway",
     "summary": "Every shortest directed KEGG route from EGFR to ERK1/2, through GRB2, SOS, RAS, RAF and MEK.",
     "request": ["pathway_graph", {"query": "MAPK signaling", "genes": "EGFR,MAPK1"}]},
    {"id": "kras-g12d", "title": "KRAS G12D vs normal", "view": "mutation",
     "summary": "Normal RAS-MAPK signalling next to the changes Reactome documents for KRAS G12D.",
     "request": ["compare_mutation", {"gene": "KRAS", "change": "G12D", "pathway": "MAPK signaling", "genes": "MAPK1"}]},
    {"id": "pi3k-akt-mtor", "title": "PI3K-AKT-mTOR", "view": "pathway",
     "summary": "PI3K, PIP3, AKT, then TSC1/2 inhibiting RHEB inhibiting mTORC1: a double negative.",
     "request": ["pathway_graph", {"query": "hsa04151", "genes": "PIK3CA,AKT1,MTOR"}]},
    {"id": "glycolysis", "title": "Glycolysis", "view": "metabolic",
     "summary": "Glucose to pyruvate in KEGG module M00001, with the human enzymes for each step.",
     "request": ["metabolic_graph", {"query": "glycolysis", "module": "M00001"}]},
]
EXTRA = [
    ["interaction_graph", {"genes": "TP53"}], ["interaction_graph", {"genes": "BRCA1"}],
    ["interaction_graph", {"genes": "KRAS"}],
    ["structures", {"query": "KRAS"}], ["structures", {"query": "TP53"}],
    ["expression", {"symbol": "KRAS"}], ["expression", {"symbol": "TP53"}],
    ["expression", {"symbol": "BRCA1"}], ["expression", {"symbol": "EGFR"}],
    ["literature", {"query": "glycolysis", "genes": "BRCA1"}],
    ["literature", {"query": "apoptosis", "genes": "TP53"}],
    ["enrichment", {"genes": "TP53,BBC3,PMAIP1,BAX,CASP9,CASP3"}],
    ["process_graph", {"query": "apoptosis", "genes": "TP53"}],
]


def key_for(op: str, params: dict) -> str:
    """Stable file key shared with explorer/src/api.ts (keep in sync)."""
    norm = "&".join(f"{k}={str(params[k]).strip()}" for k in sorted(params) if str(params[k]).strip())
    return f"{op}-{hashlib.sha1(norm.encode()).hexdigest()[:10]}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args(argv)
    svc = Service(HttpClient(offline=args.offline))
    OUT.mkdir(parents=True, exist_ok=True)
    index = {"scenarios": [], "files": {}}

    def save(op, params):
        k = key_for(op, params)
        if k in index["files"]:
            return k
        print(f"  {op} {params}", file=sys.stderr)
        data = svc.call(op, dict(params))
        (OUT / f"{k}.json").write_text(json.dumps(data, default=str, separators=(",", ":")))
        index["files"][k] = {"op": op, "params": params}
        return k

    symbols = set()
    for sc in SCENARIOS:
        op, params = sc["request"]
        k = save(op, params)
        data = json.loads((OUT / f"{k}.json").read_text())
        index["scenarios"].append({**{x: sc[x] for x in ("id", "title", "view", "summary")}, "op": op,
                                   "params": params, "file": k})
        graph = data.get("normal", data)
        for n in graph["elements"]["nodes"]:
            d = n["data"]
            if d["kind"] in ("gene", "complex"):
                symbols.update((d.get("members") or [])[:3] or [d["label"]])
    for op, params in EXTRA:
        save(op, params)
    for op, params in EXTRA:
        if op == "structures":
            st = json.loads((OUT / f"{key_for(op, params)}.json").read_text())
            if st.get("predicted"):
                save("structure_coords", {"kind": "alphafold", "id": "", "accession": st["accession"]})
            for e in st.get("experimental", [])[:2]:
                save("structure_coords", {"kind": "pdb", "id": e["id"], "accession": st["accession"]})
    for sym in sorted(s for s in symbols if s and ":" not in s and "+" not in s)[:120]:
        try:
            save("node_info", {"symbol": sym})
        except Exception as exc:  # one bad symbol should not stop the bundle
            print(f"    skipped {sym}: {exc}", file=sys.stderr)
    (OUT / "index.json").write_text(json.dumps(index, indent=1))
    total = sum(f.stat().st_size for f in OUT.glob("*.json"))
    print(f"Wrote {len(index['files'])} files ({total / 1e6:.1f} MB) to {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
