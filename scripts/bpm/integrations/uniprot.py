"""UniProtKB REST API. Docs: https://www.uniprot.org/help/api"""

from __future__ import annotations

from ..http import HttpClient, SourceError

BASE = "https://rest.uniprot.org/uniprotkb"
ENTRY_FIELDS = ("accession,id,gene_names,protein_name,cc_function,go_p,"
                "xref_reactome,xref_kegg,xref_string,xref_geneid")
FEATURE_FIELDS = ("ft_variant,ft_domain,ft_binding,ft_act_site,ft_region,ft_motif,"
                  "ft_mutagen,ft_mod_res,ft_dna_bind,ft_zn_fing,sequence")


class UniProtClient:
    source = "uniprot"

    def __init__(self, http: HttpClient):
        self.http = http

    def find_protein(self, symbol: str, taxid: int = 9606) -> dict | None:
        """Canonical reviewed (Swiss-Prot) entry for a gene symbol, if one exists."""
        for query, reviewed in ((f"gene_exact:{symbol} AND organism_id:{taxid} AND reviewed:true", True),
                                (f"gene_exact:{symbol} AND organism_id:{taxid}", False)):
            data = self.http.get_json(self.source, f"{BASE}/search",
                                      {"query": query, "format": "json", "size": 1,
                                       "fields": ENTRY_FIELDS})
            results = data.get("results", [])
            if results:
                return self._entry(results[0], reviewed)
        return None

    def get_protein(self, accession: str) -> dict | None:
        try:
            data = self.http.get_json(self.source, f"{BASE}/{accession}.json",
                                      {"fields": ENTRY_FIELDS})
        except SourceError as exc:
            if exc.status in (400, 404):
                return None
            raise
        return self._entry(data, "reviewed" in data.get("entryType", "").lower()
                           and "unreviewed" not in data.get("entryType", "").lower())

    @staticmethod
    def _entry(e: dict, reviewed: bool) -> dict:
        desc = e.get("proteinDescription", {})
        name = (desc.get("recommendedName") or (desc.get("submissionNames") or [{}])[0]) \
            .get("fullName", {}).get("value", "")
        genes = e.get("genes", [])
        symbol = genes[0].get("geneName", {}).get("value", "") if genes else ""
        functions = []
        for comment in e.get("comments", []):
            if comment.get("commentType", "FUNCTION") != "FUNCTION":
                continue
            for text in comment.get("texts", []):
                functions.append({"text": text.get("value", ""),
                                  "evidences": text.get("evidences", [])})
        go_bp, xrefs = [], {"Reactome": [], "KEGG": [], "STRING": [], "GeneID": []}
        for x in e.get("uniProtKBCrossReferences", []):
            db = x.get("database")
            props = {p.get("key"): p.get("value") for p in x.get("properties", [])}
            if db == "GO" and props.get("GoTerm", "").startswith("P:"):
                go_bp.append({"id": x.get("id"), "term": props["GoTerm"][2:],
                              "evidence": props.get("GoEvidenceType", "")})
            elif db in xrefs:
                xrefs[db].append(x.get("id"))
        acc = e.get("primaryAccession", "")
        return {"accession": acc, "entry_name": e.get("uniProtkbId", ""), "symbol": symbol,
                "protein_name": name, "reviewed": reviewed, "functions": functions,
                "go_bp": go_bp, "xrefs": xrefs,
                "url": f"https://www.uniprot.org/uniprotkb/{acc}/entry"}

    def features(self, accession: str) -> dict:
        """Sequence plus positional features (variants, domains, sites) of an entry."""
        data = self.http.get_json(self.source, f"{BASE}/{accession}.json",
                                  {"fields": FEATURE_FIELDS})
        feats = []
        for f in data.get("features", []):
            loc = f.get("location", {})
            start, end = loc.get("start", {}).get("value"), loc.get("end", {}).get("value")
            if start is None or end is None:
                continue
            alt = f.get("alternativeSequence") or {}
            feats.append({
                "type": f.get("type", ""), "start": start, "end": end,
                "description": f.get("description", ""),
                "ligand": (f.get("ligand") or {}).get("name", ""),
                "original": alt.get("originalSequence", ""),
                "alternatives": alt.get("alternativeSequences", []),
                "feature_id": f.get("featureId", ""),
                "evidences": f.get("evidences", []),
                "xrefs": [f"{x.get('database')}:{x.get('id')}"
                          for x in f.get("featureCrossReferences", [])],
            })
        return {"sequence": data.get("sequence", {}).get("value", ""), "features": feats}
