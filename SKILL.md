---
name: biopathway-mapper
description: Evidence-traceable analysis of genes, proteins, mutations, signalling pathways, metabolic pathways and biological processes, built from live NCBI Gene, UniProt, Reactome, STRING, KEGG, ClinVar and PubMed records, with Mermaid/Graphviz pathway diagrams and source citations. Every relationship is labelled experimentally validated, curated, predicted, literature-supported or hypothetical. Use this skill whenever the user asks how a gene or protein works, what pathway it is in, what it interacts with, what a mutation (e.g. KRAS G12D, TP53 R175H, BRCA1 variants) does, how a signalling cascade runs (MAPK, PI3K-AKT-mTOR, p53, Wnt...), how a metabolic route proceeds (glycolysis, TCA...), how a process like apoptosis or DNA repair is organised, or wants a pathway diagram, even if they do not name any database.
compatibility: Python 3.9+ standard library only; outbound HTTPS to eutils.ncbi.nlm.nih.gov, rest.uniprot.org, reactome.org, string-db.org and rest.kegg.jp. Graphviz is optional (only for SVG rendering).
---

# BioPathway Mapper

Answer molecular-biology questions from database records rather than memory, and show the user exactly which record supports each claim and how strong that support is.

The bundled CLI does the retrieval, identifier resolution, evidence labelling and diagram drawing. Your job is to pick the right analysis, run it, read the report critically, and write an answer that stays inside what the evidence supports.

## Why this matters

Pathway questions invite confident storytelling: "X activates Y which drives Z". Much of that is textbook-true, some is cell-type specific, and some is folklore. Users of this skill want to know which is which. So:

- **Every relationship you state must trace to a record in the report.** If the report has no edge or statement for it, either leave it out or present it explicitly as your background knowledge labelled *hypothetical/insufficiently established* and suggest how to check it.
- **Association is not mechanism.** STRING edges, ClinVar classifications and PubMed co-mentions say two things are linked, not that one causes or controls the other. Say "associated with", never "causes" or "activates", unless a curated directed relation (KEGG relation, Reactome reaction) says so.
- **Absence of a record is not evidence of absence.** If a gene is not drawn on a KEGG map or not placed in a Reactome hierarchy, say the database does not place it there, not that it has no role.

## Workflow

1. **Identify the input type** and choose the analysis:

   | The user asks about... | Command |
   |---|---|
   | a gene/protein: identity, function, pathways, interactors | `gene SYMBOL [SYMBOL ...]` |
   | a signalling pathway or a cascade between genes | `pathway "NAME or hsaNNNNN" --genes A,B[,C]` |
   | a biological process/phenomenon (apoptosis, DNA repair, autophagy...) | `process "NAME or R-HSA-N" --genes A` |
   | a metabolic pathway | `metabolic "NAME or hsaNNNNN" [--module MNNNNN]` |
   | a protein variant | `mutation GENE CHANGE` (R175H, p.Arg175His, G12D, E746_A750del) |

   Mixed questions need more than one run, e.g. "how does KRAS G12D drive MAPK signalling" = `mutation KRAS G12D` + `pathway "MAPK signaling" --genes KRAS,MAPK1`. Read `references/analysis-workflows.md` for what each analysis retrieves, its options, and worked recipes.

2. **Run it** from the skill directory (absolute path shown as `<skill>`):

   ```bash
   python3 <skill>/scripts/bpm_cli.py process apoptosis --genes TP53 --out ./bpm_tp53_apoptosis
   ```

   `--out` writes `report.md` (read this), `analysis.json` (full data), `diagram.mmd` and `diagram.dot`. Without `--out` the Markdown report is printed. Responses are cached for 7 days in `~/.cache/biopathway-mapper`; `--offline` answers from cache only.

3. **Read `report.md` critically before writing anything.** Check, in order:
   - *Resolved identifiers*: is it the gene the user meant? Alias matches are warned about.
   - *Data source status and Warnings*: a failed source means a gap, not a negative finding. Tell the user which sources were unavailable.
   - *Interpretation notes*: which KEGG/Reactome record was picked from the name candidates. If the pick is wrong, re-run with the explicit id from the candidate list.
   - *Relationships and statements*: these are the only material you may present as supported.

4. **Explain the mechanism** using the report's directed routes, Reactome events and UniProt/ClinVar statements. Group by evidence class. Mark each claim inline with its label code, e.g. "AKT inhibits the TSC1/TSC2 complex, relieving inhibition of RHEB, which activates mTORC1 [CUR; KEGG hsa04151]". Make nuances explicit: KEGG boxes such as `RRAS2/MRAS/HRAS (+3)` are gene groups KEGG draws as one node, not proof each member acts identically.

5. **Show the diagram.** Paste the `mermaid` block from the report (it renders in most Markdown viewers) and include the legend. If the user wants an image file and Graphviz is installed, `--out` also writes `diagram.svg`. Otherwise give them `diagram.dot`.

6. **Cite sources.** Use the numbered Sources list from the report (database + stable id + URL). Literature marked LIT came from a search and only supports "this topic is discussed in"; do not cite it as proof of a specific interaction.

7. **State limits** at the end: unavailable sources, cell-type/context dependence, map-drawing limits, and anything you added from background knowledge (labelled hypothetical).

## Evidence labels

| Code | Label | Typical source in this tool |
|---|---|---|
| EXP | experimentally validated | UniProt ECO:0000269/0000314/0000315/0000353; GO IDA/IMP/IPI...; STRING experiments channel >= 0.4 |
| CUR | curated database evidence | KEGG map relations and reactions; Reactome non-inferred events; ClinVar expert panel / multi-submitter; STRING databases channel |
| PRED | computationally predicted | Reactome inferred-from-orthology; UniProt similarity/automatic; GO IEA/ISS; STRING co-expression, neighbourhood, fusion, co-occurrence |
| LIT | literature-supported association | STRING text-mining only; ClinVar single submitter; PubMed search hits |
| HYP | hypothetical/insufficiently established | no channel or record strong enough; your own background claims |

The exact rules and their rationale are in `references/evidence-framework.md`. Do not upgrade a label in prose. If you think the database under-labels something, say so and explain why, but keep the label.

## Answer template

```markdown
## <Question restated>

**Inputs resolved:** <symbol (NCBI Gene id, UniProt acc)> ...
**Sources queried:** <ok / failed list>

### Mechanism
<Narrative built from report statements, each with [CODE; source id]>

### Pathway diagram
<mermaid block + legend>

### Evidence summary
| Relationship | Evidence | Source |
...

### Caveats
- <unavailable sources, context dependence, map limits, background-knowledge claims labelled HYP>

### Sources
1. <Database id — title. URL>
```

## When things go wrong

- **Exit code 2 / "Could not resolve"**: check spelling and organism; try the official HGNC symbol or a UniProt accession.
- **Exit code 3 / all sources failed**: network or service outage. Retry later or use `--offline` if the query was run before. Do not answer from memory as if the tool had succeeded.
- **Wrong pathway picked**: re-run with the id from "KEGG name candidates" / "Reactome candidates".
- **"No directed KEGG route"**: the map does not draw a path between those genes. Try `--hops 2` with one focus gene, another map, or `process` for Reactome.
- **Reference residue mismatch in `mutation`**: the variant probably uses a non-canonical isoform's numbering. Say so; do not interpret domain overlaps.
- **Commercial use**: the KEGG API is free for academic use only. Use `--no-kegg` (or `BPM_DISABLE_KEGG=1`) if the user is not an academic user; `pathway` then falls back to Reactome and `metabolic` reports that KEGG is required.

## Reference files

- `references/analysis-workflows.md`: per-analysis inputs, options, what is retrieved, recipes for combined questions. Read when choosing commands or options.
- `references/evidence-framework.md`: labelling rules and the reasoning behind each threshold. Read when a label surprises you or the user challenges it.
- `references/data-sources.md`: endpoints, rate limits, licences, caching and identifier systems. Read for API failures, licensing or organism questions.
- `references/interpretation-guide.md`: pitfalls (paralog boxes, correlation vs causation, context dependence, ClinVar semantics) with wording examples. Read before writing a mechanism explanation for the first time in a session.
