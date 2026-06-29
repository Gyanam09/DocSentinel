import os
import base64
import io
import re
import sys
import zipfile
import pdfkit
import resend
from PIL import Image
from dotenv import load_dotenv
from config import load_config

Image.MAX_IMAGE_PIXELS = None
load_dotenv()

# â”€â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
resend.api_key = os.getenv("RESEND_API_KEY")
cfg = load_config()

import json as _json

ndvi_results = {}
try:
    with open("output/ndvi_results.json", "r") as f:
        ndvi_results = _json.load(f)
except FileNotFoundError:
    ndvi_results = {"mean_ndvi": 0, "loss_pct": 0, "loss_patches": 0, "alert": False}

report_data = {
    "client_email":  cfg["client_email"],
    "aoi_name":      cfg.get("aoi_name", "AOI"),
    "scene_date":    cfg["scene_date"],
    "mean_ndvi":     ndvi_results.get("mean_ndvi", 0),
    "loss_pct":      ndvi_results.get("loss_pct", 0),
    "loss_patches":  ndvi_results.get("loss_patches", 0),
    "alert":         ndvi_results.get("alert", False),
}

# â”€â”€â”€ Compress images â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def compress_image(path, max_width=800):
    img = Image.open(path)
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.convert("RGBA").split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    buf.seek(0)
    return buf

print("Compressing maps for email...")
for fname, outname in [
    ("output/ndvi_t1_map.png",   "output/ndvi_t1_map_sm.png"),
    ("output/loss_contours.png", "output/loss_contours_sm.png"),
    ("output/true_color.png",    "output/true_color_sm.png"),
]:
    with open(outname, "wb") as f:
        f.write(compress_image(fname).read())
print("Compressed maps saved.")

# â”€â”€â”€ Regenerate compressed PDF â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if sys.platform == "win32":
    wk_path = os.environ.get(
        "WKHTMLTOPDF_PATH",
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
    )
else:
    wk_path = os.environ.get("WKHTMLTOPDF_PATH", "/usr/bin/wkhtmltopdf")

config_pdf = pdfkit.configuration(wkhtmltopdf=wk_path)
options = {"enable-local-file-access": "", "quiet": ""}

with open("output/report.html", "r", encoding="utf-8") as f:
    html = f.read()

html_sm = (html
    .replace("ndvi_t1_map.png",   "ndvi_t1_map_sm.png")
    .replace("loss_contours.png", "loss_contours_sm.png")
    .replace("true_color.png",    "true_color_sm.png"))

with open("output/report_email.html", "w", encoding="utf-8") as f:
    f.write(html_sm)

email_pdf = "output/report_email.pdf"
pdfkit.from_file("output/report_email.html", email_pdf,
                 configuration=config_pdf, options=options)
print(f"Email PDF saved -> {email_pdf}")

with open(email_pdf, "rb") as f:
    pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

# â”€â”€â”€ Make HTML self-contained (embed images as base64) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def embed_images(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    img_pattern = re.compile(
        r'src=["\']([^"\']+\.(png|jpg|jpeg))["\']', re.IGNORECASE)

    def replace_with_base64(match):
        img_path = match.group(1)
        if not os.path.isabs(img_path):
            img_path = os.path.join("output", os.path.basename(img_path))
        if os.path.exists(img_path):
            img = Image.open(img_path)
            if img.width > 600:
                ratio = 600 / img.width
                img = img.resize((600, int(img.height * ratio)), Image.LANCZOS)
            if img.mode not in ("RGB",):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=55)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f'src="data:image/jpeg;base64,{b64}"'
        return match.group(0)

    return img_pattern.sub(replace_with_base64, html)

print("Embedding images into standalone HTML...")
report_standalone = embed_images("output/report.html")
with open("output/report_standalone.html", "w", encoding="utf-8") as f:
    f.write(report_standalone)

# â”€â”€â”€ Create ZIP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
zip_path = "output/docsentinel_report.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write("output/report_standalone.html", "report.html")
    zf.write("output/terrain_3d.html", "terrain_3d.html")

zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
print(f"ZIP created -> {zip_path} ({zip_size_mb:.1f} MB)")

with open(zip_path, "rb") as f:
    zip_base64 = base64.b64encode(f.read()).decode("utf-8")

# â”€â”€â”€ Build attachments list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
attachments = [{
    "filename": f"DocSentinel_Report_{report_data['scene_date']}.pdf",
    "content": pdf_base64,
}]

if zip_size_mb < 5:
    attachments.append({
        "filename": f"DocSentinel_Interactive_{report_data['scene_date']}.zip",
        "content": zip_base64,
    })
    print(f"ZIP ({zip_size_mb:.1f}MB) - attaching to email")
else:
    print(f"ZIP too large ({zip_size_mb:.1f}MB) - sending PDF only")

# â”€â”€â”€ Email content â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
links_html = """
<div style="margin:20px 0;padding:14px 16px;background:#0d2137;border-radius:8px;
            border-left:3px solid #38bdf8;">
  <p style="font-size:12px;color:#64748b;margin-bottom:10px;
             font-family:monospace;letter-spacing:1px;">REPORT ACCESS</p>
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="padding:6px 0;">
        <span style="font-size:13px;color:#94a3b8;">Full analysis report</span>
      </td>
      <td style="text-align:right;padding:6px 0;">
        <span style="font-size:12px;color:#38bdf8;font-family:monospace;">
          Attached as PDF</span>
      </td>
    </tr>
    <tr>
      <td style="padding:6px 0;">
        <span style="font-size:13px;color:#94a3b8;">Interactive terrain viewer</span>
      </td>
      <td style="text-align:right;padding:6px 0;">
        <span style="font-size:12px;color:#38bdf8;font-family:monospace;">
          Included in ZIP attachment</span>
      </td>
    </tr>
  </table>
</div>
"""

if report_data["alert"]:
    subject = f"ALERT: Canopy Loss Detected - {report_data['aoi_name']}"
    intro = f"""
    <p style="font-size:14px;color:#e2e8f0;line-height:1.7;">
      A significant vegetation change has been detected on your monitored land parcel.
    </p>
    <ul style="margin:12px 0;padding-left:20px;font-size:13px;color:#94a3b8;line-height:2;">
      <li><strong style="color:#e2e8f0;">AOI:</strong> {report_data['aoi_name']}</li>
      <li><strong style="color:#e2e8f0;">Scene date:</strong> {report_data['scene_date']}</li>
      <li><strong style="color:#e2e8f0;">Mean NDVI:</strong> {report_data['mean_ndvi']:.3f}</li>
      <li><strong style="color:#e2e8f0;">Loss area:</strong> {report_data['loss_pct']:.1f}% of AOI</li>
      <li><strong style="color:#e2e8f0;">Loss patches:</strong> {report_data['loss_patches']}</li>
    </ul>
    {links_html}
    <p style="font-size:13px;color:#94a3b8;">
      Full report attached as PDF. Extract the ZIP for the interactive
      HTML report and 3D terrain viewer.
    </p>
    """
else:
    subject = f"Monthly Report - {report_data['aoi_name']}"
    intro = f"""
    <p style="font-size:14px;color:#e2e8f0;line-height:1.7;">
      Your monthly land monitoring report is ready. No significant change detected.
    </p>
    <ul style="margin:12px 0;padding-left:20px;font-size:13px;color:#94a3b8;line-height:2;">
      <li><strong style="color:#e2e8f0;">AOI:</strong> {report_data['aoi_name']}</li>
      <li><strong style="color:#e2e8f0;">Scene date:</strong> {report_data['scene_date']}</li>
      <li><strong style="color:#e2e8f0;">Mean NDVI:</strong> {report_data['mean_ndvi']:.3f}</li>
    </ul>
    {links_html}
    """

email_html = f"""
<html>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;
             padding:24px;color:#e2e8f0;background:#080f1a;">
  <div style="border-left:4px solid {'#ef4444' if report_data['alert'] else '#22c55e'};
              padding-left:16px;margin-bottom:24px;">
    <h2 style="margin:0 0 4px;font-size:18px;color:#f1f5f9;">
      DocSentinel Land Monitoring</h2>
    <p style="margin:0;color:#64748b;font-size:13px;">
      Automated satellite analysis report</p>
  </div>
  {intro}
  <p style="font-size:12px;color:#1e3a5f;border-top:1px solid #1e3a5f;
             padding-top:16px;margin-top:32px;">
    Powered by Sentinel-2 (ESA Copernicus), NASA GIBS, SRTM, and DocSentinel
  </p>
</body>
</html>
"""

# â”€â”€â”€ Send â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"Sending report to {report_data['client_email']}...")

params = {
    "from": "DocSentinel <onboarding@resend.dev>",
    "to": [report_data["client_email"]],
    "subject": subject,
    "html": email_html,
    "attachments": attachments,
}

response = resend.Emails.send(params)
print(f"Email sent! ID: {response['id']}")

