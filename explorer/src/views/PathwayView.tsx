import { useCallback, useMemo, useRef, useState } from "react";
import type { Elements, GraphPayload } from "../types";
import NetworkCanvas, { type CanvasHandle, type LayoutName, type Selection } from "../components/NetworkCanvas";
import { PlaybackBar, usePlayback } from "../components/Playback";
import InfoPanel from "../components/InfoPanel";
import EvidencePanel from "../components/EvidencePanel";
import Legend from "../components/Legend";
import { ErrorBox, Loading, Section } from "../components/ui";
import { IconDownload, IconExpand, IconFit, IconScissors, IconSearch, IconUndo } from "../components/Icons";
import { useApi, usePrefersReducedMotion } from "../lib/hooks";
import { CODES } from "../lib/evidence";
import { defaultSources, neighbourExpansion, perturb, playbackPlan, searchNodes } from "../lib/graph";
import { motion } from "motion/react";

export interface Field { key: string; label: string; placeholder: string; width?: number }

interface Props {
  op: string; params: Record<string, string>; fields: Field[]; dark: boolean;
  layout?: LayoutName; legend?: "signalling" | "metabolic" | "network" | "hierarchy";
  allowPerturb?: boolean; allowPlayback?: boolean; onNavigate?: (t: string) => void;
  presets?: { label: string; params: Record<string, string> }[];
}

const REL_GROUPS: Record<string, string[]> = {
  activation: ["activation"], inhibition: ["inhibition", "repression"], expression: ["expression"],
  "binding/association": ["binding", "association", "dissociation"], other: [],
};

export default function PathwayView(p: Props) {
  const [params, setParams] = useState(p.params);
  const [form, setForm] = useState(p.params);
  const { data, error, loading } = useApi<GraphPayload>(p.op, params);
  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100%", minHeight: 0 }}>
        <div className="toolbar">
          <form className="row wrap" style={{ gap: 8 }} onSubmit={(e) => { e.preventDefault(); setParams({ ...form }); }}>
            {p.fields.map((f) => (
              <input key={f.key} className="input" style={{ width: f.width ?? 170 }} placeholder={f.placeholder} aria-label={f.label}
                value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
            ))}
            <button className="btn primary" type="submit">Map</button>
          </form>
          {p.presets && <select className="input" style={{ width: 170 }} value="" aria-label="Examples"
            onChange={(e) => { const pr = p.presets![+e.target.value]; if (pr) { setForm(pr.params); setParams(pr.params); } }}>
            <option value="">Examples…</option>
            {p.presets.map((pr, i) => <option key={pr.label} value={i}>{pr.label}</option>)}
          </select>}
        </div>
        <div style={{ position: "relative", minHeight: 0 }}>
          {error != null && <div style={{ padding: 14 }}><ErrorBox error={error} /></div>}
          {loading && <Loading />}
          {data && !error && <GraphStage key={JSON.stringify(params)} data={data} {...p} />}
        </div>
    </div>
  );
}

function GraphStage({ data, dark, layout: layoutInit = "dagre-lr", legend = "signalling", allowPerturb = true,
  allowPlayback = true, onNavigate }: Props & { data: GraphPayload }) {
  const canvas = useRef<CanvasHandle>(null);
  const canvases = useMemo(() => [canvas], []);
  const reduced = usePrefersReducedMotion();
  const [base] = useState<Elements>(() => data.elements);
  const [shown, setShown] = useState<Elements>(() => data.elements);
  const [layout, setLayout] = useState<LayoutName>(layoutInit);
  const [sel, setSel] = useState<Selection>(null);
  const [query, setQuery] = useState("");
  const [trace, setTrace] = useState<"both" | "upstream" | "downstream" | "none">("both");
  const [codes, setCodes] = useState<Set<string>>(new Set(CODES));
  const [rels, setRels] = useState<Set<string>>(new Set(Object.keys(REL_GROUPS)));
  const [tab, setTab] = useState<"details" | "evidence" | "perturb">("details");
  const [sources, setSources] = useState<string[]>(() => defaultSources(data.elements, data.focus));
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [cut, setCut] = useState<Set<string>>(new Set());
  const [showModified, setShowModified] = useState(true);

  const label = useMemo(() => new Map(shown.nodes.map((n) => [n.data.id, n.data.label])), [shown]);
  const labelOf = useCallback((id: string) => label.get(id) ?? id, [label]);
  const hits = useMemo(() => searchNodes(shown.nodes, query), [shown, query]);

  const hidden = useMemo(() => {
    const h = new Set<string>();
    const relOf = (r: string) => Object.entries(REL_GROUPS).find(([, v]) => v.includes(r))?.[0] ?? "other";
    for (const { data: e } of shown.edges) if (!codes.has(e.evidenceCode) || !rels.has(relOf(e.relation))) h.add(e.id);
    const visibleNodes = new Set(shown.edges.filter((e) => !h.has(e.data.id)).flatMap((e) => [e.data.source, e.data.target]));
    for (const n of shown.nodes) if (!visibleNodes.has(n.data.id) && !n.data.focus && shown.edges.length) h.add(n.data.id);
    return h;
  }, [shown, codes, rels]);

  const perturbing = removed.size > 0 || cut.size > 0;
  const blocked = useMemo(() => new Map([...cut].map((id) => [id, "inhibited by you"])), [cut]);
  const steps = useMemo(() => allowPlayback ? playbackPlan(shown, sources, { blocked, removed }) : [], [shown, sources, blocked, removed, allowPlayback]);
  const pb = usePlayback(canvases, steps, sources, reduced);
  const pert = useMemo(() => perturbing ? perturb(shown, sources, removed, cut) : null, [shown, sources, removed, cut, perturbing]);

  const { nodeClasses, edgeClasses } = useMemo(() => {
    const nc: Record<string, string[]> = {}, ec: Record<string, string[]> = {};
    if (pert && showModified) {
      for (const id of removed) nc[id] = ["pt-removed"];
      for (const id of cut) ec[id] = ["pt-cut"];
      const lost = new Set(pert.unreachable.map((u) => u.node));
      for (const id of lost) nc[id] = [...(nc[id] ?? []), "pt-lost"];
      for (const e of shown.edges) if (lost.has(e.data.target) && !cut.has(e.data.id)) ec[e.data.id] = ["pt-lost"];
      for (const r of pert.rerouted) for (let i = 0; i + 1 < r.alternative.length; i++) {
        const e = shown.edges.find((x) => x.data.source === r.alternative[i] && x.data.target === r.alternative[i + 1]);
        if (e) ec[e.data.id] = ["pt-reroute"];
      }
    }
    return { nodeClasses: nc, edgeClasses: ec };
  }, [pert, removed, cut, shown, showModified]);

  const expand = () => {
    if (sel?.type !== "node") return;
    const add = neighbourExpansion(shown, data.full, sel.data.id);
    if (!add.nodes.length && !add.edges.length) return;
    canvas.current?.add(add, sel.data.id);
    setShown((s) => ({ nodes: [...s.nodes, ...add.nodes], edges: [...s.edges, ...add.edges] }));
  };
  const toggle = (set: Set<string>, v: string, fn: (s: Set<string>) => void) => { const n = new Set(set); n.has(v) ? n.delete(v) : n.add(v); fn(n); };
  const expandable = sel?.type === "node" && data.full ? neighbourExpansion(shown, data.full, sel.data.id).edges.length : 0;
  const fileName = `biopathway-${data.kind}-${(data.full?.pathway ?? data.query).replace(/[^a-z0-9]+/gi, "-").slice(0, 40)}`;

  return (
    <>
      <div className="workspace" style={{ height: "100%", minHeight: 0 }}>
        <div className="stage" style={{ gridTemplateRows: "auto 1fr auto" }}>
          <div className="toolbar" style={{ borderTop: 0 }}>
            <div className="row" style={{ gap: 6 }}>
              <IconSearch size={15} />
              <input className="input" style={{ width: 150 }} placeholder="Find node…" value={query} onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && hits.length) canvas.current?.fit(hits); }} aria-label="Search nodes" />
              {query && <span className="tiny muted">{hits.length} hit{hits.length === 1 ? "" : "s"}</span>}
            </div>
            <div className="divider-v" />
            <div className="seg" role="group" aria-label="Evidence filter">
              {CODES.map((c) => <button key={c} className={codes.has(c) ? "on" : ""} style={{ color: codes.has(c) ? `var(--ev-${c})` : undefined }}
                onClick={() => toggle(codes, c, setCodes)} title={`Show ${c} relations`}>{c}</button>)}
            </div>
            {legend === "signalling" && <select className="input" style={{ width: 132 }} aria-label="Relation filter" value=""
              onChange={(e) => e.target.value && toggle(rels, e.target.value, setRels)}>
              <option value="">Relations ({rels.size}/{Object.keys(REL_GROUPS).length})</option>
              {Object.keys(REL_GROUPS).map((r) => <option key={r} value={r}>{rels.has(r) ? "✓ " : "  "}{r}</option>)}
            </select>}
            <div className="seg" role="group" aria-label="Trace on select">
              {(["both", "upstream", "downstream", "none"] as const).map((m) => <button key={m} className={trace === m ? "on" : ""} onClick={() => setTrace(m)}>
                {m === "both" ? "Up+down" : m === "none" ? "No trace" : m[0].toUpperCase() + m.slice(1)}</button>)}
            </div>
            <div className="seg" role="group" aria-label="Layout">
              {(["dagre-lr", "dagre-tb", "fcose"] as LayoutName[]).map((l) => <button key={l} className={layout === l ? "on" : ""} onClick={() => setLayout(l)}>
                {l === "dagre-lr" ? "→" : l === "dagre-tb" ? "↓" : "Force"}</button>)}
            </div>
            <div className="spacer" />
            {data.full && <button className="btn" disabled={!expandable} onClick={expand} title="Add this node's other relations from the full KEGG map">
              <IconExpand /> Expand{expandable ? ` (${expandable})` : ""}</button>}
            <button className="btn" onClick={() => canvas.current?.exportSvg(fileName)} title="Export SVG"><IconDownload /> SVG</button>
            <button className="btn" onClick={() => canvas.current?.exportPng(fileName)} title="Export PNG"><IconDownload /> PNG</button>
          </div>
          <div className="canvas-wrap">
            <NetworkCanvas ref={canvas} elements={base} layout={layout} dark={dark} selectedId={sel?.data.id ?? null}
              onSelect={setSel} nodeClasses={nodeClasses} edgeClasses={edgeClasses} hidden={hidden} highlight={hits} traceMode={trace} />
            <div className="canvas-overlay"><Legend kind={legend} /></div>
            <div className="canvas-corner">
              <button className="icon-btn" onClick={() => canvas.current?.fit()} title="Fit to view" aria-label="Fit to view"><IconFit /></button>
            </div>
            {data.full && <div style={{ position: "absolute", left: 14, top: 12 }} className="chip">
              KEGG {data.full.pathway} · {data.full.title} · showing {shown.edges.length} of {data.full.edges.length} relations</div>}
          </div>
          {allowPlayback && steps.length > 0 && <div className="playback">
            <div style={{ flex: 1 }}>
              <PlaybackBar pb={pb} steps={steps} labelOf={labelOf} reduced={reduced}
                sourceLabel={sources.map(labelOf).join(", ")}
                onPickSource={sel?.type === "node" ? () => setSources([sel.data.id]) : undefined} />
            </div>
          </div>}
        </div>
        <aside className="panel">
          <div className="panel-inner">
            <div className="seg" role="tablist">
              <button className={tab === "details" ? "on" : ""} onClick={() => setTab("details")}>Details</button>
              <button className={tab === "evidence" ? "on" : ""} onClick={() => setTab("evidence")}>Evidence</button>
              {allowPerturb && <button className={tab === "perturb" ? "on" : ""} onClick={() => setTab("perturb")}>
                Perturb{perturbing ? ` (${removed.size + cut.size})` : ""}</button>}
            </div>
            {tab === "details" && <InfoPanel sel={sel} labelOf={labelOf} onNavigate={onNavigate} empty={
              <div className="stack small muted">
                <p style={{ margin: 0 }}>Click a gene, protein, compound or arrow to see its records. Selecting a node traces everything upstream (cyan) and downstream (green) of it.</p>
                {allowPlayback && <p style={{ margin: 0 }}>Press <b>Play signal</b> to step through the documented relations from <b>{sources.map(labelOf).join(", ")}</b>.</p>}
              </div>} />}
            {tab === "evidence" && <EvidencePanel data={data} />}
            {tab === "perturb" && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="stack" style={{ gap: 14 }}>
                <div className="callout info">Remove a node or inhibit a relation, then see which nodes lose the source's influence and which signals find another route. Playback shows the signal stopping at the change.</div>
                <div className="row wrap" style={{ gap: 6 }}>
                  <button className="btn" disabled={sel?.type !== "node"} onClick={() => sel?.type === "node" && toggle(removed, sel.data.id, setRemoved)}>
                    <IconScissors /> {sel?.type === "node" && removed.has(sel.data.id) ? "Restore node" : "Remove node"}</button>
                  <button className="btn" disabled={sel?.type !== "edge"} onClick={() => sel?.type === "edge" && toggle(cut, sel.data.id, setCut)}>
                    ⊣ {sel?.type === "edge" && cut.has(sel.data.id) ? "Restore relation" : "Inhibit relation"}</button>
                  <button className="btn ghost" disabled={!perturbing} onClick={() => { setRemoved(new Set()); setCut(new Set()); }}><IconUndo /> Reset</button>
                </div>
                <div className="small">Source: <b>{sources.map(labelOf).join(", ")}</b>{sel?.type === "node" && <> · <button className="btn ghost" style={{ height: 22, padding: "0 4px" }} onClick={() => setSources([sel.data.id])}>use selected</button></>}</div>
                {pert && <>
                  <div className="row" style={{ gap: 6 }}>
                    <div className="seg"><button className={!showModified ? "on" : ""} onClick={() => setShowModified(false)}>Original</button>
                      <button className={showModified ? "on" : ""} onClick={() => setShowModified(true)}>Modified</button></div>
                  </div>
                  <div className="grid-2">
                    <div className="card card-pad" style={{ padding: 12 }}><div className="tiny muted">Reachable before</div><div style={{ fontSize: 22, fontWeight: 700 }}>{pert.before.size}</div></div>
                    <div className="card card-pad" style={{ padding: 12 }}><div className="tiny muted">Reachable after</div><div style={{ fontSize: 22, fontWeight: 700, color: pert.after.size < pert.before.size ? "var(--inh)" : undefined }}>{pert.after.size}</div></div>
                  </div>
                  <Section title={`Lose the source's influence (${pert.unreachable.length})`}>
                    {pert.unreachable.length ? <ul className="list">{pert.unreachable.map((u) => (
                      <li key={u.node} className="row" style={{ gap: 6 }}>
                        <span className="chip" style={{ color: u.netSign === "+" ? "var(--act)" : u.netSign === "-" ? "var(--inh)" : undefined }}
                          title="Net sign of the lost route (product of relation signs)">{u.netSign === "+" ? "net +" : u.netSign === "-" ? "net −" : "sign ?"}</span>
                        <b>{labelOf(u.node)}</b></li>))}</ul> : <p className="small muted" style={{ margin: 0 }}>Every node is still reachable.</p>}
                  </Section>
                  {pert.rerouted.length > 0 && <Section title={`Alternative routes (${pert.rerouted.length})`}>
                    <ul className="list">{pert.rerouted.slice(0, 8).map((r) => (
                      <li key={r.target} className="small"><b>{labelOf(r.target)}</b>: {r.alternative.map(labelOf).join(" → ")}
                        <div className="tiny muted">was {r.original.map(labelOf).join(" → ")}</div></li>))}</ul></Section>}
                  <div className="callout warn"><b>Computational hypothesis.</b> "Losing influence" means the source no longer reaches the node along drawn relations; it does not mean the node switches off. Removing an inhibitor (net −) would usually relieve inhibition. Compensation, unmapped routes, dosage and kinetics are not modelled.</div>
                </>}
              </motion.div>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
