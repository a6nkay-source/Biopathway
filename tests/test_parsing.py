import tempfile
import unittest
from pathlib import Path

from _helpers import FakeTransport
from bpm.analysis import _all_shortest_paths, _relation_from_subtypes, parse_protein_change, rank_names
from bpm.http import HttpClient
from bpm.integrations.kegg import KeggClient, normalise_pathway_id, parse_kgml

KGML = """<?xml version="1.0"?>
<pathway name="path:hsa99999" org="hsa" number="99999" title="Toy pathway">
  <entry id="1" name="hsa:1956" type="gene"><graphics name="EGFR, ERBB1"/></entry>
  <entry id="2" name="hsa:2885" type="gene"><graphics name="GRB2"/></entry>
  <entry id="3" name="hsa:5594 hsa:5595" type="gene"><graphics name="MAPK1"/></entry>
  <entry id="4" name="cpd:C05981" type="compound"><graphics name="C05981"/></entry>
  <entry id="5" name="undefined" type="group"><component id="1"/><component id="2"/></entry>
  <entry id="6" name="hsa:3098" type="gene" reaction="rn:R01786"><graphics name="HK1"/></entry>
  <relation entry1="1" entry2="2" type="PPrel"><subtype name="binding/association" value="---"/></relation>
  <relation entry1="2" entry2="3" type="PPrel"><subtype name="activation" value="--&gt;"/><subtype name="phosphorylation" value="+p"/></relation>
  <relation entry1="3" entry2="1" type="PPrel"><subtype name="compound" value="4"/><subtype name="inhibition" value="--|"/></relation>
  <reaction id="6" name="rn:R01786" type="irreversible">
    <substrate id="7" name="cpd:C00267"/><product id="8" name="cpd:C00668"/>
  </reaction>
</pathway>"""

FLAT = """ENTRY       hsa00010                    Pathway
NAME        Glycolysis / Gluconeogenesis - Homo sapiens (human)
CLASS       Metabolism; Carbohydrate metabolism
MODULE      hsa_M00001  Glycolysis (Embden-Meyerhof pathway), glucose => pyruvate [PATH:hsa00010]
GENE        3098  HK1; hexokinase 1 [KO:K00844] [EC:2.7.1.1]
            5315  PKM; pyruvate kinase M1/2 [KO:K00873] [EC:2.7.1.40]
COMPOUND    C00022  Pyruvate
REFERENCE   PMID:12345678
  AUTHORS   Someone A.
///
"""

MODULE = """ENTRY       M00001            Pathway   Module
NAME        Glycolysis (Embden-Meyerhof pathway), glucose => pyruvate
DEFINITION  (K00844,K12407) K01810
REACTION    R01786,R02189  C00267 -> C00668
            R02740  C00668 -> C05345
///
"""


class KgmlTests(unittest.TestCase):
    def test_parse_entries_relations_reactions(self):
        kg = parse_kgml(KGML)
        self.assertEqual(kg["title"], "Toy pathway")
        self.assertEqual(kg["entries"]["3"]["names"], ["hsa:5594", "hsa:5595"])
        self.assertEqual(kg["entries"]["5"]["components"], ["1", "2"])
        self.assertEqual(kg["entries"]["6"]["reactions"], ["R01786"])
        rel = kg["relations"][2]
        self.assertEqual(rel["subtypes"], ["compound", "inhibition"])
        self.assertEqual(rel["compound_entries"], ["4"])
        self.assertEqual(kg["reactions"][0]["substrates"], ["C00267"])
        self.assertFalse(kg["reactions"][0]["reversible"])

    def test_relation_mapping(self):
        self.assertEqual(_relation_from_subtypes(["activation", "phosphorylation"]), ("activation", ["+p"]))
        self.assertEqual(_relation_from_subtypes(["phosphorylation"]), ("phosphorylation", []))
        self.assertEqual(_relation_from_subtypes(["repression"])[0], "inhibition")
        self.assertEqual(_relation_from_subtypes(["binding/association"])[0], "binding")

    def test_flat_file_and_module(self):
        t = FakeTransport({"get/hsa00010": [(200, FLAT)], "get/M00001": [(200, MODULE)]})
        kegg = KeggClient(HttpClient(cache_dir=Path(tempfile.mkdtemp()), transport=t, sleep=lambda s: None))
        info = kegg.pathway_info("hsa00010")
        self.assertEqual(info["name"], "Glycolysis / Gluconeogenesis")
        self.assertEqual(info["genes"], {"3098": "HK1", "5315": "PKM"})
        self.assertEqual(info["pmids"], ["12345678"])
        self.assertTrue(info["class"].startswith("Metabolism"))
        mod = kegg.module("M00001")
        self.assertEqual(mod["reactions"][0], {"ids": ["R01786", "R02189"],
                                               "substrates": ["C00267"], "products": ["C00668"]})
        self.assertEqual(len(mod["reactions"]), 2)

    def test_pathway_id_normalisation(self):
        self.assertEqual(normalise_pathway_id("map04010"), "hsa04010")
        self.assertEqual(normalise_pathway_id("path:hsa04151"), "hsa04151")
        self.assertEqual(normalise_pathway_id("map00010", "mmu"), "mmu00010")


class VariantParsing(unittest.TestCase):
    def test_one_and_three_letter(self):
        for text in ("R175H", "p.R175H", "p.Arg175His", "Arg175His", "p.(Arg175His)"):
            v = parse_protein_change(text)
            self.assertEqual((v["ref"], v["start"], v["alt"], v["kind"]), ("R", 175, "H", "missense"), text)
            self.assertEqual(v["hgvs_p"], "p.Arg175His")

    def test_nonsense_and_frameshift(self):
        self.assertEqual(parse_protein_change("R213*")["kind"], "nonsense")
        self.assertEqual(parse_protein_change("p.Arg213Ter")["alt"], "*")
        self.assertEqual(parse_protein_change("R213X")["alt"], "*")
        self.assertEqual(parse_protein_change("p.K1183fs")["kind"], "frameshift")

    def test_inframe_deletion(self):
        v = parse_protein_change("E746_A750del")
        self.assertEqual((v["start"], v["end"]), (746, 750))

    def test_garbage(self):
        self.assertIsNone(parse_protein_change("not a variant"))


class Matching(unittest.TestCase):
    ITEMS = [{"id": "hsa04151", "name": "PI3K-Akt signaling pathway"},
             {"id": "hsa04150", "name": "mTOR signaling pathway"},
             {"id": "hsa00010", "name": "Glycolysis / Gluconeogenesis"},
             {"id": "hsa04210", "name": "Apoptosis"},
             {"id": "hsa04215", "name": "Apoptosis - multiple species"}]

    def test_multi_token(self):
        ranked = rank_names("PI3K-AKT-mTOR", self.ITEMS)
        self.assertEqual(ranked[0]["id"], "hsa04151")
        self.assertNotIn("hsa04150", [r["id"] for r in ranked])  # 1/3 tokens is below threshold

    def test_exact_beats_partial(self):
        self.assertEqual(rank_names("apoptosis", self.ITEMS)[0]["id"], "hsa04210")

    def test_boost_by_gene_membership(self):
        ranked = rank_names("mTOR signaling", self.ITEMS, boost_ids={"hsa04150"})
        self.assertEqual(ranked[0]["id"], "hsa04150")

    def test_no_match(self):
        self.assertEqual(rank_names("photosynthesis", self.ITEMS), [])


class ShortestPaths(unittest.TestCase):
    def test_all_equal_routes(self):
        adj = {"A": {"B", "C"}, "B": {"D"}, "C": {"D"}, "D": {"E"}}
        paths = sorted(_all_shortest_paths(adj, "A", "E"))
        self.assertEqual(paths, [["A", "B", "D", "E"], ["A", "C", "D", "E"]])

    def test_unreachable(self):
        self.assertEqual(_all_shortest_paths({"A": {"B"}}, "B", "A"), [])


if __name__ == "__main__":
    unittest.main()
