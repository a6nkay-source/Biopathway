import { lazy, Suspense, useEffect, useState, type ReactElement } from "react";
import { motion } from "motion/react";
import { detectMode, type Mode } from "./api";
import { useTheme } from "./lib/hooks";
import * as I from "./components/Icons";
import Overview from "./views/Overview";
import PathwayView from "./views/PathwayView";
import { Loading } from "./components/ui";

const MutationView = lazy(() => import("./views/MutationView"));
const StructureView = lazy(() => import("./views/StructureView"));
const GeneView = lazy(() => import("./views/GeneView"));
const LiteratureView = lazy(() => import("./views/LiteratureView"));

export type ViewId = "overview" | "gene" | "pathway" | "mutation" | "interactions" | "metabolic" | "process" | "literature" | "structure";

const NAV: { id: ViewId; label: string; icon: (p: { size?: number }) => ReactElement; section?: string }[] = [
  { id: "overview", label: "Overview", icon: I.IconOverview },
  { id: "gene", label: "Gene Explorer", icon: I.IconGene, section: "Explore" },
  { id: "pathway", label: "Pathway Explorer", icon: I.IconPathway },
  { id: "mutation", label: "Mutation Analysis", icon: I.IconMutation },
  { id: "interactions", label: "Protein Interactions", icon: I.IconInteractions },
  { id: "metabolic", label: "Metabolic Pathways", icon: I.IconMetabolic },
  { id: "process", label: "Biological Processes", icon: I.IconPathway },
  { id: "literature", label: "Literature Research", icon: I.IconLiterature, section: "Evidence" },
  { id: "structure", label: "3D Structures", icon: I.IconStructure },
];

const TITLES: Record<ViewId, [string, string]> = {
  overview: ["Overview", "Evidence-labelled molecular biology, from database records"],
  gene: ["Gene Explorer", "Identity, function, tissue context and cross-pathway analysis"],
  pathway: ["Pathway Explorer", "Directed KEGG relations with signal playback and perturbation"],
  mutation: ["Mutation Analysis", "Normal vs documented variant changes, side by side"],
  interactions: ["Protein Interactions", "STRING functional associations by evidence channel"],
  metabolic: ["Metabolic Pathways", "Metabolite flow from KEGG reactions and enzymes"],
  process: ["Biological Processes", "Reactome process hierarchies and curated events"],
  literature: ["Literature Research", "Primary studies, methods, conflicts and gaps"],
  structure: ["3D Structures", "AlphaFold predictions and experimental PDB structures"],
};

function parseHash(): { view: ViewId; arg: string } {
  const [v, arg = ""] = decodeURIComponent(location.hash.replace(/^#\/?/, "")).split("/");
  return { view: (NAV.some((n) => n.id === v) ? v : "overview") as ViewId, arg };
}

export default function App() {
  const [dark, toggleTheme] = useTheme();
  const [route, setRoute] = useState(parseHash);
  const [mode, setMode] = useState<Mode | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => { detectMode().then(setMode); }, []);
  useEffect(() => {
    const f = () => setRoute(parseHash());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  const go = (view: ViewId, arg = "") => { location.hash = `/${view}${arg ? "/" + encodeURIComponent(arg) : ""}`; };
  const navigate = (t: string) => {
    const [kind, sym] = t.split(":");
    go(kind === "structure" ? "structure" : kind === "interactions" ? "interactions" : "gene", sym);
  };
  const { view, arg } = route;

  const content = (() => {
    switch (view) {
      case "overview": return <Overview go={go} mode={mode} />;
      case "pathway": {
        const presets = [
          { label: "EGFR → ERK (MAPK)", params: { query: "MAPK signaling", genes: "EGFR,MAPK1" } },
          { label: "PI3K-AKT-mTOR", params: { query: "hsa04151", genes: "PIK3CA,AKT1,MTOR" } },
          { label: "p53 → apoptosis", params: { query: "hsa04115", genes: "TP53,BBC3,PMAIP1,BAX,CASP3" } },
        ];
        const init = arg === "pi3k-akt-mtor" ? presets[1].params : arg === "tp53-apoptosis" ? presets[2].params : presets[0].params;
        return <PathwayView key={`pathway-${arg}`} op="pathway_graph" params={init} dark={dark} onNavigate={navigate} presets={presets}
          fields={[{ key: "query", label: "Pathway", placeholder: "Pathway name or KEGG id" }, { key: "genes", label: "Focus genes", placeholder: "Focus genes, e.g. EGFR,MAPK1", width: 200 }]} />;
      }
      case "metabolic":
        return <PathwayView key="metabolic" op="metabolic_graph" params={{ query: "glycolysis", module: "M00001" }} dark={dark} legend="metabolic" layout="dagre-tb"
          onNavigate={navigate} allowPerturb fields={[{ key: "query", label: "Pathway", placeholder: "Metabolic pathway" },
            { key: "module", label: "KEGG module", placeholder: "Module, e.g. M00001", width: 130 }, { key: "genes", label: "Enzymes", placeholder: "Enzyme genes (optional)" }]} />;
      case "process":
        return <PathwayView key={`process-${arg}`} op="process_graph" params={arg === "tp53" ? { query: "apoptosis", genes: "TP53" } : { query: "DNA repair", genes: "BRCA1" }}
          dark={dark} legend="hierarchy" layout="dagre-lr" allowPerturb={false} allowPlayback={false} onNavigate={navigate}
          presets={[{ label: "BRCA1 in DNA repair", params: { query: "DNA repair", genes: "BRCA1" } }, { label: "TP53 in apoptosis", params: { query: "apoptosis", genes: "TP53" } }]}
          fields={[{ key: "query", label: "Process", placeholder: "Process or Reactome id" }, { key: "genes", label: "Genes", placeholder: "Genes" }]} />;
      case "interactions":
        return <PathwayView key={`int-${arg}`} op="interaction_graph" params={{ genes: arg || "TP53" }} dark={dark} legend="network" layout="fcose"
          allowPerturb={false} allowPlayback={false} onNavigate={navigate}
          presets={[{ label: "TP53", params: { genes: "TP53" } }, { label: "BRCA1", params: { genes: "BRCA1" } }, { label: "KRAS", params: { genes: "KRAS" } }]}
          fields={[{ key: "genes", label: "Genes", placeholder: "One gene (partners) or several (network)", width: 260 }]} />;
      case "mutation": return <MutationView dark={dark} onNavigate={navigate} />;
      case "structure": return <StructureView key={arg} dark={dark} initial={arg || "KRAS"} />;
      case "gene": return <GeneView key={arg} initial={arg || "KRAS"} />;
      case "literature": return <LiteratureView />;
    }
  })();

  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <nav className="sidebar" aria-label="Main">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
            <path d="M9 16 L23 8 M9 16 L23 24 M23 8 L23 24" stroke="var(--text-3)" strokeWidth="1.6" />
            <circle cx="9" cy="16" r="5" fill="var(--accent)" /><circle cx="23" cy="8" r="4" fill="var(--act)" /><circle cx="23" cy="24" r="4" fill="var(--inh)" />
          </svg>
          <span className="brand-text">BioPathway<small>EXPLORER · v2.0</small></span>
        </div>
        {NAV.map((n) => (
          <div key={n.id}>
            {n.section && <div className="nav-section">{n.section}</div>}
            <button className={`nav-item ${view === n.id ? "active" : ""}`} onClick={() => go(n.id)} aria-current={view === n.id ? "page" : undefined} title={n.label}>
              {view === n.id && <motion.span layoutId="nav-bg" className="nav-bg" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              <n.icon /><span className="nav-label">{n.label}</span>
            </button>
          </div>
        ))}
        <div className="sidebar-foot">
          Data: NCBI · UniProt · Reactome · STRING · KEGG · ClinVar · PubMed · AlphaFold · PDB · GTEx · HPA · GEO
        </div>
      </nav>
      <div className="main">
        <header className="topbar">
          <button className="icon-btn" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar"><I.IconMenu /></button>
          <h1>{TITLES[view][0]}</h1><span className="crumb">{TITLES[view][1]}</span>
          <div className="spacer" />
          {mode && <span className={`mode-pill ${mode}`} title={mode === "live" ? "Connected to the local API: live database queries" :
            "Bundled demo data (six reference scenarios). Start scripts/bpm_api.py for live queries."}>
            <span className="dot" />{mode === "live" ? "Live databases" : "Demo data"}</span>}
          <button className="icon-btn" onClick={toggleTheme} aria-label="Toggle theme" title="Toggle light/dark">{dark ? <I.IconSun /> : <I.IconMoon />}</button>
        </header>
        <main className="view" key={view}>
          <Suspense fallback={<div style={{ position: "relative", height: "100%" }}><Loading label="Loading view" /></div>}>{content}</Suspense>
        </main>
      </div>
    </div>
  );
}
