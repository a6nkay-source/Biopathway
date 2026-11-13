"""Reactome Content Service. Docs: https://reactome.org/ContentService/"""

from __future__ import annotations

import re

from ..http import HttpClient, SourceError

BASE = "https://reactome.org/ContentService"
_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


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
        data = self._get(f"/data/pathway/{st_id}/containedEvents", empty=[])
        # The service inlines each object once and afterwards refers to it by integer id.
        return [self._event(e) for e in data or [] if isinstance(e, dict)]

    def detail(self, st_id: str) -> dict | None:
        d = self._get(f"/data/query/enhanced/{st_id}", empty=None)
        if not d:
            return None
        out = self._event(d)
        out["summary"] = strip_html(" ".join(s.get("text", "") for s in d.get("summation", [])
                                             if isinstance(s, dict)))
        out["pmids"] = [str(l["pubMedIdentifier"]) for l in d.get("literatureReference", [])
                        if isinstance(l, dict) and l.get("pubMedIdentifier")]
        out["children"] = [self._event(e) for e in d.get("hasEvent", []) if isinstance(e, dict)]
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

    @staticmethod
    def _event(e: dict) -> dict:
        return {"id": e.get("stId", ""), "name": e.get("displayName", ""),
                "type": e.get("schemaClass", ""), "category": e.get("category", ""),
                "inferred": bool(e.get("isInferred", False)),
                "disease": bool(e.get("isInDisease", False)),
                "url": url_for(e.get("stId", ""))}
