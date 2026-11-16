// Pure graph logic shared by the canvas, playback and perturbation views.
// Mirrors scripts/bpm/explorer.py (perturb, path_sign) so both front ends agree.

import type { EdgeData, Elements, NodeData } from "../types";

export type Sign = "+" | "-" | "?";
type E = { data: EdgeData };
type N = { data: NodeData };

export function adjacency(edges: E[], removed: Set<string> = new Set(), cut: Set<string> = new Set()) {
  const adj = new Map<string, { to: string; edge: EdgeData }[]>();
  const push = (a: string, b: string, edge: EdgeData) => {
    if (!adj.has(a)) adj.set(a, []);
    adj.get(a)!.push({ to: b, edge });
  };
  for (const { data: d } of edges) {
    if (cut.has(d.id) || removed.has(d.source) || removed.has(d.target)) continue;
    push(d.source, d.target, d);
    if (!d.directed) push(d.target, d.source, d);
  }
  for (const list of adj.values()) list.sort((x, y) => x.edge.id.localeCompare(y.edge.id));
  return adj;
}

export function reachable(sources: string[], edges: E[], removed = new Set<string>(), cut = new Set<string>()) {
  const adj = adjacency(edges.filter((e) => !e.data.suspect), removed, cut);
  const seen = new Set(sources.filter((s) => !removed.has(s)));
  const queue = [...seen];
  while (queue.length) {
    const n = queue.shift()!;
    for (const { to } of adj.get(n) ?? []) if (!seen.has(to)) { seen.add(to); queue.push(to); }
  }
  for (const s of sources) seen.delete(s);
  return seen;
}

export function shortestPath(adj: ReturnType<typeof adjacency>, src: string, dst: string): string[] {
  const prev = new Map<string, string | null>([[src, null]]);
  const queue = [src];
  while (queue.length) {
    const n = queue.shift()!;
    if (n === dst) break;
    for (const { to } of adj.get(n) ?? []) if (!prev.has(to)) { prev.set(to, n); queue.push(to); }
  }
  if (!prev.has(dst)) return [];
  const path: string[] = [];
  for (let cur: string | null = dst; cur !== null; cur = prev.get(cur) ?? null) path.push(cur);
  return path.reverse();
}

function edgeBetween(edges: E[], u: string, v: string): EdgeData | undefined {
  return edges.find((e) => e.data.source === u && e.data.target === v)?.data ??
    edges.find((e) => !e.data.directed && e.data.source === v && e.data.target === u)?.data;
}

/** Product of edge signs along a path; '?' if any step is unsigned (binding, phosphorylation alone). */
export function pathSign(path: string[], edges: E[]): Sign {
  let sign = 1;
  for (let i = 0; i + 1 < path.length; i++) {
    const s = edgeBetween(edges, path[i], path[i + 1])?.sign ?? "0";
    if (s === "0") return "?";
    if (s === "-") sign = -sign;
  }
  return sign > 0 ? "+" : "-";
}

export function upstream(id: string, edges: E[]): Set<string> {
  const rev: E[] = edges.map((e) => ({ data: { ...e.data, source: e.data.target, target: e.data.source } }));
  return reachable([id], rev);
}
export function downstream(id: string, edges: E[]): Set<string> {
  return reachable([id], edges);
}

// ------------------------------------------------------------ playback
export type StepKind = "activate" | "inhibit" | "express" | "bind" | "convert" | "modify" | "link";
export interface Step {
  index: number; edgeId: string; source: string; target: string; relation: string;
  kind: StepKind; phospho: boolean; layer: number; netSign: Sign;
  evidenceCode: string; blocked: boolean; blockReason?: string; firstArrival: boolean;
}

export function stepKind(relation: string, sign: string): StepKind {
  if (relation === "inhibition" || sign === "-") return "inhibit";
  if (relation === "expression") return "express";
  if (relation === "activation") return "activate";
  if (relation === "conversion") return "convert";
  if (relation === "binding" || relation === "association") return "bind";
  if (relation === "pathway link" || relation === "contains" || relation === "participates in") return "link";
  return "modify";
}

/**
 * Order documented relations by graph distance from the source(s). One step per
 * relation, taken when its source node is first expanded. The order is graph
 * order only: it says nothing about timing or kinetics. `blocked` edges (removed,
 * inhibited by the user, or documented as impaired in a mutant) are shown but do
 * not propagate.
 */
export function playbackPlan(elements: Elements, sources: string[],
  opts: { blocked?: Map<string, string>; removed?: Set<string> } = {}): Step[] {
  const blocked = new Map(opts.blocked ?? []);
  // Probably mis-encoded KEGG relations are shown, but the signal does not travel through them.
  for (const { data } of elements.edges) if (data.suspect && !blocked.has(data.id)) blocked.set(data.id, "direction suspect in KEGG file");
  const removed = opts.removed ?? new Set<string>();
  const adj = adjacency(elements.edges, removed);
  const sign = new Map<string, Sign>();
  const layer = new Map<string, number>();
  const queue: string[] = [];
  for (const s of sources) if (!removed.has(s)) { sign.set(s, "+"); layer.set(s, 0); queue.push(s); }
  const steps: Step[] = [];
  const usedEdges = new Set<string>();
  while (queue.length) {
    const u = queue.shift()!;
    for (const { to, edge } of adj.get(u) ?? []) {
      const key = `${edge.id}|${u}`;
      if (usedEdges.has(edge.id) && edge.directed) continue;
      if (usedEdges.has(key)) continue;
      usedEdges.add(edge.directed ? edge.id : key);
      if (!edge.directed && usedEdges.has(`${edge.id}|${to}`)) continue;
      const isBlocked = blocked.has(edge.id);
      const parentSign = sign.get(u) ?? "?";
      const net: Sign = parentSign === "?" || edge.sign === "0" ? "?" :
        (edge.sign === "-") !== (parentSign === "-") ? "-" : "+";
      const first = !layer.has(to) && !isBlocked;
      steps.push({ index: steps.length, edgeId: edge.id, source: u, target: to, relation: edge.relation,
        kind: stepKind(edge.relation, edge.sign), phospho: edge.phospho, layer: (layer.get(u) ?? 0) + 1,
        netSign: net, evidenceCode: edge.evidenceCode, blocked: isBlocked, blockReason: blocked.get(edge.id),
        firstArrival: first });
      if (first) { layer.set(to, (layer.get(u) ?? 0) + 1); sign.set(to, net); queue.push(to); }
    }
  }
  return steps;
}

/** Node states after applying steps[0..upto) — used for step-back and reduced-motion playback. */
export function stateAt(steps: Step[], upto: number) {
  const reached = new Map<string, Sign>();
  const edges = new Map<string, Step>();
  for (const st of steps.slice(0, upto)) {
    edges.set(st.edgeId, st);
    if (!st.blocked && !reached.has(st.target)) reached.set(st.target, st.netSign);
  }
  return { reached, edges };
}

// --------------------------------------------------------- perturbation
export interface Perturbation {
  before: Set<string>; after: Set<string>; unreachable: { node: string; netSign: Sign; route: string[] }[];
  rerouted: { target: string; original: string[]; alternative: string[] }[];
}

export function perturb(elements: Elements, sources: string[], removed: Set<string>, cut: Set<string>): Perturbation {
  const edges = elements.edges;
  const before = reachable(sources, edges);
  const after = reachable(sources, edges, removed, cut);
  const trusted = edges.filter((e) => !e.data.suspect);
  const adj0 = adjacency(trusted), adj1 = adjacency(trusted, removed, cut);
  const unreachable = [...before].filter((n) => !after.has(n) && !removed.has(n)).sort().map((n) => {
    const route = sources.map((s) => shortestPath(adj0, s, n)).find((p) => p.length) ?? [];
    return { node: n, netSign: pathSign(route, edges), route };
  });
  // A node is re-routed when its original shortest route used the removed node or inhibited edge.
  const usesChange = (p: string[]) => p.some((x) => removed.has(x)) || p.slice(1).some((v, i) => {
    const e = edges.find((x) => (x.data.source === p[i] && x.data.target === v) || (!x.data.directed && x.data.source === v && x.data.target === p[i]));
    return !!e && cut.has(e.data.id);
  });
  const rerouted: Perturbation["rerouted"] = [];
  for (const n of [...after].sort()) {
    for (const s of sources) {
      const p0 = shortestPath(adj0, s, n), p1 = shortestPath(adj1, s, n);
      if (p0.length && p1.length && usesChange(p0)) { rerouted.push({ target: n, original: p0, alternative: p1 }); break; }
    }
  }
  return { before, after, unreachable, rerouted };
}

// ----------------------------------------------------------- helpers
export function neighbourExpansion(shown: Elements, full: { nodes: N[]; edges: E[] } | undefined, id: string): Elements {
  if (!full) return { nodes: [], edges: [] };
  const have = new Set(shown.nodes.map((n) => n.data.id));
  const haveE = new Set(shown.edges.map((e) => e.data.id));
  const edges = full.edges.filter((e) => !haveE.has(e.data.id) && (e.data.source === id || e.data.target === id));
  const ids = new Set(edges.flatMap((e) => [e.data.source, e.data.target]).filter((x) => !have.has(x)));
  return { nodes: full.nodes.filter((n) => ids.has(n.data.id)), edges };
}

export function searchNodes(nodes: N[], q: string): string[] {
  const s = q.trim().toLowerCase();
  if (!s) return [];
  return nodes.filter(({ data }) => data.label.toLowerCase().includes(s) ||
    (data.members ?? []).some((m) => m.toLowerCase() === s || m.toLowerCase().startsWith(s))).map((n) => n.data.id);
}

/** A sensible playback source: a focus node with no incoming edge from another focus node. */
export function defaultSources(elements: Elements, focus: string[]): string[] {
  const inDeg = new Map<string, number>();
  for (const { data } of elements.edges) if (data.directed) inDeg.set(data.target, (inDeg.get(data.target) ?? 0) + 1);
  const roots = elements.nodes.map((n) => n.data.id).filter((id) => !inDeg.get(id));
  const focusRoots = focus.filter((f) => roots.includes(f));
  if (focusRoots.length) return focusRoots.slice(0, 1);
  if (focus.length) {
    // the focus node that reaches the most others
    let best = focus[0], bestN = -1;
    for (const f of focus) { const n = reachable([f], elements.edges).size; if (n > bestN) { best = f; bestN = n; } }
    return [best];
  }
  return roots.slice(0, 1);
}
