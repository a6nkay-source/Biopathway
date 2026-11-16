import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CODES, EVIDENCE } from "../lib/evidence";

/** Compact one-line legend; expands for the full key. */
export default function Legend({ kind = "signalling" }: { kind?: "signalling" | "metabolic" | "network" | "hierarchy" }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="legend" style={{ minWidth: 0 }}>
      <div className="row wrap" style={{ gap: 10 }}>
        {CODES.map((c) => (
          <span key={c} className="legend-row" title={EVIDENCE[c].label} style={{ gap: 5 }}>
            <span className="legend-swatch" style={{ borderColor: `var(--ev-${c})`, width: 16 }} />
            <span className="mono" style={{ color: `var(--ev-${c})` }}>{c}</span></span>
        ))}
        {kind === "signalling" && <span className="legend-row">→ act · ⊣ inh · <b style={{ color: "var(--phos)" }}>+p</b></span>}
        <button className="btn ghost" style={{ height: 20, padding: "0 2px", fontSize: 11, color: "var(--text-3)" }} onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "less ▾" : "key ▸"}</button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: "hidden" }}>
            <div style={{ marginTop: 6 }}>
              {CODES.map((c) => <div key={c} className="legend-row"><span className="mono" style={{ width: 34, color: `var(--ev-${c})` }}>{c}</span>{EVIDENCE[c].label}</div>)}
              {kind === "signalling" && <>
                <div className="legend-row"><span className="legend-swatch dash" style={{ borderColor: "var(--text-3)" }} />expression, indirect, or non-curated evidence</div>
                <div className="legend-row"><span style={{ width: 22, height: 10, border: "3px double var(--border-2)", display: "inline-block" }} />complex · box with "+n" = KEGG gene group</div>
                <div className="legend-row"><span style={{ color: "var(--warn)" }}>⚠</span> direction suspect in KEGG's file</div>
              </>}
              {kind === "metabolic" && <div className="legend-row">compound → compound, labelled with the enzyme genes for each reaction</div>}
              {kind === "network" && <div className="legend-row">no arrowhead = undirected functional association (STRING)</div>}
              {kind === "hierarchy" && <div className="legend-row">hexagon = Reactome pathway · dashed "contains" skips levels</div>}
              <div className="legend-row"><span style={{ width: 14, height: 14, borderRadius: 3, border: "3px solid #d4a017", display: "inline-block" }} />query focus</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
