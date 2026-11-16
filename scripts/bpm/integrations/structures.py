"""Protein structures: AlphaFold DB (predicted) and RCSB PDB (experimental).

Docs: https://alphafold.ebi.ac.uk/api-docs  https://www.rcsb.org/docs/programmatic-access/web-apis-overview
Coordinates are reduced to C-alpha traces for the Explorer's 3D viewer. Residues
are mapped to UniProt numbering: AlphaFold models use it natively; PDB entries
are mapped through RCSB's SIFTS alignments (label_seq_id -> UniProt position).
"""

from __future__ import annotations

import json
import shlex

from ..http import HttpClient, SourceError

AFDB = "https://alphafold.ebi.ac.uk/api/prediction"
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA = "https://data.rcsb.org/rest/v1/core"
RCSB_FILES = "https://files.rcsb.org/download"


class StructureClient:
    def __init__(self, http: HttpClient):
        self.http = http

    # ------------------------------------------------------------ AlphaFold
    def alphafold(self, accession: str) -> dict | None:
        try:
            data = self.http.get_json("alphafold", f"{AFDB}/{accession}")
        except SourceError as exc:
            if exc.status in (400, 404):
                return None
            raise
        if not data:
            return None
        d = data[0]
        return {
            "id": d.get("modelEntityId", f"AF-{accession}-F1"),
            "source": "AlphaFold DB",
            "provenance": "computationally predicted",
            "method": d.get("toolUsed", "AlphaFold"),
            "version": d.get("latestVersion"),
            "created": (d.get("modelCreatedDate") or "")[:10],
            "mean_plddt": d.get("globalMetricValue"),
            "plddt_fractions": {k: d.get(f"fractionPlddt{k}") for k in ("VeryHigh", "Confident", "Low", "VeryLow")},
            "range": [d.get("sequenceStart"), d.get("sequenceEnd")],
            "cif_url": d.get("cifUrl"),
            "pae_image": d.get("paeImageUrl"),
            "numbering": "UniProt (native)",
            "url": f"https://alphafold.ebi.ac.uk/entry/{accession}",
        }

    # ------------------------------------------------------------------ PDB
    def pdb_entries(self, accession: str, limit: int = 8, min_residues: int = 50) -> dict:
        """Experimental entries for a UniProt accession, best resolution first.

        Peptide-only entries (fewer than `min_residues` residues per chain on
        average) are skipped so short fragments don't crowd out domain structures."""
        query = {
            "query": {"type": "terminal", "service": "text", "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match", "value": accession}},
            "return_type": "entry",
            "request_options": {"paginate": {"start": 0, "rows": max(limit * 3, 24)},
                                "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}]},
        }
        data = self.http.get_json("rcsb", RCSB_SEARCH, {"json": json.dumps(query, separators=(",", ":"))})
        ids = [r["identifier"] for r in data.get("result_set", [])]
        entries = [e for e in (self.pdb_entry(i) for i in ids) if e]
        kept = [e for e in entries if (e["residues_per_chain"] or 0) >= min_residues][:limit]
        return {"total": data.get("total_count", len(ids)), "entries": kept,
                "skipped_short": len([e for e in entries if (e["residues_per_chain"] or 0) < min_residues])}

    def pdb_entry(self, pdb_id: str) -> dict | None:
        try:
            d = self.http.get_json("rcsb", f"{RCSB_DATA}/entry/{pdb_id}")
        except SourceError as exc:
            if exc.status == 404:
                return None
            raise
        info = d.get("rcsb_entry_info", {})
        cit = next((c for c in d.get("citation", []) if c.get("rcsb_is_primary") == "Y"), {})
        res = info.get("resolution_combined") or [None]
        chains = info.get("deposited_polymer_entity_instance_count") or 0
        residues = info.get("deposited_polymer_monomer_count") or 0
        return {
            "id": pdb_id,
            "source": "RCSB PDB",
            "provenance": "experimentally determined",
            "title": d.get("struct", {}).get("title", ""),
            "method": ", ".join(x.get("method", "") for x in d.get("exptl", [])),
            "resolution": res[0],
            "released": (d.get("rcsb_accession_info", {}).get("initial_release_date") or "")[:10],
            "chains": chains, "residues_per_chain": round(residues / chains) if chains else None,
            "entity_ids": d.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", []),
            "pmid": str(cit.get("pdbx_database_id_PubMed") or ""),
            "doi": cit.get("pdbx_database_id_DOI") or "",
            "url": f"https://www.rcsb.org/structure/{pdb_id}",
        }

    def sifts_map(self, pdb_id: str, entity_ids: list, accession: str) -> dict:
        """chain -> {label_seq_id: uniprot_position} for entities that map to `accession`."""
        out = {}
        for ent in entity_ids:
            try:
                d = self.http.get_json("rcsb", f"{RCSB_DATA}/polymer_entity/{pdb_id}/{ent}")
            except SourceError:
                continue
            ids = d.get("rcsb_polymer_entity_container_identifiers", {})
            refs = [r for r in ids.get("reference_sequence_identifiers") or [] if r.get("database_accession") == accession]
            if not refs:
                continue
            mapping = {}
            for al in d.get("rcsb_polymer_entity_align", []):
                if al.get("reference_database_accession") not in (None, accession):
                    continue
                for reg in al.get("aligned_regions", []):
                    for k in range(reg["length"]):
                        mapping[reg["entity_beg_seq_id"] + k] = reg["ref_beg_seq_id"] + k
            for chain in ids.get("auth_asym_ids", []):
                out[chain] = mapping
        return out

    # -------------------------------------------------------- coordinates
    def ca_trace(self, kind: str, ident: str, accession: str) -> dict:
        """C-alpha trace with per-residue UniProt numbering and B-factor (pLDDT for AlphaFold)."""
        if kind == "alphafold":
            meta = self.alphafold(accession)
            if not meta or not meta.get("cif_url"):
                raise SourceError("alphafold", AFDB, "no AlphaFold model for this accession", 404)
            text = self.http.get("alphafold", meta["cif_url"])
            atoms = parse_mmcif_ca(text)
            for a in atoms:
                a["uniprot"] = a["label_seq"]
            return {"id": meta["id"], "provenance": meta["provenance"], "b_factor": "pLDDT",
                    "numbering": "UniProt (native)", "atoms": atoms}
        entry = self.pdb_entry(ident)
        if not entry:
            raise SourceError("rcsb", f"{RCSB_DATA}/entry/{ident}", "no such PDB entry", 404)
        text = self.http.get("rcsb", f"{RCSB_FILES}/{ident}.cif")
        atoms = parse_mmcif_ca(text)
        sifts = self.sifts_map(ident, entry["entity_ids"], accession)
        for a in atoms:
            a["uniprot"] = sifts.get(a["chain"], {}).get(a["label_seq"])
        mapped = sorted({a["chain"] for a in atoms if a["uniprot"]})
        return {"id": ident, "provenance": "experimentally determined", "b_factor": "crystallographic B-factor",
                "numbering": f"UniProt via SIFTS (chains {', '.join(mapped) or 'none mapped'})",
                "target_chains": mapped, "atoms": atoms}


def parse_mmcif_ca(text: str, max_atoms: int = 20000) -> list[dict]:
    """C-alpha atoms of the first model from an mmCIF atom_site loop."""
    cols, atoms, in_loop, model = [], [], False, None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("_atom_site."):
            in_loop = True
            cols.append(line.split(".", 1)[1].strip())
        elif in_loop and cols and not line.startswith("_"):
            if line.startswith("#") or line.startswith("loop_"):
                break
            parts = shlex.split(line) if ("'" in line or '"' in line) else line.split()
            if len(parts) < len(cols):
                i += 1
                continue
            row = dict(zip(cols, parts))
            m = row.get("pdbx_PDB_model_num", "1")
            model = model or m
            if m == model and row.get("group_PDB") == "ATOM" and row.get("label_atom_id") == "CA":
                try:
                    atoms.append({
                        "chain": row.get("auth_asym_id") or row.get("label_asym_id"),
                        "label_seq": int(row["label_seq_id"]),
                        "auth_seq": row.get("auth_seq_id"),
                        "res": row.get("label_comp_id"),
                        "x": round(float(row["Cartn_x"]), 3), "y": round(float(row["Cartn_y"]), 3),
                        "z": round(float(row["Cartn_z"]), 3),
                        "b": round(float(row.get("B_iso_or_equiv", 0) or 0), 2),
                    })
                except (KeyError, ValueError):
                    pass
                if len(atoms) >= max_atoms:
                    break
        i += 1
    return atoms
