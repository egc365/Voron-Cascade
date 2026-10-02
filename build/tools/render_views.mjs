// Render the vision page headlessly and save the view screenshots.
// Usage: node render_views.mjs <page dir with index.html + cascade.glb> <out dir> [light|dark]
// Needs `npm i three@0.170.0 playwright` next to this script (three is served
// from node_modules because the sandbox can't reach the CDN).
import { chromium } from "playwright";
import fs from "fs"; import path from "path"; import http from "http";
const PAGE = process.argv[2], OUT = process.argv[3];
const THREE_DIR = path.join(path.dirname(new URL(import.meta.url).pathname), "node_modules/three");
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">${fs.readFileSync(PAGE + "/index.html", "utf8")}</body></html>`;
const srv = http.createServer((q, r) => {
  if (q.url === "/" ) { r.writeHead(200, {"content-type": "text/html"}); return r.end(html); }
  const f = path.join(PAGE, decodeURIComponent(q.url)); if (fs.existsSync(f)) { r.writeHead(200); return r.end(fs.readFileSync(f)); }
  r.writeHead(404); r.end();
}).listen(8765);
const b = await chromium.launch({ executablePath: process.env.CHROME || undefined, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: process.argv[4] || "light" });
const errs = []; p.on("console", (m) => m.type() === "error" && errs.push(m.text())); p.on("pageerror", (e) => errs.push(String(e)));
await p.route(/cdn\.jsdelivr\.net\/npm\/three@0\.170\.0\/(.*)/, (route) => {
  const rel = route.request().url().split("three@0.170.0/")[1];
  route.fulfill({ path: path.join(THREE_DIR, rel), contentType: "application/javascript" });
});
await p.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
await p.goto("http://localhost:8765/");
await p.waitForFunction(() => document.getElementById("status").hidden, null, { timeout: 120000 });
await p.waitForTimeout(1500);
const stage = p.locator(".stage");
await stage.screenshot({ path: OUT + "/orbit.png" });
for (const id of ["A", "B", "C"]) { await p.click("#v-" + id); await p.waitForTimeout(1200); await stage.screenshot({ path: `${OUT}/cam_${id}_view.png` }); }
await p.click("#v-iso");
await p.evaluate(() => { const c = window.__cascade; c.orbitCam.position.set(-0.85, 0.3, -0.17); c.controls.target.copy(c.V([21, 150, 60])); });
await p.waitForTimeout(1200); await stage.screenshot({ path: OUT + "/side.png" });
await p.screenshot({ path: OUT + "/_page.png", fullPage: true });
const m = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(800);
const m2 = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
await p.screenshot({ path: OUT + "/_phone.png", fullPage: true });
console.log(JSON.stringify({ errs, desktop: m, phone: m2 }));
await b.close(); srv.close();
