import os
from datetime import date
from jinja2 import Environment, FileSystemLoader
from fetch_gibs import fetch_gibs_thumbnail
from config import load_config
from fetch_location import fetch_location_name

# ─── Load config first ───────────────────────────────────────────────────
cfg = load_config()
BBOX = cfg["bbox_tuple"]

# ─── Fetch fresh true-color image from NASA GIBS ─────────────────────────
print("Fetching NASA GIBS true-color image...")
fetch_gibs_thumbnail(BBOX, cfg=cfg, output_path="output/true_color.png")

# ─── Auto-detect location name ───────────────────────────────────────────
location_name, addr = fetch_location_name(cfg)

# ─── Report data ──────────────────────────────────────────────────────────
report_data = {
    "scene_date":       cfg["scene_date"],
    "generated_date":   str(date.today()),
    "aoi_name":         location_name,
    "country":          addr.get("country", ""),
    "state":            addr.get("state", ""),
    "mean_ndvi":        0.198,
    "loss_pct":         15.32,
    "loss_patches":     6093,
    "alert":            True,
    "ndvi_map_path":    os.path.abspath("output/ndvi_t1_map.png"),
    "loss_map_path":    os.path.abspath("output/loss_contours.png"),
    "true_color_path":  os.path.abspath("output/true_color.png"),
    "elevation_path":   os.path.abspath("output/elevation_map.png"),
    "fire_map_path":    os.path.abspath("output/fire_map.png"),
    "osm_land_use":     None,
    "bbox":             cfg["bbox"],
}

# ─── Render HTML from Jinja2 template ───────────────────────────────────
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("report.html")
html_output = template.render(**report_data)

# ─── Save rendered HTML ──────────────────────────────────────────────────
os.makedirs("output", exist_ok=True)
output_path = "output/report.html"

with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_output)

print(f"Report saved → {output_path}")
print("Open it in your browser to preview.")

# ─── Phase 5b: Export to PDF ────────────────────────────────────────────
import pdfkit

import sys

if sys.platform == "win32":
    wkhtmltopdf_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
else:
    wkhtmltopdf_path = os.environ.get("WKHTMLTOPDF_PATH", "/usr/bin/wkhtmltopdf")

config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

options = {
    "enable-local-file-access": "",
    "quiet": ""
}

pdf_path = "output/report.pdf"
pdfkit.from_file(output_path, pdf_path, configuration=config, options=options)
print(f"PDF saved  → {pdf_path}")