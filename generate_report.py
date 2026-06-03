import os
from datetime import date
from jinja2 import Environment, FileSystemLoader
from fetch_gibs import fetch_gibs_thumbnail

# ─── Fetch fresh true-color image from NASA GIBS ─────────────────────────
BBOX = (23.15, 77.35, 23.35, 77.55)  # same AOI as download_bands.py
print("Fetching NASA GIBS true-color image...")
fetch_gibs_thumbnail(BBOX, output_path="output/true_color.png")

# ─── Report data ──────────────────────────────────────────────────────────
report_data = {
    "scene_date":        "2026-05-25",
    "generated_date":    str(date.today()),
    "aoi_name":          "Bhopal Test AOI",
    "mean_ndvi":         0.198,
    "loss_pct":          15.32,
    "loss_patches":      6093,
    "alert":             True,
    "ndvi_map_path":     os.path.abspath("output/ndvi_t1_map.png"),
    "loss_map_path":     os.path.abspath("output/loss_contours.png"),
    "true_color_path":   os.path.abspath("output/true_color.png"),  # NEW
    "osm_land_use":      None,   # None = OSM unavailable, report handles gracefully
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

config = pdfkit.configuration(
    wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
)

options = {
    "enable-local-file-access": "",
    "quiet": ""
}

pdf_path = "output/report.pdf"
pdfkit.from_file(output_path, pdf_path, configuration=config, options=options)
print(f"PDF saved  → {pdf_path}")