import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import type { GraphPayload } from "../types";
import { ErrorBox, ExtLink, Loading, Section, SourceStatus, Warnings } from "../components/ui";
import { useApi } from "../lib/hooks";

interface Mined {
  pmid: string; doi: string; title: string; year: string; journal: string; type: string; design: string;
  methods: string[]; systems: string[]; limitations: string[]; has_abstract: boolean; url: string;
  claims: { sentence: string; direction: string; implied_gene_effect: string }[];
}
interface Lit extends GraphPayload { mining: { papers: Mined[]; conflicts: { papers: string[]; a: string; b: string; note: string }[];
  gaps: string[]; counts: { primary: number; reviews: number }; caveat: string } }

const ARROW: Record<string, string> = { up: "↑", down: "↓", mixed: "↕" };

export default function LiteratureView() {
  const init = { query: "glycolysis", genes: "BRCA1" };
  const [form, setForm] = useState(init);
  const [params, setParams] = useState(init);
  const { data, error, loading } = useApi<Lit>("literature", params);
  const [open, setOpen] = useState<string | null>(null);
  const abstracts = new Map((data?.literature ?? []).map((p) => [p.pmid, p.abstract ?? ""]));
  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100%", minHeight: 0 }}>
      <form className="toolbar" onSubmit={(e) => { e.preventDefault(); setParams({ ...form }); }}>
        <input className="input" style={{ width: 120 }} aria-label="Genes" placeholder="Genes" value={form.genes} onChange={(e) => setForm({ ...form, genes: e.target.value })} />
        <input className="input" style={{ width: 240 }} aria-label="Topic" placeholder="Topic" value={form.query} onChange={(e) => setForm({ ...form, query: e.target.value })} />
        <button className="btn primary">Search PubMed</button>
        <select className="input" value="" onChange={(e) => { const v = JSON.parse(e.target.value || "null"); if (v) { setForm(v); setParams(v); } }} aria-label="Examples">
          <option value="">Examples…</option>
          <option value={JSON.stringify({ query: "glycolysis", genes: "BRCA1" })}>BRCA1 · glycolysis</option>
          <option value={JSON.stringify({ query: "apoptosis", genes: "TP53" })}>TP53 · apoptosis</option>
        </select>
      </form>
      <div className="view" style={{ position: "relative" }}>
        {loading && <Loading label="Searching PubMed and reading abstracts" />}
        {error != null && <div style={{ padding: 14 }}><ErrorBox error={error} /></div>}
        {data && !error && <div style={{ padding: 20, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px", gap: 16, maxWidth: 1500 }}>
          <div className="stack" style={{ gap: 12 }}>
            <div className="callout warn small">{data.mining.caveat}</div>
            {data.mining.papers.map((p, i) => (
              <motion.article key={p.pmid} className="card card-pad" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
                <div className="row wrap" style={{ gap: 6 }}>
                  <span className="badge" style={{ color: p.type === "review" ? "var(--ev-LIT)" : "var(--accent)" }}>{p.type}</span>
                  <span className="chip">{p.design}</span>
                  <span className="tiny muted">{p.journal} · {p.year}</span>
                  <span className="spacer" />
                  <ExtLink href={p.url}>PMID {p.pmid}</ExtLink>
                  {p.doi && <ExtLink href={`https://doi.org/${p.doi}`}>DOI</ExtLink>}
                </div>
                <h3 style={{ fontSize: 15, margin: "8px 0 6px", lineHeight: 1.35 }}>{p.title}</h3>
                <div className="row wrap" style={{ gap: 5 }}>
                  {p.methods.map((m) => <span key={m} className="chip">{m}</span>)}
                  {p.systems.map((s) => <span key={s} className="chip" style={{ color: "var(--accent-2)" }}>{s}</span>)}
                  {p.limitations.map((l) => <span key={l} className="chip" style={{ color: "var(--warn)" }}>⚠ {l}</span>)}
                </div>
                {p.claims.length > 0 && <ul className="list" style={{ marginTop: 10 }}>{p.claims.map((c, j) => (
                  <li key={j} className="small" style={{ display: "grid", gridTemplateColumns: "22px 1fr", gap: 6 }}>
                    <span className="mono" title={c.implied_gene_effect ? `implied effect of the gene: ${c.implied_gene_effect}` : "no clear direction"}
                      style={{ color: c.implied_gene_effect === "up" ? "var(--act)" : c.implied_gene_effect === "down" ? "var(--inh)" : "var(--text-3)" }}>
                      {ARROW[c.implied_gene_effect] ?? "·"}</span>
                    <span>"{c.sentence}"</span></li>))}</ul>}
                {p.has_abstract && <button className="btn ghost" style={{ height: 24, padding: 0, marginTop: 6 }} onClick={() => setOpen(open === p.pmid ? null : p.pmid)}>
                  {open === p.pmid ? "Hide abstract ▴" : "Show abstract ▾"}</button>}
                <AnimatePresence>{open === p.pmid && <motion.p initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                  className="small" style={{ whiteSpace: "pre-line", overflow: "hidden", color: "var(--text-2)" }}>{abstracts.get(p.pmid)}</motion.p>}</AnimatePresence>
              </motion.article>
            ))}
          </div>
          <div className="stack" style={{ gap: 16 }}>
            <div className="card card-pad"><Section title="Retrieved">
              <div className="grid-2"><div><div style={{ fontSize: 24, fontWeight: 700 }}>{data.mining.counts.primary}</div><div className="tiny muted">primary studies</div></div>
                <div><div style={{ fontSize: 24, fontWeight: 700 }}>{data.mining.counts.reviews}</div><div className="tiny muted">reviews</div></div></div></Section>
              <div style={{ marginTop: 10 }}><SourceStatus status={data.source_status} /></div></div>
            <div className="card card-pad"><Section title={`Candidate conflicts (${data.mining.conflicts.length})`}>
              {data.mining.conflicts.length ? data.mining.conflicts.map((c, i) => (
                <div key={i} className="statement small" style={{ marginBottom: 8 }}>
                  <div><b>PMID {c.papers[0]}</b>: "{c.a}"</div><div style={{ marginTop: 4 }}><b>PMID {c.papers[1]}</b>: "{c.b}"</div>
                  <div className="tiny muted" style={{ marginTop: 4 }}>{c.note}</div></div>)) :
                <p className="small muted" style={{ margin: 0 }}>No opposite-direction statements detected in the retrieved abstracts.</p>}</Section></div>
            <div className="card card-pad"><Section title="Evidence gaps in this set">
              {data.mining.gaps.length ? <ul className="list">{data.mining.gaps.map((g, i) => <li key={i} className="small">{g}</li>)}</ul> :
                <p className="small muted" style={{ margin: 0 }}>The set includes in vivo, patient and mechanistic studies.</p>}</Section></div>
            <Warnings items={data.warnings} />
            <div className="callout info small">Arrows show the <b>implied effect of the gene</b>: "loss of X increased Y" counts as X lowering Y. Read the abstract before relying on any of it.</div>
          </div>
        </div>}
      </div>
    </div>
  );
}
