"""BioPathway 2.0 backend: Cytoscape graphs, direction, comparison, perturbation,
structures, tissue context, citations, database errors, API and MCP servers.

Real-data tests replay tests/fixtures/cache offline (recorded from the live APIs).
"""

import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from _helpers import FIXTURE_CACHE, ROOT, FakeTransport
from bpm import analysis as an
from bpm import evidence as ev
from bpm import explorer as ex
from bpm.http import HttpClient
from bpm.integrations.structures import StructureClient, parse_mmcif_ca
from bpm.litmine import mine
from bpm.service import Service

LEVEL_CODES = set(ev.SHORT.values())


def svc():
    return Service(HttpClient(cache_dir=FIXTURE_CACHE, offline=True))


def by_label(elements, prefix):
    """Exact label first (so 'TP53' is not TP53AIP1), then prefix (KEGG boxes like 'AKT1/AKT3/AKT2')."""
    exact = [n["data"]["id"] for n in elements["nodes"] if n["data"]["label"] == prefix]
    return exact[0] if exact else next(n["data"]["id"] for n in elements["nodes"]
                                       if re.match(rf"{re.escape(prefix)}([/:+ ]|$)", n["data"]["label"]) or n["data"]["label"].startswith(prefix))


def rel(elements, a, b):
    ia, ib = by_label(elements, a), by_label(elements, b)
    return next((e["data"] for e in elements["edges"] if e["data"]["source"] == ia and e["data"]["target"] == ib), None)


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class CytoscapeGraphs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = svc()
        cls.egfr = s.call("pathway_graph", {"query": "MAPK signaling", "genes": "EGFR,MAPK1"})
        cls.pi3k = s.call("pathway_graph", {"query": "hsa04151", "genes": "PIK3CA,AKT1,MTOR"})
        cls.p53 = s.call("pathway_graph", {"query": "hsa04115", "genes": "TP53,BBC3,PMAIP1,BAX,CASP3"})

    def test_elements_are_well_formed_and_traceable(self):
        for g in (self.egfr, self.pi3k, self.p53):
            for scope in (g["elements"], g["full"]):
                ids = [n["data"]["id"] for n in scope["nodes"]]
                self.assertEqual(len(ids), len(set(ids)))
                eids = [e["data"]["id"] for e in scope["edges"]]
                self.assertEqual(len(eids), len(set(eids)))
                for e in scope["edges"]:
                    d = e["data"]
                    self.assertIn(d["source"], ids)
                    self.assertIn(d["target"], ids)
                    self.assertIn(d["evidenceCode"], LEVEL_CODES)
                    self.assertIn(d["sign"], {"+", "-", "0"})
                    self.assertTrue(d["citations"], d["id"])
            self.assertTrue(set(n["data"]["id"] for n in g["elements"]["nodes"]) <=
                            set(n["data"]["id"] for n in g["full"]["nodes"]))
            json.dumps(g)  # serialisable for the HTTP API

    def test_focus_and_full_map(self):
        self.assertEqual(self.egfr["full"]["pathway"], "hsa04010")
        self.assertGreater(len(self.egfr["full"]["edges"]), len(self.egfr["elements"]["edges"]))
        self.assertTrue(self.egfr["focus"])


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class RelationshipDirection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = svc()
        cls.pi3k = s.call("pathway_graph", {"query": "hsa04151", "genes": "PIK3CA,AKT1,MTOR"})["full"]
        cls.egfr = s.call("pathway_graph", {"query": "MAPK signaling", "genes": "EGFR,MAPK1"})["full"]
        cls.p53 = s.call("pathway_graph", {"query": "hsa04115", "genes": "TP53"})["full"]

    def test_pi3k_akt_mtor_signs_and_direction(self):
        self.assertEqual(rel(self.pi3k, "AKT", "TSC2")["sign"], "-")
        self.assertEqual(rel(self.pi3k, "TSC2", "RHEB")["sign"], "-")
        self.assertEqual(rel(self.pi3k, "RHEB", "RPTOR")["sign"], "+")
        self.assertIsNone(rel(self.pi3k, "RPTOR", "RHEB"))
        self.assertTrue(rel(self.pi3k, "AKT", "TSC2")["phospho"])

    def test_binding_is_undirected_and_mek_erk_is_phosphorylation(self):
        g = by_label(self.egfr, "GRB2")
        grb2 = next(e["data"] for e in self.egfr["edges"] if e["data"]["relation"] == "binding"
                    and g in (e["data"]["source"], e["data"]["target"]))
        self.assertFalse(grb2["directed"])
        self.assertEqual(grb2["sign"], "0")
        mek_erk = rel(self.egfr, "MAP2K1", "MAPK1")
        self.assertTrue(mek_erk["phospho"])

    def test_p53_puma_inversion_flagged_not_hidden(self):
        bbc3 = rel(self.p53, "BBC3", "TP53")
        self.assertIsNotNone(bbc3)
        self.assertTrue(bbc3["suspect"])
        self.assertEqual(rel(self.p53, "TP53", "BAX")["relation"], "expression")

    def test_second_inversion_from_same_source_flagged(self):
        """Independent review: BBC3 -> TP53AIP1 shares the mis-encoded source (should be TP53 -> TP53AIP1)."""
        e = rel(self.p53, "BBC3", "TP53AIP1")
        self.assertTrue(e["suspect"])
        self.assertIn("probably", e["detail"])

    def test_suspect_edges_are_not_routes(self):
        bbc3 = by_label(self.p53, "BBC3")
        r = ex.perturb(self.p53, [bbc3])
        self.assertEqual(r["reachable_before"], [])   # only suspect edges leave BBC3

    def test_signed_route_logic(self):
        src, rheb = by_label(self.pi3k, "PIK3CA"), by_label(self.pi3k, "RHEB")
        path = ex._shortest(ex._adjacency(self.pi3k["edges"]), src, rheb)
        self.assertEqual(ex.path_sign(path, self.pi3k["edges"]), "+")   # PI3K -> AKT -| TSC -| RHEB


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class EvidenceOnElements(unittest.TestCase):
    def test_string_mdm2_experimental_undirected(self):
        g = svc().call("interaction_graph", {"genes": "TP53"})
        mdm2 = next(e["data"] for e in g["elements"]["edges"] if "MDM2" in (e["data"]["source"], e["data"]["target"]))
        self.assertEqual(mdm2["evidenceCode"], "EXP")
        self.assertFalse(mdm2["directed"])
        self.assertGreaterEqual(mdm2["scores"]["experiments"], 0.4)

    def test_metabolic_edges_curated_with_enzymes(self):
        g = svc().call("metabolic_graph", {"query": "glycolysis", "module": "M00001"})
        # Independent review: archaeal GAPOR step (R07159, GAP -> 3PG) has no human enzyme and is not drawn.
        self.assertFalse(any("R07159" in e["data"]["detail"] for e in g["elements"]["edges"]))
        self.assertTrue(any("R07159" in n for n in g["notes"]))
        pk = next(e["data"] for e in g["elements"]["edges"] if e["data"]["target"] == "c:C00022")
        self.assertEqual(pk["evidenceCode"], "CUR")
        self.assertTrue(any("PKM" in m for m in pk["modifiers"]))


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class MutationComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = svc().call("compare_mutation", {"gene": "KRAS", "change": "G12D", "pathway": "MAPK signaling", "genes": "MAPK1"})

    def test_variant_entity_and_curated_changes(self):
        self.assertEqual(self.c["reactome"]["entities"][0]["id"], "R-HSA-6802333")
        names = {ch["name"]: ch for ch in self.c["changes"]}
        self.assertIn("RAS GTPase mutants don't hydrolyze GTP", names)
        self.assertEqual(names["RAS GTPase mutants don't hydrolyze GTP"]["type"], "FailedReaction")
        for ch in self.c["changes"]:
            self.assertIn(ch["code"], LEVEL_CODES)
            self.assertTrue(ch["pmids"] or ch["normal"])

    def test_gap_inhibition_of_ras_marked_impaired(self):
        full = self.c["normal"]["full"]
        label = {n["data"]["id"]: n["data"]["label"] for n in full["nodes"]}
        impaired = [eid for eid, v in self.c["overlay"]["edges"].items() if v["status"] == "impaired in mutant"]
        srcs = {label[eid.split("__")[0]] for eid in impaired}
        self.assertTrue({"NF1", "RASA1"} <= srcs, srcs)
        for eid in impaired:
            self.assertEqual(eid.split("__")[1], "inhibition")

    def test_hydrolysis_defect_is_node_level(self):
        node = next(iter(self.c["overlay"]["nodes"].values()))
        self.assertIn("RAS GTPase mutants don't hydrolyze GTP", node.get("impaired", []))

    def test_downstream_reaches_erk(self):
        label = {n["data"]["id"]: n["data"]["label"] for n in self.c["normal"]["full"]["nodes"]}
        self.assertTrue(any(label[i].startswith("MAPK1") for i in self.c["downstream"]))

    def test_only_failed_reactions_are_drawn_as_changes(self):
        for ch in self.c["changes"]:
            if ch["type"] != "FailedReaction":
                self.assertEqual(ch["edges"], [], ch["name"])
                self.assertNotIn("impaired", ch["status"])
        braf = next(ch for ch in self.c["changes"] if ch["name"].startswith("Inactive BRAF mutants bind"))
        self.assertIn("co-occurring BRAF", braf["status"])
        self.assertTrue(all(v["status"] == "impaired in mutant" for v in self.c["overlay"]["edges"].values()))

    def test_no_entity_means_no_assumed_change(self):
        """A variant without a Reactome entity gets no edge changes (no transfer from other variants)."""
        s = svc()
        orig = s.ctx.reactome.variant_entities
        s.ctx.reactome.variant_entities = lambda *a, **k: []
        try:
            c = s.call("compare_mutation", {"gene": "KRAS", "change": "G12D", "pathway": "MAPK signaling", "genes": "MAPK1"})
        finally:
            s.ctx.reactome.variant_entities = orig
        self.assertEqual(c["changes"], [])
        self.assertEqual(c["overlay"]["edges"], {})
        self.assertTrue(any("no disease entity" in w for w in c["warnings"]))


class Perturbation(unittest.TestCase):
    def toy(self):
        def e(s, t, rel, sign, directed=True):
            return {"data": {"id": f"{s}__{rel}__{t}", "source": s, "target": t, "relation": rel, "sign": sign, "directed": directed}}
        return {"nodes": [{"data": {"id": x, "label": x}} for x in "SABT"],
                "edges": [e("S", "A", "activation", "+"), e("A", "T", "inhibition", "-"), e("S", "B", "activation", "+"),
                          e("B", "T", "activation", "+")]}

    def test_cut_edge_reroutes_and_reports_signs(self):
        r = ex.perturb(self.toy(), ["S"], inhibit_edges=["S__activation__A"])
        self.assertEqual(r["unreachable"], ["A"])
        self.assertEqual(r["rerouted"][0]["alternative"], ["S", "B", "T"])
        self.assertEqual(r["rerouted"][0]["sign_original"], "-")
        self.assertEqual(r["rerouted"][0]["sign_alternative"], "+")
        self.assertIn("computational hypothesis", r["caveat"])

    def test_removed_node_not_reported_as_unreachable(self):
        r = ex.perturb(self.toy(), ["S"], remove_nodes=["A"])
        self.assertNotIn("A", r["unreachable"])
        self.assertEqual(r["removed"], ["A"])

    @unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
    def test_service_perturb_on_real_pi3k_map(self):
        r = svc().call("perturb_pathway", {"query": "hsa04151", "genes": "PIK3CA,AKT1,MTOR", "source": "PIK3CA", "remove": "TSC2"})
        lost = {x["node"]: x["net_sign"] for x in r["influence_lost"]}
        self.assertEqual(lost.get("RHEB"), "+")
        self.assertEqual(lost.get("RPTOR:MTOR:MLST8"), "+")
        self.assertEqual(r["removed"], ["TSC2:TSC1"])


MMCIF = """data_test
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.B_iso_or_equiv
_atom_site.auth_seq_id
_atom_site.auth_asym_id
_atom_site.pdbx_PDB_model_num
ATOM 1 N   MET A 1 0.0 0.0 0.0 90.1 1 A 1
ATOM 2 CA  MET A 1 1.0 2.0 3.0 91.5 1 A 1
ATOM 3 CA  THR A 2 4.8 2.0 3.0 88.0 2 A 1
HETATM 4 CA  GDP A . 9.0 9.0 9.0 10.0 201 A 1
ATOM 5 CA  MET A 1 7.0 7.0 7.0 50.0 1 A 2
#
"""


class StructureProvenance(unittest.TestCase):
    def test_mmcif_ca_parser_first_model_only(self):
        atoms = parse_mmcif_ca(MMCIF)
        self.assertEqual([(a["res"], a["label_seq"], a["b"]) for a in atoms], [("MET", 1, 91.5), ("THR", 2, 88.0)])

    def test_sifts_mapping_to_uniprot(self):
        entity = json.dumps({"rcsb_polymer_entity_container_identifiers": {
            "auth_asym_ids": ["A"], "reference_sequence_identifiers": [{"database_accession": "P01116"}]},
            "rcsb_polymer_entity_align": [{"reference_database_accession": "P01116",
                                           "aligned_regions": [{"entity_beg_seq_id": 2, "length": 3, "ref_beg_seq_id": 1}]}]})
        http = HttpClient(cache_dir=Path(tempfile.mkdtemp()), transport=FakeTransport({"polymer_entity": [(200, entity)]}),
                          sleep=lambda s: None)
        m = StructureClient(http).sifts_map("4OBE", ["1"], "P01116")
        self.assertEqual(m, {"A": {2: 1, 3: 2, 4: 3}})

    @unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
    def test_predicted_vs_experimental_labels(self):
        s = svc().call("structures", {"query": "KRAS"})
        self.assertEqual(s["predicted"]["provenance"], "computationally predicted")
        self.assertTrue(s["experimental"])
        self.assertTrue(all(e["provenance"] == "experimentally determined" for e in s["experimental"]))
        self.assertTrue(all((e["residues_per_chain"] or 0) >= 50 for e in s["experimental"]))
        self.assertTrue(any(f["type"] == "Binding site" for f in s["features"]))

    @unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
    def test_alphafold_trace_uses_uniprot_numbering(self):
        t = svc().call("structure_coords", {"kind": "alphafold", "id": "", "accession": "P01116"})
        self.assertEqual(len(t["atoms"]), 189)
        self.assertTrue(all(a["uniprot"] == a["label_seq"] for a in t["atoms"]))
        self.assertEqual(t["atoms"][11]["res"], "GLY")   # G12
        self.assertEqual(t["b_factor"], "pLDDT")


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class TissueContext(unittest.TestCase):
    def test_gtex_hpa_geo(self):
        x = svc().call("expression", {"symbol": "TP53"})
        tpm = [t["tpm"] for t in x["gtex"]["tissues"]]
        self.assertEqual(tpm, sorted(tpm, reverse=True))
        self.assertGreater(len(tpm), 40)
        self.assertTrue(x["hpa"]["tissue_specificity"])
        self.assertGreater(x["geo"]["count"], 0)
        self.assertTrue(any("does not show" in n for n in x["notes"]))

    def test_expression_source_failure_is_reported(self):
        s = Service(HttpClient(cache_dir=Path(tempfile.mkdtemp()), transport=FakeTransport({"": [OSError("down")]}),
                               sleep=lambda s: None, max_retries=0))
        x = s.call("expression", {"symbol": "TP53"})
        self.assertTrue(all(v.startswith("failed") for v in x["source_status"].values()))
        self.assertIsNone(x["gtex"])


@unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
class CitationValidation(unittest.TestCase):
    PATTERNS = {"KEGG": r"^https://www\.kegg\.jp/(pathway|module)/", "Reactome": r"^https://reactome\.org/content/detail/R-HSA-\d+$",
                "PubMed": r"^https://pubmed\.ncbi\.nlm\.nih\.gov/\d+/$", "UniProt": r"^https://www\.uniprot\.org/uniprotkb/\w+/entry$",
                "STRING": r"^https://string-db\.org/cgi/network\?", "NCBI Gene": r"^https://www\.ncbi\.nlm\.nih\.gov/gene/\d+$",
                "ClinVar": r"^https://www\.ncbi\.nlm\.nih\.gov/clinvar/variation/\d+/$"}

    def check(self, cites):
        for c in cites:
            self.assertIn(c["source"], self.PATTERNS, c)
            self.assertRegex(c["url"], self.PATTERNS[c["source"]])

    def test_graph_citations_resolve_to_known_record_urls(self):
        s = svc()
        for op, p in (("pathway_graph", {"query": "MAPK signaling", "genes": "EGFR,MAPK1"}),
                      ("interaction_graph", {"genes": "TP53"}), ("process_graph", {"query": "apoptosis", "genes": "TP53"})):
            self.check(s.call(op, p)["citations"])

    def test_literature_mining_only_cites_retrieved_papers(self):
        out = svc().call("literature", {"query": "glycolysis", "genes": "BRCA1"})
        retrieved = {p["pmid"] for p in out["literature"]}
        self.assertTrue(retrieved)
        self.assertEqual({p["pmid"] for p in out["mining"]["papers"]}, retrieved)
        for c in out["mining"]["conflicts"]:
            self.assertTrue(set(c["papers"]) <= retrieved)
        for p in out["mining"]["papers"]:
            if p["doi"]:
                self.assertRegex(p["doi"], r"^10\.\d{4,9}/")
        self.assertIn("32470015", retrieved)                     # BRCA1/ZBRK1 PFKP study
        types = {p["pmid"]: p["type"] for p in out["mining"]["papers"]}
        self.assertTrue(any(t == "review" for t in types.values()))


class LiteratureMining(unittest.TestCase):
    def rec(self, pmid, abstract, review=False):
        return {"pmid": pmid, "title": "t", "abstract": abstract, "is_review": review, "url": ""}

    def test_loss_of_function_wording_is_inverted(self):
        out = mine([self.rec("1", "Silencing BRCA1 increased glycolysis in ovarian cells."),
                    self.rec("2", "BRCA1 overexpression decreased glycolysis in MCF-7 cells.")], ["BRCA1"], "glycolysis")
        self.assertEqual([c["implied_gene_effect"] for p in out["papers"] for c in p["claims"]], ["down", "down"])
        self.assertEqual(out["conflicts"], [])

    def test_real_opposition_is_flagged_and_methods_extracted(self):
        out = mine([self.rec("1", "BRCA1 knockdown by siRNA reduced glycolysis in HeLa cells."),
                    self.rec("2", "Loss of BRCA1 in mice increased glycolysis in tumours.")], ["BRCA1"], "glycolysis")
        self.assertEqual(len(out["conflicts"]), 1)
        p1 = out["papers"][0]
        self.assertIn("knockdown / RNAi", p1["methods"])
        self.assertIn("human cell lines", p1["systems"])
        self.assertEqual(p1["design"], "mechanistic experimental")
        self.assertIn("mouse / rat model", out["papers"][1]["systems"])

    def test_gaps_and_reviews(self):
        out = mine([self.rec("1", "BRCA1 expression correlated with glycolysis in patients."),
                    self.rec("2", "A review of BRCA1.", review=True)], ["BRCA1"], "glycolysis")
        self.assertEqual(out["counts"], {"primary": 1, "reviews": 1})
        self.assertTrue(any("in vivo" in g for g in out["gaps"]))
        self.assertTrue(any("unreplicated" in g for g in out["gaps"]))
        self.assertEqual(out["papers"][1]["type"], "review")


class DatabaseErrors(unittest.TestCase):
    def test_service_validates_parameters(self):
        s = Service(HttpClient(cache_dir=Path(tempfile.mkdtemp()), offline=True))
        with self.assertRaises(ValueError):
            s.call("pathway_graph", {})
        with self.assertRaises(KeyError):
            s.call("not_an_op", {})

    def test_offline_without_cache_degrades_gracefully(self):
        s = Service(HttpClient(cache_dir=Path(tempfile.mkdtemp()), offline=True))
        g = s.call("pathway_graph", {"query": "hsa04151", "genes": "AKT1"})
        self.assertEqual(g["elements"]["edges"], [])
        self.assertTrue(all(v.startswith("failed") for v in g["source_status"].values()))


class ApiServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bpm_api
        service = Service(HttpClient(cache_dir=FIXTURE_CACHE, offline=True))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), bpm_api.make_handler(service))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health_lists_ops(self):
        code, body = self.get("/api/health")
        self.assertEqual(code, 200)
        self.assertIn("compare_mutation", body["ops"])

    def test_errors_map_to_http_status(self):
        self.assertEqual(self.get("/api/nope")[0], 404)
        self.assertEqual(self.get("/api/pathway_graph")[0], 400)

    @unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
    def test_graph_over_http(self):
        code, body = self.get("/api/pathway_graph?query=hsa04151&genes=PIK3CA,AKT1,MTOR")
        self.assertEqual(code, 200)
        self.assertTrue(body["elements"]["edges"])


class McpServer(unittest.TestCase):
    def run_mcp(self, *messages):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "bpm_mcp.py")], input="\n".join(map(json.dumps, messages)) + "\n",
                           capture_output=True, text=True, timeout=120,
                           env={"BPM_OFFLINE": "1", "BPM_CACHE_DIR": str(FIXTURE_CACHE), "PATH": "/usr/bin:/bin"})
        return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]

    def test_lifecycle_tools_and_errors(self):
        out = self.run_mcp(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "report", "arguments": {"kind": "bogus"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "unknown/method"})
        self.assertEqual(len(out), 4)   # the notification gets no reply
        self.assertEqual(out[0]["result"]["protocolVersion"], "2024-11-05")
        names = {t["name"] for t in out[1]["result"]["tools"]}
        self.assertTrue({"pathway_graph", "compare_mutation", "perturb_pathway", "structures", "expression", "literature"} <= names)
        for t in out[1]["result"]["tools"]:
            self.assertEqual(t["inputSchema"]["type"], "object")
        self.assertTrue(out[2]["result"]["isError"])
        self.assertEqual(out[3]["error"]["code"], -32601)

    @unittest.skipUnless(FIXTURE_CACHE.exists(), "fixtures not recorded")
    def test_report_tool_returns_markdown(self):
        out = self.run_mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": "report", "arguments": {"kind": "metabolic", "query": "glycolysis", "module": "M00001"}}})
        text = out[0]["result"]["content"][0]["text"]
        self.assertIn("# BioPathway Mapper: metabolic analysis", text)
        self.assertIn("```mermaid", text)


if __name__ == "__main__":
    unittest.main()
