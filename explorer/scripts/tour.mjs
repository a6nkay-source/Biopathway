// Records the README hero animation: a captioned multi-scene tour of the Explorer.
//   node scripts/tour.mjs --url http://127.0.0.1:8790 --out ../docs/images/tour.gif
import puppeteer from "puppeteer-core";
import { writeFileSync } from "node:fs";
import { PNG } from "pngjs";
import gifenc from "gifenc";
const { GIFEncoder, quantize, applyPalette } = gifenc;

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const URL_ = arg("--url", "http://127.0.0.1:8790");
const OUT = arg("--out", "tour.gif");
const W = 1200, H = 750, SCALE = 0.8;           // 960 x 600 output
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: "new", args: ["--no-sandbox", "--enable-webgl", "--ignore-gpu-blocklist"],
  defaultViewport: { width: W, height: H, deviceScaleFactor: SCALE },
});
const page = await browser.newPage();
await page.evaluateOnNewDocument(() => { try { localStorage.setItem("bpm-theme", "dark"); } catch {} });

const enc = GIFEncoder();
let frames = 0;
let prev = null;
// Frame differencing: pixels identical to the previous frame become transparent and the
// previous frame is kept underneath (dispose = 1), so static UI costs almost nothing.
async function frame(delay) {
  const png = PNG.sync.read(Buffer.from(await page.screenshot({ encoding: "binary" })));
  const data = new Uint8Array(png.data.buffer, png.data.byteOffset, png.data.length);
  const n = png.width * png.height;
  if (!prev) {
    const palette = quantize(data, 255);
    enc.writeFrame(applyPalette(data, palette), png.width, png.height, { palette, delay, dispose: 1 });
  } else {
    const changed = new Uint8Array(n);
    let count = 0;
    for (let i = 0; i < n; i++) {
      const k = i * 4;
      if (Math.abs(data[k] - prev[k]) + Math.abs(data[k + 1] - prev[k + 1]) + Math.abs(data[k + 2] - prev[k + 2]) > 6) { changed[i] = 1; count++; }
    }
    const sample = new Uint8Array(Math.max(count, 1) * 4);
    for (let i = 0, j = 0; i < n; i++) if (changed[i]) { sample.set(data.subarray(i * 4, i * 4 + 4), j * 4); j++; }
    const palette = quantize(sample, 255);
    palette.push([0, 0, 0]);
    const t = palette.length - 1;
    const index = applyPalette(data, palette.slice(0, t));
    for (let i = 0; i < n; i++) if (!changed[i]) index[i] = t;
    enc.writeFrame(index, png.width, png.height, { palette, delay, transparent: true, transparentIndex: t, dispose: 1 });
    // keep what the viewer actually sees for unchanged pixels
    for (let i = 0; i < n; i++) if (!changed[i]) data.set(prev.subarray(i * 4, i * 4 + 4), i * 4);
  }
  prev = data.slice();
  frames++;
}
async function record(n, every, delay = every) { for (let i = 0; i < n; i++) { await frame(delay); await sleep(every); } }
async function caption(step, title, sub) {
  await page.evaluate((step, title, sub) => {
    document.getElementById("tour-cap")?.remove();
    const d = document.createElement("div");
    d.id = "tour-cap";
    d.innerHTML = `<span style="background:#3b82f6;color:#fff;border-radius:999px;padding:2px 10px;font-weight:700;margin-right:10px">${step}</span><b>${title}</b><span style="opacity:.75;margin-left:10px">${sub}</span>`;
    Object.assign(d.style, { position: "fixed", left: "50%", top: "64px", transform: "translateX(-50%)", zIndex: 9999,
      background: "rgba(10,14,23,.92)", color: "#e6ebf3", border: "1px solid #2b3a52", borderRadius: "12px",
      padding: "10px 18px", font: "600 15px Inter Variable, sans-serif", boxShadow: "0 12px 32px -12px rgba(0,0,0,.8)",
      whiteSpace: "nowrap" });
    document.body.appendChild(d);
  }, step, title, sub);
}
async function go(hash, wait = 3500) { await page.goto(`${URL_}/#/${hash}`, { waitUntil: "networkidle0", timeout: 120000 }); await sleep(wait); }
const click = (t) => page.evaluate((t) => [...document.querySelectorAll("button")].find((b) => b.textContent.includes(t))?.click(), t);
const tapNode = (prefix) => page.evaluate((p) => { const cy = document.querySelector(".canvas")?._cyreg?.cy;
  cy?.nodes().filter((n) => String(n.data("label")).startsWith(p))[0]?.emit("tap"); }, prefix);

// 0 · title card on the overview
await go("overview", 2500);
await caption("BioPathway Explorer", "every arrow comes from a database record", "· KEGG · Reactome · STRING · UniProt · ClinVar");
await record(10, 150, 220);

// 1 · signal playback EGFR -> ERK
await go("pathway", 3500);
await caption("1", "Signal playback", "documented relations from EGFR to ERK (KEGG hsa04010)");
await record(4, 150);
await click("Play signal");
await record(52, 170);
await click("Pause");

// 2 · protein panel
await tapNode("MAP2K1");
await sleep(1600);
await caption("2", "Click any protein", "identifiers, function, pathways, partners, evidence");
await record(12, 180);

// 3 · normal vs KRAS G12D
await go("mutation", 5000);
await caption("3", "Normal vs KRAS G12D", "Reactome: GAPs no longer switch RAS off (✕ impaired)");
await record(4, 150);
await click("Play both");
await record(40, 170);

// 4 · perturbation
await go("pathway/pi3k-akt-mtor", 3500);
await tapNode("TSC2");
await sleep(400);
await click("Perturb");
await sleep(300);
await click("Remove node");
await sleep(600);
await page.evaluate(() => { const el = document.querySelector(".canvas"); const cy = el?._cyreg?.cy; if (!cy) return;
  el.dispatchEvent(new WheelEvent("wheel", { bubbles: false }));   // counts as a manual zoom: stops auto re-fit
  const focus = cy.nodes().filter((n) => /^(AKT|TSC2|RHEB|RPTOR)/.test(String(n.data("label"))));
  cy.fit(focus, 30); if (cy.zoom() > 1.3) { cy.zoom(1.3); cy.center(focus); } });
await sleep(300);
await caption("4", "Perturb the network", "remove TSC1/2 → which nodes lose PI3K's influence (signed)");
await record(4, 150);
await click("Play signal");
await record(26, 170);

// 5 · 3D structure
await go("structure/KRAS", 6500);
await caption("5", "3D structures", "AlphaFold (predicted) vs PDB (experimental), domains and binding sites");
await record(26, 160);

enc.finish();
writeFileSync(OUT, enc.bytes());
await browser.close();
console.log(`frames ${frames} -> ${OUT} (${(enc.bytes().length / 1e6).toFixed(1)} MB)`);
