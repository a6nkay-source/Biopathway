"""KEGG REST API. Docs: https://www.kegg.jp/kegg/rest/keggapi.html

Licence note: the KEGG API is provided for academic use by academic users.
Commercial users need a licence (https://www.kegg.jp/kegg/legal.html). Pass
--no-kegg (or BPM_DISABLE_KEGG=1) to switch this integration off.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..http import HttpClient, SourceError

BASE = "https://rest.kegg.jp"
_PATHWAY_ID = re.compile(r"^(?:path:)?([a-z]{2,4})(\d{5})$")


def pathway_url(pid: str) -> str:
    return f"https://www.kegg.jp/pathway/{pid}"


class KeggClient:
    source = "kegg"

    def __init__(self, http: HttpClient):
        self.http = http

    def _get(self, path: str) -> str:
        """KEGG answers 404 (or 400) for unknown entries; treat as empty."""
        try:
            return self.http.get(self.source, f"{BASE}/{path}")
        except SourceError as exc:
            if exc.status in (400, 404):
                return ""
            raise

    @staticmethod
    def _rows(text: str) -> list[list[str]]:
        return [line.split("\t") for line in text.splitlines() if line.strip()]

    def list_pathways(self, org: str = "hsa") -> list[dict]:
        out = []
        for row in self._rows(self._get(f"list/pathway/{org}")):
            if len(row) >= 2:
                name = re.sub(r"\s+-\s+[^-]*\([^)]*\)\s*$", "", row[1])  # drop " - Homo sapiens (human)"
                out.append({"id": row[0].replace("path:", ""), "name": name})
        return out

    def gene_pathways(self, gene_id: str, org: str = "hsa") -> list[str]:
        return [row[1].replace("path:", "") for row in self._rows(self._get(f"link/pathway/{org}:{gene_id}"))
                if len(row) >= 2]

    def pathway_info(self, pid: str) -> dict | None:
        """Parse the KEGG flat file for a pathway (name, class, gene and compound tables)."""
        text = self._get(f"get/{pid}")
        if not text.strip():
            return None
        info = {"id": pid, "name": "", "description": "", "class": "", "genes": {},
                "compounds": {}, "pmids": [], "modules": [], "url": pathway_url(pid)}
        section = ""
        for line in text.splitlines():
            if line.startswith("///"):
                break
            key, value = line[:12].strip(), line[12:].strip()
            if key:
                section = key
            if section == "NAME" and key:
                info["name"] = re.sub(r"\s+-\s+[^-]*\([^)]*\)\s*$", "", value)
            elif section == "DESCRIPTION":
                info["description"] = (info["description"] + " " + value).strip()
            elif section == "CLASS" and key:
                info["class"] = value
            elif section == "GENE":
                m = re.match(r"(\S+)\s+([^;]+);", value)
                if m:
                    info["genes"][m.group(1)] = m.group(2).strip()
                else:
                    parts = value.split(None, 1)
                    if len(parts) == 2:
                        info["genes"][parts[0]] = parts[1].split(";")[0].strip()
            elif section == "COMPOUND":
                parts = value.split(None, 1)
                if parts:
                    info["compounds"][parts[0]] = parts[1] if len(parts) > 1 else parts[0]
            elif section == "MODULE":
                info["modules"].append(value)
            elif section == "REFERENCE" and key:
                m = re.search(r"PMID:(\d+)", value)
                if m:
                    info["pmids"].append(m.group(1))
        return info

    def module(self, mid: str) -> dict | None:
        """Parse a KEGG module flat file: name, definition and its main reactions."""
        text = self._get(f"get/{mid}")
        if not text.strip():
            return None
        info = {"id": mid, "name": "", "definition": "", "reactions": [],
                "url": f"https://www.kegg.jp/module/{mid}"}
        section = ""
        for line in text.splitlines():
            if line.startswith("///"):
                break
            key, value = line[:12].strip(), line[12:].strip()
            if key:
                section = key
            if section == "NAME" and key:
                info["name"] = value
            elif section == "DEFINITION":
                info["definition"] = (info["definition"] + " " + value).strip()
            elif section == "REACTION":
                m = re.match(r"(\S+)\s+(.+?)\s*->\s*(.+)$", value)
                if m:
                    info["reactions"].append({
                        "ids": m.group(1).split(","),
                        "substrates": [c.strip() for c in m.group(2).split("+")],
                        "products": [c.strip() for c in m.group(3).split("+")],
                    })
        return info

    def compound_names(self, ids: list[str]) -> dict:
        """Primary names for compound/glycan ids (the API accepts 10 per call)."""
        names = {}
        ids = sorted(set(ids))
        for i in range(0, len(ids), 10):
            chunk = "+".join(ids[i:i + 10])
            for row in self._rows(self._get(f"list/{chunk}")):
                if len(row) >= 2:
                    names[row[0].split(":")[-1]] = row[1].split(";")[0].strip()
        return names

    def kgml(self, pid: str) -> dict | None:
        text = self._get(f"get/{pid}/kgml")
        if not text.strip():
            return None
        try:
            return parse_kgml(text)
        except ET.ParseError as exc:
            raise SourceError(self.source, f"{BASE}/get/{pid}/kgml", f"unparseable KGML: {exc}") from exc


def parse_kgml(text: str) -> dict:
    """KGML -> entries, relations (signalling) and reactions (metabolism).

    Spec: https://www.kegg.jp/kegg/xml/docs/
    """
    root = ET.fromstring(text)
    entries = {}
    for e in root.findall("entry"):
        graphics = e.find("graphics")
        entries[e.get("id")] = {
            "id": e.get("id"), "type": e.get("type"),
            "names": e.get("name", "").split(),
            "reactions": [r.replace("rn:", "") for r in e.get("reaction", "").split()],
            "label": (graphics.get("name", "") if graphics is not None else ""),
            "components": [c.get("id") for c in e.findall("component")],
        }
    relations = []
    for r in root.findall("relation"):
        subs = [(s.get("name"), s.get("value")) for s in r.findall("subtype")]
        relations.append({"entry1": r.get("entry1"), "entry2": r.get("entry2"),
                          "type": r.get("type"), "subtypes": [s[0] for s in subs],
                          "compound_entries": [v for n, v in subs if n == "compound"]})
    reactions = []
    for r in root.findall("reaction"):
        reactions.append({
            "entry_id": r.get("id"),
            "ids": [x.replace("rn:", "") for x in r.get("name", "").split()],
            "reversible": r.get("type") == "reversible",
            "substrates": [s.get("name", "").split(":")[-1] for s in r.findall("substrate")],
            "products": [p.get("name", "").split(":")[-1] for p in r.findall("product")],
        })
    return {"id": root.get("name", "").replace("path:", ""), "title": root.get("title", ""),
            "entries": entries, "relations": relations, "reactions": reactions}


def is_pathway_id(text: str) -> bool:
    return bool(_PATHWAY_ID.match(text.strip()))


def normalise_pathway_id(text: str, org: str = "hsa") -> str:
    m = _PATHWAY_ID.match(text.strip())
    if not m:
        return text
    prefix = org if m.group(1) in ("map", "ko") else m.group(1)
    return f"{prefix}{m.group(2)}"
