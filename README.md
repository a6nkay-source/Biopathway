# BioPathway Mapper

A Claude Skill that answers questions about genes, proteins, mutations, signalling pathways, metabolic pathways and biological processes from live database records. Each answer comes with evidence labels, a Mermaid/Graphviz diagram and source citations.

It does not use an LLM to invent relationships. Every edge in a diagram comes from a database record that states it: a KEGG relation or reaction, Reactome membership or event, a STRING association, a UniProt feature, or a ClinVar assertion. The record is cited, and the edge is labelled *experimentally validated*, *curated database evidence*, *computationally predicted*, *literature-supported association* or *hypothetical/insufficiently established*.

## Layout

```
biopathway-mapper/
├── SKILL.md                     # what Claude reads: when/how to use, answer rules
├── README.md
├── references/
│   ├── analysis-workflows.md    # each analysis, options, recipes
│   ├── evidence-framework.md    # labelling rules + rationale
│   ├── data-sources.md          # endpoints, limits, licences, caching, ids
│   └── interpretation-guide.md  # pitfalls and wording
├── scripts/
│   ├── bpm_cli.py               # command line entry point
│   └── bpm/
│       ├── http.py              # cache, rate limits, retries, provenance log
│       ├── models.py            # Node / Edge / Statement / Analysis / Citation
│       ├── evidence.py          # evidence classification rules
│       ├── analysis.py          # gene, pathway, process, metabolic, mutation
│       ├── diagram.py           # Mermaid + DOT (+ SVG if Graphviz installed)
│       ├── report.py            # Markdown report
│       └── integrations/        # ncbi.py uniprot.py reactome.py stringdb.py kegg.py
├── tests/                       # unittest suite; fixtures/cache = recorded API responses
└── examples/                    # generated outputs for the reference scenarios
```

Standard library only (Python 3.9+). No `pip install` needed.

## Install as a skill

Copy or symlink the folder into a skills directory, e.g.

```bash
git clone https://github.com/a6nkay-source/Biopathway.git ~/.claude/skills/biopathway-mapper
```

or package it with the skill-creator `package_skill.py` script and upload the `.skill` file.

## Use directly

```bash
python3 scripts/bpm_cli.py gene TP53
python3 scripts/bpm_cli.py process apoptosis --genes TP53 --out out/tp53
python3 scripts/bpm_cli.py process "DNA repair" --genes BRCA1
python3 scripts/bpm_cli.py pathway "MAPK signaling" --genes EGFR,MAPK1
python3 scripts/bpm_cli.py pathway hsa04151 --genes PIK3CA,AKT1,MTOR
python3 scripts/bpm_cli.py metabolic glycolysis --module M00001
python3 scripts/bpm_cli.py mutation KRAS G12D
python3 scripts/bpm_cli.py literature glycolysis --genes BRCA1
```

`--out DIR` writes `report.md`, `analysis.json`, `diagram.mmd`, `diagram.dot` (and `diagram.svg` if Graphviz is installed). Exit codes: 0 ok, 2 nothing resolved, 3 every source failed.

## Reference scenarios

Generated outputs are in `examples/` (see `examples/README.md`). What each reconstructs:

| Scenario | Command | Result (from the records, not hand-written) |
|---|---|---|
| TP53 / apoptosis | `process apoptosis --genes TP53` | Reactome places TP53 in *Activation of PUMA/NOXA and translocation to mitochondria* under the intrinsic pathway; curated events "TP53 stimulates BBC3 (PUMA) expression", "... PMAIP1 (NOXA) expression" |
| BRCA1 / DNA repair | `process "DNA repair" --genes BRCA1` | BRCA1 in HRR, SSA, SDSA, D-loop resolution, DSB recruitment, NHEJ; 20+ curated events (BRCA1:BARD1 heterodimer, CHEK2 phosphorylation, RBBP8 binding...) |
| EGFR / MAPK | `pathway "MAPK signaling" --genes EGFR,MAPK1` | RTK — GRB2 — SOS → RAS → RAF → MEK (+p) → ERK, all equal-length RAF routes drawn |
| KRAS | `mutation KRAS G12D` | residue check G12; UniProt VAR_016026; ClinVar VCV000012582 Pathogenic/Likely pathogenic (multi-submitter) and oncogenicity (single submitter, labelled LIT); KRAS KEGG maps |
| PI3K-AKT-mTOR | `pathway "PI3K-AKT-mTOR" --genes PIK3CA,AKT1,MTOR` | PI3K → PIP3 → AKT ⊣ TSC2:TSC1 ⊣ RHEB → RPTOR:MTOR:MLST8 |
| Glycolysis | `metabolic glycolysis --module M00001` | glucose → … → pyruvate in 10 human steps with HK/GPI/PFK/ALDO/TPI/GAPDH/PGK/PGAM/ENO/PK; archaeal R07159 flagged as having no human enzyme |

## Tests

```bash
cd tests && python3 -m unittest discover -v
```

55 tests: evidence rules, HTTP cache/retry/rate-limit/secret handling, KGML/flat-file/variant parsing, name matching, path finding, diagram and report grammar, graceful degradation with failing sources, and offline end-to-end replays of all reference scenarios against recorded real API responses.

### Refreshing fixtures

The scenario tests replay `tests/fixtures/cache`. To refresh from the live APIs (needs network, about 2 minutes):

```bash
rm -rf tests/fixtures/cache
export BPM_CACHE_DIR="$PWD/tests/fixtures/cache"
python3 scripts/bpm_cli.py process apoptosis --genes TP53 >/dev/null
python3 scripts/bpm_cli.py process "DNA repair" --genes BRCA1 >/dev/null
python3 scripts/bpm_cli.py pathway "MAPK signaling" --genes EGFR,MAPK1 >/dev/null
python3 scripts/bpm_cli.py pathway "PI3K-AKT-mTOR" --genes PIK3CA,AKT1,MTOR >/dev/null
python3 scripts/bpm_cli.py metabolic glycolysis --module M00001 >/dev/null
python3 scripts/bpm_cli.py mutation KRAS G12D >/dev/null
python3 scripts/bpm_cli.py mutation TP53 R175H >/dev/null
python3 scripts/bpm_cli.py gene TP53 >/dev/null
cd tests && python3 -m unittest test_scenarios -v
```

A failing scenario after a refresh means an upstream record changed or the reconstruction broke. Inspect it before loosening an assertion.

## Known limits

- Organisms: KEGG/Reactome mapping for human, mouse, rat, zebrafish, fly, worm and yeast only.
- `pathway` reconstructs KEGG maps. Reactome reaction-level directed networks (input → output → regulator) are not reconstructed; `process` uses the Reactome hierarchy and event names.
- STRING, ClinVar and PubMed give association-level evidence only, by design.
- Diagrams are rendered to SVG only if Graphviz `dot` is installed; Mermaid text is always produced (verified to parse with Mermaid 10.9.1).
- KEGG API use is restricted to academic users; use `--no-kegg` otherwise.
- `literature` returns relevance-ranked abstracts (re-ranked by title match), not a systematic review. Grading what a paper shows is left to Claude, under the EXP-lit/LIT rules.
- KEGG KGML files contain occasional direction errors. Expression edges that contradict a map's transcriptional hub are flagged "direction suspect" (e.g. BBC3 -> TP53 in hsa04115) but not altered.

## Licence notes for data

Outputs contain data from NCBI (public domain), UniProt (CC BY 4.0), Reactome (CC0/CC BY 4.0), STRING (CC BY 4.0) and KEGG (academic-use terms). Keep the citations when redistributing outputs.
