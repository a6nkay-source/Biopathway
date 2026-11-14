import json
import tempfile
import unittest
from pathlib import Path

from _helpers import FakeTransport
from bpm import analysis as an
from bpm import evidence as ev
from bpm.http import HttpClient
from bpm.integrations.ncbi import parse_pubmed_xml
from bpm.models import Analysis, Edge, Node

XML = """<?xml version="1.0"?>
<PubmedArticleSet>
 <PubmedArticle><MedlineCitation><PMID>111</PMID><Article>
  <Journal><ISOAbbreviation>PLoS One</ISOAbbreviation><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
  <ArticleTitle>Gene <i>X</i> represses gene Y</ArticleTitle>
  <Abstract><AbstractText Label="METHODS">ChIP and reporter assays.</AbstractText>
            <AbstractText Label="RESULTS">X occupies the <i>Y</i> promoter.</AbstractText></Abstract>
  <AuthorList><Author><LastName>Smith</LastName><Initials>J</Initials></Author></AuthorList>
  <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
 </Article></MedlineCitation></PubmedArticle>
 <PubmedArticle><MedlineCitation><PMID>222</PMID><Article>
  <Journal><Title>Some Review Journal</Title><JournalIssue><PubDate><MedlineDate>2019 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
  <ArticleTitle>A review</ArticleTitle>
  <PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList>
 </Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


class PubmedXml(unittest.TestCase):
    def test_parse(self):
        recs = parse_pubmed_xml(XML)
        self.assertEqual([r["pmid"] for r in recs], ["111", "222"])
        self.assertEqual(recs[0]["title"], "Gene X represses gene Y")       # inline tags flattened
        self.assertEqual(recs[0]["abstract"], "METHODS: ChIP and reporter assays.\nRESULTS: X occupies the Y promoter.")
        self.assertEqual((recs[0]["year"], recs[0]["first_author"], recs[0]["is_review"]), ("2020", "Smith J", False))
        self.assertEqual((recs[1]["year"], recs[1]["is_review"], recs[1]["abstract"]), ("2019", True, ""))

    def test_bad_xml(self):
        self.assertEqual(parse_pubmed_xml("<html>oops"), [])

    def test_title_score(self):
        self.assertEqual(an._title_score("BRCA1 induces metabolism reprogramming", ["BRCA1"], "glycolysis"), 2)
        self.assertEqual(an._title_score("Loss of BRCA1 induces glycolysis", ["BRCA1"], "glycolysis"), 3)
        self.assertEqual(an._title_score("BRCA10 and glycolytic flux", ["BRCA1"], "glycolysis"), 1)  # no partial symbol


class LiteratureAnalysis(unittest.TestCase):
    def test_ranks_on_topic_titles_first_and_warns_on_missing_pmid(self):
        ids = [str(i) for i in range(1, 13)]
        search = json.dumps({"esearchresult": {"idlist": ids}})
        summary = json.dumps({"result": {"uids": ids, **{i: {"uid": i, "title": "unrelated"} for i in ids},
                                         "12": {"uid": "12", "title": "Gene X represses glycolysis"}}})
        transport = FakeTransport({
            "esearch.fcgi": [(200, search)],
            "esummary.fcgi": [(200, summary)],
            "efetch.fcgi": [(200, XML.replace("<PMID>111</PMID>", "<PMID>12</PMID>"))],
        })
        ctx = an.Context(HttpClient(cache_dir=Path(tempfile.mkdtemp()), transport=transport,
                                    sleep=lambda s: None), use_kegg=False)
        a = an.analyze_literature(ctx, "glycolysis", pmids=["999"], max_results=3)
        efetch_url = next(u for u in transport.calls if "efetch" in u)
        self.assertIn("12", efetch_url.split("id=")[1].split("&")[0].split("%2C"))  # on-topic title promoted
        self.assertTrue(any("PMID 999" in w for w in a.warnings))
        self.assertEqual(a.literature[0]["pmid"], "12")
        self.assertTrue(all(r["evidence"] == ev.LITERATURE for r in a.literature))
        self.assertEqual(a.edges, [])


class SuspectInversions(unittest.TestCase):
    def build(self, extra):
        a = Analysis("pathway", "toy")
        for n in ["HUB", "T1", "T2", "T3", "T4", "T5", "X"]:
            a.add_node(Node(n, n))
        edges = [Edge("HUB", t, "expression", ev.CURATED) for t in ["T1", "T2", "T3", "T4", "T5"]] + extra
        return a, edges

    def test_flags_backwards_edge_without_changing_it(self):
        a, edges = self.build([Edge("X", "HUB", "expression", ev.CURATED)])
        flagged = an.flag_suspect_inversions(a, edges, "hsa99999")
        self.assertEqual([(e.source, e.target) for e in flagged], [("X", "HUB")])
        self.assertIn("direction suspect", flagged[0].modifiers)
        self.assertTrue(any("probably an inversion" in w for w in a.warnings))

    def test_reciprocal_or_small_hub_not_flagged(self):
        a, edges = self.build([Edge("X", "HUB", "expression", ev.CURATED),
                               Edge("HUB", "X", "expression", ev.CURATED)])
        self.assertEqual(an.flag_suspect_inversions(a, edges, "p"), [])
        a2 = Analysis("pathway", "toy")
        small = [Edge("A", "B", "expression", ev.CURATED), Edge("B", "C", "expression", ev.CURATED)]
        self.assertEqual(an.flag_suspect_inversions(a2, small, "p"), [])

    def test_activation_edges_ignored(self):
        a, edges = self.build([Edge("X", "HUB", "activation", ev.CURATED)])
        self.assertEqual(an.flag_suspect_inversions(a, edges, "p"), [])


if __name__ == "__main__":
    unittest.main()
