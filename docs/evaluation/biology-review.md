# Biology review of the six reference scenarios

Reviewer: independent audit (did not build the tool). Date: 2026-11-15.

Scope: every edge shown to users in the six scenarios listed in `explorer/public/data/index.json`:

| Scenario | Data file |
|---|---|
| TP53 and apoptosis | `pathway_graph-71f6b4049c.json` (KEGG hsa04115) |
| BRCA1 and DNA repair | `process_graph-973a649980.json` (Reactome hierarchy) |
| EGFR to ERK | `pathway_graph-be76af5b1f.json` (KEGG hsa04010) |
| KRAS G12D vs normal | `compare_mutation-441a993866.json` (KEGG hsa04010 + Reactome disease events) |
| PI3K-AKT-mTOR | `pathway_graph-ec194c21fc.json` (KEGG hsa04151) |
| Glycolysis | `metabolic_graph-0c0ff50e23.json` (KEGG module M00001) |

Method: I read every edge (`source`, `target`, `relation`, `sign`, `modifiers`, `evidenceCode`, `directed`, `suspect`, `detail`). I checked the edges against established biology, and I checked the points that mattered against the primary records:

- KEGG KGML for hsa04115, fetched from `rest.kegg.jp`.
- KEGG REACTION entries R07159, R02189, R09085, R01063, R05805 and R13199.
- The Reactome ContentService: NHEJ participants and the event ancestors for R-HSA-5693571 and R-HSA-5693579.

For KRAS G12D, the mutation view does more than draw `normal.elements`. It also pulls overlay edges from `normal.full` (`MutationView.tsx`, lines 43-53). That adds the three GAP ⊣ RAS edges, so I reviewed them too.

Verdict scale: **CORRECT**, **ACCEPTABLE** (true but simplified, e.g. a paralog box or a skipped intermediate), **QUESTIONABLE**, **WRONG**.

Convention: KEGG `phosphorylation` edges carry `sign = 0` and no `+p` modifier. Edges that KEGG encodes as `activation, phosphorylation` instead get `sign = +` and `+p`. When the direction and relation are right, I graded these edges on their biology (usually CORRECT). The encoding inconsistency is listed once, as issue 8.

## Summary

| Scenario | Edges reviewed | CORRECT | ACCEPTABLE | QUESTIONABLE | WRONG |
|---|---|---|---|---|---|
| TP53 and apoptosis | 10 | 4 | 4 | 0 | 2 |
| BRCA1 and DNA repair | 23 | 12 | 10 | 1 | 0 |
| EGFR to ERK (MAPK) | 17 | 9 | 8 | 0 | 0 |
| KRAS G12D vs normal (edges) | 17 | 11 | 6 | 0 | 0 |
| KRAS G12D: documented mutant changes | 4 | 1 | 1 | 2 | 0 |
| PI3K-AKT-mTOR | 5 | 3 | 2 | 0 | 0 |
| Glycolysis (M00001) | 12 | 10 | 1 | 1 | 0 |
| **Total edges (excluding the change rows)** | **84** | **49** | **31** | **2** | **2** |

Bottom line: the transcribed relations are mostly faithful to the source databases and biologically sound. Three findings are material:

1. **TP53: two KEGG KGML errors reach users.** Only one of them is flagged. As a result, the scenario never draws "p53 induces PUMA". It also routes PUMA to caspases through a fictitious PUMA → p53AIP1 transcription step.
2. **KRAS G12D: two of the four "documented for mutant" annotations on RAS → RAF do not describe a G12D effect.** One describes a presumed normal-like dissociation. The other concerns kinase-dead BRAF mutants. Meanwhile, the defining gain of G12D (more RAS-GTP, so more RAF engagement) is shown only indirectly, through the GAP edges marked impaired.
3. **Glycolysis shows an archaeal-only step** (GAPOR, R07159) in a human scenario.

---

## 1. TP53 and apoptosis (KEGG hsa04115)

| # | Edge (as drawn) | Rel / sign / mods | Verdict | Reasoning |
|---|---|---|---|---|
| 1 | TP53 → TNFRSF10B/TNFRSF10A | expression, + | ACCEPTABLE | DR5/KILLER (TNFRSF10B) is a canonical direct p53 target. DR4 (TNFRSF10A) induction by p53 is reported but weaker. Paralog box. |
| 2 | TP53 → BAX | expression, + | CORRECT | BAX is a direct p53 transcriptional target. |
| 3 | TP53 → PMAIP1 (NOXA) | expression, + | CORRECT | NOXA is a direct p53 transcriptional target. |
| 4 | BBC3 (PUMA) → TP53 | expression, +, `direction suspect`, suspect=true | WRONG (flag justified) | Backwards. p53 induces PUMA (PMID 11463391, 11463392). PUMA is a BH3-only mitochondrial protein, not a transcription factor. KGML entry 65 → 50 really does encode this, so it is a KEGG erratum. The suspect flag and warning are correct, but the edge is still drawn the wrong way round, and no TP53 → BBC3 edge exists. |
| 5 | BBC3 (PUMA) → TP53AIP1 | expression, +, suspect=false | WRONG (not flagged) | PUMA does not drive transcription of p53AIP1. p53AIP1 is a p53 target induced after Ser46 phosphorylation of p53 (PMID 11030628). KGML encodes 65 → 64 the same way, so this is the same KEGG erratum as edge 4 (the source should be TP53). The hub heuristic misses it because the target is not a hub. |
| 6 | TP53AIP1 → CYCS | indirect effect, 0 | ACCEPTABLE | p53AIP1 is mitochondrial and dissipates the membrane potential, consistent with cytochrome c release. The edge is correctly marked indirect, but the sign could be + (pro-release). |
| 7 | CYCS → CASP9 | activation, + | ACCEPTABLE | True, but the APAF1 apoptosome intermediate is skipped. |
| 8 | CASP9 → CASP3 | activation, + | CORRECT | Initiator caspase-9 cleaves and activates caspase-3. |
| 9 | CASP8 → CASP3 | activation, + | CORRECT | Caspase-8 cleaves caspase-3 directly. |
| 10 | TNFRSF10B/A → CASP8 | indirect effect, 0 | ACCEPTABLE | True via the DISC (FADD), which is skipped. Correctly marked indirect, but the sign could be +. |

Consequence: the "PUMA route" users see is BBC3 → TP53AIP1 → CYCS → CASP9 → CASP3, which is mechanistically fictitious. Physiologically, PUMA neutralises BCL2/BCL-XL and frees BAX/BAK, which then release cytochrome c. BAX and PMAIP1 are dead ends in the drawing, because hsa04115 has no BAX → CYCS relation. That is a completeness gap in KEGG, not an error in the tool.

Evidence labels: CUR ("curated database evidence") is appropriate for KEGG map relations.

---

## 2. BRCA1 and DNA repair (Reactome hierarchy)

Edges here are "contains" (pathway hierarchy) or "participates in" (gene → pathway). They have no sign, which is appropriate. I verified NHEJ and Homologous DNA Pairing ancestry with the Reactome ContentService.

| # | Edge | Verdict | Reasoning |
|---|---|---|---|
| 1-7 | DNA Repair contains BER / DNA Damage Bypass / DNA Damage Reversal / DSB Repair / NER / MMR / Fanconi Anemia Pathway | CORRECT (×7) | These are direct Reactome children of R-HSA-73894. |
| 8 | DSB Repair contains HDR through SSA | ACCEPTABLE | True. Skips Homology Directed Repair and "HRR or SSA" (labelled "intermediate omitted"). |
| 9 | DSB Repair contains HDR through HRR | ACCEPTABLE | True. Same skipped levels. |
| 10 | DSB Repair contains Resolution of D-loop via SDSA | ACCEPTABLE | True, but it sits inside HRR, which is itself drawn. Flattening hides that nesting. |
| 11 | DSB Repair contains Recruitment and ATM-mediated phosphorylation at DSBs | ACCEPTABLE | True. Skips DNA Double Strand Break Response. |
| 12 | DSB Repair contains Resolution of D-loop via Holliday Junctions | ACCEPTABLE | True. Nested inside HRR (drawn), as in row 10. |
| 13 | DSB Repair contains Homologous DNA Pairing and Strand Exchange | ACCEPTABLE | True. Reactome ancestry is HRR > HRR-or-SSA > HDR > DSBR, so its HRR parent is drawn but not connected. |
| 14 | DSB Repair contains Processing of DSB ends | ACCEPTABLE | True. Skips HDR and HRR-or-SSA. |
| 15 | DNA Repair contains NHEJ ("intermediate sub-pathways omitted") | QUESTIONABLE | In Reactome, NHEJ (R-HSA-5693571) is a direct child of DSB Repair, and that node is on the canvas. Hanging NHEJ off the root visually places it outside DSB repair. |
| 16 | BRCA1 participates in HDR through SSA | CORRECT | BRCA1-CtIP-driven resection is required for SSA, and BRCA1 loss reduces SSA. |
| 17 | BRCA1 participates in HDR through HRR | CORRECT | Core HR factor (resection, PALB2-BRCA2-RAD51 loading). |
| 18 | BRCA1 participates in Resolution of D-loop via SDSA | ACCEPTABLE | Reactome places BRCA1:BARD1 complexes in these events. A direct BRCA1 role in SDSA itself is less established than in the earlier HR steps. |
| 19 | BRCA1 participates in Recruitment / ATM phosphorylation at DSBs | CORRECT | ATM phosphorylates BRCA1, and the BRCA1-A complex is recruited via RAP80/ubiquitin. |
| 20 | BRCA1 participates in Resolution of D-loop via HJ | ACCEPTABLE | Reflects Reactome participant complexes. No direct resolvase role is established. |
| 21 | BRCA1 participates in NHEJ | ACCEPTABLE | Verified: Reactome NHEJ participants include the BRCA1-A complex and p-BRCA1:p-BARD1. Biologically, though, BRCA1 mainly antagonises 53BP1/RIF1-dependent NHEJ. An unsigned "participates in" is accurate to the record but could be read as "promotes NHEJ". |
| 22 | BRCA1 participates in Homologous DNA Pairing and Strand Exchange | CORRECT | BRCA1-PALB2-BRCA2 mediates RAD51 loading for strand invasion. |
| 23 | BRCA1 participates in Processing of DSB ends | CORRECT | BRCA1 promotes CtIP/MRN resection. |

Evidence labels: CUR is appropriate for Reactome.

---

## 3. EGFR to ERK (KEGG hsa04010)

The RAS box is HRAS, KRAS, NRAS, MRAS, RRAS and RRAS2. The RTK box holds 25 receptors (EGFR, CSF1R, EPHA2, FGFRs, IGF1R, INSR, KIT, MET, NTRKs, PDGFRs, ERBB2/4 and others).

| # | Edge | Rel / sign / mods | Verdict | Reasoning |
|---|---|---|---|---|
| 1 | GRB2 — RTK box | binding, undirected | ACCEPTABLE | GRB2's SH2 binds phospho-Tyr on these RTKs. Correct as undirected binding. Paralog box. |
| 2 | SOS1/2 — GRB2 | binding, undirected | CORRECT | GRB2's SH3 domains bind SOS proline-rich regions. |
| 3 | SOS1/2 → RAS box | activation, + | ACCEPTABLE | SOS is the GEF for H/K/NRAS. MRAS, RRAS and RRAS2 are poor SOS substrates, so the box overstates it. |
| 4 | RAS box → BRAF | activation, + | ACCEPTABLE | RAS-GTP recruits RAF and promotes dimerisation. Box members RRAS and MRAS do not activate RAF in this way. |
| 5 | RAS box → RAF1 | activation, + | ACCEPTABLE | As row 4. |
| 6 | RAS box → ARAF | activation, + | ACCEPTABLE | As row 4. |
| 7-10 | BRAF → MAP2K1, BRAF → MAP2K2, RAF1 → MAP2K1, RAF1 → MAP2K2 | phosphorylation, 0 | CORRECT (×4) | RAF phosphorylates MEK1/2 at S218/S222 and activates them. Sign should be + (issue 8). |
| 11-12 | MAP2K1 → MAPK1/3, MAP2K2 → MAPK1/3 | phosphorylation, 0 | CORRECT (×2) | MEK1/2 dual-phosphorylate ERK1/2 at TEY. Paralog box. Sign should be + (issue 8). |
| 13-14 | MAP3K1 → MAP2K1, MAP3K1 → MAP2K2 | phosphorylation, 0 | ACCEPTABLE (×2) | MEKK1 can phosphorylate MEK1/2, but its dominant physiological substrates are MKK4/7 (JNK). This is a minor ERK route, which KEGG draws. |
| 15-16 | ARAF → MAP2K1, ARAF → MAP2K2 | activation, +, +p | CORRECT (×2) | ARAF is a weaker MEK kinase but does phosphorylate and activate MEK. |
| 17 | RAS box → MAP3K1 | relation (no subtype), 0 | ACCEPTABLE | MEKK1 binds RAS-GTP. "No subtype" with sign 0 is an honest rendering. |

---

## 4. KRAS G12D vs normal

### 4a. Edges drawn (14 normal edges plus 3 GAP edges pulled in from `normal.full`)

| # | Edge | Verdict | Reasoning |
|---|---|---|---|
| 1-3 | RAS box → BRAF / RAF1 / ARAF (activation, +) | ACCEPTABLE (×3) | Same as EGFR rows 4-6. |
| 4-7 | BRAF/RAF1 → MAP2K1/2 (phosphorylation, 0) | CORRECT (×4) | Same as EGFR rows 7-10. |
| 8-9 | MAP2K1/2 → MAPK1/3 (phosphorylation, 0) | CORRECT (×2) | Same as EGFR rows 11-12. |
| 10-11 | MAP3K1 → MAP2K1/2 | ACCEPTABLE (×2) | Same as EGFR rows 13-14. |
| 12-13 | ARAF → MAP2K1/2 (activation, +p) | CORRECT (×2) | Same as EGFR rows 15-16. |
| 14 | RAS box → MAP3K1 (relation, 0) | ACCEPTABLE | Same as EGFR row 17. |
| 15 | NF1 ⊣ RAS box (inhibition, −) | CORRECT | NF1 is a RAS GAP. GAP-stimulated GTP hydrolysis inactivates RAS. |
| 16 | RASA1 (p120GAP) ⊣ RAS box | CORRECT | Canonical RAS GAP. |
| 17 | RASA2 ⊣ RAS box | CORRECT | RAS GAP (GAP1 family). |

### 4b. Documented mutant changes (`data.changes` / `data.overlay`)

Reactome lists the entity KRAS G12D (R-HSA-6802333) as a member of both "RAS GAP mutants" and "RAS GTPase mutants", so the source events do include G12D.

| # | Reactome event → mapped edge(s) | Status shown | Verdict | Reasoning |
|---|---|---|---|---|
| 1 | R-HSA-9651280 "RAS GAP mutants aren't stimulated by GAPs" → NF1/RASA1/RASA2 ⊣ RAS | impaired in mutant | CORRECT | G12D sterically blocks the GAP arginine finger, so GAP-stimulated hydrolysis is essentially lost (Hunter et al. 2015, PMID 26037647, profiled intrinsic and GAP-stimulated hydrolysis across KRAS mutants). Mapping to the GAP ⊣ RAS edges is right, and playback logic that blocks those inhibitions (so RAS stays on) is biologically sound. |
| 2 | R-HSA-6802834 "RAS GTPase mutants don't hydrolyze GTP" → node only | impaired (node) | ACCEPTABLE | Right not to map it to an edge, because intrinsic hydrolysis is a property of the node. For G12D, intrinsic hydrolysis is reduced rather than abolished. The main defect is GAP insensitivity, so "don't hydrolyze" overstates G12D. |
| 3 | R-HSA-6803233 "Dissociation of oncogenic RAS:RAF complex" → RAS → BRAF, RAS → RAF1 | documented for mutant | QUESTIONABLE | Reactome describes this as a step that "presumably" happens as it does for wild type. It is not a G12D-specific change. Highlighting the RAS → RAF activation edges as changed by a dissociation event says nothing about the real G12D effect (sustained RAS-GTP, so more RAF recruitment), and users may read it as a loss. |
| 4 | R-HSA-6802937 "Inactive BRAF mutants bind mutant RAS:GTP" → RAS → BRAF | documented for mutant | QUESTIONABLE | This event concerns kinase-dead or impaired BRAF mutants (paradoxical CRAF activation) that co-occur with mutant RAS. KRAS G12D alone does not create it. Attaching it to the KRAS G12D scenario implies a G12D-intrinsic change. The event also carries no PMIDs in the payload. |

Additional mapping observations:

- **Whole box relabelled.** The overlay node relabels the entire RAS paralog box (HRAS/NRAS/MRAS/RRAS/RRAS2/KRAS) as "KRAS p.G12D". The mutation only affects KRAS, so the label should name KRAS as the mutated member, not imply that the box is mutant.
- **Missing gain event.** The defining gain of G12D (constitutive RAS-GTP feeding RAF → MEK → ERK) is conveyed only by blocking the GAP edges. No "enhanced in mutant" status exists.
- **Variant statements not misattributed.** The UniProt statements for G12A/C/R/S are correctly labelled "different substitution at this position", and the notes say explicitly that nothing is transferred between variants. Good practice.

---

## 5. PI3K-AKT-mTOR (KEGG hsa04151)

| # | Edge | Rel / sign / mods | Verdict | Reasoning |
|---|---|---|---|---|
| 1 | PI3K box (PIK3CA/CB/CD, PIK3R1/2/3, P3R3URF-PIK3R3) → PIP3 | activation, + | ACCEPTABLE | PI3K phosphorylates PIP2 to make PIP3. That is catalytic production, not "activation" of PIP3. The box also includes a readthrough locus (P3R3URF-PIK3R3), which is an odd second label. |
| 2 | PIP3 → AKT1/2/3 | activation, + | ACCEPTABLE | PIP3 recruits AKT via its PH domain. The activating phosphorylation by PDK1 (T308) and mTORC2 (S473) is skipped. |
| 3 | AKT ⊣ TSC2:TSC1 | inhibition, −, +p | CORRECT | AKT phosphorylates TSC2 (e.g., S939/T1462) and inhibits its GAP function. |
| 4 | TSC2:TSC1 ⊣ RHEB | inhibition, − | CORRECT | TSC2 is the GAP for RHEB. |
| 5 | RHEB → RPTOR:MTOR:MLST8 (mTORC1) | activation, + | CORRECT | RHEB-GTP activates mTORC1. The complex is correctly mTORC1, not mTORC2. |

The double negative described in the scenario summary is correctly encoded.

---

## 6. Glycolysis (KEGG M00001, human enzymes)

Reversibility checked: HK, PFK and PK are shown irreversible, and the other steps reversible. That is correct.

| # | Substrate → product | Enzymes shown | Verdict | Reasoning |
|---|---|---|---|---|
| 1 | α-D-glucose → α-D-glucose 6-P | ADPGK/GCK/HK1 (+3: HK2, HK3, HKDC1) | CORRECT | Hexokinases/glucokinase, irreversible. ADPGK (ADP-dependent, R09085) is a genuine but minor human enzyme. The `detail` also cites R02189 (polyphosphate glucokinase, bacterial), which is harmless but has no human enzyme. |
| 2 | G6P → F6P | GPI, reversible | CORRECT | |
| 3 | F6P → F1,6BP | PFKL/PFKM/PFKP, irreversible | CORRECT | `detail` also cites R05805 (ADP-dependent PFK, archaeal). Harmless. |
| 4 | F1,6BP → DHAP | ALDOA/B/C, reversible | CORRECT | |
| 5 | F1,6BP → GAP | ALDOA/B/C, reversible | CORRECT | Same reaction (R01068) split into two products. Fine. |
| 6 | DHAP → GAP | TPI1, reversible | CORRECT | |
| 7 | GAP → 1,3-BPG | GAPDH/GAPDHS, reversible | CORRECT | GAPDHS is the sperm-specific paralog. `detail` also cites R01063 (NADP-dependent, plant), which is minor. |
| 8 | 1,3-BPG → 3PG | PGK1/PGK2, reversible | CORRECT | PGK2 is testis-specific. Fine. |
| 9 | GAP → 3PG (R07159) | "enzyme not mapped in this organism" | QUESTIONABLE | R07159 is GAP:ferredoxin oxidoreductase (GAPOR, EC 1.2.7.6), an archaeal enzyme with no human counterpart. Drawing it as a solid conversion in a human scenario suggests a bypass of GAPDH/PGK that humans do not have, even with the modifier text. |
| 10 | 3PG → 2PG | BPGM/PGAM1/PGAM2 (+1: PGAM4), reversible | ACCEPTABLE | PGAM1/2 are the glycolytic mutases. BPGM's main role is 2,3-BPG synthesis, with only minor mutase activity. |
| 11 | 2PG → PEP | ENO1/2/3 (+1: ENO4), reversible | CORRECT | |
| 12 | PEP → pyruvate | PKLR/PKM, irreversible | CORRECT | |

---

## Concrete issues and suggested fixes

1. **TP53: BBC3 → TP53 is drawn backwards (WRONG; flag justified).** This KEGG KGML erratum (entry 65 → 50) is correctly detected and warned about, but the arrow is still drawn as source → target. **Fix:** for this known erratum, draw TP53 → BBC3 (expression, +) and keep a note that KEGG encodes it reversed, or at least render the suspect edge without an arrowhead. The scenario summary says "p53 drives PUMA", and at present no edge shows that.

2. **TP53: BBC3 → TP53AIP1 is the same erratum, not flagged (WRONG).** p53AIP1 is a p53 target (PMID 11030628). PUMA is not a transcription factor. **Fix:** re-source this edge to TP53 → TP53AIP1. Extend the suspect heuristic as well: if a node has an inverted-suspect GErel, flag its other GErel out-edges too, or flag GErel edges whose source is not a known transcription factor. A small erratum table for hsa04115 (65 → 50 and 65 → 64) is the simplest reliable fix.

3. **TP53: fictitious PUMA-to-caspase route.** Because of issue 2, the path selector shows BBC3 → TP53AIP1 → CYCS as the PUMA route. **Fix:** once issue 2 is fixed, this route disappears. Consider a note that KEGG has no BAX/PUMA/NOXA → cytochrome c relations, which is why those nodes are dead ends.

4. **KRAS G12D: "Dissociation of oncogenic RAS:RAF complex" mapped as a mutant change (QUESTIONABLE).** **Fix:** do not highlight edges for disease events that Reactome describes as proceeding as in wild type. Show the event as context in the side panel only. Better still, map Reactome's mutant RAS:GTP-binds-RAF events (the "Signaling downstream of RAS mutants" pathway, R-HSA-9649948) with a status such as "sustained in mutant".

5. **KRAS G12D: "Inactive BRAF mutants bind mutant RAS:GTP" mapped onto RAS → BRAF (QUESTIONABLE).** This event belongs to "Paradoxical activation of RAF signaling by kinase inactive BRAF" (R-HSA-6802955) and needs a co-occurring BRAF mutation. **Fix:** exclude events whose defining entity is a mutant of another gene, or label them "requires a co-mutation in BRAF".

6. **KRAS G12D: the whole paralog box is labelled "KRAS p.G12D".** **Fix:** label the box as "KRAS p.G12D (in RAS box: HRAS/NRAS/MRAS/RRAS/RRAS2)", or split KRAS out of the box in mutation view.

7. **KRAS G12D: intrinsic hydrolysis overstated (ACCEPTABLE, minor).** **Fix:** add a qualifier such as "G12D mainly abolishes GAP-stimulated hydrolysis; intrinsic hydrolysis is reduced, not abolished (PMID 26037647)".

8. **Inconsistent sign/modifier encoding for KEGG phosphorylation (cross-cutting, minor).** Pure `phosphorylation` edges get `sign = 0` and no `+p`, while `activation, phosphorylation` edges get `sign = +` and `+p`. RAF → MEK and MEK → ERK are activating phosphorylations, but they render as unsigned. **Fix:** always add the `+p` modifier when the subtype includes phosphorylation, and leave the sign 0 unless activation or inhibition is also present. If the sign is left unknown, say so in the legend so users do not read 0 as "no effect".

9. **Glycolysis: R07159 (GAPOR, archaeal) drawn for human (QUESTIONABLE).** **Fix:** omit module reactions that have no enzyme in the selected organism, or render them faded with the label "not present in human (archaeal ferredoxin-dependent GAP oxidoreductase)". Also consider filtering the `detail` reaction lists (R02189, R05805, R01063) to reactions with human enzymes.

10. **BRCA1: NHEJ attached to the DNA Repair root (QUESTIONABLE).** Reactome places NHEJ directly under DNA Double-Strand Break Repair, which is on the canvas. **Fix:** when choosing the drawn parent of a sub-pathway, use the nearest ancestor that is present on the canvas. The same rule would attach Homologous DNA Pairing, SDSA and HJ resolution to the drawn HRR node instead of DSBR (ACCEPTABLE now, but it would preserve the nesting).

11. **BRCA1 → NHEJ "participates in" can be misread (ACCEPTABLE, minor).** **Fix:** add a tooltip saying that BRCA1 largely antagonises 53BP1-dependent NHEJ, and that Reactome lists it as a participant through the BRCA1-A and BRCA1:BARD1 complexes at break sites.

12. **PI3K → PIP3 labelled "activation" (ACCEPTABLE, minor).** **Fix:** render KEGG PCrel enzyme → compound edges as "produces / catalyses (PIP2 → PIP3)".

13. **Paralog boxes that overstate specificity (ACCEPTABLE, informational).** SOS → RAS and RAS → RAF boxes include MRAS, RRAS and RRAS2, which are not classical SOS substrates or RAF activators. **Fix:** no change needed in the data. A tooltip on boxed edges ("not every member is established for this relation") would help.

## Verified references

- PMID 11463391: Yu et al., Mol Cell 2001, PUMA induced by p53.
- PMID 11463392: Nakano and Vousden, Mol Cell 2001, PUMA induced by p53.
- PMID 11030628: Oda et al., Cell 2000, p53AIP1 is a p53 target regulated via Ser46.
- PMID 26037647: Hunter et al., Mol Cancer Res 2015, biochemistry of KRAS mutants, including intrinsic and GAP-stimulated hydrolysis.
- KEGG KGML hsa04115 (relations 65 → 50 and 65 → 64), and KEGG REACTION R07159 (EC 1.2.7.6).
- Reactome ContentService: ancestors of R-HSA-5693571 (NHEJ > DSB Repair > DNA Repair) and R-HSA-5693579; NHEJ participants include the BRCA1-A complex and p-BRCA1:p-BARD1.
