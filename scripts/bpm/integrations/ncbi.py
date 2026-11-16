"""NCBI E-utilities: Gene, PubMed and ClinVar.

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25497/
Set NCBI_API_KEY to raise the rate limit from 3 to 10 requests/s. Set
NCBI_EMAIL if you want NCBI to be able to contact you; it is never sent
otherwise.
"""

from __future__ import annotations

import os

from ..http import HttpClient

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class NcbiClient:
    source = "ncbi"

    def __init__(self, http: HttpClient):
        self.http = http

    def _call(self, endpoint: str, **params):
        params.update({"retmode": "json", "tool": "biopathway-mapper"})
        if os.environ.get("NCBI_EMAIL"):
            params["email"] = os.environ["NCBI_EMAIL"]
        secret = {"api_key": os.environ["NCBI_API_KEY"]} if os.environ.get("NCBI_API_KEY") else None
        return self.http.get_json(self.source, f"{BASE}/{endpoint}.fcgi", params, secret_params=secret)

    def _search(self, db: str, term: str, retmax: int = 5, sort: str = "") -> list[str]:
        params = {"db": db, "term": term, "retmax": retmax}
        if sort:
            params["sort"] = sort
        data = self._call("esearch", **params)
        return list(data.get("esearchresult", {}).get("idlist", []))

    def _summaries(self, db: str, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        result = self._call("esummary", db=db, id=",".join(ids)).get("result", {})
        return [result[i] for i in result.get("uids", []) if i in result]

    # ----------------------------------------------------------------- gene
    def find_gene(self, symbol: str, taxid: int = 9606) -> dict | None:
        """Resolve an official symbol (falling back to any alias) to a Gene record."""
        for term in (f"{symbol}[sym] AND {taxid}[taxid] AND alive[prop]",
                     f"{symbol}[gene] AND {taxid}[taxid] AND alive[prop]"):
            ids = self._search("gene", term, retmax=5)
            if ids:
                records = self._summaries("gene", ids)
                exact = [r for r in records if r.get("name", "").upper() == symbol.upper()]
                record = (exact or records)[0]
                return {
                    "gene_id": record["uid"],
                    "symbol": record.get("name", ""),
                    "description": record.get("description", ""),
                    "aliases": [a.strip().strip("'\"") for a in record.get("otheraliases", "").split(",") if a.strip().strip("'\"")],
                    "map_location": record.get("maplocation", ""),
                    "summary": record.get("summary", ""),
                    "matched_by": "official symbol" if exact else "alias",
                    "url": f"https://www.ncbi.nlm.nih.gov/gene/{record['uid']}",
                }
        return None

    # --------------------------------------------------------------- pubmed
    def pubmed_search(self, term: str, retmax: int = 5) -> list[dict]:
        ids = self._search("pubmed", term, retmax=retmax, sort="relevance")
        return [self._pubmed_record(r) for r in self._summaries("pubmed", ids)]

    def pubmed_summaries(self, pmids: list[str]) -> list[dict]:
        return [self._pubmed_record(r) for r in self._summaries("pubmed", [str(p) for p in pmids])]

    def pubmed_abstracts(self, pmids: list[str]) -> list[dict]:
        """Title, abstract, publication types and year for PMIDs (efetch XML)."""
        pmids = [str(p) for p in pmids if str(p).strip()]
        if not pmids:
            return []
        params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "tool": "biopathway-mapper"}
        if os.environ.get("NCBI_EMAIL"):
            params["email"] = os.environ["NCBI_EMAIL"]
        secret = {"api_key": os.environ["NCBI_API_KEY"]} if os.environ.get("NCBI_API_KEY") else None
        text = self.http.get(self.source, f"{BASE}/efetch.fcgi", params, secret_params=secret)
        return parse_pubmed_xml(text)

    @staticmethod
    def _pubmed_record(r: dict) -> dict:
        authors = [a.get("name", "") for a in r.get("authors", [])]
        return {
            "pmid": r["uid"],
            "title": r.get("title", ""),
            "journal": r.get("source", ""),
            "year": (r.get("pubdate", "") or "")[:4],
            "first_author": authors[0] if authors else "",
            "pubtypes": r.get("pubtype", []),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{r['uid']}/",
        }

    # -------------------------------------------------------------- clinvar
    def clinvar_search(self, gene: str, protein_changes: list[str], retmax: int = 10) -> list[dict]:
        """Find ClinVar variation records for a gene + protein change (any notation)."""
        changes = " OR ".join(f'"{c}"' for c in protein_changes)
        ids = self._search("clinvar", f"{gene}[gene] AND ({changes})", retmax=retmax)
        out = []
        for r in self._summaries("clinvar", ids):
            def cls(key):
                block = r.get(key) or {}
                return {
                    "classification": block.get("description", ""),
                    "review_status": block.get("review_status", ""),
                    "last_evaluated": (block.get("last_evaluated", "") or "")[:10],
                    "conditions": [t.get("trait_name", "") for t in block.get("trait_set", [])
                                   if t.get("trait_name")],
                }
            out.append({
                "uid": r["uid"],
                "accession": r.get("accession", ""),
                "title": r.get("title", ""),
                "variant_type": r.get("obj_type", ""),
                "protein_change": [p.strip() for p in (r.get("protein_change", "") or "").split(",") if p.strip()],
                "genes": [g.get("symbol", "") for g in r.get("genes", [])],
                "germline": cls("germline_classification"),
                "oncogenicity": cls("oncogenicity_classification"),
                "clinical_impact": cls("clinical_impact_classification"),
                "url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{r['uid']}/",
            })
        return out


REVIEW_TYPES = {"Review", "Systematic Review", "Meta-Analysis", "Editorial", "Comment"}


def parse_pubmed_xml(text: str) -> list[dict]:
    """PubmedArticleSet XML -> records with abstract text (section labels kept)."""
    import xml.etree.ElementTree as ET

    def flat(el):
        return " ".join("".join(el.itertext()).split()) if el is not None else ""

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    out = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//MedlineCitation/PMID", "")
        parts = []
        for sec in art.findall(".//Abstract/AbstractText"):
            body = flat(sec)
            label = sec.get("Label")
            parts.append(f"{label}: {body}" if label else body)
        types = [p.text for p in art.findall(".//PublicationType") if p.text]
        year = (art.findtext(".//Journal/JournalIssue/PubDate/Year")
                or (art.findtext(".//Journal/JournalIssue/PubDate/MedlineDate") or "")[:4])
        authors = art.findall(".//AuthorList/Author")
        first = ""
        if authors:
            first = f"{authors[0].findtext('LastName', '')} {authors[0].findtext('Initials', '')}".strip()
        doi = next((x.text for x in art.findall(".//PubmedData/ArticleIdList/ArticleId")
                    if x.get("IdType") == "doi" and x.text), "")
        out.append({
            "pmid": pmid,
            "doi": doi,
            "title": flat(art.find(".//ArticleTitle")),
            "journal": art.findtext(".//Journal/ISOAbbreviation", "") or art.findtext(".//Journal/Title", ""),
            "year": year,
            "first_author": first,
            "pubtypes": types,
            "is_review": bool(set(types) & REVIEW_TYPES),
            "abstract": "\n".join(parts),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return out
