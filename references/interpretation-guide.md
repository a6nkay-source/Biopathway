# Interpretation guide

Common ways a pathway explanation goes wrong, and how to phrase things instead.

## 1. Correlation is not causation

| Record | It shows | Do not write | Write |
|---|---|---|---|
| STRING edge, any channel | functional association, undirected | "MDM2 regulates TP53" (from STRING) | "TP53 and MDM2 are strongly associated in STRING, with experimental support [EXP]. Direction and effect come from KEGG/Reactome: ..." |
| ClinVar Pathogenic | variant-disease association judged by submitters | "G12D causes pancreatic cancer" | "ClinVar classifies KRAS p.Gly12Asp as Pathogenic/Likely pathogenic (multiple submitters, no conflicts) [CUR]" |
| PubMed hit | the topic is discussed | "As shown in PMID:x, A activates B" (unless you read it) | "Further reading: PMID:x" |
| Co-membership in a pathway | both are drawn on the map | "A and B interact" | "Both are components of KEGG hsaNNNNN; the map draws no direct relation between them" |

## 2. KEGG boxes are groups

`RRAS2/MRAS/HRAS (+3)` is one KEGG box with six genes. The relation applies to the box as drawn. Don't conclude that every member, e.g. MRAS, activates RAF equally. The EGFR box in hsa04010 is a generic receptor tyrosine kinase box (25 genes); say "receptor tyrosine kinases including EGFR".

## 3. Routes are drawings, not measurements

A shortest route on a KEGG map is the curated textbook path. The cell may use several, in parallel, with feedback. When several equally short routes exist the report draws all of them; mention the alternatives (e.g. ARAF, BRAF and RAF1 for RAS -> MEK). Missing routes ("No directed KEGG route for MAPK1 -> EGFR") mean the map draws none, not that no feedback exists. Known feedbacks you add from memory need the HYP label.

## 4. Context

Curated pathways are composites across cell types, species and conditions. When the user asks about a specific tissue, disease or condition, say that the reconstruction is generic and point to what would establish context-specific relevance (expression data, cell-type-specific studies).

## 5. Variants

- Pathway membership belongs to the wild-type gene. "KRAS G12D is in the MAPK pathway" is wrong; "KRAS is a MAPK-pathway component; G12D ..." is right.
- Functional consequences come only from records that state them: UniProt natural variant or mutagenesis descriptions (quote, with the label), or curated statements. If the UniProt description for the exact substitution only lists cancers where it was found, it supports occurrence, not mechanism.
- Overlap with a domain or binding site is positional context [label of the feature], not proof the function is disrupted.
- A reference residue mismatch means stop and check numbering before interpreting.

## 6. Mechanism wording by relation type

| Report relation | Phrase |
|---|---|
| activation | "activates" (KEGG: often via the modifier shown, e.g. +p = phosphorylation) |
| inhibition | "inhibits" / "suppresses" |
| expression | "induces expression of" (transcriptional) |
| binding (undirected) | "binds / associates with" |
| phosphorylation (alone) | "phosphorylates" (effect not specified by the map) |
| participates in (Reactome) | "is a participant in" |
| contains (Reactome) | "is a sub-pathway of" |
| conversion (metabolic) | "is converted to ... by ..." |
| indirect effect (dashed) | "acts on ... through intermediates not drawn" |

## 7. Primary literature

- Curated absence plus published primary evidence is a common, important pattern. Report both: "KEGG and Reactome do not place X in Y [CUR]; however, study Z showed ... in <system> [EXP-lit; PMID]".
- Name what the experiment was. Promoter occupancy (ChIP), reporter assays, knockdown with rescue and genetic models are mechanistic. Expression-survival correlations are not.
- Give the system and replication: "one study, mouse fibroblasts" weighs differently from "several labs, patient tumours".
- Reviews summarise. Cite the primary studies they point to when you have read those.

## 8. Honesty about your own checks

- State only checks you ran, with what you saw. "The KEGG report shows BBC3 -> TP53, flagged 'direction suspect'; Reactome R-HSA-139913 states TP53 stimulates BBC3 expression" is good. "I checked the KGML and it says the opposite" is not acceptable unless you opened the KGML.
- When a database record seems wrong, say so as a suspicion, give the conflicting source, and don't blame the tool or the database without evidence.

## 9. Writing the answer

- Lead with the mechanism the curated records support, then layer in associations with their weaker labels.
- Put the label next to each claim, not only in a table at the end.
- If a source failed, say what kind of evidence is therefore missing (e.g. "STRING was unavailable, so interaction-partner evidence is absent").
- Don't use superlatives ("the master regulator") unless a cited record says so.
