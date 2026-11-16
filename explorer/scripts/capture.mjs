// Headless verification + README screenshots for BioPathway Explorer.
//   node scripts/capture.mjs --url http://localhost:5174 --out ../docs/images [--gif] [--theme dark|light]
// Uses the locally installed Google Chrome through puppeteer-core.
import puppeteer from "puppeteer-core";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PNG } from "pngjs";
import gifenc from "gifenc";
const { GIFEncoder, quantize, applyPalette } = gifenc;

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const URL_ = arg("--url", "http://localhost:5174");
const OUT = arg("--out", "shots");
const THEME = arg("--theme", "dark");
const ONLY = arg("--only", "");
const GIF = process.argv.includes("--gif");
mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: "new", args: ["--no-sandbox", "--use-angle=metal", "--enable-webgl", "--ignore-gpu-blocklist"],
  defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1.5 },
});
const report = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function open(hash, theme = THEME) {
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.evaluateOnNewDocument((t) => { try { localStorage.setItem("bpm-theme", t); } catch {} }, theme);
  await page.goto(`${URL_}/#/${hash}`, { waitUntil: "networkidle0", timeout: 120000 });
  return { page, errors };
}
async function clickText(page, text) {
  await page.evaluate((t) => { const b = [...document.querySelectorAll("button")].find((x) => x.textContent.includes(t)); b?.click(); }, text);
}
async function shot(name, hash, prepare, wait = 2500, theme = THEME) {
  if (ONLY && !ONLY.split(",").includes(name)) return;
  const { page, errors } = await open(hash, theme);
  await sleep(wait);
  const info = prepare ? await prepare(page) : null;
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  const text = await page.evaluate(() => document.querySelector("main")?.innerText.slice(0, 400) ?? "");
  report.push({ name, hash, errors, info, text: text.replace(/\s+/g, " ").slice(0, 200) });
  await page.close();
}

await shot("overview", "overview", null, 1800);
await shot("pathway-egfr-playback", "pathway", async (p) => {
  await clickText(p, "Play signal"); await sleep(7600);
  await clickText(p, "Pause"); await sleep(1300);
  return p.evaluate(() => document.querySelector(".step-caption")?.innerText);
}, 3500);
await shot("pathway-pi3k-perturb", "pathway/pi3k-akt-mtor", async (p) => {
  // select TSC2:TSC1 through the cytoscape instance and remove it
  await p.evaluate(() => {
    const cyEl = document.querySelector(".canvas"); const cy = cyEl?._cyreg?.cy;
    const n = cy?.nodes().filter((x) => String(x.data("label")).startsWith("TSC2"))[0];
    n?.emit("tap");
  });
  await sleep(500); await clickText(p, "Perturb"); await sleep(400); await clickText(p, "Remove node"); await sleep(600);
  await clickText(p, "Play signal"); await sleep(6200);
  return p.evaluate(() => document.querySelector(".panel")?.innerText.slice(0, 300));
}, 3500);
await shot("mutation-kras-g12d", "mutation", async (p) => {
  await sleep(1500); await clickText(p, "Play both"); await sleep(5200);
  return p.evaluate(() => document.querySelector(".panel")?.innerText.slice(0, 300));
}, 4500);
await shot("node-panel-akt1", "pathway/pi3k-akt-mtor", async (p) => {
  await p.evaluate(() => { const cy = document.querySelector(".canvas")?._cyreg?.cy;
    cy?.nodes().filter((x) => String(x.data("label")).startsWith("AKT"))[0]?.emit("tap"); });
  await sleep(2500);
  return p.evaluate(() => document.querySelector(".panel")?.innerText.slice(0, 200));
}, 3500);
await shot("structure-kras", "structure/KRAS", async (p) => { await sleep(3500); return p.evaluate(() => !!document.querySelector(".viewer3d canvas")); }, 3000);
await shot("structure-tp53-domains", "structure/TP53", async (p) => {
  await clickText(p, "Domains"); await sleep(800);
  await p.evaluate(() => [...document.querySelectorAll(".feature-row")].find((b) => b.textContent.includes("DNA binding") || b.textContent.includes("DNA-binding"))?.click());
  await sleep(2500); return true;
}, 3500);
await shot("metabolic-glycolysis", "metabolic", async (p) => { await clickText(p, "Play signal"); await sleep(5200); await clickText(p, "Pause"); await sleep(1300); return true; }, 3000);
await shot("process-brca1", "process", null, 3500);
await shot("interactions-tp53", "interactions/TP53", null, 4500);
await shot("gene-kras", "gene/KRAS", null, 4000);
await shot("literature-brca1", "literature", null, 3500);
await shot("pathway-light", "pathway/tp53-apoptosis", async (p) => {
  await p.evaluate(() => { const cy = document.querySelector(".canvas")?._cyreg?.cy;
    cy?.nodes().filter((x) => x.data("label") === "TP53")[0]?.emit("tap"); });
  await sleep(2500); return true;
}, 3500, "light");

if (GIF) {
  const { page } = await open("pathway");
  await sleep(3500);
  const box = await page.evaluate(() => { const r = document.querySelector(".stage").getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; });
  await clickText(page, "Play signal");
  const frames = [];
  for (let i = 0; i < 70; i++) {
    const buf = await page.screenshot({ clip: box, encoding: "binary" });
    frames.push(buf); await sleep(170);
  }
  const enc = GIFEncoder();
  for (const buf of frames) {
    const png = PNG.sync.read(Buffer.from(buf));
    // downscale 2x for size
    const w = Math.floor(png.width / 2), h = Math.floor(png.height / 2);
    const data = new Uint8Array(w * h * 4);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const s = ((y * 2) * png.width + x * 2) * 4, d = (y * w + x) * 4;
      data[d] = png.data[s]; data[d + 1] = png.data[s + 1]; data[d + 2] = png.data[s + 2]; data[d + 3] = 255;
    }
    const palette = quantize(data, 128);
    enc.writeFrame(applyPalette(data, palette), w, h, { palette, delay: 170 });
  }
  enc.finish();
  writeFileSync(join(OUT, "signal-playback.gif"), enc.bytes());
  await page.close();
}
await browser.close();
writeFileSync(join(OUT, "capture-report.json"), JSON.stringify(report, null, 2));
for (const r of report) console.log(`${r.errors.length ? "ERR" : "ok "} ${r.name}  ${r.errors.slice(0, 2).join(" | ").slice(0, 200)}  :: ${JSON.stringify(r.info ?? "").slice(0, 160)}`);
