# Iteration 3 grading summary (with_skill)

| Case | Run | Passed/Total | Notable issues |
|---|---|---|---|
| p53-apoptosis-evidence | run-1 | 7/7 | Header says "13 primary papers" but 12 are listed. The missing KEGG MDM2→TP53 relation is hedged as "in the parsed relations", so it may be a parser gap. Checks verified: Banin 1998, Jeffers 2003, R-HSA-5693609 |
| p53-apoptosis-evidence | run-2 | 7/7 | Marks MDM2 release as HYP although Reactome R-HSA-69541 states it (over-conservative). Checks verified: Yu 2001, R-HSA-111453, R-HSA-114294; the "12+4 of 66 relations" claim matches the tool output |
| brca1-dna-repair | run-1 | 5/5 | Misses the curated 53BP1/RIF1 event (R-HSA-5686685) and the BRCA1-PALB2 D-loop event (R-HSA-5693620), but says plainly that its event search has gaps. IDs verified: Nilavar 2026, Johnson 2013, R-HSA-5684108 |
| brca1-dna-repair | run-2 | 5/5 | Six diagram arrows have no label; the legend calls them Reactome sequence links (borderline). Strong NHEJ nuance: BRCA1 is the factor displaced there, not an actor. IDs verified: Wang 2023, van de Kooij 2023 (preprint), R-HSA-5686685 |
| egfr-mapk | run-1 | 5/5 | The colour legend in combined diagram B matches nothing drawn (no linkStyle). R-HSA-5675194, hsa04010, hsa04012 verified |
| egfr-mapk | run-2 | 5/5 | Diagram edges are labelled only with a generic "CUR+EXP". The records are named per step in the text. R-HSA-182993, R-HSA-182990, hsa04012 verified |
| kras-g12d-mechanism | run-1 | 5/5 | No issues. Keeps G12V UniProt text out of the G12D claims. Song 2025, R-HSA-9651280, R-HSA-6802333 verified |
| kras-g12d-mechanism | run-2 | 5/5 | Small overstatement: says the Reactome GAP summary "lists G12D". G12D's inclusion comes from set membership, not from the summary text. Watano 2026, Li 2022, R-HSA-6802834 verified |
| pi3k-tsc2-loss | run-1 | 4/4 | No issues. The HTTP 429 report and the perturbation claims match the tool output. R-HSA-165181, Pollizzi 2015, Riley 2022 verified |
| pi3k-tsc2-loss | run-2 | 4/4 | Unused colour legend (boilerplate). The "S6K still reachable" claim matches the perturbation output. Martin 2014, Agarwal 2016, hsa04151 verified |
| glycolysis-steps | run-1 | 5/5 | No issues. M00001, R-HSA-70171, PMID 16051738 verified |
| glycolysis-steps | run-2 | 5/5 | No issues. M00001, hsa00010, R-HSA-9634600 verified |

**Overall: 62/62 assertions pass (100%).** All 36 spot-checked identifiers exist and match how the answers describe them. No fabricated citations or biological errors were found.

**Weak evals:** most assertions are easy for any competent answer to pass. These ones actually separate good answers from weak ones:
- p53 A7 (no invented verification)
- PI3K A4 ("unreachable" does not mean switched off)
- glycolysis A5 (no human enzyme on R07159)
- KRAS A5 (nothing carried over from other variants)

Gaps no assertion covers:
- Whether IDs exist, outside BRCA1.
- Whether the KEGG BBC3→TP53 inversion is handled.
- Whether BRCA1's NHEJ/SSA membership is read as a real mechanism or only as participation. Run-2 handled this much better than run-1.
- Whether the diagram's colour legend matches the edges actually drawn.
