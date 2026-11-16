import { describe, expect, it } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import type { EdgeData, Elements } from "../types";
import { defaultSources, downstream, neighbourExpansion, pathSign, perturb, playbackPlan, searchNodes, stateAt, upstream } from "./graph";

const edge = (source: string, target: string, relation: string, sign: "+" | "-" | "0", extra: Partial<EdgeData> = {}) =>
  ({ data: { id: `${source}__${relation}__${target}`, source, target, relation, sign, evidence: "curated database evidence",
    evidenceCode: "CUR", directed: true, indirect: false, modifiers: [], phospho: false, suspect: false, detail: "",
    citations: [{ source: "KEGG", id: "hsa00000", url: "" }], ...extra } as EdgeData });
const node = (id: string, members: string[] = [id]) => ({ data: { id, label: id, kind: "gene", focus: false, members } });

// AKT -| TSC -| RHEB -> MTOR ; PI3K -> AKT ; AKT -> X (side branch); GRB2 -- SOS binding
const toy: Elements = {
  nodes: ["PI3K", "AKT", "TSC", "RHEB", "MTOR", "X"].map((n) => node(n)),
  edges: [edge("PI3K", "AKT", "activation", "+", { phospho: true, modifiers: ["+p"] }), edge("AKT", "TSC", "inhibition", "-"),
    edge("TSC", "RHEB", "inhibition", "-"), edge("RHEB", "MTOR", "activation", "+"), edge("AKT", "X", "activation", "+")],
};

describe("relationship direction and sign", () => {
  it("double negative gives net activation", () => {
    expect(pathSign(["PI3K", "AKT", "TSC", "RHEB", "MTOR"], toy.edges)).toBe("+");
    expect(pathSign(["PI3K", "AKT", "TSC"], toy.edges)).toBe("-");
  });
  it("direction matters: no path upstream along a directed edge", () => {
    expect(downstream("RHEB", toy.edges)).toEqual(new Set(["MTOR"]));
    expect(upstream("RHEB", toy.edges)).toEqual(new Set(["TSC", "AKT", "PI3K"]));
  });
  it("unsigned binding makes the net sign unknown", () => {
    const g = [edge("A", "B", "binding", "0", { directed: false }), edge("B", "C", "activation", "+")];
    expect(pathSign(["A", "B", "C"], g)).toBe("?");
    expect(pathSign(["B", "A"], g)).toBe("?");
  });
});

describe("animation consistency", () => {
  const plan = playbackPlan(toy, ["PI3K"]);
  it("every step is a documented edge traversed in its drawn direction", () => {
    const ids = new Map(toy.edges.map((e) => [e.data.id, e.data]));
    for (const st of plan) {
      const e = ids.get(st.edgeId)!;
      expect(e).toBeDefined();
      expect([e.source, e.target]).toEqual([st.source, st.target]);
    }
  });
  it("steps are ordered by graph distance and each relation appears once", () => {
    const layers = plan.map((s) => s.layer);
    expect(layers).toEqual([...layers].sort((a, b) => a - b));
    expect(new Set(plan.map((s) => s.edgeId)).size).toBe(plan.length);
    expect(plan[0]).toMatchObject({ source: "PI3K", target: "AKT", kind: "activate", phospho: true });
  });
  it("inhibition steps are typed and net signs propagate", () => {
    const tsc = plan.find((s) => s.target === "TSC")!;
    expect(tsc.kind).toBe("inhibit");
    expect(tsc.netSign).toBe("-");
    expect(plan.find((s) => s.target === "MTOR")!.netSign).toBe("+");
  });
  it("blocked edges are shown but do not propagate", () => {
    const blocked = new Map([[toy.edges[2].data.id, "user inhibited"]]);
    const p = playbackPlan(toy, ["PI3K"], { blocked });
    const st = p.find((s) => s.edgeId === toy.edges[2].data.id)!;
    expect(st.blocked).toBe(true);
    expect(p.some((s) => s.target === "MTOR")).toBe(false);
  });
  it("stateAt replays exactly the first n steps (step back = recompute)", () => {
    const s2 = stateAt(plan, 2);
    expect([...s2.reached.keys()].sort()).toEqual(plan.slice(0, 2).map((s) => s.target).sort());
    expect(s2.edges.size).toBe(2);
    expect(stateAt(plan, plan.length).reached.get("MTOR")).toBe("+");
  });
});

describe("pathway perturbation", () => {
  it("removing a node reports unreachable nodes with the lost route's net sign", () => {
    const r = perturb(toy, ["PI3K"], new Set(["TSC"]), new Set());
    expect(r.unreachable.map((u) => u.node)).toEqual(["MTOR", "RHEB"]);
    expect(r.unreachable.find((u) => u.node === "RHEB")!.netSign).toBe("+");
    expect(r.after.has("X")).toBe(true);
  });
  it("cutting an edge finds alternative routes", () => {
    const g: Elements = { nodes: ["S", "A", "B", "T"].map((n) => node(n)),
      edges: [edge("S", "A", "activation", "+"), edge("A", "T", "activation", "+"), edge("S", "B", "activation", "+"), edge("B", "T", "activation", "+")] };
    const r = perturb(g, ["S"], new Set(), new Set(["S__activation__A"]));
    expect(r.unreachable.map((u) => u.node)).toEqual(["A"]);
    expect(r.rerouted).toEqual([{ target: "T", original: ["S", "A", "T"], alternative: ["S", "B", "T"] }]);
  });
});

describe("graph helpers", () => {
  it("search matches labels and KEGG box members", () => {
    expect(searchNodes([node("g:1", ["MAPK1", "MAPK3"])], "mapk3")).toEqual(["g:1"]);
    expect(searchNodes(toy.nodes, "")).toEqual([]);
  });
  it("expansion adds only new incident edges and their new nodes", () => {
    const shown: Elements = { nodes: [toy.nodes[0], toy.nodes[1]], edges: [toy.edges[0]] };
    const add = neighbourExpansion(shown, { nodes: toy.nodes, edges: toy.edges }, "AKT");
    expect(add.edges.map((e) => e.data.target).sort()).toEqual(["TSC", "X"]);
    expect(add.nodes.map((n) => n.data.id).sort()).toEqual(["TSC", "X"]);
  });
  it("default source is the upstream focus node", () => {
    expect(defaultSources(toy, ["MTOR", "PI3K"])).toEqual(["PI3K"]);
  });
});

// Cross-check against real exported data, when the bundle exists.
const dataDir = new URL("../../public/data/", import.meta.url);
const keyFor = (op: string, params: Record<string, string>) => {
  const norm = Object.keys(params).sort().map((k) => `${k}=${params[k]}`).join("&");
  return `${op}-${createHash("sha1").update(norm).digest("hex").slice(0, 10)}`;
};
const pi3kFile = new URL(`${keyFor("pathway_graph", { genes: "PIK3CA,AKT1,MTOR", query: "hsa04151" })}.json`, dataDir);
describe.skipIf(!existsSync(pi3kFile))("real KEGG PI3K-AKT map (bundled)", () => {
  const g = JSON.parse(readFileSync(pi3kFile, "utf8"));
  const find = (prefix: string) => g.full.nodes.find((n: any) => n.data.label.startsWith(prefix)).data.id;
  it("removing TSC1/TSC2 cuts PI3K's net-activating route to RHEB and mTORC1", () => {
    const r = perturb(g.full, [find("PIK3CA")], new Set([find("TSC2")]), new Set());
    const lost = new Map(r.unreachable.map((u) => [g.full.nodes.find((n: any) => n.data.id === u.node).data.label, u.netSign]));
    expect(lost.get("RHEB")).toBe("+");
    expect(lost.get("RPTOR:MTOR:MLST8")).toBe("+");
  });
  it("AKT inhibits TSC2:TSC1 and RHEB activates mTORC1 in the drawn direction", () => {
    const rel = (a: string, b: string) => g.full.edges.find((e: any) => e.data.source === find(a) && e.data.target === find(b))?.data;
    expect(rel("AKT", "TSC2")?.relation).toBe("inhibition");
    expect(rel("RHEB", "RPTOR")?.relation).toBe("activation");
    expect(rel("RPTOR", "RHEB")).toBeUndefined();
  });
});

const mutFile = new URL(`${keyFor("compare_mutation", { change: "G12D", gene: "KRAS", genes: "MAPK1", pathway: "MAPK signaling" })}.json`, dataDir);
describe.skipIf(!existsSync(mutFile))("KRAS G12D comparison (bundled)", () => {
  const c = JSON.parse(readFileSync(mutFile, "utf8"));
  const full = c.normal.full;
  const impaired = Object.entries(c.overlay.edges).filter(([, v]: any) => v.status.startsWith("impaired")).map(([k]) => k);
  const elements = { nodes: full.nodes, edges: full.edges.filter((e: any) => impaired.includes(e.data.id) || c.normal.elements.edges.some((x: any) => x.data.id === e.data.id)) };
  const gapSources = impaired.map((id) => id.split("__")[0]);
  it("documented impaired edges are GAP inhibitions of the RAS box", () => {
    expect(impaired.length).toBeGreaterThanOrEqual(2);
    for (const id of impaired) expect(id.split("__")[1]).toBe("inhibition");
  });
  it("mutant playback blocks exactly the impaired edges; normal playback does not", () => {
    const normal = playbackPlan(elements, gapSources);
    const mutant = playbackPlan(elements, gapSources, { blocked: new Map(impaired.map((id) => [id, "impaired"])) });
    expect(normal.filter((s) => s.blocked)).toHaveLength(0);
    expect(new Set(mutant.filter((s) => s.blocked).map((s) => s.edgeId))).toEqual(new Set(impaired));
    // in the normal map the GAPs inhibit RAS (net -); in the mutant that inhibition never arrives
    const ras = impaired[0].split("__")[2];
    expect(normal.find((s) => s.target === ras)?.kind).toBe("inhibit");
    expect(mutant.some((s) => s.target === ras && !s.blocked)).toBe(false);
  });
});

const egfrFile = new URL(`${keyFor("pathway_graph", { genes: "EGFR,MAPK1", query: "MAPK signaling" })}.json`, dataDir);
describe.skipIf(!existsSync(egfrFile))("EGFR to ERK playback on the real map (bundled)", () => {
  const g = JSON.parse(readFileSync(egfrFile, "utf8"));
  const egfr = g.elements.nodes.find((n: any) => n.data.label.startsWith("EGFR")).data.id;
  const plan = playbackPlan(g.elements, [egfr]);
  const ids = new Map(g.elements.edges.map((e: any) => [e.data.id, e.data]));
  it("every step is a documented, cited relation; MEK to ERK steps carry phosphorylation", () => {
    for (const s of plan) {
      const e: any = ids.get(s.edgeId);
      expect(e).toBeDefined();
      expect(e.citations.length).toBeGreaterThan(0);
      if (e.directed) expect([e.source, e.target]).toEqual([s.source, s.target]);
    }
    const erk = g.elements.nodes.find((n: any) => n.data.label.startsWith("MAPK1")).data.id;
    expect(plan.some((s) => s.target === erk && s.phospho)).toBe(true);
  });
  it("signal reaches ERK only after passing RAS and RAF/MEK layers", () => {
    const erk = g.elements.nodes.find((n: any) => n.data.label.startsWith("MAPK1")).data.id;
    const first = plan.find((s) => s.target === erk && s.firstArrival)!;
    expect(first.layer).toBeGreaterThanOrEqual(5);
  });
});
