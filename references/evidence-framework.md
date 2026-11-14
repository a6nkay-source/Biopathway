# Evidence framework

Implemented in `scripts/bpm/evidence.py`. Keep this file and that module in sync.

## Principles

1. **Label what the record states, not what is plausible.** The label describes the kind of support a database record offers for the specific claim made from it.
2. **Strongest applicable label, never upgraded.** If a record carries several evidence codes, the strongest wins. If a record does not justify a label, the next weaker one is used.
3. **Associations stay associations.** Undirected or statistical links (STRING, ClinVar, text mining) never become directed or causal claims, whatever their score.
4. **Curation is not the same as experiment.** KEGG and Reactome are expert-curated summaries of literature. Their individual steps are well supported but are labelled CUR, not EXP, because the record does not tell us which experiment, in which system, supports that step.

## Labels and rules

### EXP: experimentally validated

| Source | Rule |
|---|---|
| UniProt annotation (function, feature, variant) | ECO:0000269 (experimental evidence, manual assertion), ECO:0000314 (direct assay), ECO:0000315 (mutant phenotype), ECO:0000353 (physical interaction) |
| GO term via UniProt | EXP, IDA, IPI, IMP, IGI, IEP and the high-throughput HTP/HDA/HMP/HGI/HEP codes |
| STRING association | experiments channel (`escore`) >= 0.4 |

Caveat for STRING: the experiments channel includes evidence transferred from orthologs, so EXP here means "experimental interaction data exist for this pair or its orthologs". The report says so in the basis column.

### CUR: curated database evidence

| Source | Rule |
|---|---|
| KEGG pathway relation (KGML) | every relation; `indirect effect` / `missing interaction` subtypes are flagged as indirect and drawn dashed |
| KEGG reaction / module step | every step |
| Reactome event or membership | `isInferred = false` |
| UniProt | ECO:0000303/0000304/0000305/0000312/0007744 (author statements, curator inference, manually imported/combinatorial); reviewed entry without a code |
| GO | TAS, NAS, IC |
| ClinVar | review status "practice guideline", "reviewed by expert panel", or "criteria provided, multiple submitters, no conflicts" |
| STRING | curated-databases channel (`dscore`) >= 0.4 when experiments < 0.4 |

### PRED: computationally predicted

| Source | Rule |
|---|---|
| Reactome | `isInferred = true` (projected from another species by orthology) |
| UniProt | ECO:0000250 (similarity), 0000255/0000256/0000259 (models, rules, signatures), automatic imports; any unreviewed TrEMBL annotation without stronger codes |
| GO | all other codes (IEA, ISS, ISO, IBA, RCA...) |
| STRING | co-expression, neighbourhood, fusion or co-occurrence channel >= 0.4 with no experimental, database or text-mining support at that level |

### EXP-lit: experimentally shown in a primary study you read

Not assigned by the tool; you assign it after reading an abstract (or full text) from `literature`.

| Condition | Label |
|---|---|
| The abstract states a specific experiment and its result (ChIP, reporter assay, knockdown or knockout with rescue, binding assay, mouse genetics...) | EXP-lit, plus model system, method, and "single study" if it is one |
| Correlation only (expression vs outcome, co-occurrence in tumours, metabolomics association) | LIT |
| Review, editorial, commentary | LIT (it summarises others; cite the primary papers it points to if you read them) |
| Title or search hit you did not read | further reading, no label |

Why a separate code: curated databases lag the literature and miss most single-lab findings. Leaving primary evidence out makes an answer look more certain than it is. But one paper in one cell line is not a curated consensus, so EXP-lit always carries its system and replication status and is never merged into CUR.

### LIT: literature-supported association

| Source | Rule |
|---|---|
| STRING | text-mining channel (`tscore`) >= 0.4 is the only channel at threshold: the genes are co-mentioned, not shown to interact |
| ClinVar | "criteria provided, single submitter" or conflicting: an assertion by one lab, not independently confirmed |
| PubMed search results | unread hits are further reading only; the tool never uses them to draw an edge. Correlational primary studies and reviews you read are LIT |

### HYP: hypothetical / insufficiently established

| Source | Rule |
|---|---|
| STRING | no single channel reaches 0.4 even if the combined score is high (several weak signals) |
| ClinVar | no assertion criteria |
| Your own background knowledge | anything you state that the report does not contain |

## Why 0.4 per channel for STRING

0.4 is STRING's own "medium confidence" cut-off. Applying it per channel rather than to the combined score prevents a pair that is weakly co-expressed, weakly co-mentioned and weakly co-occurring from being presented as one kind of strong evidence. The combined score is still reported in `analysis.json` (`scores.combined`).

## What labels do not capture

- **Context.** A CUR KEGG relation may hold only in particular cell types or conditions. KEGG maps are composites across systems.
- **Direction and sign for associations.** STRING tells you neither.
- **Variant effect.** Pathway membership is that of the wild-type gene. A variant's effect is only stated where UniProt (natural variant / mutagenesis description) or another cited record says so.
- **Quantity.** Labels are categorical; they are not probabilities.

## Wording by label

| Label | Acceptable verbs |
|---|---|
| EXP | "has been shown experimentally to bind / phosphorylate...", with the record |
| CUR | "is curated in KEGG/Reactome as activating / inhibiting / converting..." |
| PRED | "is predicted to...", "by orthology..." |
| LIT | "is associated with...", "is co-reported with..." |
| HYP | "may...", "has been proposed...", "is not established in the retrieved records" |
