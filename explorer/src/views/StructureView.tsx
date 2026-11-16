import { useMemo, useState } from "react";
import { motion } from "motion/react";
import Structure3D, { PLDDT_COLORS, colourDomains, domainColor, type Atom, type ColorMode, type Feature } from "../components/Structure3D";
import { Ev, ErrorBox, ExtLink, Loading, Section, SourceStatus, Warnings } from "../components/ui";
import { useApi, usePrefersReducedMotion } from "../lib/hooks";

interface Entry { id: string; source: string; provenance: string; method: string; resolution?: number; title?: string; mean_plddt?: number; url: string; released?: string; pmid?: string; doi?: string; range?: number[]; created?: string }
interface Structs {
  symbol: string; accession: string; protein_name: string; predicted: Entry | null; experimental: Entry[]; experimental_total: number;
  features: (Feature & { evidence: string; basis: string; alternatives: string[]; original: string })[];
  pathways: { id: string; name: string; url: string }[]; warnings: string[]; source_status: Record<string, string>; notes: string[]; sequence_length?: number;
}
interface Coords { id: string; provenance: string; b_factor: string; numbering: string; target_chains?: string[]; atoms: Atom[] }

export default function StructureView({ dark, initial }: { dark: boolean; initial: string }) {
  const [q, setQ] = useState(initial);
  const [query, setQuery] = useState(initial);
  const { data, error, loading } = useApi<Structs>("structures", { query });
  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100%", minHeight: 0 }}>
      <form className="toolbar" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
        <input className="input" style={{ width: 180 }} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Gene or UniProt accession" placeholder="Gene or UniProt accession" />
        <button className="btn primary">Load structures</button>
        <span className="small muted">AlphaFold DB (predicted) · RCSB PDB (experimental) · UniProt features</span>
      </form>
      <div style={{ position: "relative", minHeight: 0 }}>
        {loading && <Loading label="Retrieving structures" />}
        {error != null && <div style={{ padding: 14 }}><ErrorBox error={error} /></div>}
        {data && !error && (data.accession ? <Viewer key={data.accession} data={data} dark={dark} /> :
          <div style={{ padding: 14 }}><Warnings items={data.warnings} /></div>)}
      </div>
    </div>
  );
}

function Viewer({ data, dark }: { data: Structs; dark: boolean }) {
  const reduced = usePrefersReducedMotion();
  const options = [...(data.predicted ? [{ kind: "alphafold", id: "", entry: data.predicted }] : []),
    ...data.experimental.map((e) => ({ kind: "pdb", id: e.id, entry: e }))];
  const [pick, setPick] = useState(0);
  const [mode, setMode] = useState<ColorMode>("confidence");
  const [focus, setFocus] = useState<Feature | null>(null);
  const [showSites, setShowSites] = useState(true);
  const cur = options[pick];
  const coords = useApi<Coords>(cur ? "structure_coords" : null, cur ? { kind: cur.kind, id: cur.id, accession: data.accession } : {});
  const predicted = cur?.kind === "alphafold";
  const domains = useMemo(() => colourDomains(data.features), [data]);
  const otherRegions = useMemo(() => data.features.filter((f) => f.type === "Region" && !domains.includes(f)), [data, domains]);
  const sites = data.features.filter((f) => ["Binding site", "Active site", "Modified residue"].includes(f.type));
  const variants = data.features.filter((f) => f.type === "Natural variant" && f.description);
  const mapped = coords.data?.atoms.filter((a) => a.uniprot != null).length ?? 0;

  return (
    <div className="workspace" style={{ height: "100%" }}>
      <div className="stage" style={{ gridTemplateRows: "auto 1fr" }}>
        <div className="toolbar">
          <div className="seg" role="group" aria-label="Colour by">
            {([["confidence", predicted ? "pLDDT" : "B-factor"], ["domain", "Domains"], ["chain", "Chains"], ["rainbow", "N→C"]] as [ColorMode, string][]).map(([m, l]) =>
              <button key={m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>{l}</button>)}
          </div>
          <label className="check"><input type="checkbox" checked={showSites} onChange={(e) => setShowSites(e.target.checked)} /> binding / active sites</label>
          <div className="spacer" />
          {cur && <span className="badge" style={{ color: predicted ? "var(--ev-PRED)" : "var(--ev-EXP)" }}>
            {predicted ? "Computationally predicted" : "Experimentally determined"}</span>}
        </div>
        <div className="canvas-wrap">
          {coords.loading && <Loading label="Loading coordinates" />}
          {coords.error != null && <div style={{ padding: 14 }}><ErrorBox error={coords.error} /></div>}
          {coords.data && <Structure3D atoms={coords.data.atoms} features={data.features} mode={mode} isPredicted={predicted}
            targetChains={coords.data.target_chains} focus={focus} showSites={showSites} dark={dark} reduced={reduced} />}
          {coords.data && <div className="canvas-overlay"><div className="legend">
            {mode === "confidence" && predicted && PLDDT_COLORS.map(([l, c]) => <div key={l} className="legend-row"><span className="swatch" style={{ background: c }} />{l}</div>)}
            {mode === "confidence" && !predicted && <div className="legend-row">blue = low B-factor (ordered) → red = high (mobile)</div>}
            {mode === "domain" && domains.slice(0, 8).map((d, i) => <div key={i} className="legend-row"><span className="swatch" style={{ background: domainColor(domains, i) }} />{d.description || d.type} ({d.start}–{d.end})</div>)}
            {mode === "chain" && <div className="legend-row">one colour per chain</div>}
            {mode === "rainbow" && <div className="legend-row">blue N-terminus → red C-terminus</div>}
            {showSites && <div className="legend-row"><span className="swatch" style={{ background: "#f43f5e", borderRadius: 99 }} />UniProt binding/active site</div>}
            <div className="legend-row tiny muted">{coords.data.atoms.length} Cα · numbering: {coords.data.numbering}</div>
          </div></div>}
          {coords.data && <div className="canvas-corner"><span className="chip">drag to rotate · scroll to zoom · hover a residue</span></div>}
        </div>
      </div>
      <aside className="panel">
        <div className="panel-inner">
          <div>
            <h3 style={{ fontSize: 19 }}>{data.symbol}</h3>
            <div className="small muted">{data.protein_name} · <ExtLink href={`https://www.uniprot.org/uniprotkb/${data.accession}/entry`}>{data.accession}</ExtLink>
              {data.sequence_length ? ` · ${data.sequence_length} aa` : ""}</div>
          </div>
          <SourceStatus status={data.source_status} />
          <Section title={`Structures (${options.length}${data.experimental_total > data.experimental.length ? ` of ${data.experimental_total + (data.predicted ? 1 : 0)}` : ""})`}>
            <div className="stack" style={{ gap: 6 }}>
              {options.map((o, i) => (
                <motion.button key={o.kind + o.id} className={`struct-item ${i === pick ? "on" : ""}`} onClick={() => { setPick(i); setFocus(null); }} layout>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <b className="mono">{o.entry.id}</b>
                    <span className="badge" style={{ color: o.kind === "alphafold" ? "var(--ev-PRED)" : "var(--ev-EXP)" }}>{o.kind === "alphafold" ? "predicted" : "experimental"}</span>
                  </div>
                  <span className="tiny muted">{o.kind === "alphafold" ? `${o.entry.method} · mean pLDDT ${o.entry.mean_plddt}` :
                    `${o.entry.method}${o.entry.resolution ? ` · ${o.entry.resolution} Å` : ""} · ${o.entry.released}`}</span>
                  {o.entry.title && <span className="tiny" style={{ lineHeight: 1.35 }}>{o.entry.title}</span>}
                </motion.button>
              ))}
            </div>
          </Section>
          {cur && <div className="small"><ExtLink href={cur.entry.url}>Open {cur.entry.id} at {cur.entry.source}</ExtLink>
            {cur.entry.pmid && <> · <a href={`https://pubmed.ncbi.nlm.nih.gov/${cur.entry.pmid}/`} target="_blank" rel="noreferrer">PMID:{cur.entry.pmid}</a></>}</div>}
          {coords.data && !predicted && <div className="callout info tiny">{mapped} of {coords.data.atoms.length} residues map to UniProt {data.accession} via SIFTS
            ({coords.data.numbering}). Overlays use only mapped residues; other chains in the entry are drawn but not annotated.</div>}
          <Section title="Domains and regions" right={focus && <button className="btn ghost" style={{ height: 22 }} onClick={() => setFocus(null)}>clear</button>}>
            {domains.map((f, i) => (
              <button key={i} className={`feature-row ${focus === f ? "on" : ""}`} onClick={() => setFocus(focus === f ? null : f)}>
                <span className="swatch" style={{ background: domainColor(domains, i) }} />
                <span>{f.description || f.type} <span className="muted">{f.start}–{f.end}</span></span><Ev code={f.code as any} />
              </button>))}
            {!domains.length && <p className="small muted">No domain annotations.</p>}
            {otherRegions.map((f, i) => (
              <button key={`r${i}`} className={`feature-row ${focus === f ? "on" : ""}`} onClick={() => setFocus(focus === f ? null : f)}>
                <span className="swatch" style={{ background: "transparent", border: "1px dashed var(--text-3)" }} />
                <span className="small muted">{f.description} {f.start}–{f.end}</span><Ev code={f.code as any} />
              </button>))}
          </Section>
          {sites.length > 0 && <Section title={`Sites (${sites.length})`}>
            {sites.slice(0, 14).map((f, i) => (
              <button key={i} className={`feature-row ${focus === f ? "on" : ""}`} onClick={() => setFocus(focus === f ? null : f)}>
                <span className="swatch" style={{ background: "#f43f5e", borderRadius: 99 }} />
                <span>{f.type}: {f.ligand || f.description || "—"} <span className="muted">{f.start === f.end ? f.start : `${f.start}–${f.end}`}</span></span><Ev code={f.code as any} />
              </button>))}
          </Section>}
          {variants.length > 0 && <Section title={`Natural variants with descriptions (${variants.length})`}>
            {variants.slice(0, 10).map((f, i) => (
              <button key={i} className={`feature-row ${focus === f ? "on" : ""}`} onClick={() => setFocus(focus === f ? null : f)}>
                <span className="swatch" style={{ background: "#facc15", borderRadius: 99 }} />
                <span className="small">{f.original}{f.start}{f.alternatives.join("/")} <span className="muted">{f.description.slice(0, 70)}{f.description.length > 70 ? "…" : ""}</span></span><Ev code={f.code as any} />
              </button>))}
          </Section>}
          {data.pathways.length > 0 && <Section title="Pathways this protein participates in (Reactome)">
            <ul className="list">{data.pathways.slice(0, 8).map((p) => <li key={p.id}><a href={p.url} target="_blank" rel="noreferrer">{p.name}</a></li>)}</ul>
          </Section>}
          <ul className="list">{data.notes.map((n, i) => <li key={i} className="tiny muted">{n}</li>)}</ul>
        </div>
      </aside>
    </div>
  );
}
