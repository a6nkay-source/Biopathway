# Analysis workflows

All commands: `python3 <skill>/scripts/bpm_cli.py <command> ...`

Shared options: `--out DIR`, `--format md|json|mermaid|dot`, `--max-edges N` (diagram size, default 50), `--taxid N` (default 9606), `--no-kegg`, `--offline`, `--no-cache`, `--cache-dir`, `--cache-ttl-days`.

Supported organisms (taxid -> KEGG code): 9606 hsa, 10090 mmu, 10116 rno, 7955 dre, 7227 dme, 6239 cel, 559292 sce. Other taxids work for NCBI/UniProt/STRING but KEGG is skipped.

## Contents

1. gene
2. pathway
3. process
4. metabolic
5. mutation
6. literature
7. Recipes for combined questions

---

## 1. `gene SYMBOL [SYMBOL ...]`

Retrieves: NCBI Gene (official symbol, aliases, location, RefSeq summary); UniProt reviewed entry (function text with ECO codes, GO biological process terms); Reactome pathways for the protein; KEGG pathways for the gene; STRING associations; PubMed reviews.

- One gene: STRING top `--partners` (default 15) interaction partners.
- Several genes: STRING network among them, plus KEGG maps containing all of them (handy for picking a map for `pathway`).

Diagram: undirected STRING association network, coloured by evidence class. It is not a signalling diagram.

## 2. `pathway QUERY --genes A,B[,C] [--hops N]`

QUERY is a name ("MAPK signaling"), a KEGG id (`hsa04010`, `map04010`) or a Reactome id (`R-HSA-...`, which is routed to `process`).

Name resolution: tokens of the query are matched against KEGG pathway names for the organism; maps containing all focus genes get a boost. Candidates are listed in the report notes. Always check the pick.

Reconstruction from KGML:
- Gene boxes become nodes labelled with their members (`MAPK1/MAPK3`); KEGG groups become complexes (`TSC2:TSC1`); compounds and linked maps are nodes too.
- Relation subtypes map to activation, inhibition (incl. repression), expression, binding (undirected), dissociation, state change, phosphorylation and other modifications. Modifiers like `+p` and `via <compound>` are kept.
- Focus selection:
  - two or more focus genes: every shortest directed route between each ordered pair (binding edges traversable both ways). Routes are listed as Mechanism statements.
  - one focus gene: its `--hops` neighbourhood (default 1).
  - none: the whole map (diagram capped by `--max-edges`).
- Also lists the focus genes' Reactome pathways whose names match the query.

## 3. `process QUERY [--genes A,B]`

QUERY is a process name or Reactome id. Uses Reactome because its hierarchy models processes well.

Retrieves: the best-matching Reactome pathway (candidates noted), its summary and cited references, its direct sub-pathways, and for each focus gene:
- the Reactome sub-pathways inside this process that contain the gene (participates in), placed under the top-level branch they belong to;
- every Reactome event (reaction) in the process whose name mentions the gene, which are the curated mechanistic steps (e.g. "TP53 stimulates BBC3 (PUMA) expression");
- the gene's Reactome pathways outside the process, listed in section 3 so you can say where else it acts;
- whether the top KEGG maps matching the query contain the gene.

If Reactome does not place a gene inside the process, the report warns. Say so plainly.

## 4. `metabolic QUERY [--module MNNNNN] [--genes A,B]`

Retrieves KEGG reactions. With `--module`, only the module's main route is drawn (e.g. M00001 = glycolysis glucose -> pyruvate; M00003 = gluconeogenesis; M00009 = TCA cycle). Without it, all reactions on the map are drawn (large); available modules are listed in the notes.

Edges are compound -> compound conversions labelled with the organism's enzyme genes from KGML and `reversible` where KEGG marks it. Steps with no enzyme in this organism are noted (e.g. archaeal or bacterial alternatives drawn on reference maps). `--genes` reports which steps those enzymes catalyse.

## 5. `mutation GENE CHANGE`

Accepted CHANGE forms: `R175H`, `p.R175H`, `p.Arg175His`, `p.(Arg175His)`, `R213*`, `R213X`, `p.Arg213Ter`, `K1183fs`, `E746_A750del`. Anything else gets a warning and only a ClinVar text search.

Retrieves:
- reference residue check against the canonical UniProt sequence (mismatch = probable isoform numbering issue; report warns);
- UniProt features overlapping the position: domains/regions/DNA-binding/zinc fingers/motifs (drawn), binding/active/modified sites (statements), natural variants and mutagenesis at the same position, with their descriptions verbatim and evidence codes;
- ClinVar germline, oncogenicity and clinical-impact classifications with review status (labelled per review status);
- KEGG maps containing the gene (wild-type membership);
- PubMed search for the variant.

The variant is never linked directly to a pathway: the diagram goes variant -> gene -> pathway, because membership belongs to the gene.

## 6. `literature [TOPIC] [--genes A,B] [--pmids N,M] [--max 8]`

Retrieves primary research and up to 3 reviews from PubMed, each with its full abstract (efetch). PubMed's relevance order often buries the most on-topic papers, so up to 100 hits are pulled and re-ranked: gene symbol in the title scores 2, each topic word scores 1, and PubMed's order breaks ties. `--pmids` fetches specific papers, e.g. to check what a reference actually says. Unknown PMIDs are warned about.

Nothing here becomes an edge. You read the abstracts and grade findings EXP-lit or LIT (see evidence-framework.md). Use it to test a user's claim, to fill gaps the curated databases leave, and to verify any paper you intend to cite.

## 7. Recipes

| Question | Runs |
|---|---|
| How does TP53 trigger apoptosis? | `process apoptosis --genes TP53`; optionally `pathway hsa04115 --genes TP53,BAX` for KEGG p53 targets |
| How does BRCA1 work in DNA repair? | `process "DNA repair" --genes BRCA1`; `gene BRCA1` for interactors (BARD1, PALB2...) |
| EGFR to ERK signalling | `pathway "MAPK signaling" --genes EGFR,MAPK1` (or `hsa04012` ErbB) |
| What does KRAS G12D do? | `mutation KRAS G12D`; `pathway "Ras signaling" --genes KRAS,MAPK1` for downstream context |
| PI3K-AKT-mTOR axis | `pathway hsa04151 --genes PIK3CA,AKT1,MTOR`; `pathway hsa04150 --genes AKT1,MTOR` for the mTOR map |
| Walk me through glycolysis | `metabolic glycolysis --module M00001` |
| Is gene X linked to process Y? | `process "Y" --genes X`; then `literature "Y" --genes X` and read the primary studies; `gene X` for STRING/GO |
| "I read that X controls Y. True?" | curated check (`process`/`pathway`/`metabolic` with `--genes X`) **and** `literature "Y" --genes X`; report both what the databases contain and what the strongest primary studies show |
| Compare several genes | `gene A B C` (STRING network + shared KEGG maps), then `pathway <shared map> --genes A,B,C` |
