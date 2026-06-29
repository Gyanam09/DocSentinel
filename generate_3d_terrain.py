import json
import os

import numpy as np

from config import load_config
from fetch_elevation import fetch_elevation


def load_ndvi_results():
    try:
        with open("output/ndvi_results.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def terrain_payload(elev_grid, cfg):
    bbox = cfg["bbox"]
    rows, cols = elev_grid.shape
    elev_min = float(elev_grid.min())
    elev_max = float(elev_grid.max())
    elev_mean = float(elev_grid.mean())
    elev_range = max(elev_max - elev_min, 1.0)

    normalized = ((elev_grid - elev_min) / elev_range).astype(float)
    ndvi = load_ndvi_results()

    return {
        "rows": int(rows),
        "cols": int(cols),
        "bbox": bbox,
        "aoi_name": cfg.get("aoi_name", "AOI"),
        "scene_date": ndvi.get("scene_date", cfg.get("scene_date", "N/A")),
        "elev_min": round(elev_min, 1),
        "elev_max": round(elev_max, 1),
        "elev_mean": round(elev_mean, 1),
        "elev_range": round(elev_max - elev_min, 1),
        "heights": [round(float(v), 4) for v in normalized.flatten()],
        "raw_elevs": [round(float(v), 1) for v in elev_grid.flatten()],
        "ndvi": {
            "mean": ndvi.get("mean_ndvi"),
            "min": ndvi.get("ndvi_min"),
            "max": ndvi.get("ndvi_max"),
            "loss_pct": ndvi.get("loss_pct"),
            "loss_patches": ndvi.get("loss_patches"),
            "alert": ndvi.get("alert", False),
            "scene_name": ndvi.get("scene_name"),
        },
    }


def generate_terrain_html(elev_grid, cfg, output_path="output/terrain_3d.html"):
    data = terrain_payload(elev_grid, cfg)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DocSentinel Terrain Viewer</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; background: #07111f; color: #dbeafe;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  body {{ overflow: hidden; }}
  #app {{ position: relative; width: 100vw; height: 100vh; }}
  canvas {{ display: block; width: 100%; height: 100%; background:
    radial-gradient(circle at 50% 35%, #0e2436 0%, #07111f 58%, #050914 100%); }}
  .topbar {{ position: absolute; inset: 0 0 auto 0; height: 44px; display: flex;
    align-items: center; justify-content: space-between; padding: 0 18px;
    background: rgba(5, 12, 24, .88); border-bottom: 1px solid #17324f; z-index: 5; }}
  .crumb {{ font-family: "Space Mono", ui-monospace, monospace; font-size: 11px; letter-spacing: 1.6px;
    text-transform: uppercase; color: #38bdf8; }}
  .links {{ display: flex; gap: 8px; }}
  .links a, button {{ border: 1px solid #214c73; background: rgba(13, 33, 55, .86); color: #bfdbfe;
    border-radius: 6px; padding: 7px 10px; text-decoration: none; font: 11px "Space Mono", ui-monospace, monospace;
    cursor: pointer; }}
  .links a.active, button.active {{ border-color: #38bdf8; color: #38bdf8; background: rgba(56, 189, 248, .12); }}
  .panel {{ position: absolute; top: 64px; width: min(280px, calc(50vw - 24px)); z-index: 4;
    background: rgba(8, 20, 35, .88); border: 1px solid #1e3a5f; border-radius: 8px;
    padding: 14px; backdrop-filter: blur(8px); }}
  .panel.left {{ left: 16px; }}
  .panel.right {{ right: 16px; }}
  .title {{ color: #38bdf8; font: 11px "Space Mono", ui-monospace, monospace; letter-spacing: 1.6px;
    text-transform: uppercase; padding-bottom: 8px; border-bottom: 1px solid #17324f; margin-bottom: 10px; }}
  .metric {{ display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: baseline; margin: 7px 0; }}
  .label {{ color: #7aa2c8; font: 11px "Space Mono", ui-monospace, monospace; text-transform: uppercase; }}
  .value {{ color: #e0f2fe; font: 700 13px "Space Mono", ui-monospace, monospace; text-align: right; }}
  .value.hot {{ color: #fb7185; }} .value.good {{ color: #4ade80; }} .value.warn {{ color: #fbbf24; }}
  .status {{ display: inline-flex; align-items: center; gap: 7px; padding: 4px 9px; border-radius: 999px;
    border: 1px solid rgba(251, 113, 133, .45); color: #fb7185; background: rgba(251, 113, 133, .1); }}
  .legend {{ display: grid; gap: 7px; }}
  .legend-row {{ display: flex; align-items: center; gap: 8px; color: #cbd5e1; font-size: 12px; }}
  .swatch {{ width: 13px; height: 13px; border-radius: 3px; border: 1px solid rgba(255,255,255,.18); }}
  .controls {{ position: absolute; left: 50%; bottom: 18px; transform: translateX(-50%); z-index: 4;
    display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }}
  .hint {{ position: absolute; left: 50%; bottom: 66px; transform: translateX(-50%); z-index: 4;
    color: #7aa2c8; font: 11px "Space Mono", ui-monospace, monospace; background: rgba(8,20,35,.8);
    border: 1px solid #17324f; border-radius: 7px; padding: 7px 12px; white-space: nowrap; }}
  .tooltip {{ position: absolute; display: none; z-index: 6; pointer-events: none;
    background: rgba(5, 12, 24, .94); border: 1px solid #38bdf8; border-radius: 8px;
    padding: 9px 11px; font: 12px "Space Mono", ui-monospace, monospace; color: #dbeafe; min-width: 160px; }}
  @media (max-width: 860px) {{
    .panel {{ top: 54px; width: calc(100vw - 32px); max-height: 30vh; overflow: auto; }}
    .panel.right {{ display: none; }}
    .hint {{ display: none; }}
  }}
</style>
</head>
<body>
<div id="app">
  <canvas id="terrain"></canvas>
  <div class="topbar">
    <div class="crumb">DocSentinel / Terrain Viewer</div>
    <div class="links">
      <a href="report.html">Report</a>
      <a class="active" href="terrain_3d.html">3D Terrain</a>
    </div>
  </div>

  <section class="panel left">
    <div class="title">Terrain Summary</div>
    <div class="metric"><span class="label">AOI</span><span class="value">{data["aoi_name"]}</span></div>
    <div class="metric"><span class="label">Scene Date</span><span class="value">{data["scene_date"]}</span></div>
    <div class="metric"><span class="label">Min Elev</span><span class="value">{data["elev_min"]} m</span></div>
    <div class="metric"><span class="label">Max Elev</span><span class="value warn">{data["elev_max"]} m</span></div>
    <div class="metric"><span class="label">Mean Elev</span><span class="value">{data["elev_mean"]} m</span></div>
    <div class="metric"><span class="label">Range</span><span class="value">{data["elev_range"]} m</span></div>
    <div class="metric"><span class="label">Grid</span><span class="value">{data["rows"]} x {data["cols"]}</span></div>
  </section>

  <section class="panel right">
    <div class="title">Analysis Context</div>
    <div class="metric"><span class="label">Mean NDVI</span><span class="value">{data["ndvi"].get("mean", "N/A")}</span></div>
    <div class="metric"><span class="label">NDVI Range</span><span class="value">{data["ndvi"].get("min", "N/A")} / {data["ndvi"].get("max", "N/A")}</span></div>
    <div class="metric"><span class="label">Loss Area</span><span class="value hot">{data["ndvi"].get("loss_pct", "N/A")}%</span></div>
    <div class="metric"><span class="label">Loss Patches</span><span class="value">{data["ndvi"].get("loss_patches", "N/A")}</span></div>
    <div class="metric"><span class="label">Status</span><span class="value"><span class="status">{"Alert" if data["ndvi"].get("alert") else "Nominal"}</span></span></div>
    <div class="title" style="margin-top:14px">Color Scale</div>
    <div class="legend">
      <div class="legend-row"><span class="swatch" style="background:#2f6f4e"></span>Lower elevation / vegetated basin</div>
      <div class="legend-row"><span class="swatch" style="background:#73b96d"></span>Mid elevation</div>
      <div class="legend-row"><span class="swatch" style="background:#d4bd63"></span>Higher ground</div>
      <div class="legend-row"><span class="swatch" style="background:#e8ecef"></span>Local high points</div>
    </div>
  </section>

  <div class="tooltip" id="tip"></div>
  <div class="hint">Drag to rotate / tilt · Scroll to zoom · Hover to inspect elevation</div>
  <div class="controls">
    <button class="active" id="btnSurface">Surface</button>
    <button id="btnWire">Wireframe</button>
    <button id="btnReset">Reset</button>
  </div>
</div>

<script>
const DATA = {json.dumps(data)};
const canvas = document.getElementById('terrain');
const ctx = canvas.getContext('2d');
const tip = document.getElementById('tip');
let yaw = -0.72, pitch = 0.78, zoom = 21, zScale = 4.2;
let wire = false, dragging = false, lastX = 0, lastY = 0;
let mouse = {{x: -9999, y: -9999}};

function resize() {{
  const dpr = Math.max(1, Math.min(devicePixelRatio || 1, 2));
  canvas.width = Math.floor(innerWidth * dpr);
  canvas.height = Math.floor(innerHeight * dpr);
  canvas.style.width = innerWidth + 'px';
  canvas.style.height = innerHeight + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}}

function elevAt(r, c) {{
  return DATA.raw_elevs[r * DATA.cols + c];
}}

function hAt(r, c) {{
  return DATA.heights[r * DATA.cols + c];
}}

function colorFor(t) {{
  const stops = [
    [0.00, [47,111,78]],
    [0.35, [115,185,109]],
    [0.63, [212,189,99]],
    [0.84, [187,126,74]],
    [1.00, [232,236,239]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {{
    const [a, ca] = stops[i], [b, cb] = stops[i + 1];
    if (t >= a && t <= b) {{
      const f = (t - a) / (b - a);
      const rgb = ca.map((v, k) => Math.round(v + (cb[k] - v) * f));
      return `rgb(${{rgb[0]}},${{rgb[1]}},${{rgb[2]}})`;
    }}
  }}
  return 'rgb(232,236,239)';
}}

function project(r, c) {{
  const x = (c / (DATA.cols - 1) - 0.5) * DATA.cols;
  const y = (r / (DATA.rows - 1) - 0.5) * DATA.rows;
  const z = hAt(r, c) * zScale;
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const rx = x * cy - y * sy;
  const ry = x * sy + y * cy;
  const screenX = innerWidth / 2 + rx * zoom;
  const screenY = innerHeight / 2 + (ry * cp - z * sp) * zoom + 35;
  return {{x: screenX, y: screenY, depth: ry + z * 0.2}};
}}

function drawGrid() {{
  ctx.save();
  ctx.strokeStyle = 'rgba(56,189,248,.08)';
  ctx.lineWidth = 1;
  for (let i = -24; i <= 24; i += 2) {{
    const a = project(0, Math.max(0, Math.min(DATA.cols - 1, Math.round((i + 24) / 48 * (DATA.cols - 1)))));
    const b = project(DATA.rows - 1, Math.max(0, Math.min(DATA.cols - 1, Math.round((i + 24) / 48 * (DATA.cols - 1)))));
    ctx.beginPath(); ctx.moveTo(a.x, a.y + 60); ctx.lineTo(b.x, b.y + 60); ctx.stroke();
  }}
  ctx.restore();
}}

function draw() {{
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  drawGrid();
  const cells = [];
  for (let r = 0; r < DATA.rows - 1; r++) {{
    for (let c = 0; c < DATA.cols - 1; c++) {{
      const p1 = project(r, c), p2 = project(r, c + 1), p3 = project(r + 1, c + 1), p4 = project(r + 1, c);
      const h = (hAt(r, c) + hAt(r, c + 1) + hAt(r + 1, c + 1) + hAt(r + 1, c)) / 4;
      cells.push({{p:[p1,p2,p3,p4], h, depth:(p1.depth+p2.depth+p3.depth+p4.depth)/4, r, c}});
    }}
  }}
  cells.sort((a, b) => a.depth - b.depth);

  for (const cell of cells) {{
    ctx.beginPath();
    ctx.moveTo(cell.p[0].x, cell.p[0].y);
    for (let i = 1; i < 4; i++) ctx.lineTo(cell.p[i].x, cell.p[i].y);
    ctx.closePath();
    ctx.fillStyle = colorFor(cell.h);
    ctx.fill();
    ctx.strokeStyle = wire ? 'rgba(191,219,254,.32)' : 'rgba(8,20,35,.22)';
    ctx.lineWidth = wire ? 0.8 : 0.35;
    ctx.stroke();
  }}

  updateTooltip();
}}

function nearestPoint(mx, my) {{
  let best = null, bestD = Infinity;
  for (let r = 0; r < DATA.rows; r += 2) {{
    for (let c = 0; c < DATA.cols; c += 2) {{
      const p = project(r, c);
      const d = Math.hypot(p.x - mx, p.y - my);
      if (d < bestD) {{ bestD = d; best = {{r, c, p}}; }}
    }}
  }}
  return bestD < 28 ? best : null;
}}

function updateTooltip() {{
  const hit = nearestPoint(mouse.x, mouse.y);
  if (!hit) {{ tip.style.display = 'none'; return; }}
  const lat = DATA.bbox.min_lat + (hit.r / (DATA.rows - 1)) * (DATA.bbox.max_lat - DATA.bbox.min_lat);
  const lon = DATA.bbox.min_lon + (hit.c / (DATA.cols - 1)) * (DATA.bbox.max_lon - DATA.bbox.min_lon);
  tip.innerHTML = `<strong>${{elevAt(hit.r, hit.c).toFixed(0)}} m ASL</strong><br>${{lat.toFixed(5)}}, ${{lon.toFixed(5)}}`;
  tip.style.display = 'block';
  tip.style.left = Math.min(innerWidth - 190, mouse.x + 14) + 'px';
  tip.style.top = Math.max(52, mouse.y - 12) + 'px';
}}

canvas.addEventListener('mousedown', e => {{ dragging = true; lastX = e.clientX; lastY = e.clientY; }});
window.addEventListener('mouseup', () => dragging = false);
window.addEventListener('mousemove', e => {{
  mouse = {{x: e.clientX, y: e.clientY}};
  if (dragging) {{
    yaw += (e.clientX - lastX) * 0.008;
    pitch = Math.max(0.35, Math.min(1.16, pitch + (e.clientY - lastY) * 0.006));
    lastX = e.clientX; lastY = e.clientY;
  }}
  draw();
}});
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  zoom = Math.max(8, Math.min(42, zoom - e.deltaY * 0.018));
  draw();
}}, {{passive:false}});

document.getElementById('btnWire').onclick = () => {{
  wire = !wire;
  document.getElementById('btnWire').classList.toggle('active', wire);
  draw();
}};
document.getElementById('btnSurface').onclick = () => {{ wire = false; document.getElementById('btnWire').classList.remove('active'); draw(); }};
document.getElementById('btnReset').onclick = () => {{ yaw = -0.72; pitch = 0.78; zoom = 21; draw(); }};
window.addEventListener('resize', resize);
resize();
</script>
</body>
</html>"""

    os.makedirs("output", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved -> {output_path}")
    return output_path


if __name__ == "__main__":
    cfg = load_config()
    print("Fetching elevation data...")
    elev_grid, _, _ = fetch_elevation(cfg)
    print("Generating 3D terrain viewer...")
    path = generate_terrain_html(elev_grid, cfg)
    print(f"Done - open {path} in your browser")
