import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { loadIndex, type Mode } from "../api";
import type { Scenario } from "../types";
import type { ViewId } from "../App";
import { CODES, EVIDENCE } from "../lib/evidence";
import { usePrefersReducedMotion } from "../lib/hooks";

const VIEW_FOR: Record<string, [ViewId, string]> = {
  "tp53-apoptosis": ["pathway", "tp53-apoptosis"], "egfr-mapk": ["pathway", ""], "pi3k-akt-mtor": ["pathway", "pi3k-akt-mtor"],
  "kras-g12d": ["mutation", ""], glycolysis: ["metabolic", ""], "brca1-dna-repair": ["process", ""],
};

export default function Overview({ go, mode }: { go: (v: ViewId, arg?: string) => void; mode: Mode | null }) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const reduced = usePrefersReducedMotion();
  useEffect(() => { loadIndex().then((i) => setScenarios(i.scenarios)).catch(() => setScenarios([])); }, []);
  const item = (i: number) => reduced ? {} : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 },
    transition: { delay: 0.05 * i, duration: 0.4, ease: [0.22, 1, 0.36, 1] as const } };
  return (
    <div>
      <section className="hero">
        <motion.h2 {...item(0)}>Explore molecular pathways where every arrow has a source.</motion.h2>
        <motion.p {...item(1)}>BioPathway Explorer draws only relationships that a database record states (KEGG, Reactome, STRING,
          UniProt, ClinVar), labels each one by evidence class, and lets you play signals through them, compare a mutant with normal
          signalling, perturb the network and inspect protein structures.</motion.p>
        <motion.div {...item(2)} className="row wrap" style={{ gap: 8 }}>
          {CODES.map((c) => <span key={c} className={`badge ev ev-${c}`} title={EVIDENCE[c].label}>{c} · {EVIDENCE[c].short}</span>)}
          {mode === "bundled" && <span className="chip">Demo data: run <code>python3 scripts/bpm_api.py</code> for live queries</span>}
        </motion.div>
      </section>
      <div className="scenario-grid">
        {scenarios.map((s, i) => (
          <motion.button key={s.id} className="scenario" {...item(i + 3)} whileHover={reduced ? undefined : { y: -2 }}
            onClick={() => { const [v, a] = VIEW_FOR[s.id] ?? ["pathway", ""]; go(v, a); }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="chip">{s.view}</span><span className="tiny muted mono">{s.params.query ?? s.params.gene ?? ""}</span>
            </div>
            <h3>{s.title}</h3>
            <p>{s.summary}</p>
            <span className="small" style={{ color: "var(--accent)", fontWeight: 600 }}>Open →</span>
          </motion.button>
        ))}
      </div>
      <div className="arch">
        {[["BioPathway Mapper skill", "SKILL.md: how Claude chooses analyses, reads evidence and words claims. Labels, citations, honesty rules."],
          ["BioPathway MCP server", "scripts/bpm_mcp.py: 13 tools over the same database clients (cache, rate limits, provenance)."],
          ["BioPathway Explorer", "This app: Cytoscape networks, signal playback, mutant comparison, perturbation, Three.js structures."]].map(([t, d], i) => (
          <motion.div key={t} className="card card-pad" {...item(i + 9)}>
            <div className="section-title">Component {i + 1}</div><h3 style={{ fontSize: 15 }}>{t}</h3>
            <p className="small muted" style={{ marginBottom: 0 }}>{d}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
