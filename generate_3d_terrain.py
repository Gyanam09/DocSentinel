import numpy as np
import json
import os
from config import load_config
from fetch_elevation import fetch_elevation

def generate_terrain_html(elev_grid, cfg, output_path="output/terrain_3d.html"):
    """
    Generates a self-contained HTML file with an interactive 3D terrain
    viewer built with Three.js. Uses the elevation grid from OpenTopoData.
    """
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox

    # Normalize elevation to 0-1 range for Three.js geometry
    elev_min = float(elev_grid.min())
    elev_max = float(elev_grid.max())
    elev_range = elev_max - elev_min

    # Convert grid to flat list for JSON
    rows, cols = elev_grid.shape
    heights = []
    for i in range(rows):
        for j in range(cols):
            norm = (float(elev_grid[i, j]) - elev_min) / elev_range if elev_range > 0 else 0
            heights.append(round(norm, 4))

    terrain_data = {
        "rows": rows,
        "cols": cols,
        "heights": heights,
        "elev_min": elev_min,
        "elev_max": elev_max,
        "aoi_name": cfg.get("aoi_name", "AOI"),
        "bbox": cfg["bbox"],
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DocSentinel 3D Terrain — {cfg.get('aoi_name','AOI')}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#080f1a; overflow:hidden; font-family:'Inter',sans-serif; }}
  #canvas-wrap {{ width:100vw; height:100vh; position:relative; }}
  canvas {{ display:block; }}

  .hud {{ position:absolute; top:0; left:0; right:0; padding:12px 20px;
           display:flex; align-items:center; justify-content:space-between;
           background:linear-gradient(180deg,rgba(8,15,26,.98) 0%,transparent 100%);
           pointer-events:none; z-index:10; }}
  .brand {{ font-family:'Space Mono',monospace; font-size:12px; color:#38bdf8;
             letter-spacing:2px; text-transform:uppercase; }}
  .hud-title {{ font-size:13px; color:#94a3b8; }}
  .hud-right {{ font-size:11px; color:#4a6fa5; font-family:'Space Mono',monospace; }}

  /* ── LEFT PANEL ── */
  .left-panel {{ position:absolute; top:56px; left:16px; display:flex;
                  flex-direction:column; gap:10px; pointer-events:none; z-index:10; width:200px; }}

  .panel-box {{ background:rgba(13,33,55,.92); border:1px solid #1e3a5f;
                border-radius:8px; padding:12px 14px; backdrop-filter:blur(4px); }}
  .panel-title {{ font-size:10px; color:#38bdf8; text-transform:uppercase;
                  letter-spacing:1.5px; font-family:'Space Mono',monospace;
                  margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid #1e3a5f; }}

  .stat-row {{ display:flex; justify-content:space-between; align-items:center;
               margin-bottom:5px; }}
  .stat-row:last-child {{ margin-bottom:0; }}
  .stat-lbl {{ font-size:11px; color:#4a6fa5; font-family:'Space Mono',monospace; }}
  .stat-val {{ font-size:11px; color:#38bdf8; font-family:'Space Mono',monospace; font-weight:700; }}
  .stat-val.red {{ color:#f87171; }}
  .stat-val.green {{ color:#4ade80; }}
  .stat-val.purple {{ color:#c4b5fd; }}
  .stat-val.amber {{ color:#fbbf24; }}

  .alert-pill {{ display:inline-flex; align-items:center; gap:5px; padding:3px 8px;
                  border-radius:10px; font-size:10px; font-weight:600;
                  font-family:'Space Mono',monospace; letter-spacing:.5px; }}
  .pill-red {{ background:rgba(239,68,68,.15); border:1px solid rgba(239,68,68,.4); color:#f87171; }}
  .pill-green {{ background:rgba(34,197,94,.12); border:1px solid rgba(34,197,94,.35); color:#4ade80; }}
  .pill-dot {{ width:5px; height:5px; border-radius:50%; }}
  .dot-red {{ background:#ef4444; box-shadow:0 0 4px #ef4444; }}
  .dot-green {{ background:#22c55e; box-shadow:0 0 4px #22c55e; }}

  .divider {{ height:1px; background:#1e3a5f; margin:6px 0; }}

  /* ── RIGHT PANEL ── */
  .right-panel {{ position:absolute; top:56px; right:16px; display:flex;
                   flex-direction:column; gap:10px; pointer-events:none; z-index:10; width:190px; }}

  .legend-bar {{ width:100%; height:10px; border-radius:3px;
                 background:linear-gradient(90deg,#1a4a2e,#22863a,#85c882,#f0c040,#c8703a,#d4cfc9);
                 margin:6px 0 4px; }}
  .legend-labels {{ display:flex; justify-content:space-between;
                    font-size:10px; color:#64748b; font-family:'Space Mono',monospace; }}

  .hint-row {{ display:flex; align-items:center; gap:6px; margin-bottom:5px; font-size:11px; color:#4a6fa5; }}
  .hint-row:last-child {{ margin-bottom:0; }}
  .hint-icon {{ color:#38bdf8; font-size:12px; }}

  /* ── BOTTOM CONTROLS ── */
  .controls {{ position:absolute; bottom:20px; left:50%; transform:translateX(-50%);
               display:flex; gap:8px; pointer-events:all; z-index:10; }}
  .ctrl-btn {{ background:rgba(13,33,55,.92); border:1px solid #1e3a5f;
               color:#94a3b8; font-size:11px; padding:7px 14px;
               border-radius:6px; cursor:pointer; font-family:'Space Mono',monospace;
               letter-spacing:1px; transition:all .2s; }}
  .ctrl-btn:hover {{ border-color:#38bdf8; color:#38bdf8; }}
  .ctrl-btn.active {{ border-color:#38bdf8; color:#38bdf8; background:rgba(56,189,248,.1); }}

  /* ── COORD BAR ── */
  .coord-bar {{ position:absolute; bottom:60px; left:50%; transform:translateX(-50%);
                background:rgba(13,33,55,.92); border:1px solid #1e3a5f;
                border-radius:6px; padding:6px 16px; display:flex; gap:20px;
                pointer-events:none; z-index:10; }}
  .coord-item {{ font-size:10px; font-family:'Space Mono',monospace; color:#4a6fa5; }}
  .coord-item span {{ color:#38bdf8; margin-left:4px; }}
</style>
</head>
<body>
<div id="canvas-wrap">

  <!-- TOP HUD -->
  <div class="hud">
    <span class="brand">DocSentinel</span>
    <span class="hud-title">3D Digital Elevation Model — {cfg.get('aoi_name','AOI')}</span>
    <span class="hud-right">SRTM 30m · OPENTOPODATA</span>
  </div>

  <!-- LEFT PANEL — Terrain + NDVI Metrics -->
  <div class="left-panel">

    <div class="panel-box">
      <div class="panel-title">Terrain Metrics</div>
      <div class="stat-row"><span class="stat-lbl">MIN ELEV</span><span class="stat-val">{elev_min:.0f}m</span></div>
      <div class="stat-row"><span class="stat-lbl">MAX ELEV</span><span class="stat-val amber">{elev_max:.0f}m</span></div>
      <div class="stat-row"><span class="stat-lbl">RANGE</span><span class="stat-val">{elev_range:.0f}m</span></div>
      <div class="stat-row"><span class="stat-lbl">MEAN ELEV</span><span class="stat-val">{(elev_min + elev_range/2):.0f}m</span></div>
      <div class="stat-row"><span class="stat-lbl">GRID RES</span><span class="stat-val">{rows}×{cols}</span></div>
      <div class="stat-row"><span class="stat-lbl">DATA SRC</span><span class="stat-val">SRTM 30m</span></div>
    </div>

    <div class="panel-box">
      <div class="panel-title">NDVI Analysis</div>
      <div class="stat-row"><span class="stat-lbl">MEAN NDVI</span><span class="stat-val">0.198</span></div>
      <div class="stat-row"><span class="stat-lbl">NDVI MIN</span><span class="stat-val red">-0.401</span></div>
      <div class="stat-row"><span class="stat-lbl">NDVI MAX</span><span class="stat-val green">0.667</span></div>
      <div class="stat-row"><span class="stat-lbl">LOSS AREA</span><span class="stat-val red">15.3%</span></div>
      <div class="stat-row"><span class="stat-lbl">PATCHES</span><span class="stat-val purple">6093</span></div>
      <div class="divider"></div>
      <div class="stat-row">
        <span class="stat-lbl">STATUS</span>
        <span class="alert-pill pill-red"><span class="pill-dot dot-red"></span>ALERT</span>
      </div>
    </div>

    <div class="panel-box">
      <div class="panel-title">Scene Info</div>
      <div class="stat-row"><span class="stat-lbl">DATE</span><span class="stat-val">{cfg.get('scene_date','N/A')}</span></div>
      <div class="stat-row"><span class="stat-lbl">SENSOR</span><span class="stat-val">S2-L2A</span></div>
      <div class="stat-row"><span class="stat-lbl">RESOLUTION</span><span class="stat-val">10m</span></div>
      <div class="stat-row"><span class="stat-lbl">CLOUD CVR</span><span class="stat-val green">&lt;5%</span></div>
    </div>

  </div>

  <!-- RIGHT PANEL — Legend + Controls hint -->
  <div class="right-panel">

    <div class="panel-box">
      <div class="panel-title">Elevation Legend</div>
      <div class="legend-bar"></div>
      <div class="legend-labels">
        <span>{elev_min:.0f}m</span>
        <span>{(elev_min + elev_range/2):.0f}m</span>
        <span>{elev_max:.0f}m</span>
      </div>
    </div>

    <div class="panel-box">
      <div class="panel-title">AOI Bounds</div>
      <div class="stat-row"><span class="stat-lbl">MIN LAT</span><span class="stat-val">{cfg['bbox']['min_lat']}°N</span></div>
      <div class="stat-row"><span class="stat-lbl">MAX LAT</span><span class="stat-val">{cfg['bbox']['max_lat']}°N</span></div>
      <div class="stat-row"><span class="stat-lbl">MIN LON</span><span class="stat-val">{cfg['bbox']['min_lon']}°E</span></div>
      <div class="stat-row"><span class="stat-lbl">MAX LON</span><span class="stat-val">{cfg['bbox']['max_lon']}°E</span></div>
    </div>

    <div class="panel-box">
      <div class="panel-title">Controls</div>
      <div class="hint-row"><span class="hint-icon">⟳</span>Left drag — rotate</div>
      <div class="hint-row"><span class="hint-icon">⊕</span>Scroll — zoom</div>
      <div class="hint-row"><span class="hint-icon">⤢</span>Right drag — pan</div>
      <div class="hint-row"><span class="hint-icon">◎</span>Touch — supported</div>
    </div>

  </div>

  <!-- COORD BAR -->
  <div class="coord-bar">
    <div class="coord-item">LAT<span>{cfg['bbox']['min_lat']}° – {cfg['bbox']['max_lat']}° N</span></div>
    <div class="coord-item">LON<span>{cfg['bbox']['min_lon']}° – {cfg['bbox']['max_lon']}° E</span></div>
    <div class="coord-item">LOCATION<span>{cfg.get('aoi_name','AOI')}</span></div>
    <div class="coord-item">PROJECTION<span>WGS84</span></div>
  </div>

  <!-- CONTROLS -->
  <div class="controls">
    <button class="ctrl-btn active" onclick="setMode('terrain',this)">TERRAIN</button>
    <button class="ctrl-btn" onclick="setMode('wireframe',this)">WIREFRAME</button>
    <button class="ctrl-btn" onclick="setMode('heatmap',this)">HEATMAP</button>
    <button class="ctrl-btn" onclick="resetCamera()">RESET VIEW</button>
    <button class="ctrl-btn" id="rotBtn" onclick="toggleRotate()">AUTO ROTATE</button>
  </div>

</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const TERRAIN = {json.dumps(terrain_data)};

// ── Scene ─────────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080f1a);
scene.fog = new THREE.FogExp2(0x080f1a, 0.010);

const camera = new THREE.PerspectiveCamera(55, innerWidth/innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
renderer.shadowMap.enabled = true;
document.getElementById('canvas-wrap').appendChild(renderer.domElement);

// ── Lights ────────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x334466, 0.9));
const sun = new THREE.DirectionalLight(0xfff4e0, 1.6);
sun.position.set(20,40,20); sun.castShadow = true;
scene.add(sun);
const fillLight = new THREE.DirectionalLight(0x4488cc, 0.4);
fillLight.position.set(-20, 10, -20);
scene.add(fillLight);

// ── Grid ──────────────────────────────────────────────────────────────────
scene.add(new THREE.GridHelper(50, 50, 0x1e3a5f, 0x0d2137));

// ── Geometry ──────────────────────────────────────────────────────────────
const rows = TERRAIN.rows, cols = TERRAIN.cols;
const SCALE_H = 8, SCALE_XZ = 22;
const heights = TERRAIN.heights;

// Fix null/spike values by clamping
const cleanHeights = heights.map(h => (h === null || h === undefined || isNaN(h)) ? 0 : Math.min(Math.max(h, 0), 1));

const geo = new THREE.PlaneGeometry(SCALE_XZ, SCALE_XZ, cols-1, rows-1);
geo.rotateX(-Math.PI/2);
const pos = geo.attributes.position;
for (let i=0; i<rows; i++)
  for (let j=0; j<cols; j++)
    pos.setY(i*cols+j, cleanHeights[i*cols+j] * SCALE_H);
pos.needsUpdate = true;
geo.computeVertexNormals();

// ── Terrain colors ────────────────────────────────────────────────────────
const stops = [
  [0.00, [0.10,0.29,0.18]],
  [0.25, [0.13,0.53,0.23]],
  [0.50, [0.52,0.78,0.51]],
  [0.70, [0.94,0.75,0.25]],
  [0.85, [0.78,0.44,0.23]],
  [1.00, [0.83,0.81,0.79]],
];
function terrainColor(t) {{
  for (let i=0; i<stops.length-1; i++) {{
    const [t0,c0]=stops[i],[t1,c1]=stops[i+1];
    if (t>=t0 && t<=t1) {{
      const f=(t-t0)/(t1-t0);
      return c0.map((v,k)=>v+(c1[k]-v)*f);
    }}
  }}
  return stops[stops.length-1][1];
}}

const tColors=[], hColors=[];
for (let i=0; i<cleanHeights.length; i++) {{
  const t=cleanHeights[i];
  const tc=terrainColor(t); tColors.push(...tc);
  const hc=new THREE.Color(); hc.setHSL(0.66-t*0.66,1,.5);
  hColors.push(hc.r,hc.g,hc.b);
}}
geo.setAttribute('color', new THREE.Float32BufferAttribute(tColors,3));

const heatGeo = geo.clone();
heatGeo.setAttribute('color', new THREE.Float32BufferAttribute(hColors,3));

// ── Materials & Meshes ────────────────────────────────────────────────────
const mats = {{
  terrain: new THREE.MeshPhongMaterial({{vertexColors:true, shininess:20}}),
  wireframe: new THREE.MeshBasicMaterial({{color:0x38bdf8, wireframe:true, transparent:true, opacity:0.45}}),
  heatmap: new THREE.MeshPhongMaterial({{vertexColors:true, shininess:5}}),
}};

const meshes = {{
  terrain: new THREE.Mesh(geo, mats.terrain),
  wireframe: new THREE.Mesh(geo, mats.wireframe),
  heatmap: new THREE.Mesh(heatGeo, mats.heatmap),
}};
Object.values(meshes).forEach(m=>{{ m.castShadow=true; m.receiveShadow=true; }});

let current = 'terrain';
scene.add(meshes.terrain);

// ── Camera ────────────────────────────────────────────────────────────────
let sph = {{theta:0.5, phi:0.85, r:38}};
let tgt = new THREE.Vector3(0,2,0);
function applyCamera() {{
  camera.position.set(
    tgt.x + sph.r*Math.sin(sph.phi)*Math.sin(sph.theta),
    tgt.y + sph.r*Math.cos(sph.phi),
    tgt.z + sph.r*Math.sin(sph.phi)*Math.cos(sph.theta)
  );
  camera.lookAt(tgt);
}}
applyCamera();

// ── Mouse / touch ─────────────────────────────────────────────────────────
let drag=false, right=false, px=0, py=0;
renderer.domElement.oncontextmenu = e=>e.preventDefault();
renderer.domElement.onmousedown = e=>{{ drag=true; right=e.button===2; px=e.clientX; py=e.clientY; }};
window.onmouseup = ()=>drag=false;
window.onmousemove = e=>{{
  if(!drag) return;
  const dx=e.clientX-px, dy=e.clientY-py;
  if(right) {{ tgt.x-=dx*0.02; tgt.z-=dy*0.02; }}
  else {{ sph.theta-=dx*0.008; sph.phi=Math.max(0.08,Math.min(1.45,sph.phi+dy*0.008)); }}
  px=e.clientX; py=e.clientY; applyCamera();
}};
renderer.domElement.onwheel = e=>{{
  sph.r=Math.max(8,Math.min(90,sph.r+e.deltaY*0.05)); applyCamera();
}};
renderer.domElement.ontouchstart = e=>{{ drag=true; px=e.touches[0].clientX; py=e.touches[0].clientY; }};
renderer.domElement.ontouchend = ()=>drag=false;
renderer.domElement.ontouchmove = e=>{{
  const dx=e.touches[0].clientX-px, dy=e.touches[0].clientY-py;
  sph.theta-=dx*0.008; sph.phi=Math.max(0.08,Math.min(1.45,sph.phi+dy*0.008));
  px=e.touches[0].clientX; py=e.touches[0].clientY; applyCamera();
}};

// ── Control functions ─────────────────────────────────────────────────────
function setMode(mode, btn) {{
  scene.remove(meshes[current]);
  current=mode;
  scene.add(meshes[current]);
  document.querySelectorAll('.ctrl-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
}}
function resetCamera() {{
  sph={{theta:0.5,phi:0.85,r:38}}; tgt=new THREE.Vector3(0,2,0); applyCamera();
}}
let rotating=false;
function toggleRotate() {{
  rotating=!rotating;
  document.getElementById('rotBtn').classList.toggle('active',rotating);
}}

// ── Resize ────────────────────────────────────────────────────────────────
window.onresize=()=>{{
  camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth,innerHeight);
}};

// ── Loop ──────────────────────────────────────────────────────────────────
(function animate(){{
  requestAnimationFrame(animate);
  if(rotating) {{ sph.theta+=0.003; applyCamera(); }}
  renderer.render(scene,camera);
}})();
</script>
</body>
</html>"""

    os.makedirs("output", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved → {output_path}")
    return output_path


if __name__ == "__main__":
    cfg = load_config()
    print("Fetching elevation data...")
    elev_grid, lats, lons = fetch_elevation(cfg)
    print("Generating 3D terrain viewer...")
    path = generate_terrain_html(elev_grid, cfg)
    print(f"Done — open {path} in your browser")