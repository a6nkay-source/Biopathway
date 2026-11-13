# BioPathway Mapper: pathway analysis

**Query:** `PI3K-AKT-mTOR | genes: PIK3CA, AKT1, MTOR`

## 1. Input and resolved identifiers

| Input | Symbol | NCBI Gene | UniProt | Name | Location |
|---|---|---|---|---|---|
| PIK3CA | PIK3CA | 5290 | P42336 | phosphatidylinositol-4,5-bisphosphate 3-kinase catalytic subunit alpha | 3q26.32 |
| AKT1 | AKT1 | 207 | P31749 | AKT serine/threonine kinase 1 | 14q32.33 |
| MTOR | MTOR | 2475 | P42345 | mechanistic target of rapamycin kinase | 1p36.22 |

## 2. Data source status

| Source | Status |
|---|---|
| KEGG | ok |
| NCBI Gene | ok |
| PubMed | ok |
| Reactome | ok |
| UniProt | ok |

22 API requests (22 served from cache).

## 3. Pathway context

| Source | ID | Name | Gene | Evidence | Note |
|---|---|---|---|---|---|
| KEGG | [hsa04151](https://www.kegg.jp/pathway/hsa04151) | PI3K-Akt signaling pathway |  | CUR |  |
| Reactome | [R-HSA-198203](https://reactome.org/content/detail/R-HSA-198203) | PI3K/AKT activation | PIK3CA | CUR |  |
| Reactome | [R-HSA-389357](https://reactome.org/content/detail/R-HSA-389357) | CD28 dependent PI3K/Akt signaling | PIK3CA | CUR |  |
| Reactome | [R-HSA-8851907](https://reactome.org/content/detail/R-HSA-8851907) | MET activates PI3K/AKT signaling | PIK3CA | CUR |  |
| Reactome | [R-HSA-6811558](https://reactome.org/content/detail/R-HSA-6811558) | PI5P, PP2A and IER3 Regulate PI3K/AKT Signaling | PIK3CA | CUR |  |
| Reactome | [R-HSA-199418](https://reactome.org/content/detail/R-HSA-199418) | Negative regulation of the PI3K/AKT network | AKT1 | CUR |  |
| Reactome | [R-HSA-389357](https://reactome.org/content/detail/R-HSA-389357) | CD28 dependent PI3K/Akt signaling | AKT1 | CUR |  |
| Reactome | [R-HSA-6811558](https://reactome.org/content/detail/R-HSA-6811558) | PI5P, PP2A and IER3 Regulate PI3K/AKT Signaling | AKT1 | CUR |  |
| Reactome | [R-HSA-389357](https://reactome.org/content/detail/R-HSA-389357) | CD28 dependent PI3K/Akt signaling | MTOR | CUR |  |

## 4. Reconstructed molecular relationships

Evidence mix: CUR 5

| From | Relation | To | Evidence | Basis | Refs |
|---|---|---|---|---|---|
| RHEB | → activation | RPTOR:MTOR:MLST8 | CUR | KEGG manually curated pathway map; KGML PPrel [activation] | [1] |
| PIK3CA/P3R3URF-PIK3R3/PIK3CB (+4) | → activation | Phosphatidylinositol-3,4,5-trisphosphate | CUR | KEGG manually curated pathway map; KGML PCrel [activation] | [1] |
| Phosphatidylinositol-3,4,5-trisphosphate | → activation | AKT1/AKT3/AKT2 | CUR | KEGG manually curated pathway map; KGML PCrel [activation] | [1] |
| TSC2:TSC1 | → inhibition | RHEB | CUR | KEGG manually curated pathway map; KGML PPrel [inhibition] | [1] |
| AKT1/AKT3/AKT2 | → inhibition +p | TSC2:TSC1 | CUR | KEGG manually curated pathway map; KGML PPrel [inhibition, phosphorylation] | [1] |

## 5. Evidence-labelled statements

### Mechanism

- **[CUR]** AKT1 to MTOR, shortest directed route in KEGG hsa04151 (PI3K-Akt signaling pathway): AKT1/AKT3/AKT2 -[inhibition +p]-> TSC2:TSC1 -[inhibition]-> RHEB -[activation]-> RPTOR:MTOR:MLST8. Each step is a KEGG-drawn relation; a route is a curated summary and may skip intermediates. [1]
- **[CUR]** PIK3CA to AKT1, shortest directed route in KEGG hsa04151 (PI3K-Akt signaling pathway): PIK3CA/P3R3URF-PIK3R3/PIK3CB (+4) -[activation]-> Phosphatidylinositol-3,4,5-trisphosphate -[activation]-> AKT1/AKT3/AKT2. Each step is a KEGG-drawn relation; a route is a curated summary and may skip intermediates. [1]
- **[CUR]** PIK3CA to MTOR, shortest directed route in KEGG hsa04151 (PI3K-Akt signaling pathway): PIK3CA/P3R3URF-PIK3R3/PIK3CB (+4) -[activation]-> Phosphatidylinositol-3,4,5-trisphosphate -[activation]-> AKT1/AKT3/AKT2 -[inhibition +p]-> TSC2:TSC1 -[inhibition]-> RHEB -[activation]-> RPTOR:MTOR:MLST8. Each step is a KEGG-drawn relation; a route is a curated summary and may skip intermediates. [1]

## 6. Pathway diagram

Directed relations redrawn from the KEGG map (KGML). Arrow = activation, x = inhibition, dashed = expression/indirect. Multi-gene boxes are paralog groups that KEGG draws as one node.

```mermaid
flowchart LR
    n0[["TSC2:TSC1"]]
    n1["RHEB"]
    n2[["RPTOR:MTOR:MLST8"]]
    n3["PIK3CA/P3R3URF-PIK3R3/PIK3CB (+4)"]
    n4(["Phosphatidylinositol-3,4,5-trisphosphate"])
    n5["AKT1/AKT3/AKT2"]
    n1 -->|"activation · CUR"| n2
    n3 -->|"activation · CUR"| n4
    n4 -->|"activation · CUR"| n5
    n0 --x|"inhibition · CUR"| n1
    n5 --x|"inhibition +p · CUR"| n0
    linkStyle 0 stroke:#2166ac,stroke-width:2px
    linkStyle 1 stroke:#2166ac,stroke-width:2px
    linkStyle 2 stroke:#2166ac,stroke-width:2px
    linkStyle 3 stroke:#2166ac,stroke-width:2px
    linkStyle 4 stroke:#2166ac,stroke-width:2px
    classDef focus fill:#fff3bf,stroke:#b8860b,stroke-width:3px
    classDef compound fill:#e6f4ea,stroke:#3c8d5a
    classDef pathway fill:#e8eaf6,stroke:#3f51b5
    classDef variant fill:#fde2e1,stroke:#c0392b,stroke-width:2px
    classDef condition fill:#f3e5f5,stroke:#8e24aa
    classDef region fill:#f1f3f4,stroke:#5f6368
    class n4 compound
    class n2,n3,n5 focus
```

| Line colour | Code | Evidence class |
|---|---|---|
| green | EXP | experimentally validated |
| blue | CUR | curated database evidence |
| orange | PRED | computationally predicted |
| purple | LIT | literature-supported association |
| grey | HYP | hypothetical/insufficiently established |

Solid arrow = activation/conversion/membership; `x` head = inhibition; dashed = expression, indirect or non-curated; no head = undirected association.

## 7. Interpretation notes and limits

- No directed KEGG route for: AKT1 -> PIK3CA; MTOR -> AKT1; MTOR -> PIK3CA. This reflects the map's drawing, not proof that no regulation exists.
- KEGG hsa04151 contains 85 reconstructable relations; 5 are kept for this question.

## 8. Literature

CUR rows are references cited by the curated pathway record; LIT rows are search hits offered for reading and were not used to draw any relationship.

- **[CUR]** Engelman JA (2006). The evolution of phosphatidylinositol 3-kinases as regulators of growth and metabolism. *Nat Rev Genet*. [PMID:16847462](https://pubmed.ncbi.nlm.nih.gov/16847462/) — reference of KEGG hsa04151
- **[CUR]** Song G (2005). The activation of Akt/PKB signaling pathway and cell survival. *J Cell Mol Med*. [PMID:15784165](https://pubmed.ncbi.nlm.nih.gov/15784165/) — reference of KEGG hsa04151
- **[CUR]** Hers I (2011). Akt signalling in health and disease. *Cell Signal*. [PMID:21620960](https://pubmed.ncbi.nlm.nih.gov/21620960/) — reference of KEGG hsa04151
- **[CUR]** Duronio V (2008). The life of a cell: apoptosis regulation by the PI3K/PKB pathway. *Biochem J*. [PMID:18842113](https://pubmed.ncbi.nlm.nih.gov/18842113/) — reference of KEGG hsa04151
- **[CUR]** Kim D (2002). Akt: versatile mediator of cell survival and beyond. *J Biochem Mol Biol*. [PMID:16248975](https://pubmed.ncbi.nlm.nih.gov/16248975/) — reference of KEGG hsa04151
- **[LIT]** Browne IM (2024). Optimal targeting of PI3K-AKT and mTOR in advanced oestrogen receptor-positive breast cancer. *Lancet Oncol*. [PMID:38547898](https://pubmed.ncbi.nlm.nih.gov/38547898/) — PubMed search: PIK3CA[tiab] AND AKT1[tiab] AND MTOR[tiab] AND (pi3k OR akt OR mtor)
- **[LIT]** Martinez-Lopez A (2019). Vascular malformations syndromes: an update. *Curr Opin Pediatr*. [PMID:31693582](https://pubmed.ncbi.nlm.nih.gov/31693582/) — PubMed search: PIK3CA[tiab] AND AKT1[tiab] AND MTOR[tiab] AND (pi3k OR akt OR mtor)
- **[LIT]** Li A (2025). Sophora Flos extract ameliorates inflammatory bowel disease via inhibiting the PI3K/AKT/mTOR signaling pathway activation and modulating M1/M2 polarization in macrophages. *Phytomedicine*. [PMID:40737847](https://pubmed.ncbi.nlm.nih.gov/40737847/) — PubMed search: PIK3CA[tiab] AND AKT1[tiab] AND MTOR[tiab] AND (pi3k OR akt OR mtor)
- **[LIT]** Sahm F (2025). European Association of Neuro-Oncology guideline on molecular testing of meningiomas for targeted therapy selection. *Neuro Oncol*. [PMID:39577862](https://pubmed.ncbi.nlm.nih.gov/39577862/) — PubMed search: PIK3CA[tiab] AND AKT1[tiab] AND MTOR[tiab] AND (pi3k OR akt OR mtor)
- **[LIT]** Alves CL (2025). Dual PI3K/mTOR inhibition is required to combat resistance to CDK4/6 inhibitor and endocrine therapy in PIK3CA-mutant breast cancer. *Sci Transl Med*. [PMID:41406241](https://pubmed.ncbi.nlm.nih.gov/41406241/) — PubMed search: PIK3CA[tiab] AND AKT1[tiab] AND MTOR[tiab] AND (pi3k OR akt OR mtor)

## Sources

1. KEGG hsa04151 — PI3K-Akt signaling pathway. <https://www.kegg.jp/pathway/hsa04151>

Records retrieved between 2026-11-13T19:28:33Z and 2026-11-13T19:29:36Z (UTC). Databases are updated continually; re-run to refresh.