import cytoscape from "cytoscape";
import type { Core, NodeSingular } from "cytoscape";
import dagre from "cytoscape-dagre";
import fcose from "cytoscape-fcose";
import svg from "cytoscape-svg";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { EdgeData, Elements, NodeData } from "../types";
import type { Step } from "../lib/graph";
import { stateAt } from "../lib/graph";

cytoscape.use(dagre);
cytoscape.use(fcose);
cytoscape.use(svg);

export type Selection = { type: "node"; data: NodeData } | { type: "edge"; data: EdgeData } | null;
export type LayoutName = "dagre-lr" | "dagre-tb" | "fcose" | "preset";

export interface CanvasHandle {
  cy: () => Core | null;
  fit: (ids?: string[]) => void;
  exportPng: (name: string) => void;
  exportSvg: (name: string) => void;
  add: (els: Elements, originId?: string) => void;
  relayout: () => void;
  positions: () => Record<string, { x: number; y: number }>;
  animateStep: (step: Step, ms: number, reduced: boolean) => Promise<void>;
  showState: (steps: Step[], upto: number, sources: string[]) => void;
  clearPlayback: () => void;
}

interface Props {
  elements: Elements;
  layout?: LayoutName;
  positions?: Record<string, { x: number; y: number }>;
  dark: boolean;
  selectedId?: string | null;
  onSelect?: (s: Selection) => void;
  nodeClasses?: Record<string, string[]>;
  edgeClasses?: Record<string, string[]>;
  hidden?: Set<string>;
  highlight?: string[];
  traceMode?: "both" | "upstream" | "downstream" | "none";
  onReady?: (cy: Core) => void;
}

export function shortLabel(d: NodeData): string {
  const members = d.members ?? [];
  if ((d.kind === "gene") && members.length > 1) {
    const first = d.label.split(/[/ ]/)[0];
    return `${first} +${members.length - 1}`;
  }
  return d.label.length > 34 ? d.label.slice(0, 32) + "…" : d.label;
}

function edgeLabel(d: EdgeData): string {
  const parts: string[] = [];
  if (d.phospho) parts.push("+p");
  if (d.modifiers?.includes("-p")) parts.push("−p");
  if (d.suspect) parts.push("⚠ direction?");
  if (d.relation === "conversion") parts.push(d.modifiers.filter((m) => m !== "reversible")[0] ?? "");
  return parts.filter(Boolean).join(" ");
}

function toCy(els: Elements) {
  return [
    ...els.nodes.map((n) => ({ group: "nodes" as const, data: { ...n.data, short: shortLabel(n.data) } })),
    ...els.edges.map((e) => ({ group: "edges" as const, data: { ...e.data, elabel: edgeLabel(e.data) } })),
  ];
}

const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";

function stylesheet(): any[] {
  const c = (n: string) => cssVar(n);
  const ev = (code: string) => c(`--ev-${code}`);
  return [
    { selector: "node", style: {
      label: "data(short)", "font-family": "Inter Variable, sans-serif", "font-size": 11, "font-weight": 600,
      color: c("--text"), "text-valign": "center", "text-halign": "center", "text-wrap": "wrap", "text-max-width": 120,
      "background-color": c("--panel"), "border-width": 1.5, "border-color": c("--border-2"), shape: "round-rectangle",
      width: "label", height: 28, padding: "8px", "transition-property": "background-color, border-color, opacity, border-width",
      "transition-duration": 250, "overlay-padding": 6, "underlay-padding": 0 } },
    { selector: "node[kind = 'complex']", style: { shape: "cut-rectangle", "border-style": "double", "border-width": 3 } },
    { selector: "node[kind = 'compound']", style: { shape: "ellipse", "background-color": c("--act-soft"), "border-color": c("--act"),
      "font-weight": 500, "font-size": 10.5, height: 26, "text-max-width": 140 } },
    { selector: "node[kind = 'pathway']", style: { shape: "round-hexagon", "background-color": c("--accent-soft"), "border-color": c("--accent"),
      "font-weight": 500, "text-max-width": 150, height: 34 } },
    { selector: "node[kind = 'variant']", style: { shape: "tag", "background-color": c("--inh-soft"), "border-color": c("--inh"), "border-width": 2.5 } },
    { selector: "node[kind = 'condition']", style: { shape: "rhomboid", "background-color": c("--panel-2"), "border-color": c("--ev-LIT") } },
    { selector: "node[kind = 'region']", style: { shape: "round-tag", "border-style": "dashed" } },
    { selector: "node[?focus]", style: { "border-color": "#d4a017", "border-width": 3, "background-color": c("--panel") } },
    { selector: "edge", style: {
      width: 2, "curve-style": "bezier", "line-color": ev("CUR"), "target-arrow-color": ev("CUR"),
      "target-arrow-shape": "triangle", "arrow-scale": 1.05, opacity: 0.9, label: "data(elabel)",
      "font-family": "JetBrains Mono Variable, monospace", "font-size": 9, color: c("--text-2"),
      "text-background-color": c("--canvas"), "text-background-opacity": 0.9, "text-background-padding": "2px",
      "text-rotation": "autorotate", "transition-property": "line-color, target-arrow-color, width, opacity",
      "transition-duration": 250 } },
    ...["EXP", "CUR", "PRED", "LIT", "HYP"].map((code) => ({ selector: `edge[evidenceCode = '${code}']`,
      style: { "line-color": ev(code), "target-arrow-color": ev(code) } })),
    { selector: "edge[relation = 'inhibition']", style: { "target-arrow-shape": "tee", "arrow-scale": 1.3 } },
    { selector: "edge[!directed]", style: { "target-arrow-shape": "none" } },
    { selector: "edge[?indirect], edge[relation = 'expression'], edge[evidenceCode = 'PRED'], edge[evidenceCode = 'LIT'], edge[evidenceCode = 'HYP']",
      style: { "line-style": "dashed", "line-dash-pattern": [6, 4] } },
    { selector: "edge[relation = 'expression']", style: { "target-arrow-shape": "triangle-backcurve" } },
    { selector: "edge[?suspect]", style: { "line-color": c("--warn"), "target-arrow-color": c("--warn"), color: c("--warn") } },
    // selection / tracing
    { selector: ".faded", style: { opacity: 0.13 } },
    { selector: "node.up", style: { "border-color": c("--accent-2"), "border-width": 2.5 } },
    { selector: "node.down", style: { "border-color": c("--act"), "border-width": 2.5 } },
    { selector: "edge.trace", style: { width: 3, opacity: 1 } },
    { selector: "node:selected", style: { "border-color": c("--accent"), "border-width": 3.5, "overlay-color": c("--accent"), "overlay-opacity": 0.08 } },
    { selector: "edge:selected", style: { width: 4, "overlay-color": c("--accent"), "overlay-opacity": 0.12 } },
    { selector: "node.hit", style: { "border-color": c("--warn"), "border-width": 3.5, "underlay-color": c("--warn"), "underlay-opacity": 0.18, "underlay-padding": 7 } },
    { selector: ".hidden", style: { display: "none" } },
    // playback
    { selector: ".pb-dim", style: { opacity: 0.28 } },
    { selector: "node.pb-source", style: { "border-color": c("--accent"), "border-width": 4, "underlay-color": c("--accent"), "underlay-opacity": 0.22, "underlay-padding": 8 } },
    { selector: "node.pb-pos", style: { "background-color": c("--act-soft"), "border-color": c("--act"), "border-width": 3 } },
    { selector: "node.pb-neg", style: { "background-color": c("--inh-soft"), "border-color": c("--inh"), "border-width": 3 } },
    { selector: "node.pb-unk", style: { "background-color": c("--accent-soft"), "border-color": c("--accent"), "border-width": 3 } },
    { selector: "node.pb-flash-act", style: { "underlay-color": c("--act"), "underlay-opacity": 0.35, "underlay-padding": 12 } },
    { selector: "node.pb-flash-inh", style: { "underlay-color": c("--inh"), "underlay-opacity": 0.35, "underlay-padding": 12 } },
    { selector: "edge.pb-active", style: { width: 5, opacity: 1, "z-index": 20 } },
    { selector: "edge.pb-done", style: { opacity: 1, width: 3 } },
    { selector: "edge.pb-blocked", style: { "line-color": c("--text-3"), "target-arrow-color": c("--text-3"), "line-style": "dotted", opacity: 0.8 } },
    { selector: "node.pulse", style: { width: 14, height: 14, shape: "ellipse", "border-width": 0, label: "data(plabel)", "font-size": 9,
      "font-weight": 800, color: "#fff", "z-index": 99, events: "no", "background-color": c("--act"),
      "underlay-color": c("--act"), "underlay-opacity": 0.35, "underlay-padding": 6, "transition-duration": 0 } },
    { selector: "node.pulse-inhibit", style: { shape: "round-rectangle", width: 16, height: 8, "background-color": c("--inh"), "underlay-color": c("--inh") } },
    { selector: "node.pulse-express", style: { shape: "diamond", "background-color": c("--accent-2"), "underlay-color": c("--accent-2") } },
    { selector: "node.pulse-bind, node.pulse-link, node.pulse-modify", style: { "background-color": c("--accent"), "underlay-color": c("--accent") } },
    { selector: "node.pulse-convert", style: { "background-color": c("--act"), shape: "hexagon", width: 15, height: 15 } },
    { selector: "node.pulse-phospho", style: { "background-color": c("--phos"), "underlay-color": c("--phos"), width: 17, height: 17 } },
    { selector: "node.pulse-blocked", style: { "background-color": c("--text-3"), "underlay-opacity": 0, label: "✕", "font-size": 11 } },
    { selector: "node.phos-badge", style: { width: 18, height: 18, shape: "ellipse", label: "P", "font-size": 10, "font-weight": 800,
      color: "#fff", "background-color": c("--phos"), "border-width": 2, "border-color": c("--canvas"), events: "no", "z-index": 98 } },
    // perturbation
    { selector: "node.pt-removed", style: { opacity: 0.35, "border-style": "dashed", "border-color": c("--inh"), "background-color": c("--inh-soft") } },
    { selector: "edge.pt-cut", style: { "line-color": c("--inh"), "target-arrow-color": c("--inh"), "line-style": "dashed", width: 3,
      label: "✕ inhibited", color: c("--inh") } },
    { selector: "node.pt-lost", style: { "border-color": c("--inh"), "border-style": "dashed", "border-width": 3, "background-color": c("--inh-soft") } },
    { selector: "edge.pt-lost", style: { opacity: 0.2 } },
    { selector: "edge.pt-reroute", style: { "line-color": c("--accent-2"), "target-arrow-color": c("--accent-2"), width: 4, opacity: 1, "z-index": 10 } },
    // mutation overlay
    { selector: "node.mut-node", style: { "border-color": c("--inh"), "border-width": 4, "background-color": c("--inh-soft"),
      "underlay-color": c("--inh"), "underlay-opacity": 0.16, "underlay-padding": 8 } },
    { selector: "edge.mut-impaired", style: { "line-color": c("--inh"), "target-arrow-color": c("--inh"), "line-style": "dashed",
      "line-dash-pattern": [3, 4], width: 3, label: "✕ impaired in mutant", color: c("--inh"), opacity: 1 } },
    { selector: "edge.mut-documented", style: { "line-color": c("--warn"), "target-arrow-color": c("--warn"), width: 4, opacity: 1 } },
    { selector: "node.mut-down", style: { "border-color": c("--warn"), "border-width": 2.5 } },
  ];
}

function layoutOptions(name: LayoutName, animate: boolean, positions?: Record<string, { x: number; y: number }>): any {
  if (name === "preset") return { name: "preset", positions: (n: NodeSingular) => positions?.[n.id()], fit: true, padding: 40, animate };
  if (name === "fcose") return { name: "fcose", animate, animationDuration: 600, randomize: true, nodeRepulsion: 9000,
    idealEdgeLength: 110, padding: 40, quality: "proof" };
  return { name: "dagre", rankDir: name === "dagre-tb" ? "TB" : "LR", nodeSep: 26, rankSep: 70, edgeSep: 12,
    animate, animationDuration: 600, animationEasing: "ease-out-cubic", padding: 40, fit: true };
}

function download(blob: Blob, name: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const NetworkCanvas = forwardRef<CanvasHandle, Props>(function NetworkCanvas(props, ref) {
  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const extra = useRef<string[]>([]);
  const { elements, layout = "dagre-lr", positions, dark } = props;

  // build once per dataset
  useEffect(() => {
    if (!box.current) return;
    const cy = cytoscape({ container: box.current, elements: toCy(elements), style: stylesheet(),
      layout: layoutOptions(layout, false, positions), wheelSensitivity: 0.25, minZoom: 0.15, maxZoom: 3.5,
      boxSelectionEnabled: false });
    cyRef.current = cy;
    // Fit once the container has its real size, and keep small graphs from being blown up.
    const capZoom = () => { if (cy.zoom() > 1.45) { cy.zoom(1.45); cy.center(); } };
    // Re-fit whenever the container resizes, until the user pans or zooms themselves.
    let userMoved = false;
    const el = box.current;
    const mark = () => { userMoved = true; };
    el.addEventListener("wheel", mark, { passive: true });
    cy.on("tapdrag", (e) => { if (e.target === cy) userMoved = true; });
    const refit = () => { if (!userMoved && el.clientHeight >= 50 && cy.nodes().length) { cy.resize(); cy.fit(undefined, 48); capZoom(); } };
    const ro = new ResizeObserver(() => { cy.resize(); refit(); });
    ro.observe(el);
    cy.one("layoutstop", refit);
    cy.on("tap", "node", (e) => { if (!e.target.hasClass("pulse")) props.onSelect?.({ type: "node", data: e.target.data() }); });
    cy.on("tap", "edge", (e) => props.onSelect?.({ type: "edge", data: e.target.data() }));
    cy.on("tap", (e) => { if (e.target === cy) props.onSelect?.(null); });
    props.onReady?.(cy);
    return () => { ro.disconnect(); cy.destroy(); cyRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elements, layout, positions]);

  useEffect(() => { cyRef.current?.style(stylesheet()); }, [dark]);

  // selection tracing
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("faded up down trace");
      cy.elements().unselect();
      const id = props.selectedId;
      if (!id) return;
      const ele = cy.getElementById(id);
      if (!ele.length) return;
      ele.select();
      if (!ele.isNode() || props.traceMode === "none") return;
      const mode = props.traceMode ?? "both";
      const up = mode !== "downstream" ? ele.predecessors() : cy.collection();
      const down = mode !== "upstream" ? ele.successors() : cy.collection();
      cy.elements().not(up.union(down).union(ele)).addClass("faded");
      up.nodes().addClass("up"); down.nodes().addClass("down");
      up.edges().union(down.edges()).addClass("trace");
    });
  }, [props.selectedId, props.traceMode, elements]);

  // external classes, hidden set, search hits
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("hidden hit pt-removed pt-cut pt-lost pt-reroute mut-node mut-impaired mut-documented mut-down");
      for (const [id, cls] of Object.entries(props.nodeClasses ?? {})) cy.getElementById(id).addClass(cls.join(" "));
      for (const [id, cls] of Object.entries(props.edgeClasses ?? {})) cy.getElementById(id).addClass(cls.join(" "));
      for (const id of props.hidden ?? []) cy.getElementById(id).addClass("hidden");
      for (const id of props.highlight ?? []) cy.getElementById(id).addClass("hit");
    });
  }, [props.nodeClasses, props.edgeClasses, props.hidden, props.highlight, elements]);

  useImperativeHandle(ref, () => ({
    cy: () => cyRef.current,
    fit: (ids) => {
      const cy = cyRef.current;
      if (!cy) return;
      const target = ids?.length ? ids.reduce((acc, i) => acc.union(cy.getElementById(i)), cy.collection()) : cy.elements(":visible");
      cy.animate({ fit: { eles: target, padding: ids?.length ? 120 : 40 } }, { duration: 500, easing: "ease-in-out-cubic" });
    },
    exportPng: (name) => {
      const cy = cyRef.current;
      if (cy) download(cy.png({ output: "blob", full: true, scale: 2, bg: cssVar("--canvas") }) as Blob, `${name}.png`);
    },
    exportSvg: (name) => {
      const cy = cyRef.current as any;
      if (cy) download(new Blob([cy.svg({ full: true, scale: 1, bg: cssVar("--canvas") })], { type: "image/svg+xml" }), `${name}.svg`);
    },
    add: (els, originId) => {
      const cy = cyRef.current;
      if (!cy || (!els.nodes.length && !els.edges.length)) return;
      const origin = originId ? cy.getElementById(originId).position() : undefined;
      const added = cy.add(toCy(els).map((e) => e.group === "nodes" && origin ? { ...e, position: { ...origin } } : e));
      added.nodes().style("opacity", 0);
      cy.layout({ ...layoutOptions(layout === "preset" ? "dagre-lr" : layout, true), randomize: false }).run();
      added.nodes().animate({ style: { opacity: 1 } }, { duration: 600 });
    },
    relayout: () => cyRef.current?.layout(layoutOptions(layout === "preset" ? "dagre-lr" : layout, true)).run(),
    positions: () => {
      const out: Record<string, { x: number; y: number }> = {};
      cyRef.current?.nodes().forEach((n) => { out[n.id()] = { ...n.position() }; });
      return out;
    },
    animateStep: (step, ms, reduced) => new Promise<void>((resolve) => {
      const cy = cyRef.current;
      if (!cy) return resolve();
      const edge = cy.getElementById(step.edgeId);
      const src = cy.getElementById(step.source), tgt = cy.getElementById(step.target);
      if (!edge.length || !src.length || !tgt.length) return resolve();
      cy.elements(".pb-dim").filter((e) => e.same(edge) || e.same(tgt)).removeClass("pb-dim");
      edge.addClass("pb-active");
      const finish = () => {
        edge.removeClass("pb-active").addClass(step.blocked ? "pb-blocked" : "pb-done");
        if (!step.blocked) {
          if (step.firstArrival) tgt.addClass(step.netSign === "+" ? "pb-pos" : step.netSign === "-" ? "pb-neg" : "pb-unk");
          if (!reduced) tgt.flashClass(step.kind === "inhibit" ? "pb-flash-inh" : "pb-flash-act", Math.min(700, ms));
          if (step.phospho && !reduced) {
            cy.remove(cy.nodes(".phos-badge"));   // only the latest phosphorylation badge is shown
            const p = tgt.position();
            const badge = cy.add({ group: "nodes", data: { id: `phos-${step.index}-${Date.now()}` }, classes: "phos-badge",
              position: { x: p.x + tgt.outerWidth() / 2 + 2, y: p.y - tgt.outerHeight() / 2 - 2 } });
            extra.current.push(badge.id());
            badge.style("opacity", 0).animate({ style: { opacity: 1 } }, { duration: 200 });
          }
        }
        resolve();
      };
      if (reduced) { finish(); return; }
      const kind = step.blocked ? "blocked" : step.phospho ? "phospho" : step.kind;
      const id = `pulse-${step.index}-${Date.now()}`;
      const pulse = cy.add({ group: "nodes", data: { id, plabel: step.phospho ? "P" : "" }, classes: `pulse pulse-${kind === "blocked" ? step.kind : kind}`,
        position: { ...src.position() } });
      const to = tgt.position(), from = src.position();
      const dest = step.blocked ? { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 } : { ...to };
      pulse.animate({ position: dest }, { duration: ms * 0.8, easing: "ease-in-out-sine", complete: () => {
        if (step.blocked) pulse.addClass("pulse-blocked");
        pulse.animate({ style: { opacity: 0 } }, { duration: step.blocked ? 500 : 180, complete: () => { pulse.remove(); } });
        finish();
      } });
    }),
    showState: (steps, upto, sources) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.batch(() => {
        cy.remove(cy.nodes(".pulse, .phos-badge"));
        extra.current = [];
        cy.elements().removeClass("pb-dim pb-source pb-pos pb-neg pb-unk pb-active pb-done pb-blocked");
        cy.elements().addClass("pb-dim");
        for (const s of sources) cy.getElementById(s).removeClass("pb-dim").addClass("pb-source");
        const { reached, edges } = stateAt(steps, upto);
        for (const [id, st] of edges) cy.getElementById(id).removeClass("pb-dim").addClass(st.blocked ? "pb-blocked" : "pb-done");
        for (const [id, sign] of reached) cy.getElementById(id).removeClass("pb-dim").addClass(sign === "+" ? "pb-pos" : sign === "-" ? "pb-neg" : "pb-unk");
        if (upto > 0) {
          const cur = steps[upto - 1];
          if (cur.phospho && !cur.blocked) {
            const t = cy.getElementById(cur.target);
            const p = t.position();
            const badge = cy.add({ group: "nodes", data: { id: `phos-s-${upto}` }, classes: "phos-badge", position: { x: p.x + t.outerWidth() / 2 + 2, y: p.y - t.outerHeight() / 2 - 2 } });
            extra.current.push(badge.id());
          }
        }
      });
    },
    clearPlayback: () => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.stop(true, true);
      cy.remove(cy.nodes(".pulse, .phos-badge"));
      extra.current = [];
      cy.elements().removeClass("pb-dim pb-source pb-pos pb-neg pb-unk pb-active pb-done pb-blocked");
    },
  }), [layout]);

  return <div ref={box} className="canvas" role="img" aria-label="Interactive molecular network" />;
});

export default NetworkCanvas;
