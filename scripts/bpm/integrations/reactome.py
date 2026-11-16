"""Reactome Content Service. Docs: https://reactome.org/ContentService/"""

from __future__ import annotations

import re

from ..http import HttpClient, SourceError

BASE = "https://reactome.org/ContentService"
_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def _index_objects(data) -> dict:
    """dbId -> object for every inlined Reactome object anywhere in a response."""
    index: dict = {}
    stack = [data]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if "dbId" in x and "stId" in x:
                index.setdefault(x["dbId"], x)
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return index


def url_for(st_id: str) -> str:
    return f"https://reactome.org/content/detail/{st_id}"


class ReactomeClient:
    source = "reactome"

    def __init__(self, http: HttpClient):
        self.http = http

    def _get(self, path: str, params: dict | None = None, empty=None):
        """Reactome answers 404 for 'nothing found'; treat that as an empty result."""
        try:
            return self.http.get_json(self.source, f"{BASE}{path}", params)
        except SourceError as exc:
            if exc.status == 404:
                return empty
            raise

    def search_pathways(self, query: str, species: str = "Homo sapiens", limit: int = 8) -> list[dict]:
        data = self._get("/search/query", {"query": query, "species": species,
                                           "types": "Pathway", "cluster": "true"}, empty={})
        out = []
        for group in (data or {}).get("results", []):
            for e in group.get("entries", []):
                out.append({"id": e.get("stId", ""), "name": strip_html(e.get("name", "")),
                            "summary": strip_html(e.get("summation", "")),
                            "url": url_for(e.get("stId", ""))})
        return out[:limit]

    def pathways_for_uniprot(self, accession: str, taxid: int = 9606) -> list[dict]:
        data = self._get(f"/data/mapping/UniProt/{accession}/pathways", {"species": taxid}, empty=[])
        return [self._event(p) for p in data or [] if isinstance(p, dict)]

    def contained_events(self, st_id: str) -> list[dict]:
        """Every pathway and reaction nested (at any depth) under `st_id`."""
        data = self._get(f"/data/pathway/{st_id}/containedEvents", empty=[]) or []
        # The service inlines each object once (possibly nested inside another object, e.g.
        # in "hasEvent") and afterwards refers to it by integer dbId. Resolve those references.
        index = _index_objects(data)
        out, seen = [], set()
        for e in data:
            obj = e if isinstance(e, dict) else index.get(e)
            if obj and obj.get("stId") and obj["stId"] not in seen:
                seen.add(obj["stId"])
                out.append(self._event(obj))
        return out

    def detail(self, st_id: str) -> dict | None:
        d = self._get(f"/data/query/enhanced/{st_id}", empty=None)
        if not d:
            return None
        out = self._event(d)
        out["summary"] = strip_html(" ".join(s.get("text", "") for s in d.get("summation", [])
                                             if isinstance(s, dict)))
        out["pmids"] = [str(l["pubMedIdentifier"]) for l in d.get("literatureReference", [])
                        if isinstance(l, dict) and l.get("pubMedIdentifier")]
        index = _index_objects(d)
        out["children"] = [self._event(e if isinstance(e, dict) else index[e]) for e in d.get("hasEvent", [])
                           if isinstance(e, dict) or e in index]
        return out

    def participants(self, st_id: str) -> list[dict]:
        data = self._get(f"/data/participants/{st_id}/referenceEntities", empty=[])
        out = []
        for p in data or []:
            if not isinstance(p, dict):
                continue
            names = p.get("geneName") or p.get("name") or []
            out.append({"database": p.get("databaseName", ""), "id": p.get("identifier", ""),
                        "name": names[0] if names else p.get("displayName", ""),
                        "type": p.get("moleculeType", p.get("schemaClass", ""))})
        return out

    # ------------------------------------------------ disease variants
    def variant_entities(self, gene: str, change: str, species: str = "Homo sapiens") -> list[dict]:
        """Reactome disease protein entities named e.g. 'KRAS G12D' (exact name match only)."""
        data = self._get("/search/query", {"query": f"{gene} {change}", "species": species,
                                           "types": "Protein", "cluster": "true"}, empty={})
        want = f"{gene} {change}".lower()
        out = []
        for group in (data or {}).get("results", []):
            for e in group.get("entries", []):
                if e.get("isDisease") and strip_html(e.get("name", "")).lower() == want:
                    out.append({"id": e["stId"], "name": strip_html(e["name"]),
                                "compartments": e.get("compartmentNames", []), "url": url_for(e["stId"])})
        return out

    def sets_containing(self, st_id: str) -> list[dict]:
        data = self._get(f"/data/entity/{st_id}/componentOf", empty=[]) or []
        out = []
        for rel in data:
            for sid, name in zip(rel.get("stIds", []), rel.get("names", [])):
                out.append({"id": sid, "name": name, "relation": rel.get("type", "")})
        return out

    def lowest_pathways(self, st_id: str, taxid: int = 9606) -> list[dict]:
        data = self._get(f"/data/pathways/low/entity/{st_id}", {"species": taxid}, empty=[]) or []
        return [self._event(p) for p in data if isinstance(p, dict)]

    def event_detail(self, st_id: str) -> dict | None:
        """Event with its normal counterpart (for disease events) and cited PMIDs."""
        d = self._get(f"/data/query/enhanced/{st_id}", empty=None)
        if not d:
            return None
        out = self._event(d)
        nr = d.get("normalReaction")
        out["normal"] = self._event(nr) if isinstance(nr, dict) else None
        out["pmids"] = [str(l["pubMedIdentifier"]) for l in d.get("literatureReference", [])
                        if isinstance(l, dict) and l.get("pubMedIdentifier")]
        out["summary"] = strip_html(" ".join(s.get("text", "") for s in d.get("summation", [])
                                             if isinstance(s, dict)))
        return out

    def participant_genes(self, st_id: str) -> list[str]:
        return sorted({p["name"] for p in self.participants(st_id)
                       if p["database"] == "UniProt" and p["name"]})

    # ------------------------------------------------------ enrichment
    def overrepresentation(self, genes: list[str], page_size: int = 25) -> dict:
        """Reactome AnalysisService over-representation (projected to human)."""
        url = f"https://reactome.org/AnalysisService/identifiers/projection?pageSize={page_size}&page=1"
        data = self.http.post_json(self.source, url, "\n".join(genes))
        rows = []
        for p in data.get("pathways", []):
            ent = p.get("entities", {})
            rows.append({"id": p["stId"], "name": p["name"], "found": ent.get("found"),
                         "total": ent.get("total"), "p_value": ent.get("pValue"), "fdr": ent.get("fdr"),
                         "disease": p.get("inDisease", False), "url": url_for(p["stId"])})
        return {"pathways_found": data.get("pathwaysFound"), "not_found": data.get("identifiersNotFound"),
                "token": data.get("summary", {}).get("token"), "pathways": rows}

    @staticmethod
    def _event(e: dict) -> dict:
        return {"id": e.get("stId", ""), "name": e.get("displayName", ""),
                "type": e.get("schemaClass", ""), "category": e.get("category", ""),
                "inferred": bool(e.get("isInferred", False)),
                "disease": bool(e.get("isInDisease", False)),
                "url": url_for(e.get("stId", ""))}
