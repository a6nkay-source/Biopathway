"""End-to-end replays of the reference scenarios from recorded API responses.

tests/fixtures/cache holds real responses captured from the live services
(see README "Refreshing fixtures"). Offline mode makes these tests
deterministic and network-free. Assertions check biology that the source
databases state, so a failure after a refresh means the upstream record
changed or the reconstruction broke: inspect, do not just loosen.
"""

import unittest

from _helpers import FIXTURE_CACHE
from bpm import analysis as an
from bpm import evidence as ev
from bpm.http import HttpClient
from bpm.report import render_markdown


def ctx():
    return an.Context(HttpClient(cache_dir=FIXTURE_CACHE, offline=True))


def labels(a):
    return {n.label for n in a.nodes.values()}


def edge(a, src_label, rel, dst_label):
    for e in a.edges:
        if (a.nodes[e.source].label == src_label and a.nodes[e.target].label == dst_label
                and e.relation == rel):
            return e
    return None


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class Scenarios(unittest.TestCase):
    def assert_traceable(self, a):
        self.assertTrue(a.edges, "expected relationships")
        for e in a.edges:
            self.assertIn(e.evidence, ev.LEVELS)
            self.assertTrue(e.citations, f"uncited edge {e.source}->{e.target}")
            # PubMed search hits must never be the sole basis of an edge.
            self.assertTrue(any(c.source != "PubMed" for c in e.citations))
        for s in a.statements:
            self.assertIn(s.evidence, ev.LEVELS)
        self.assertFalse([k for k, v in a.source_status.items() if v.startswith("failed")])
        md = render_markdown(a)
        self.assertIn("```mermaid", md)

    def test_tp53_apoptosis(self):
        a = an.analyze_process(ctx(), "apoptosis", ["TP53"])
        self.assert_traceable(a)
        self.assertEqual(a.pathways[0]["id"], "R-HSA-109581")
        self.assertIsNotNone(edge(a, "TP53", "participates in", "Activation of PUMA and translocation to mitochondria"))
        self.assertIsNotNone(edge(a, "Intrinsic Pathway for Apoptosis", "contains",
                                  "Activation of PUMA and translocation to mitochondria"))
        texts = " ".join(s.text for s in a.statements)
        self.assertIn("TP53 stimulates BBC3 (PUMA) expression", texts)
        self.assertIn("TP53 stimulates PMAIP1 (NOXA) expression", texts)

    def test_brca1_dna_repair(self):
        a = an.analyze_process(ctx(), "DNA repair", ["BRCA1"])
        self.assert_traceable(a)
        self.assertEqual(a.pathways[0]["id"], "R-HSA-73894")
        self.assertIsNotNone(edge(a, "BRCA1", "participates in", "HDR through Homologous Recombination (HRR)"))
        self.assertIsNotNone(edge(a, "DNA Repair", "contains", "DNA Double-Strand Break Repair"))
        self.assertIn("BRCA1 forms a heterodimer with BARD1", " ".join(s.text for s in a.statements))

    def test_egfr_mapk(self):
        a = an.analyze_pathway(ctx(), "MAPK signaling", ["EGFR", "MAPK1"])
        self.assert_traceable(a)
        self.assertIn("hsa04010", [p["id"] for p in a.pathways])
        route = next(s.text for s in a.statements if s.text.startswith("EGFR to MAPK1"))
        for step in ("GRB2", "SOS1", "MAP2K", "MAPK1"):
            self.assertIn(step, route)
        grb2 = next(e for e in a.edges if "GRB2" in (a.nodes[e.source].label, a.nodes[e.target].label)
                    and e.relation == "binding")
        self.assertFalse(grb2.directed)   # KGML binding is symmetric
        self.assertTrue(all(e.evidence == ev.CURATED for e in a.edges))

    def test_pi3k_akt_mtor(self):
        a = an.analyze_pathway(ctx(), "PI3K-AKT-mTOR", ["PIK3CA", "AKT1", "MTOR"])
        self.assert_traceable(a)
        self.assertIn("hsa04151", [p["id"] for p in a.pathways])
        self.assertIsNotNone(edge(a, "AKT1/AKT3/AKT2", "inhibition", "TSC2:TSC1"))
        self.assertIsNotNone(edge(a, "TSC2:TSC1", "inhibition", "RHEB"))
        self.assertIsNotNone(edge(a, "RHEB", "activation", "RPTOR:MTOR:MLST8"))
        self.assertIn("Phosphatidylinositol-3,4,5-trisphosphate", labels(a))

    def test_kras_g12d(self):
        a = an.analyze_mutation(ctx(), "KRAS", "G12D")
        self.assert_traceable(a)
        self.assertEqual(a.resolved["variant"]["hgvs_p"], "p.Gly12Asp")
        texts = [s.text for s in a.statements]
        self.assertTrue(any("position 12 is G" in t for t in texts))
        self.assertTrue(any("G12D (same substitution)" in t for t in texts))
        self.assertTrue(any(t.startswith("ClinVar VCV000012582") and "Pathogenic" in t for t in texts))
        # The variant is linked to its gene and to clinical records, never directly to pathways.
        var_id = next(n.id for n in a.nodes.values() if n.kind == "variant")
        targets = {a.nodes[e.target].kind for e in a.edges if e.source == var_id}
        self.assertNotIn("pathway", targets)

    def test_glycolysis(self):
        a = an.analyze_metabolic(ctx(), "glycolysis", module="M00001")
        self.assert_traceable(a)
        names = labels(a)
        for metabolite in ("alpha-D-Glucose", "D-Fructose 1,6-bisphosphate", "Phosphoenolpyruvate", "Pyruvate"):
            self.assertIn(metabolite, names)
        pk = edge(a, "Phosphoenolpyruvate", "conversion", "Pyruvate")
        self.assertIn("PKLR/PKM", pk.modifiers[0])
        self.assertTrue(any("R07159" in n for n in a.notes))  # archaeal step, no human enzyme

    def test_tp53_gene_string_labels(self):
        a = an.analyze_gene(ctx(), ["TP53"])
        self.assert_traceable(a)
        mdm2 = next(e for e in a.edges if "MDM2" in (e.source, e.target))
        self.assertEqual(mdm2.evidence, ev.EXPERIMENTAL)
        self.assertFalse(mdm2.directed)

    def test_tp53_r175h_in_dna_binding_region(self):
        a = an.analyze_mutation(ctx(), "TP53", "p.Arg175His")
        self.assert_traceable(a)
        self.assertIn("DNA binding (102-292)", labels(a))
        self.assertTrue(any("Li-Fraumeni" in s.text and "expert panel" in s.text for s in a.statements))


if __name__ == "__main__":
    unittest.main()
