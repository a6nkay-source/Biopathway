import unittest

import _helpers  # noqa: F401
from bpm import evidence as ev
from bpm.diagram import dot, mermaid, select_edges
from bpm.models import Analysis, Citation, Edge, Node, Statement
from bpm.report import render_markdown


def toy():
    a = Analysis("pathway", "toy")
    a.add_node(Node("A", 'Gene "A"', focus=True))
    a.add_node(Node("B", "B"))
    a.add_node(Node("C", "C", kind="compound"))
    a.add_node(Node("D", "D"))
    cite = Citation("KEGG", "hsa99999", "https://www.kegg.jp/pathway/hsa99999", "Toy")
    a.add_edge(Edge("A", "B", "activation", ev.CURATED, modifiers=["+p"], citations=[cite]))
    a.add_edge(Edge("B", "C", "inhibition", ev.EXPERIMENTAL, citations=[cite]))
    a.add_edge(Edge("C", "D", "association", ev.PREDICTED, directed=False, citations=[cite]))
    a.statements.append(Statement("A activates B.", ev.CURATED, [cite]))
    return a


class DiagramTests(unittest.TestCase):
    def test_mermaid_grammar(self):
        m = mermaid(toy())
        self.assertTrue(m.startswith("flowchart LR"))
        self.assertIn('-->|"activation +p · CUR"|', m)
        self.assertIn("--x|", m)
        self.assertIn("-.-|", m)             # predicted + undirected = dashed, no head
        self.assertIn("#quot;A#quot;", m)    # quotes escaped
        self.assertEqual(m.count("linkStyle"), 3)
        self.assertIn(ev_color(ev.EXPERIMENTAL), m)

    def test_dot_grammar(self):
        d = dot(toy())
        self.assertTrue(d.startswith("digraph"))
        self.assertIn("arrowhead=tee", d)
        self.assertIn("dir=none", d)
        self.assertIn("style=dashed", d)
        self.assertIn('Gene \\"A\\"', d)
        self.assertEqual(d.count("{"), d.count("}"))

    def test_select_edges_keeps_focus_first(self):
        a = toy()
        kept = select_edges(a, 1)
        self.assertEqual((kept[0].source, kept[0].target), ("A", "B"))

    def test_duplicate_edges_merge(self):
        a = toy()
        a.add_edge(Edge("A", "B", "activation", ev.CURATED, modifiers=["via X"]))
        self.assertEqual(len(a.edges), 3)
        self.assertIn("via X", a.edges[0].modifiers)
        a.add_edge(Edge("D", "C", "association", ev.PREDICTED, directed=False))
        self.assertEqual(len(a.edges), 3)  # undirected A-B == B-A


class ReportTests(unittest.TestCase):
    def test_report_sections_and_citation_numbers(self):
        md = render_markdown(toy())
        for heading in ("## 1. Input", "## 2. Data source status", "## 4. Reconstructed",
                        "## 5. Evidence-labelled statements", "## 6. Pathway diagram", "## Sources"):
            self.assertIn(heading, md)
        self.assertIn("```mermaid", md)
        self.assertIn("**[CUR]** A activates B. [1]", md)
        self.assertIn("1. KEGG hsa99999", md)

    def test_empty_analysis_says_so(self):
        md = render_markdown(Analysis("gene", "NOTAGENE"))
        self.assertIn("No relationships could be reconstructed", md)
        self.assertIn("No diagram", md)
        self.assertNotIn("```mermaid", md)


def ev_color(level):
    from bpm.diagram import COLOR
    return COLOR[level]


if __name__ == "__main__":
    unittest.main()
