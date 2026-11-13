import unittest

import _helpers  # noqa: F401
from bpm import evidence as ev


class StringClassification(unittest.TestCase):
    def test_experimental_channel_wins(self):
        level, why = ev.classify_string({"escore": 0.9, "dscore": 0.9, "tscore": 0.9, "score": 0.99})
        self.assertEqual(level, ev.EXPERIMENTAL)
        self.assertIn("experiments", why)

    def test_database_only_is_curated(self):
        self.assertEqual(ev.classify_string({"dscore": 0.5, "tscore": 0.9})[0], ev.CURATED)

    def test_textmining_only_is_literature_not_interaction(self):
        level, why = ev.classify_string({"tscore": 0.95, "score": 0.95})
        self.assertEqual(level, ev.LITERATURE)
        self.assertIn("not a demonstrated interaction", why)

    def test_coexpression_only_is_predicted(self):
        self.assertEqual(ev.classify_string({"ascore": 0.6})[0], ev.PREDICTED)

    def test_high_combined_but_weak_channels_is_hypothetical(self):
        # Several weak channels can combine to a high score; none alone justifies a label.
        level, _ = ev.classify_string({"escore": 0.3, "tscore": 0.3, "ascore": 0.3, "score": 0.75})
        self.assertEqual(level, ev.HYPOTHETICAL)


class OtherClassifiers(unittest.TestCase):
    def test_eco_strongest_code_wins(self):
        level, why = ev.classify_eco([{"evidenceCode": "ECO:0000250"}, {"evidenceCode": "ECO:0000269"}])
        self.assertEqual(level, ev.EXPERIMENTAL)
        self.assertIn("ECO:0000269", why)

    def test_eco_similarity_only_is_predicted(self):
        self.assertEqual(ev.classify_eco([{"evidenceCode": "ECO:0000250"}])[0], ev.PREDICTED)

    def test_eco_unreviewed_without_codes_is_predicted(self):
        self.assertEqual(ev.classify_eco([], reviewed=False)[0], ev.PREDICTED)

    def test_go_codes(self):
        self.assertEqual(ev.classify_go("IDA:UniProtKB")[0], ev.EXPERIMENTAL)
        self.assertEqual(ev.classify_go("TAS:Reactome")[0], ev.CURATED)
        self.assertEqual(ev.classify_go("IEA:InterPro")[0], ev.PREDICTED)

    def test_clinvar_review_status(self):
        self.assertEqual(ev.classify_clinvar("reviewed by expert panel")[0], ev.CURATED)
        self.assertEqual(ev.classify_clinvar("criteria provided, single submitter")[0], ev.LITERATURE)
        self.assertEqual(ev.classify_clinvar("no assertion criteria provided")[0], ev.HYPOTHETICAL)

    def test_reactome_inferred(self):
        self.assertEqual(ev.classify_reactome(False)[0], ev.CURATED)
        self.assertEqual(ev.classify_reactome(True)[0], ev.PREDICTED)

    def test_kegg_indirect_flagged(self):
        level, why = ev.classify_kegg(["indirect effect"])
        self.assertEqual(level, ev.CURATED)
        self.assertIn("indirect", why)

    def test_strongest(self):
        self.assertEqual(ev.strongest([ev.PREDICTED, ev.CURATED]), ev.CURATED)
        self.assertEqual(ev.strongest([]), ev.HYPOTHETICAL)


if __name__ == "__main__":
    unittest.main()
