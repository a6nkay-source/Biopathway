"""Rule-based extraction from retrieved abstracts: methods, model systems, design,
candidate conflicts, stated limitations and evidence gaps.

This is keyword extraction, not reading comprehension. Every output says what it
matched and quotes the sentence, so Claude or the user can verify it against the
abstract. Nothing here is a finding by itself.
"""

from __future__ import annotations

import re

METHODS = {
    "ChIP / promoter occupancy": r"\bChIP(?:-seq|-qPCR)?\b|chromatin immunoprecipitation",
    "reporter assay": r"luciferase|reporter assay|reporter gene",
    "knockdown / RNAi": r"\bsiRNA|\bshRNA|knock-?down|RNA interference",
    "knockout / CRISPR": r"CRISPR|knock-?out|\bKO\b|-/-|null (?:mice|cells)",
    "overexpression / re-expression": r"over-?express|re-?express|ectopic expression|transfect",
    "co-immunoprecipitation / binding": r"co-?immunoprecipitat|pull-?down|\bco-IP\b|binding assay|surface plasmon",
    "western blot": r"western blot|immunoblot",
    "qPCR / RNA-seq": r"\bqPCR\b|RT-PCR|RNA-?seq|transcriptom|microarray",
    "metabolite / flux measurement": r"metabolom|seahorse|oxygen consumption|extracellular acidification|lactate (?:production|secretion)|glucose (?:uptake|consumption)|isotope|13C",
    "structural / biophysical": r"crystal structure|cryo-?EM|\bNMR\b|X-ray",
    "pharmacological inhibition": r"\binhibitor\b|treated with|antagonist",
    "patient cohort / tissue microarray": r"cohort|tissue microarray|\bTMA\b|patients?\b|clinical samples|tumou?r samples",
    "survival / correlation analysis": r"survival|prognos|correlat|associated with|Kaplan",
    "computational / database analysis": r"bioinformatic|\bTCGA\b|in silico|database|computational|machine learning",
}
SYSTEMS = {
    "human cell lines": r"\b(?:MCF-?7|MDA-MB-\d+|HCC\d+|HeLa|HEK-?293\w*|A549|H1299|HCT-?116|U2OS|SW480|PANC-?1|MIA ?PaCa|K562|Jurkat|T47D|U87)\b|cell lines?",
    "mouse / rat model": r"\bmice\b|\bmouse\b|murine|\brats?\b|xenograft|transgenic",
    "primary / patient material": r"patients?|human (?:tumou?rs?|tissues?|samples)|biops|primary (?:cells|tumou?rs)",
    "organoids": r"organoid",
    "zebrafish / fly / worm / yeast": r"zebrafish|drosophila|C\. elegans|yeast",
    "mouse embryonic fibroblasts": r"\bMEFs?\b|embryonic fibroblast",
    "in vitro biochemistry": r"recombinant|purified protein",
    "cultured cells (unspecified)": r"\bcells\b",
}
UP = r"increas|promot|activat|enhanc|induc|up-?regulat|stimulat|elevat|rais|drive"
DOWN = r"decreas|inhibit|suppress|reduc|down-?regulat|repress|attenuat|impair|lower|block"
LOSS = r"\u0394|\u25b3|silenc|knock-?down|knock-?out|loss|deficien|delet|deplet|null|mutant|mutation|-/-|lack"
LIMITS = {
    "single cell line": r"\bin (?:a|one) (?:single )?cell line",
    "small sample": r"\b(?:n ?= ?\d{1,2}\b|small (?:sample|cohort))",
    "in vitro only": r"in vitro",
    "correlational design": r"correlat|associated with",
    "authors state limitation": r"limitation|further (?:studies|investigation) (?:are|is) (?:needed|required)|remain(?:s)? unclear|warrant",
}


def _sentences(text: str) -> list[str]:
    text = re.sub(r"^[A-Z ]+: ", "", text, flags=re.M)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text) if len(s.strip()) > 20]


def _hits(patterns: dict, text: str) -> list[str]:
    return [k for k, p in patterns.items() if re.search(p, text, re.I)]


def _direction(sentence: str) -> str:
    up, down = bool(re.search(UP, sentence, re.I)), bool(re.search(DOWN, sentence, re.I))
    return "up" if up and not down else "down" if down and not up else "mixed" if up and down else ""


def _implied(sentence: str, direction: str) -> str:
    """Effect of the gene itself: 'loss of X increased Y' implies X lowers Y."""
    if direction not in ("up", "down"):
        return ""
    if re.search(LOSS, sentence, re.I):
        return "down" if direction == "up" else "up"
    return direction


def _short(s: str, n: int = 260) -> str:
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + " ..."


def mine(records: list[dict], genes: list[str], topic: str) -> dict:
    gene_re = [re.compile(rf"(?<![A-Za-z0-9]){re.escape(g)}(?![A-Za-z0-9])", re.I) for g in genes]
    topic_words = [w for w in re.findall(r"[a-z0-9]+", topic.lower()) if len(w) >= 4]
    papers = []
    for r in records:
        text = f"{r.get('title', '')}. {r.get('abstract', '')}"
        sents = _sentences(r.get("abstract", ""))
        key = [s for s in sents if any(g.search(s) for g in gene_re)
               and (not topic_words or any(w[:6] in s.lower() for w in topic_words))]
        claims = []
        for s in key[:3]:
            d = _direction(s)
            claims.append({"sentence": _short(s), "direction": d, "implied_gene_effect": _implied(s, d)})
        methods, systems = _hits(METHODS, text), _hits(SYSTEMS, text)
        mechanistic = {"ChIP / promoter occupancy", "reporter assay", "knockdown / RNAi", "knockout / CRISPR",
                       "overexpression / re-expression", "co-immunoprecipitation / binding",
                       "structural / biophysical"}
        design = ("review" if r.get("is_review") else
                  "mechanistic experimental" if set(methods) & mechanistic else
                  "correlational / observational" if set(methods) & {"survival / correlation analysis",
                                                                      "patient cohort / tissue microarray"} else
                  "computational" if "computational / database analysis" in methods else "unclear from abstract")
        papers.append({"pmid": r["pmid"], "doi": r.get("doi", ""), "title": r.get("title", ""),
                       "year": r.get("year", ""), "journal": r.get("journal", ""),
                       "type": "review" if r.get("is_review") else "primary research",
                       "design": design, "methods": methods, "systems": systems,
                       "limitations": _hits(LIMITS, r.get("abstract", "")), "claims": claims,
                       "has_abstract": bool(r.get("abstract")), "url": r.get("url", "")})
    primary = [p for p in papers if p["type"] == "primary research"]
    conflicts = []
    for i, p in enumerate(primary):
        for q in primary[i + 1:]:
            dp = {c["implied_gene_effect"] for c in p["claims"]} - {""}
            dq = {c["implied_gene_effect"] for c in q["claims"]} - {""}
            if len(dp) == 1 and len(dq) == 1 and dp != dq:
                conflicts.append({"papers": [p["pmid"], q["pmid"]],
                                  "a": next(c["sentence"] for c in p["claims"] if c["implied_gene_effect"] in dp),
                                  "b": next(c["sentence"] for c in q["claims"] if c["implied_gene_effect"] in dq),
                                  "note": "The implied effect of the gene on the topic points opposite ways "
                                          "(after accounting for loss-of-function wording). Often explained by "
                                          "different systems or conditions; verify by reading both."})
    gaps = []
    sys_all = {s for p in primary for s in p["systems"]}
    if primary and "mouse / rat model" not in sys_all:
        gaps.append("No retrieved primary study reports an in vivo animal model.")
    if primary and "primary / patient material" not in sys_all:
        gaps.append("No retrieved primary study reports patient or primary human material.")
    if primary and not any(p["design"] == "mechanistic experimental" for p in primary):
        gaps.append("No retrieved primary study reports a mechanistic perturbation (e.g. knockdown, ChIP, rescue).")
    if len(primary) == 1:
        gaps.append("Only one primary study was retrieved; the finding is unreplicated in this set.")
    if not records:
        gaps.append("Nothing was retrieved; absence of hits is not evidence against the claim.")
    return {"papers": papers, "conflicts": conflicts, "gaps": gaps,
            "counts": {"primary": len(primary), "reviews": len(papers) - len(primary)},
            "caveat": ("Methods, systems, directions and limitations are keyword matches on titles and "
                       "abstracts. They point you to what to read; they are not findings, and full texts "
                       "were not retrieved.")}
