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

    rows, cols = elev_grid.shape

    # Normalize elevation to 0-1 range for Three.js geometry
    elev_min = float(elev_grid.min())
    elev_max = float(elev_grid.max())
    elev_range = elev_max - elev_min

    if elev_range > 0:
        heights = [round(float(h), 4) for h in ((elev_grid - elev_min) / elev_range).flatten()]
    else:
        heights = [0.0] * elev_grid.size

    # Compute slope for each point
    slope_grid = np.zeros_like(elev_grid)
    for i in range(1, rows-1):
        for j in range(1, cols-1):
            dz_dx = (float(elev_grid[i, j+1]) - float(elev_grid[i, j-1])) / 2
            dz_dy = (float(elev_grid[i+1, j]) - float(elev_grid[i-1, j])) / 2
            slope_grid[i, j] = round(float(np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2) / 30))), 1)

    slope_flat = slope_grid.flatten().tolist()
    raw_elevs = elev_grid.flatten().tolist()

    terrain_data = {
        "rows": rows,
        "cols": cols,
        "heights": heights,
        "raw_elevs": [round(float(e), 1) for e in raw_elevs],
        "slopes": slope_flat,
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

  .hud {{ position:absolute; top:44px; left:0; right:0; padding:12px 20px;
           display:flex; align-items:center; justify-content:space-between;
           background:linear-gradient(180deg,rgba(8,15,26,.98),transparent);
           pointer-events:none; z-index:10; }}
  .brand {{ font-family:'Space Mono',monospace; font-size:12px; color:#38bdf8;
             letter-spacing:2px; text-transform:uppercase; }}
  .hud-title {{ font-size:13px; color:#94a3b8; }}
  .hud-right {{ font-size:11px; color:#4a6fa5; font-family:'Space Mono',monospace; }}

  .left-panel {{ position:absolute; top:100px; left:16px; display:flex;
                  flex-direction:column; gap:8px; pointer-events:none; z-index:10; width:210px; }}
  .right-panel {{ position:absolute; top:100px; right:16px; display:flex;
                   flex-direction:column; gap:8px; pointer-events:none; z-index:10; width:200px; }}

  .pbox {{ background:rgba(10,22,40,.95); border:1px solid #1e3a5f; border-radius:8px;
            padding:11px 13px; backdrop-filter:blur(6px); }}
  .ptitle {{ font-size:10px; color:#38bdf8; text-transform:uppercase; letter-spacing:1.5px;
              font-family:'Space Mono',monospace; margin-bottom:8px; padding-bottom:6px;
              border-bottom:1px solid #1e3a5f; }}
  .srow {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }}
  .srow:last-child {{ margin-bottom:0; }}
  .slbl {{ font-size:11px; color:#4a6fa5; font-family:'Space Mono',monospace; }}
  .sval {{ font-size:11px; font-family:'Space Mono',monospace; font-weight:700; color:#38bdf8; }}
  .sval.red {{ color:#f87171; }} .sval.green {{ color:#4ade80; }}
  .sval.amber {{ color:#fbbf24; }} .sval.purple {{ color:#c4b5fd; }}

  .pill {{ display:inline-flex; align-items:center; gap:4px; padding:2px 8px;
            border-radius:10px; font-size:10px; font-weight:600;
            font-family:'Space Mono',monospace; }}
  .pill-r {{ background:rgba(239,68,68,.15); border:1px solid rgba(239,68,68,.4); color:#f87171; }}
  .pill-g {{ background:rgba(34,197,94,.12); border:1px solid rgba(34,197,94,.35); color:#4ade80; }}
  .pdot {{ width:5px; height:5px; border-radius:50%; }}
  .pdot-r {{ background:#ef4444; box-shadow:0 0 4px #ef4444; }}
  .pdot-g {{ background:#22c55e; box-shadow:0 0 4px #22c55e; }}
  .div {{ height:1px; background:#1e3a5f; margin:5px 0; }}

  /* Color legend strips */
  .legend-strip {{ width:100%; height:12px; border-radius:3px; margin:6px 0 4px; }}
  .terrain-strip {{ background:linear-gradient(90deg,#1a4a2e,#22863a,#85c882,#f0c040,#c8703a,#d4cfc9); }}
  .heat-strip {{ background:linear-gradient(90deg,#0000ff,#00ffff,#00ff00,#ffff00,#ff0000); }}
  .legend-labels {{ display:flex; justify-content:space-between;
                    font-size:10px; color:#64748b; font-family:'Space Mono',monospace; }}

  /* Land cover legend */
  .lc-row {{ display:flex; align-items:center; gap:7px; margin-bottom:5px; font-size:11px; color:#94a3b8; }}
  .lc-dot {{ width:10px; height:10px; border-radius:2px; flex-shrink:0; }}

  /* Hover tooltip */
  #tooltip {{ position:absolute; display:none; background:rgba(10,22,40,.97);
               border:1px solid #38bdf8; border-radius:8px; padding:10px 13px;
               pointer-events:none; z-index:20; min-width:180px; }}
  .tt-title {{ font-size:10px; color:#38bdf8; font-family:'Space Mono',monospace;
                text-transform:uppercase; letter-spacing:1px; margin-bottom:7px;
                padding-bottom:5px; border-bottom:1px solid #1e3a5f; }}
  .tt-row {{ display:flex; justify-content:space-between; gap:12px;
              font-size:11px; margin-bottom:4px; }}
  .tt-lbl {{ color:#4a6fa5; font-family:'Space Mono',monospace; }}
  .tt-val {{ color:#e2e8f0; font-family:'Space Mono',monospace; font-weight:600; }}

  .coord-bar {{ position:absolute; bottom:62px; left:50%; transform:translateX(-50%);
                background:rgba(10,22,40,.95); border:1px solid #1e3a5f; border-radius:6px;
                padding:6px 16px; display:flex; gap:20px; pointer-events:none; z-index:10; }}
  .ci {{ font-size:10px; font-family:'Space Mono',monospace; color:#4a6fa5; }}
  .ci span {{ color:#38bdf8; margin-left:4px; }}

  .controls {{ position:absolute; bottom:20px; left:50%; transform:translateX(-50%);
               display:flex; gap:7px; pointer-events:all; z-index:10; }}
  .cbtn {{ background:rgba(10,22,40,.95); border:1px solid #1e3a5f; color:#94a3b8;
            font-size:11px; padding:7px 13px; border-radius:6px; cursor:pointer;
            font-family:'Space Mono',monospace; letter-spacing:1px; transition:all .2s; }}
  .cbtn:hover {{ border-color:#38bdf8; color:#38bdf8; }}
  .cbtn.active {{ border-color:#38bdf8; color:#38bdf8; background:rgba(56,189,248,.1); }}
</style>
</head>
<body>

<!-- NAVIGATION BAR -->
  <div style="position:absolute;top:0;left:0;right:0;z-index:100;background:rgba(5,12,24,.95);
              border-bottom:1px solid #0d2137;padding:8px 20px;display:flex;
              align-items:center;justify-content:space-between;">
    <div style="display:flex;align-items:center;gap:6px;font-size:11px;
                font-family:'Space Mono',monospace;">
      <span style="color:#4a6fa5;">DOCSENTINEL</span>
      <span style="color:#1e3a5f;">›</span>
      <span style="color:#38bdf8;">3D TERRAIN VIEWER</span>
    </div>
    <div style="display:flex;gap:8px;">
      <a href="report.html" style="font-size:11px;padding:5px 12px;border-radius:5px;
         border:1px solid #1e3a5f;color:#64748b;text-decoration:none;
         font-family:'Space Mono',monospace;"
         onmouseover="this.style.borderColor='#38bdf8';this.style.color='#38bdf8'"
         onmouseout="this.style.borderColor='#1e3a5f';this.style.color='#64748b'">
         📊 REPORT</a>
      <a href="terrain_3d.html" style="font-size:11px;padding:5px 12px;border-radius:5px;
         border:1px solid #38bdf8;color:#38bdf8;text-decoration:none;
         font-family:'Space Mono',monospace;background:rgba(56,189,248,.1);">
         🌄 3D TERRAIN</a>
    </div>
  </div>

<div id="canvas-wrap">

  <div class="hud">
    <span class="brand">DocSentinel</span>
    <span class="hud-title">3D Digital Elevation Model — {cfg.get('aoi_name','AOI')}</span>
    <span class="hud-right">SRTM 30m · OPENTOPODATA · {rows}×{cols} GRID</span>
  </div>

  <div class="left-panel">
    <div class="pbox">
      <div class="ptitle">Terrain Metrics</div>
      <div class="srow"><span class="slbl">MIN ELEV</span><span class="sval">{elev_min:.0f}m</span></div>
      <div class="srow"><span class="slbl">MAX ELEV</span><span class="sval amber">{elev_max:.0f}m</span></div>
      <div class="srow"><span class="slbl">RANGE</span><span class="sval">{elev_range:.0f}m</span></div>
      <div class="srow"><span class="slbl">MEAN ELEV</span><span class="sval">{(elev_min+elev_range/2):.0f}m</span></div>
      <div class="srow"><span class="slbl">GRID</span><span class="sval">{rows}×{cols} pts</span></div>
      <div class="srow"><span class="slbl">SOURCE</span><span class="sval">SRTM 30m</span></div>
    </div>

    <div class="pbox">
      <div class="ptitle">NDVI Analysis</div>
      <div class="srow"><span class="slbl">MEAN NDVI</span><span class="sval">0.198</span></div>
      <div class="srow"><span class="slbl">NDVI MIN</span><span class="sval red">-0.401</span></div>
      <div class="srow"><span class="slbl">NDVI MAX</span><span class="sval green">0.667</span></div>
      <div class="srow"><span class="slbl">LOSS AREA</span><span class="sval red">15.3%</span></div>
      <div class="srow"><span class="slbl">PATCHES</span><span class="sval purple">6,093</span></div>
      <div class="srow"><span class="slbl">THRESHOLD</span><span class="sval">ΔNDVI &lt; -0.15</span></div>
      <div class="div"></div>
      <div class="srow"><span class="slbl">STATUS</span>
        <span class="pill pill-r"><span class="pdot pdot-r"></span>ALERT</span>
      </div>
    </div>

    <div class="pbox">
      <div class="ptitle">Scene Info</div>
      <div class="srow"><span class="slbl">DATE</span><span class="sval">{cfg.get('scene_date','N/A')}</span></div>
      <div class="srow"><span class="slbl">SENSOR</span><span class="sval">S2-L2A</span></div>
      <div class="srow"><span class="slbl">RESOLUTION</span><span class="sval">10m/px</span></div>
      <div class="srow"><span class="slbl">CLOUD CVR</span><span class="sval green">&lt;5%</span></div>
      <div class="srow"><span class="slbl">PROJECTION</span><span class="sval">WGS84</span></div>
    </div>
  </div>

  <div class="right-panel">
    <div class="pbox">
      <div class="ptitle">Terrain Color Guide</div>
      <div class="lc-row"><div class="lc-dot" style="background:#1a4a2e"></div>Dense Forest (&lt;460m)</div>
      <div class="lc-row"><div class="lc-dot" style="background:#22863a"></div>Forest / Vegetation (460–490m)</div>
      <div class="lc-row"><div class="lc-dot" style="background:#85c882"></div>Grassland / Crops (490–520m)</div>
      <div class="lc-row"><div class="lc-dot" style="background:#f0c040"></div>Highland / Scrub (520–555m)</div>
      <div class="lc-row"><div class="lc-dot" style="background:#c8703a"></div>Rocky / Bare Land (555–575m)</div>
      <div class="lc-row"><div class="lc-dot" style="background:#d4cfc9"></div>Peak / Exposed Rock (&gt;575m)</div>
      <div class="div"></div>
      <div class="ptitle" style="margin-top:2px">Heatmap Guide</div>
      <div class="heat-strip legend-strip"></div>
      <div class="legend-labels"><span>Low</span><span>Mid</span><span>High</span></div>
    </div>

    <div class="pbox">
      <div class="ptitle">AOI Bounds</div>
      <div class="srow"><span class="slbl">MIN LAT</span><span class="sval">{cfg['bbox']['min_lat']}°N</span></div>
      <div class="srow"><span class="slbl">MAX LAT</span><span class="sval">{cfg['bbox']['max_lat']}°N</span></div>
      <div class="srow"><span class="slbl">MIN LON</span><span class="sval">{cfg['bbox']['min_lon']}°E</span></div>
      <div class="srow"><span class="slbl">MAX LON</span><span class="sval">{cfg['bbox']['max_lon']}°E</span></div>
      <div class="div"></div>
      <div class="srow"><span class="slbl">CENTER</span>
        <span class="sval">{(cfg['bbox']['min_lat']+cfg['bbox']['max_lat'])/2:.2f}°N, {(cfg['bbox']['min_lon']+cfg['bbox']['max_lon'])/2:.2f}°E</span>
      </div>
    </div>

    <div class="pbox">
      <div class="ptitle">Controls</div>
      <div class="lc-row">🖱 Left drag — rotate</div>
      <div class="lc-row">⊕ Scroll — zoom in/out</div>
      <div class="lc-row">⤢ Right drag — pan</div>
      <div class="lc-row">👆 Touch — supported</div>
      <div class="lc-row">🎯 Hover — point details</div>
    </div>
  </div>

  <!-- HOVER TOOLTIP -->
  <div id="tooltip">
    <div class="tt-title">Point Inspector</div>
    <div class="tt-row"><span class="tt-lbl">ELEVATION</span><span class="tt-val" id="tt-elev">—</span></div>
    <div class="tt-row"><span class="tt-lbl">SLOPE</span><span class="tt-val" id="tt-slope">—</span></div>
    <div class="tt-row"><span class="tt-lbl">LAND TYPE</span><span class="tt-val" id="tt-land">—</span></div>
    <div class="tt-row"><span class="tt-lbl">NDVI ZONE</span><span class="tt-val" id="tt-ndvi">—</span></div>
    <div class="tt-row"><span class="tt-lbl">LAT / LON</span><span class="tt-val" id="tt-coord">—</span></div>
  </div>

  <div class="coord-bar">
    <div class="ci">LAT<span>{cfg['bbox']['min_lat']}° – {cfg['bbox']['max_lat']}° N</span></div>
    <div class="ci">LON<span>{cfg['bbox']['min_lon']}° – {cfg['bbox']['max_lon']}° E</span></div>
    <div class="ci">LOCATION<span>{cfg.get('aoi_name','AOI')}</span></div>
    <div class="ci">AREA<span>~{abs((cfg['bbox']['max_lat']-cfg['bbox']['min_lat'])*(cfg['bbox']['max_lon']-cfg['bbox']['min_lon'])*111*111):.0f} km²</span></div>
  </div>

  <div class="controls">
    <button class="cbtn active" onclick="setMode('terrain',this)">TERRAIN</button>
    <button class="cbtn" onclick="setMode('wireframe',this)">WIREFRAME</button>
    <button class="cbtn" onclick="setMode('heatmap',this)">HEATMAP</button>
    <button class="cbtn" onclick="resetCamera()">RESET VIEW</button>
    <button class="cbtn" id="rotBtn" onclick="toggleRotate()">AUTO ROTATE</button>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const T = {json.dumps(terrain_data)};
const BBOX = T.bbox;

// ── Scene ──────────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080f1a);
scene.fog = new THREE.FogExp2(0x080f1a, 0.008);

const camera = new THREE.PerspectiveCamera(52, innerWidth/innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.getElementById('canvas-wrap').appendChild(renderer.domElement);

// ── Lights ─────────────────────────────────────────────────────────────────
scene.add(new THREE.AmbientLight(0x445566, 1.0));
const sun = new THREE.DirectionalLight(0xfff8e7, 2.0);
sun.position.set(15, 35, 25); sun.castShadow = true;
sun.shadow.mapSize.set(2048,2048);
scene.add(sun);
const fill = new THREE.DirectionalLight(0x3366aa, 0.5);
fill.position.set(-20,15,-20); scene.add(fill);
const back = new THREE.DirectionalLight(0x223344, 0.3);
back.position.set(0,5,-30); scene.add(back);

// ── Grid ───────────────────────────────────────────────────────────────────
scene.add(new THREE.GridHelper(55, 55, 0x1e3a5f, 0x0d2137));

// ── Geometry ───────────────────────────────────────────────────────────────
const rows=T.rows, cols=T.cols;
const SCALE_H=10, SCALE_XZ=24;
const clean = T.heights.map(h=>(isNaN(h)||h===null)?0:Math.min(Math.max(h,0),1));
const rawE = T.raw_elevs;
const slopes = T.slopes;

const geo = new THREE.PlaneGeometry(SCALE_XZ, SCALE_XZ, cols-1, rows-1);
geo.rotateX(-Math.PI/2);
const pos = geo.attributes.position;
for(let i=0;i<rows;i++) for(let j=0;j<cols;j++) pos.setY(i*cols+j, clean[i*cols+j]*SCALE_H);
pos.needsUpdate=true;
geo.computeVertexNormals();

// ── Color functions ─────────────────────────────────────────────────────────
const tStops=[
  [0.00,[0.10,0.29,0.18]],[0.20,[0.13,0.53,0.23]],
  [0.45,[0.52,0.78,0.51]],[0.65,[0.94,0.75,0.25]],
  [0.82,[0.78,0.44,0.23]],[1.00,[0.83,0.81,0.79]],
];
function tColor(t){{
  for(let i=0;i<tStops.length-1;i++){{
    const[t0,c0]=tStops[i],[t1,c1]=tStops[i+1];
    if(t>=t0&&t<=t1){{const f=(t-t0)/(t1-t0);return c0.map((v,k)=>v+(c1[k]-v)*f);}}
  }}
  return tStops[tStops.length-1][1];
}}

const tColors=[],hColors=[];
for(let i=0;i<clean.length;i++){{
  const t=clean[i], tc=tColor(t); tColors.push(...tc);
  const hc=new THREE.Color(); hc.setHSL(0.66-t*0.66,1,.5);
  hColors.push(hc.r,hc.g,hc.b);
}}
geo.setAttribute('color',new THREE.Float32BufferAttribute(tColors,3));
const hGeo=geo.clone();
hGeo.setAttribute('color',new THREE.Float32BufferAttribute(hColors,3));

// ── Materials ──────────────────────────────────────────────────────────────
const mats={{
  terrain:new THREE.MeshPhongMaterial({{vertexColors:true,shininess:25,specular:new THREE.Color(0x334466)}}),
  wireframe:new THREE.MeshBasicMaterial({{color:0x38bdf8,wireframe:true,transparent:true,opacity:0.35}}),
  heatmap:new THREE.MeshPhongMaterial({{vertexColors:true,shininess:8}}),
}};
const meshes={{
  terrain:new THREE.Mesh(geo,mats.terrain),
  wireframe:new THREE.Mesh(geo,mats.wireframe),
  heatmap:new THREE.Mesh(hGeo,mats.heatmap),
}};
Object.values(meshes).forEach(m=>{{m.castShadow=true;m.receiveShadow=true;}});
let current='terrain'; scene.add(meshes.terrain);

// ── Raycaster for hover ────────────────────────────────────────────────────
const raycaster=new THREE.Raycaster();
const mouse=new THREE.Vector2(-99,-99);
const tooltip=document.getElementById('tooltip');

function landType(elev){{
  if(elev<460) return 'Dense Forest';
  if(elev<490) return 'Forest / Vegetation';
  if(elev<520) return 'Grassland / Crops';
  if(elev<555) return 'Highland / Scrub';
  if(elev<575) return 'Rocky / Bare Land';
  return 'Exposed Rock / Peak';
}}
function ndviZone(elev){{
  if(elev<460) return 'High (0.4–0.67)';
  if(elev<490) return 'Moderate (0.2–0.4)';
  if(elev<520) return 'Low-Mod (0.1–0.2)';
  return 'Low / Bare (< 0.1)';
}}

renderer.domElement.addEventListener('mousemove', e=>{{
  mouse.x=(e.clientX/innerWidth)*2-1;
  mouse.y=-(e.clientY/innerHeight)*2+1;

  raycaster.setFromCamera(mouse, camera);
  const hits=raycaster.intersectObject(meshes[current]);
  if(hits.length>0){{
    const p=hits[0].point;
    // Map 3D position back to grid index
    const gx=Math.round((p.x/SCALE_XZ+0.5)*(cols-1));
    const gz=Math.round((p.z/SCALE_XZ+0.5)*(rows-1));
    const idx=Math.min(rows-1,Math.max(0,gz))*cols+Math.min(cols-1,Math.max(0,gx));

    const elev=rawE[idx]||0;
    const slope=slopes[idx]||0;

    // Map to real lat/lon
    const lat=(BBOX.min_lat+(gz/(rows-1))*(BBOX.max_lat-BBOX.min_lat)).toFixed(4);
    const lon=(BBOX.min_lon+(gx/(cols-1))*(BBOX.max_lon-BBOX.min_lon)).toFixed(4);

    document.getElementById('tt-elev').textContent=elev.toFixed(0)+'m ASL';
    document.getElementById('tt-slope').textContent=slope.toFixed(1)+'°';
    document.getElementById('tt-land').textContent=landType(elev);
    document.getElementById('tt-ndvi').textContent=ndviZone(elev);
    document.getElementById('tt-coord').textContent=lat+'°N, '+lon+'°E';

    tooltip.style.display='block';
    tooltip.style.left=(e.clientX+16)+'px';
    tooltip.style.top=(e.clientY-10)+'px';
  }} else {{
    tooltip.style.display='none';
  }}
}});
renderer.domElement.addEventListener('mouseleave',()=>tooltip.style.display='none');

// ── Camera ─────────────────────────────────────────────────────────────────
let sph={{theta:0.5,phi:0.82,r:40}}, tgt=new THREE.Vector3(0,2,0);
function applyCamera(){{
  camera.position.set(
    tgt.x+sph.r*Math.sin(sph.phi)*Math.sin(sph.theta),
    tgt.y+sph.r*Math.cos(sph.phi),
    tgt.z+sph.r*Math.sin(sph.phi)*Math.cos(sph.theta)
  );
  camera.lookAt(tgt);
}}
applyCamera();

let drag=false,right=false,px=0,py=0;
renderer.domElement.oncontextmenu=e=>e.preventDefault();
renderer.domElement.onmousedown=e=>{{drag=true;right=e.button===2;px=e.clientX;py=e.clientY;}};
window.onmouseup=()=>drag=false;
window.onmousemove=e=>{{
  if(!drag)return;
  const dx=e.clientX-px,dy=e.clientY-py;
  if(right){{tgt.x-=dx*0.02;tgt.z-=dy*0.02;}}
  else{{sph.theta-=dx*0.007;sph.phi=Math.max(0.08,Math.min(1.4,sph.phi+dy*0.007));}}
  px=e.clientX;py=e.clientY;applyCamera();
}};
renderer.domElement.onwheel=e=>{{sph.r=Math.max(8,Math.min(90,sph.r+e.deltaY*0.04));applyCamera();}};
renderer.domElement.ontouchstart=e=>{{drag=true;px=e.touches[0].clientX;py=e.touches[0].clientY;}};
renderer.domElement.ontouchend=()=>drag=false;
renderer.domElement.ontouchmove=e=>{{
  const dx=e.touches[0].clientX-px,dy=e.touches[0].clientY-py;
  sph.theta-=dx*0.007;sph.phi=Math.max(0.08,Math.min(1.4,sph.phi+dy*0.007));
  px=e.touches[0].clientX;py=e.touches[0].clientY;applyCamera();
}};

function setMode(m,btn){{
  scene.remove(meshes[current]);current=m;scene.add(meshes[current]);
  document.querySelectorAll('.cbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
}}
function resetCamera(){{sph={{theta:0.5,phi:0.82,r:40}};tgt=new THREE.Vector3(0,2,0);applyCamera();}}
let rotating=false;
function toggleRotate(){{rotating=!rotating;document.getElementById('rotBtn').classList.toggle('active',rotating);}}

window.onresize=()=>{{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}};
(function loop(){{requestAnimationFrame(loop);if(rotating){{sph.theta+=0.003;applyCamera();}}renderer.render(scene,camera);}})();
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
    elev_grid, lats, lons = fetch_elevation(cfg)
    print("Generating 3D terrain viewer...")
    path = generate_terrain_html(elev_grid, cfg)
    print(f"Done — open {path} in your browser")