# BioPathway 2.0: operations, MCP server and Explorer

## Contents
1. Architecture
2. Operations (shared by CLI `tool`, MCP and Explorer API)
3. How mutant changes are derived
4. Perturbation semantics
5. Signal playback semantics
6. Structures
7. Expression and datasets
8. Literature mining
9. Running the MCP server and the Explorer

## 1. Architecture

```
SKILL.md (reasoning rules)      scripts/bpm/ (database clients, evidence, analyses)
        │                                   │
        │                        scripts/bpm/service.py  ← one operation table
        │                         ├── scripts/bpm_cli.py tool <op>   (Claude in a shell)
        │                         ├── scripts/bpm_mcp.py             (MCP stdio server)
        │                         └── scripts/bpm_api.py             (HTTP API → Explorer)
        └──────────── uses ────────────────────────┘          explorer/ (React, Cytoscape, Three.js)
```

Database access exists once (`scripts/bpm/integrations`). The MCP server and the Explorer never call databases themselves.

## 2. Operations

| Operation | Returns |
|---|---|
| `report` kind=gene/pathway/process/metabolic/mutation/literature | the Markdown evidence report |
| `pathway_graph` query, genes, hops | Cytoscape elements for the focused KEGG subgraph + `full` map for expansion |
| `interaction_graph` genes | STRING association network (undirected) |
| `metabolic_graph` query, module | compound → compound conversions with enzyme genes |
| `process_graph` query, genes | Reactome hierarchy + the genes' sub-pathways |
| `node_info` symbol | identifiers, function (ECO-labelled), GO, pathways, partners |
| `compare_mutation` gene, change, pathway, genes | normal graph + overlay of documented variant changes |
| `perturb_pathway` query, genes, source, remove, inhibit | reachability before/after, signed lost routes, reroutes |
| `structures` query | AlphaFold model + PDB entries + UniProt features + Reactome pathways |
| `structure_coords` kind=alphafold\|pdb, id, accession | C-alpha trace in UniProt numbering |
| `expression` symbol, context | GTEx median TPM by tissue, HPA specificity, GEO datasets |
| `enrichment` genes | Reactome over-representation + shared KEGG maps |
| `literature` query, genes, pmids | abstracts + extracted methods/systems/claims, candidate conflicts, gaps |

Every edge element carries `relation`, `sign` (+, −, 0), `evidenceCode`, `directed`, `indirect`, `modifiers` (e.g. `+p`), `suspect` (KEGG direction inversion flag), `detail` and `citations`.

## 3. How mutant changes are derived

1. Find a Reactome *disease* protein entity whose name is exactly `GENE CHANGE` (e.g. KRAS G12D, R-HSA-6802333).
2. Collect the curated sets it belongs to (e.g. "RAS GTPase mutants", "RAS GAP mutants"). Membership via `hasCandidate` (unconfirmed) downgrades derived changes to PRED.
3. Collect the disease pathways containing it and their reactions.
4. For a **FailedReaction** (e.g. "RAS GAP mutants aren't stimulated by GAPs"), take the participant genes of its *normal* reaction ("RAS GAPs bind RAS:GTP") and mark drawn edges between the variant's node and those genes as **impaired in mutant**. If no drawn edge connects them (e.g. "RAS GTPase mutants don't hydrolyze GTP"), attach the change to the variant node.
5. Other disease reactions mark edges between the variant node and their participants as **documented for mutant**.
6. `downstream` = graph-reachable from the variant node: structural, not measured.

Without a Reactome entity, nothing is drawn as changed. UniProt variant text and ClinVar classifications are listed separately, as statements, not as edge changes.

## 4. Perturbation semantics

- Reachability is computed over directed edges; undirected (binding/association) edges are traversable both ways.
- `influence_lost` lists nodes the source no longer reaches, each with the **net sign** of the lost route (product of edge signs; `?` if any step is unsigned).
- `rerouted` lists nodes still reached whose original shortest route used the removed node or inhibited edge, with the alternative route and both signs.
- Interpretation: losing a net `+` route ≈ less activating input from the source; losing a route through an inhibitor (`−` steps) often means *disinhibition* in a cell. Example: removing TSC1/TSC2 cuts PI3K's net `+` route to mTORC1, yet TSC loss in cells activates mTORC1, because the map's route to mTORC1 runs through a double negative. Say this explicitly.
- Always present results as computational hypotheses. Compensation, unmapped routes, dosage, feedback and kinetics are not modelled.

## 5. Signal playback semantics

The Explorer animates one documented relation per step, ordered by graph distance from the source. Step order is **not** timing, rate or kinetics. Activation, inhibition, expression, binding and conversion have distinct visuals; `+p` badges appear only where KEGG records phosphorylation. Blocked steps (user-inhibited or documented as impaired in a mutant) are shown stopping half-way.

## 6. Structures

- AlphaFold DB models: provenance "computationally predicted", per-residue pLDDT (very high > 90, confident 70–90, low 50–70, very low < 50). Numbering = UniProt.
- RCSB PDB entries: provenance "experimentally determined", method and resolution, best resolution first; peptide-only entries (< 50 residues per chain) are skipped. Residues are mapped to UniProt via RCSB's SIFTS alignment; unmapped residues are not annotated.
- A PDB entry may be a fragment, a mutant (check the title, e.g. "Y220C") or a complex.

## 7. Expression and datasets

- GTEx v8 median TPM per tissue (bulk RNA-seq of normal tissue).
- Human Protein Atlas tissue, single-cell-type and cancer specificity categories (CC BY-SA 4.0).
- GEO DataSets/Series matching the gene (and optional context) are pointers for analysis, not results.
- Expression ≠ pathway activity ≠ protein activity.

## 8. Literature mining

Keyword extraction from titles/abstracts: methods (ChIP, reporter, knockdown, knockout, overexpression, co-IP, metabolite measurement…), model systems, design (mechanistic / correlational / computational / review), stated limitations, gene+topic sentences with an *implied gene effect* (loss-of-function wording inverts direction), candidate conflicts between primary studies, and gaps (no in vivo, no patient material, no mechanistic perturbation, unreplicated). All of it points to what to read; none of it is a finding.

## 9. Running

```bash
# MCP server (Claude Code)
claude mcp add biopathway -- python3 /path/to/biopathway-mapper/scripts/bpm_mcp.py

# Explorer: API + built UI on one port
cd explorer && npm install && npm run build && cd ..
python3 scripts/bpm_api.py          # http://127.0.0.1:8790
```
