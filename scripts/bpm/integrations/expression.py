"""Tissue and cell-type context: GTEx (bulk RNA by tissue), Human Protein Atlas
(tissue / single-cell-type specificity) and NCBI GEO (datasets for follow-up).

Docs: https://gtexportal.org/api/v2/redoc  https://www.proteinatlas.org/about/help/dataaccess
      https://www.ncbi.nlm.nih.gov/geo/info/geo_paccess.html
Expression shows that a gene is transcribed in a tissue. It does not show that a
pathway is active there.
"""

from __future__ import annotations

from ..http import HttpClient, SourceError

GTEX = "https://gtexportal.org/api/v2"
HPA = "https://www.proteinatlas.org/api/search_download.php"


class ExpressionClient:
    def __init__(self, http: HttpClient):
        self.http = http

    def gtex_tissues(self, symbol: str) -> dict | None:
        ref = self.http.get_json("gtex", f"{GTEX}/reference/gene", {"geneId": symbol})
        genes = [g for g in ref.get("data", []) if g.get("geneSymbolUpper") == symbol.upper()]
        if not genes:
            return None
        gid = genes[0]["gencodeId"]
        data = self.http.get_json("gtex", f"{GTEX}/expression/medianGeneExpression",
                                  {"gencodeId": gid, "datasetId": "gtex_v8"})
        rows = sorted(({"tissue": r["tissueSiteDetailId"].replace("_", " "), "tpm": round(r["median"], 2),
                        "uberon": r.get("ontologyId", "")} for r in data.get("data", [])),
                      key=lambda r: -r["tpm"])
        return {"gencode_id": gid, "dataset": "GTEx v8", "unit": "median TPM", "tissues": rows,
                "url": f"https://gtexportal.org/home/gene/{symbol}"}

    def hpa_specificity(self, symbol: str) -> dict | None:
        cols = "g,eg,rnats,rnatsm,rnascs,rnascsm,rnacas"
        try:
            data = self.http.get_json("hpa", HPA, {"search": symbol, "format": "json",
                                                   "columns": cols, "compress": "no"})
        except SourceError as exc:
            if exc.status in (400, 404):
                return None
            raise
        row = next((r for r in data or [] if str(r.get("Gene", "")).upper() == symbol.upper()), None)
        if not row:
            return None
        return {
            "ensembl": row.get("Ensembl"),
            "tissue_specificity": row.get("RNA tissue specificity"),
            "tissue_specific_ntpm": row.get("RNA tissue specific nTPM") or {},
            "cell_type_specificity": row.get("RNA single cell type specificity"),
            "cell_type_specific_ncpm": row.get("RNA single cell type specific nCPM") or {},
            "cancer_specificity": row.get("RNA cancer specificity"),
            "url": f"https://www.proteinatlas.org/{row.get('Ensembl')}",
            "licence": "Human Protein Atlas, CC BY-SA 4.0",
        }


def geo_datasets(ncbi, symbol: str, context: str = "", retmax: int = 5) -> dict:
    """GEO DataSets/Series mentioning the gene (and optional tissue/disease context)."""
    term = f"{symbol}[All Fields] AND Homo sapiens[Organism]" + (f" AND ({context})" if context else "")
    data = ncbi._call("esearch", db="gds", term=term, retmax=retmax)
    res = data.get("esearchresult", {})
    ids = res.get("idlist", [])
    items = []
    if ids:
        summ = ncbi._call("esummary", db="gds", id=",".join(ids)).get("result", {})
        for uid in summ.get("uids", []):
            r = summ[uid]
            acc = r.get("accession", "")
            items.append({"accession": acc, "title": r.get("title", ""), "type": r.get("gdstype", ""),
                          "samples": r.get("n_samples"), "platform": r.get("gpl", ""),
                          "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}"})
    return {"query": term, "count": int(res.get("count", 0) or 0), "datasets": items}
