import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export interface Atom { chain: string; label_seq: number; auth_seq: string; res: string; x: number; y: number; z: number; b: number; uniprot: number | null }
export interface Feature { type: string; start: number; end: number; description: string; code: string; ligand?: string }
export type ColorMode = "confidence" | "domain" | "chain" | "rainbow";

export const PLDDT_COLORS = [["Very high (>90)", "#0053d6"], ["Confident (70–90)", "#65cbf3"], ["Low (50–70)", "#ffdb13"], ["Very low (<50)", "#ff7d45"]] as const;
const DOMAIN_PALETTE = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#14b8a6", "#8b5cf6", "#ef4444", "#84cc16", "#06b6d4", "#f97316"];
const CHAIN_PALETTE = ["#60a5fa", "#f472b6", "#34d399", "#fbbf24", "#a78bfa", "#fb7185", "#2dd4bf", "#facc15"];
const PRIMARY_TYPES = new Set(["Domain", "DNA binding", "Zinc finger", "Motif"]);
/** Features used for colouring: structural domains first; broad interaction/disorder regions only as fallback. */
export function colourDomains(features: Feature[]): Feature[] {
  const primary = features.filter((f) => PRIMARY_TYPES.has(f.type));
  const regions = features.filter((f) => f.type === "Region" && !/^(interaction|required for|disordered)/i.test(f.description));
  return [...primary, ...regions];
}
const SITE_TYPES = new Set(["Binding site", "Active site"]);

function plddt(b: number) { return b > 90 ? PLDDT_COLORS[0][1] : b > 70 ? PLDDT_COLORS[1][1] : b > 50 ? PLDDT_COLORS[2][1] : PLDDT_COLORS[3][1]; }

export function domainColor(_features: Feature[], i: number) { return DOMAIN_PALETTE[i % DOMAIN_PALETTE.length]; }

export default function Structure3D({ atoms, features, mode, isPredicted, targetChains, focus, showSites, dark, reduced }: {
  atoms: Atom[]; features: Feature[]; mode: ColorMode; isPredicted: boolean; targetChains?: string[];
  focus: Feature | null; showSites: boolean; dark: boolean; reduced: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const api = useRef<{ setFocus: (f: Feature | null) => void } | null>(null);

  useEffect(() => {
    const el = box.current;
    if (!el || !atoms.length) return;
    const W = () => el.clientWidth, H = () => el.clientHeight;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W(), H());
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, W() / H(), 0.1, 5000);
    scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x223344 : 0x8899aa, dark ? 1.0 : 1.2));
    const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(60, 80, 100); scene.add(key);
    const rim = new THREE.DirectionalLight(0x88aaff, 0.5); rim.position.set(-80, -40, -60); scene.add(rim);

    // centre the molecule
    const centre = new THREE.Vector3();
    atoms.forEach((a) => centre.add(new THREE.Vector3(a.x, a.y, a.z)));
    centre.divideScalar(atoms.length);
    const pos = (a: Atom) => new THREE.Vector3(a.x - centre.x, a.y - centre.y, a.z - centre.z);
    const group = new THREE.Group(); scene.add(group);

    const domains = colourDomains(features);
    const chains = [...new Set(atoms.map((a) => a.chain))];
    const maxB = Math.max(...atoms.map((a) => a.b), 1);
    const colorOf = (a: Atom, idx: number, n: number): THREE.Color => {
      const target = isPredicted || !targetChains?.length || targetChains.includes(a.chain);
      if (mode === "chain") return new THREE.Color(CHAIN_PALETTE[chains.indexOf(a.chain) % CHAIN_PALETTE.length]);
      if (mode === "rainbow") return new THREE.Color().setHSL(0.66 * (1 - idx / Math.max(1, n - 1)), 0.75, 0.55);
      if (mode === "confidence") {
        if (isPredicted) return new THREE.Color(plddt(a.b));
        const t = Math.min(1, a.b / maxB);
        return new THREE.Color().setHSL(0.62 - 0.62 * t, 0.7, 0.55);
      }
      if (!target || a.uniprot == null) return new THREE.Color(dark ? "#3b4556" : "#c3cad6");
      // most specific (shortest) covering feature wins
      let d = -1;
      domains.forEach((f, i) => { if (a.uniprot! >= f.start && a.uniprot! <= f.end && (d < 0 || f.end - f.start < domains[d].end - domains[d].start)) d = i; });
      return new THREE.Color(d >= 0 ? domainColor(domains, d) : dark ? "#64748b" : "#94a3b8");
    };

    // backbone tubes, broken at chain changes and gaps
    const segments: Atom[][] = [];
    let cur: Atom[] = [];
    const sorted = [...atoms].sort((p, q) => p.chain.localeCompare(q.chain) || p.label_seq - q.label_seq);
    sorted.forEach((a, i) => {
      const prev = sorted[i - 1];
      if (prev && (prev.chain !== a.chain || pos(prev).distanceTo(pos(a)) > 4.4)) { if (cur.length) segments.push(cur); cur = []; }
      cur.push(a);
    });
    if (cur.length) segments.push(cur);
    const material = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.45, metalness: 0.05 });
    const chainIndex = new Map<string, number>();
    for (const seg of segments) {
      const n = sorted.filter((a) => a.chain === seg[0].chain).length;
      if (seg.length < 2) continue;
      const pts = seg.map(pos);
      const curve = new THREE.CatmullRomCurve3(pts, false, "centripetal");
      const tubular = Math.max(8, pts.length * 6), radial = 8;
      const geo = new THREE.TubeGeometry(curve, tubular, 0.42, radial, false);
      const colors = new Float32Array(geo.attributes.position.count * 3);
      for (let i = 0; i <= tubular; i++) {
        const r = Math.min(seg.length - 1, Math.round((i / tubular) * (seg.length - 1)));
        const base = chainIndex.get(seg[0].chain) ?? 0;
        const c = colorOf(seg[r], base + r, n);
        for (let j = 0; j <= radial; j++) { const k = (i * (radial + 1) + j) * 3; colors[k] = c.r; colors[k + 1] = c.g; colors[k + 2] = c.b; }
      }
      chainIndex.set(seg[0].chain, (chainIndex.get(seg[0].chain) ?? 0) + seg.length);
      geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      group.add(new THREE.Mesh(geo, material));
    }

    // invisible picking spheres + site markers
    const pickGeo = new THREE.SphereGeometry(1.6, 6, 6);
    const pick = new THREE.InstancedMesh(pickGeo, new THREE.MeshBasicMaterial({ visible: false }), sorted.length);
    const m4 = new THREE.Matrix4();
    sorted.forEach((a, i) => { m4.setPosition(pos(a)); pick.setMatrixAt(i, m4); });
    group.add(pick);
    const siteMeshes: THREE.Object3D[] = [];
    if (showSites) {
      const sites = features.filter((f) => SITE_TYPES.has(f.type));
      const sg = new THREE.SphereGeometry(0.95, 16, 16);
      const sm = new THREE.MeshStandardMaterial({ color: "#f43f5e", emissive: "#7f1d1d", roughness: 0.3 });
      for (const a of sorted) {
        if (a.uniprot == null || (!isPredicted && targetChains?.length && !targetChains.includes(a.chain))) continue;
        if (sites.some((f) => a.uniprot! >= f.start && a.uniprot! <= f.end)) {
          const s = new THREE.Mesh(sg, sm); s.position.copy(pos(a)); group.add(s); siteMeshes.push(s);
        }
      }
    }
    const focusGroup = new THREE.Group(); group.add(focusGroup);

    // camera framing
    const sphere = new THREE.Box3().setFromObject(group).getBoundingSphere(new THREE.Sphere());
    const dist = sphere.radius / Math.sin((camera.fov * Math.PI) / 360) * 1.05;
    camera.position.set(0, 0, dist);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.autoRotate = !reduced; controls.autoRotateSpeed = 0.8;
    controls.addEventListener("start", () => { controls.autoRotate = false; });
    let lookTarget: THREE.Vector3 | null = null;

    api.current = {
      setFocus: (f) => {
        focusGroup.clear();
        if (!f) { lookTarget = new THREE.Vector3(); return; }
        const hits = sorted.filter((a) => a.uniprot != null && a.uniprot >= f.start && a.uniprot <= f.end &&
          (isPredicted || !targetChains?.length || targetChains.includes(a.chain)));
        if (!hits.length) return;
        const g = new THREE.SphereGeometry(f.start === f.end ? 1.4 : hits.length > 40 ? 0.55 : 0.8, 12, 12);
        const mat = new THREE.MeshStandardMaterial({ color: "#facc15", emissive: "#a16207", emissiveIntensity: 0.6 });
        const c = new THREE.Vector3();
        hits.forEach((a) => { const s = new THREE.Mesh(g, mat); s.position.copy(pos(a)); focusGroup.add(s); c.add(pos(a)); });
        lookTarget = c.divideScalar(hits.length);
        controls.autoRotate = false;
      },
    };
    api.current.setFocus(focus);

    const ray = new THREE.Raycaster(); const mouse = new THREE.Vector2();
    const onMove = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mouse, camera);
      const hit = ray.intersectObject(pick)[0];
      if (hit?.instanceId == null) { setTip(null); return; }
      const a = sorted[hit.instanceId];
      const covering = features.filter((f) => a.uniprot != null && a.uniprot >= f.start && a.uniprot <= f.end && f.type !== "Natural variant" && f.type !== "Mutagenesis");
      setTip({ x: e.clientX - r.left + 12, y: e.clientY - r.top + 12,
        text: `${a.res} ${a.uniprot ?? `(auth ${a.auth_seq}, unmapped)`} · chain ${a.chain} · ${isPredicted ? "pLDDT" : "B"} ${a.b}` +
          (covering.length ? ` · ${covering.slice(0, 2).map((f) => f.description || f.type).join("; ")}` : "") });
    };
    renderer.domElement.addEventListener("pointermove", onMove);
    renderer.domElement.addEventListener("pointerleave", () => setTip(null));

    let raf = 0;
    const tick = () => {
      if (lookTarget) {
        controls.target.lerp(lookTarget, 0.08);
        if (controls.target.distanceTo(lookTarget) < 0.05) lookTarget = null;
      }
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();
    const ro = new ResizeObserver(() => { renderer.setSize(W(), H()); camera.aspect = W() / H(); camera.updateProjectionMatrix(); });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); controls.dispose();
      scene.traverse((o) => { if ((o as THREE.Mesh).geometry) (o as THREE.Mesh).geometry.dispose(); });
      renderer.dispose(); el.removeChild(renderer.domElement); api.current = null;
    };
  }, [atoms, features, mode, isPredicted, targetChains, showSites, dark, reduced]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { api.current?.setFocus(focus); }, [focus]);

  return (
    <div ref={box} className="viewer3d" aria-label="3D protein structure viewer; drag to rotate, scroll to zoom">
      {tip && <div className="tooltip3d" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  );
}
