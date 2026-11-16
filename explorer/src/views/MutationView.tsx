import { useCallback, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import type { Elements, MutationPayload } from "../types";
import NetworkCanvas, { type CanvasHandle, type Selection } from "../components/NetworkCanvas";
import { PlaybackBar, usePlayback } from "../components/Playback";
import InfoPanel from "../components/InfoPanel";
import Legend from "../components/Legend";
import { Cites, Ev, ErrorBox, ExtLink, Loading, Section, SourceStatus, StatementItem, Warnings } from "../components/ui";
import { useApi, usePrefersReducedMotion } from "../lib/hooks";
import { playbackPlan } from "../lib/graph";

/** Normal pathway on the left; the same graph with only documented variant changes on the right. */
export default function MutationView({ dark, onNavigate }: { dark: boolean; onNavigate?: (t: string) => void }) {
  const init = { gene: "KRAS", change: "G12D", pathway: "MAPK signaling", genes: "MAPK1" };
  const [params, setParams] = useState(init);
  const [form, setForm] = useState(init);
  const { data, error, loading } = useApi<MutationPayload>("compare_mutation", params);
  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100%", minHeight: 0 }}>
      <form className="toolbar" onSubmit={(e) => { e.preventDefault(); setParams({ ...form }); }}>
        <input className="input" style={{ width: 90 }} aria-label="Gene" value={form.gene} onChange={(e) => setForm({ ...form, gene: e.target.value })} />
        <input className="input" style={{ width: 110 }} aria-label="Protein change" placeholder="e.g. G12D" value={form.change} onChange={(e) => setForm({ ...form, change: e.target.value })} />
        <span className="muted small">in</span>
        <input className="input" style={{ width: 170 }} aria-label="Pathway" value={form.pathway} onChange={(e) => setForm({ ...form, pathway: e.target.value })} />
        <input className="input" style={{ width: 150 }} aria-label="Downstream focus genes" placeholder="downstream genes" value={form.genes} onChange={(e) => setForm({ ...form, genes: e.target.value })} />
        <button className="btn primary" type="submit">Compare</button>
      </form>
      <div style={{ position: "relative", minHeight: 0 }}>
        {loading && <Loading label="Comparing normal and variant records" />}
        {error != null && <div style={{ padding: 14 }}><ErrorBox error={error} /></div>}
        {data && !error && <Compare key={JSON.stringify(params)} data={data} dark={dark} onNavigate={onNavigate} />}
      </div>
    </div>
  );
}

function Compare({ data, dark, onNavigate }: { data: MutationPayload; dark: boolean; onNavigate?: (t: string) => void }) {
  const left = useRef<CanvasHandle>(null), right = useRef<CanvasHandle>(null);
  const reduced = usePrefersReducedMotion();
  const [sel, setSel] = useState<Selection>(null);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }> | undefined>();

  // Normal focus subgraph, plus any full-map edges a documented change touches (e.g. GAP ⊣ RAS).
  const elements: Elements = useMemo(() => {
    const base = data.normal.elements;
    const full = data.normal.full;
    if (!full) return base;
    const want = new Set(Object.keys(data.overlay.edges));
    const haveE = new Set(base.edges.map((e) => e.data.id));
    const extraE = full.edges.filter((e) => want.has(e.data.id) && !haveE.has(e.data.id));
    const haveN = new Set(base.nodes.map((n) => n.data.id));
    const ids = new Set(extraE.flatMap((e) => [e.data.source, e.data.target]).filter((x) => !haveN.has(x)));
    return { nodes: [...base.nodes, ...full.nodes.filter((n) => ids.has(n.data.id))], edges: [...base.edges, ...extraE] };
  }, [data]);

  const mutNodes = Object.keys(data.overlay.nodes);
  const sources = useMemo(() => {
    // play from the upstream end of the documented changes when there is one
    const gap = Object.keys(data.overlay.edges).map((id) => elements.edges.find((e) => e.data.id === id)?.data)
      .filter((e) => e && e.relation === "inhibition" && mutNodes.includes(e.target)).map((e) => e!.source);
    return gap.length ? [...new Set([...gap, ...mutNodes])].slice(0, 4) : mutNodes.slice(0, 1);
  }, [data, elements]); // eslint-disable-line react-hooks/exhaustive-deps

  const normalSteps = useMemo(() => playbackPlan(elements, sources), [elements, sources]);
  const mutantBlocked = useMemo(() => new Map(Object.entries(data.overlay.edges).filter(([, v]) => v.status.startsWith("impaired"))
    .map(([id, v]) => [id, `impaired in ${data.gene} p.${data.variant?.one_letter ?? data.change} (${v.events[0]?.name})`])), [data]);
  const mutantSteps = useMemo(() => playbackPlan(elements, sources, { blocked: mutantBlocked }), [elements, sources, mutantBlocked]);
  const pbL = usePlayback(useMemo(() => [left], []), normalSteps, sources, reduced);
  const pbR = usePlayback(useMemo(() => [right], []), mutantSteps, sources, reduced);
  const label = useMemo(() => new Map(elements.nodes.map((n) => [n.data.id, n.data.label])), [elements]);
  const labelOf = useCallback((id: string) => label.get(id) ?? id, [label]);

  const mutClasses = useMemo(() => {
    const nc: Record<string, string[]> = {}, ec: Record<string, string[]> = {};
    for (const id of data.downstream) nc[id] = ["mut-down"];
    for (const id of mutNodes) nc[id] = ["mut-node"];
    for (const [id, v] of Object.entries(data.overlay.edges)) ec[id] = [v.status.startsWith("impaired") ? "mut-impaired" : "mut-documented"];
    return { nc, ec };
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  const normalClasses = useMemo(() => Object.fromEntries(mutNodes.map((id) => [id, ["hit"]])), [mutNodes.join()]); // eslint-disable-line react-hooks/exhaustive-deps

  const playBoth = () => { void pbL.play(); void pbR.play(); };
  const replayBoth = () => { pbL.replay(); pbR.replay(); };
  const v = data.variant;
  const groups = new Map<string, typeof data.variant_statements>();
  for (const s of data.variant_statements) groups.set(s.section, [...(groups.get(s.section) ?? []), s]);

  return (
    <div className="workspace" style={{ height: "100%" }}>
      <div className="stage" style={{ gridTemplateRows: "1fr auto" }}>
        <div className="grid-2" style={{ gap: 0, minHeight: 0, gridTemplateRows: "1fr" }}>
          {[["Normal", left, undefined, normalClasses, {}], [`${data.gene} p.${v?.one_letter ?? data.change}`, right, positions, mutClasses.nc, mutClasses.ec]].map(([title, ref, pos, nc, ec], i) => (
            <div key={i} className="canvas-wrap" style={{ borderRight: i === 0 ? "1px solid var(--border)" : undefined, minHeight: 360 }}>
              <NetworkCanvas ref={ref as any} elements={elements} layout={i === 0 ? "dagre-tb" : positions ? "preset" : "dagre-tb"}
                positions={pos as any} dark={dark} selectedId={sel?.data.id ?? null} onSelect={setSel}
                nodeClasses={nc as any} edgeClasses={ec as any} traceMode="none"
                onReady={i === 0 ? (cy) => cy.one("layoutstop", () => setTimeout(() => setPositions(left.current?.positions()), 30)) : undefined} />
              <motion.div className="chip" style={{ position: "absolute", left: 12, top: 12, fontWeight: 650, color: i ? "var(--inh)" : "var(--act)" }}
                initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>{title as string}</motion.div>
              {i === 1 && <div className="canvas-overlay"><Legend kind="signalling" /></div>}
            </div>
          ))}
        </div>
        <div className="playback">
          <div className="row" style={{ gap: 6 }}>
            <button className="btn primary" onClick={playBoth} disabled={pbL.playing}>▶ Play both</button>
            <button className="btn" onClick={replayBoth}>↺ Replay</button>
          </div>
          <div style={{ flex: 1, minWidth: 280 }}>
            <PlaybackBar pb={pbR} steps={mutantSteps} labelOf={labelOf} reduced={reduced} sourceLabel={sources.map(labelOf).join(", ")} />
          </div>
        </div>
      </div>
      <aside className="panel">
        <div className="panel-inner">
          {sel ? <>
            <button className="btn ghost" style={{ alignSelf: "flex-start" }} onClick={() => setSel(null)}>← Variant summary</button>
            <InfoPanel sel={sel} labelOf={labelOf} onNavigate={onNavigate} />
          </> : <>
            <div>
              <h3 style={{ fontSize: 19 }}>{data.gene} {v?.hgvs_p ?? data.change}</h3>
              {v && <div className="small muted">{v.kind} at residue {v.start}{v.end !== v.start ? `–${v.end}` : ""}</div>}
            </div>
            <Section title="Sources queried"><SourceStatus status={data.source_status} /></Section>
            <Warnings items={data.warnings} />
            {Object.values(data.overlay.nodes).map((n, i) => (n as any).box_note ? <div key={i} className="callout info tiny">{(n as any).box_note}</div> : null)}
            <Section title={`Reactome disease events for this variant (${data.changes.length})`}>
              {data.changes.length === 0 ? <p className="small muted" style={{ margin: 0 }}>None curated for this exact variant. The right panel only marks the gene; no change is assumed.</p> :
                <div className="stack">{data.changes.map((c) => (
                  <div key={c.event} className="statement">
                    <div className="row" style={{ gap: 6, alignItems: "flex-start" }}>
                      <Ev code={c.code} />
                      <span className="chip" style={{ color: c.status.startsWith("impaired") ? "var(--inh)" : "var(--text-3)" }}>{c.status}</span>
                    </div>
                    <div style={{ marginTop: 6, fontWeight: 600 }}><ExtLink href={c.url}>{c.name}</ExtLink></div>
                    {c.normal && <div className="tiny muted">Normal counterpart: <a href={c.normal.url} target="_blank" rel="noreferrer">{c.normal.name}</a></div>}
                    <div className="tiny" style={{ marginTop: 4 }}>{c.status.startsWith("impaired") ? (c.edges.length ? `Drawn on ${c.edges.length} relation${c.edges.length > 1 ? "s" : ""} (✕ impaired)` : "No drawn relation between participants; shown on the variant node") : "Context only: not drawn as a change"}</div>
                    {c.pmids.length > 0 && <div style={{ marginTop: 6 }}><Cites items={c.pmids.map((p) => ({ source: "PubMed", id: p, url: `https://pubmed.ncbi.nlm.nih.gov/${p}/` }))} max={4} /></div>}
                  </div>))}</div>}
            </Section>
            {[...groups.entries()].map(([sec, items]) => (
              <Section key={sec} title={sec}><div className="stack">{items.slice(0, 5).map((s, i) => <StatementItem key={i} s={s} />)}</div></Section>
            ))}
            <Section title={`Graph-downstream of the variant (${data.downstream.length})`}>
              <div className="row wrap" style={{ gap: 6 }}>{data.downstream.slice(0, 24).map((id) => <span key={id} className="chip">{labelOf(id)}</span>)}</div>
            </Section>
            <ul className="list">{data.notes.map((n, i) => <li key={i} className="tiny muted">{n}</li>)}</ul>
          </>}
        </div>
      </aside>
    </div>
  );
}
