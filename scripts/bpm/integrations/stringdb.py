"""STRING API. Docs: https://string-db.org/help/api/"""

from __future__ import annotations

from ..http import HttpClient, SourceError

BASE = "https://string-db.org/api/json"
CALLER = "biopathway-mapper"
CHANNELS = ("score", "nscore", "fscore", "pscore", "ascore", "escore", "dscore", "tscore")


class StringClient:
    source = "string"

    def __init__(self, http: HttpClient):
        self.http = http

    def _get(self, method: str, params: dict) -> list:
        params = dict(params, caller_identity=CALLER)
        try:
            data = self.http.get_json(self.source, f"{BASE}/{method}", params)
        except SourceError as exc:
            if exc.status in (400, 404):   # STRING uses these for unknown identifiers
                return []
            raise
        return data if isinstance(data, list) else []

    def resolve(self, identifiers: list[str], taxid: int = 9606) -> dict:
        rows = self._get("get_string_ids", {"identifiers": "\r".join(identifiers),
                                            "species": taxid, "limit": 1})
        return {r["queryItem"]: {"string_id": r["stringId"], "name": r["preferredName"]}
                for r in rows if "queryItem" in r}

    def partners(self, identifier: str, taxid: int = 9606, limit: int = 25) -> list[dict]:
        rows = self._get("interaction_partners", {"identifiers": identifier,
                                                  "species": taxid, "limit": limit})
        return [self._row(r) for r in rows]

    def network(self, identifiers: list[str], taxid: int = 9606) -> list[dict]:
        if len(identifiers) < 2:
            return []
        rows = self._get("network", {"identifiers": "\r".join(identifiers), "species": taxid})
        seen, out = set(), []
        for r in rows:  # STRING can return the same pair more than once
            row = self._row(r)
            key = tuple(sorted((row["a"], row["b"])))
            if key not in seen:
                seen.add(key)
                out.append(row)
        return out

    @staticmethod
    def _row(r: dict) -> dict:
        return {"a": r.get("preferredName_A", ""), "b": r.get("preferredName_B", ""),
                "id_a": r.get("stringId_A", ""), "id_b": r.get("stringId_B", ""),
                "scores": {c: float(r.get(c, 0) or 0) for c in CHANNELS}}


def network_url(identifiers: list[str], taxid: int = 9606) -> str:
    return (f"https://string-db.org/cgi/network?identifiers={'%0d'.join(identifiers)}"
            f"&species={taxid}")
