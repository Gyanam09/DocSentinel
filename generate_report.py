import os
from datetime import date
from jinja2 import Environment, FileSystemLoader

# ─── Report data — pulled from calculate_ndvi.py results ────────────────
# In production these values will be passed in dynamically.
# For now we use the values from our last NDVI run.

report_data = {
    "scene_date":     "2026-05-25",
    "generated_date": str(date.today()),
    "aoi_name":       "Bhopal Test AOI",
    "mean_ndvi":      0.198,
    "loss_pct":       15.32,
    "loss_patches":   6093,
    "alert":          True,   # True if loss_pct > 1.0
    "ndvi_map_path":  os.path.abspath("output/ndvi_t1_map.png"),
    "loss_map_path":  os.path.abspath("output/loss_contours.png"),
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