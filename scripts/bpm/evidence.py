"""Evidence classification.

Each rule maps what a database *actually records* onto one of five labels. The
rules are deliberately conservative: when a record does not justify a stronger
label, the weaker one is used. The reasoning for every threshold is written up
in references/evidence-framework.md; keep the two in sync.
"""

from __future__ import annotations

EXPERIMENTAL = "experimentally validated"
CURATED = "curated database evidence"
PREDICTED = "computationally predicted"
LITERATURE = "literature-supported association"
HYPOTHETICAL = "hypothetical/insufficiently established"

LEVELS = [EXPERIMENTAL, CURATED, PREDICTED, LITERATURE, HYPOTHETICAL]
SHORT = {EXPERIMENTAL: "EXP", CURATED: "CUR", PREDICTED: "PRED",
         LITERATURE: "LIT", HYPOTHETICAL: "HYP"}

# STRING's own "medium confidence" cut-off, applied per evidence channel.
STRING_THRESHOLD = 0.4


def classify_string(scores: dict) -> tuple[str, str]:
    """Label a STRING association from its per-channel scores.

    STRING edges are undirected functional associations. The label says what
    kind of evidence supports the *association*; it never implies direction,
    sign or mechanism.
    """
    def s(name):
        try:
            return float(scores.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    t = STRING_THRESHOLD
    if s("escore") >= t:
        return EXPERIMENTAL, (f"STRING experiments channel {s('escore'):.3f} (>= {t}); "
                              "channel can include evidence transferred from orthologs")
    if s("dscore") >= t:
        return CURATED, f"STRING curated-database channel {s('dscore'):.3f} (>= {t})"
    if s("tscore") >= t:
        return LITERATURE, (f"STRING text-mining channel {s('tscore'):.3f} only; "
                            "co-mention in literature, not a demonstrated interaction")
    predicted = {k: s(k) for k in ("nscore", "fscore", "pscore", "ascore")}
    best = max(predicted, key=predicted.get)
    if predicted[best] >= t:
        names = {"nscore": "gene neighbourhood", "fscore": "gene fusion",
                 "pscore": "phylogenetic co-occurrence", "ascore": "co-expression"}
        return PREDICTED, f"STRING {names[best]} channel {predicted[best]:.3f} only"
    return HYPOTHETICAL, (f"no single STRING channel reaches {t} "
                          f"(combined score {s('score'):.3f})")


# ECO codes used in UniProtKB manual and automatic assertions.
_ECO = {
    "ECO:0000269": EXPERIMENTAL,   # experimental evidence used in manual assertion
    "ECO:0000314": EXPERIMENTAL,   # direct assay evidence
    "ECO:0000315": EXPERIMENTAL,   # mutant phenotype evidence
    "ECO:0000353": EXPERIMENTAL,   # physical interaction evidence
    "ECO:0007744": CURATED,        # combinatorial evidence (e.g. PDB, large-scale data), manual
    "ECO:0000303": CURATED,        # non-traceable author statement
    "ECO:0000304": CURATED,        # traceable author statement
    "ECO:0000305": CURATED,        # curator inference
    "ECO:0000312": CURATED,        # imported from another database, manual
    "ECO:0000250": PREDICTED,      # sequence similarity
    "ECO:0000255": PREDICTED,      # sequence model / match to rule
    "ECO:0000256": PREDICTED,      # automatic annotation rule
    "ECO:0000259": PREDICTED,      # InterPro signature match
    "ECO:0007829": PREDICTED,      # combinatorial evidence, automatic
    "ECO:0000313": PREDICTED,      # imported, automatic
}
_ORDER = {level: i for i, level in enumerate(LEVELS)}


def classify_eco(evidences: list, reviewed: bool = True) -> tuple[str, str]:
    """Label a UniProt annotation from its ECO evidence codes (strongest wins)."""
    codes = [e.get("evidenceCode") for e in (evidences or []) if e.get("evidenceCode")]
    known = [(_ECO[c], c) for c in codes if c in _ECO]
    if known:
        level, code = min(known, key=lambda pair: _ORDER[pair[0]])
        return level, f"UniProt evidence code {code}"
    if reviewed:
        return CURATED, "UniProtKB/Swiss-Prot reviewed annotation without a specific evidence code"
    return PREDICTED, "UniProtKB/TrEMBL unreviewed annotation"


_GO_EXPERIMENTAL = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP", "HTP", "HDA", "HMP", "HGI", "HEP"}
_GO_CURATED = {"TAS", "NAS", "IC"}


def classify_go(evidence_type: str) -> tuple[str, str]:
    """GO evidence code as given by UniProt, e.g. 'IDA:UniProtKB'."""
    code = (evidence_type or "").split(":")[0].strip().upper()
    if code in _GO_EXPERIMENTAL:
        return EXPERIMENTAL, f"GO evidence code {code}"
    if code in _GO_CURATED:
        return CURATED, f"GO evidence code {code}"
    if code:
        return PREDICTED, f"GO evidence code {code} (computational or by similarity)"
    return HYPOTHETICAL, "GO annotation without an evidence code"


def classify_kegg(subtypes: list) -> tuple[str, str]:
    """KEGG pathway maps are manually drawn from the literature: curated."""
    if "indirect effect" in subtypes or "missing interaction" in subtypes:
        return CURATED, ("KEGG manually curated pathway map; flagged by KEGG as an "
                         "indirect effect or missing interaction, so intermediate steps are not specified")
    return CURATED, "KEGG manually curated pathway map"


def classify_reactome(is_inferred: bool) -> tuple[str, str]:
    if is_inferred:
        return PREDICTED, "Reactome event computationally inferred from another species"
    return CURATED, "Reactome expert-curated, peer-reviewed event"


_CLINVAR_STRONG = ("practice guideline", "reviewed by expert panel",
                   "criteria provided, multiple submitters, no conflicts")


def classify_clinvar(review_status: str) -> tuple[str, str]:
    """ClinVar records clinical assertions, i.e. variant-disease association."""
    status = (review_status or "").strip().lower()
    if status in _CLINVAR_STRONG:
        return CURATED, f"ClinVar review status: {status}"
    if status.startswith("criteria provided"):
        return LITERATURE, f"ClinVar review status: {status} (not independently confirmed)"
    return HYPOTHETICAL, f"ClinVar review status: {status or 'none'}"


def strongest(levels) -> str:
    levels = list(levels)
    return min(levels, key=lambda l: _ORDER[l]) if levels else HYPOTHETICAL
