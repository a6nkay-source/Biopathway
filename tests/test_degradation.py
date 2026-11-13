"""Source outages must produce honest partial results, never exceptions."""

import json
import tempfile
import unittest
from pathlib import Path

from _helpers import FakeTransport
from bpm import analysis as an
from bpm.http import HttpClient

GENE_SEARCH = json.dumps({"esearchresult": {"idlist": ["7157"]}})
GENE_SUMMARY = json.dumps({"result": {"uids": ["7157"], "7157": {
    "uid": "7157", "name": "TP53", "description": "tumor protein p53", "otheraliases": "P53, LFS1",
    "maplocation": "17p13.1", "summary": "Tumor suppressor."}}})
UNIPROT = json.dumps({"results": [{
    "entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "P04637",
    "uniProtkbId": "P53_HUMAN",
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}},
    "genes": [{"geneName": {"value": "TP53"}}],
    "comments": [{"commentType": "FUNCTION", "texts": [{"value": "Transcription factor (PubMed:1).",
                                                         "evidences": [{"evidenceCode": "ECO:0000269",
                                                                        "source": "PubMed", "id": "1"}]}]}],
    "uniProtKBCrossReferences": [{"database": "GO", "id": "GO:0006915",
                                  "properties": [{"key": "GoTerm", "value": "P:apoptotic process"},
                                                 {"key": "GoEvidenceType", "value": "IDA:UniProtKB"}]}]}]})


def ctx_with(routes, use_kegg=True):
    http = HttpClient(cache_dir=Path(tempfile.mkdtemp()), transport=FakeTransport(routes),
                      sleep=lambda s: None, max_retries=0)
    return an.Context(http, use_kegg=use_kegg)


class Degradation(unittest.TestCase):
    def test_everything_down(self):
        ctx = ctx_with({"": [OSError("offline")]})
        a = an.analyze_gene(ctx, ["TP53"])
        self.assertEqual(a.edges, [])
        self.assertTrue(all(v.startswith("failed") for v in a.source_status.values()))
        self.assertTrue(any("Could not resolve" in w for w in a.warnings))

    def test_string_and_kegg_down_still_reports_identity_and_function(self):
        ctx = ctx_with({
            "esearch.fcgi?db=gene": [(200, GENE_SEARCH)],
            "esummary.fcgi?db=gene": [(200, GENE_SUMMARY)],
            "rest.uniprot.org": [(200, UNIPROT)],
            "reactome.org": [(200, "[]")],
            "string-db.org": [(503, "")],
            "rest.kegg.jp": [OSError("timeout")],
            "db=pubmed": [(200, json.dumps({"esearchresult": {"idlist": []}}))],
        })
        a = an.analyze_gene(ctx, ["TP53"])
        self.assertEqual(a.resolved["TP53"]["uniprot"], "P04637")
        self.assertTrue(a.source_status["STRING"].startswith("failed"))
        self.assertTrue(a.source_status["KEGG"].startswith("failed"))
        self.assertEqual(a.source_status["UniProt"], "ok")
        self.assertTrue(any("STRING unavailable" in w for w in a.warnings))
        fn = [s for s in a.statements if s.section == "Function"]
        self.assertEqual(fn[0].evidence, "experimentally validated")
        self.assertNotIn("PubMed:1", fn[0].text)   # inline refs stripped, kept as citations
        go = [s for s in a.statements if s.section == "Biological process"]
        self.assertIn("apoptotic process", go[0].text)

    def test_kegg_disabled_is_reported_not_failed(self):
        ctx = ctx_with({"": [OSError("offline")]}, use_kegg=False)
        a = an.analyze_metabolic(ctx, "glycolysis")
        self.assertIn("not queried", a.source_status["KEGG"])
        self.assertTrue(any("disabled" in w for w in a.warnings))

    def test_unparseable_variant_is_flagged(self):
        ctx = ctx_with({
            "esearch.fcgi?db=gene": [(200, GENE_SEARCH)],
            "esummary.fcgi?db=gene": [(200, GENE_SUMMARY)],
            "rest.uniprot.org": [(200, UNIPROT)],
            "db=clinvar": [(200, json.dumps({"esearchresult": {"idlist": []}}))],
            "db=pubmed": [(200, json.dumps({"esearchresult": {"idlist": []}}))],
            "rest.kegg.jp": [(200, "")],
        })
        a = an.analyze_mutation(ctx, "TP53", "weird-change")
        self.assertTrue(any("not a recognised protein-level change" in w for w in a.warnings))


if __name__ == "__main__":
    unittest.main()
