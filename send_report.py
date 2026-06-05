import os
import base64
import resend
from dotenv import load_dotenv

load_dotenv()

# ─── Configure Resend ────────────────────────────────────────────────────
resend.api_key = os.getenv("RESEND_API_KEY")

# ─── Report data — in production this comes from calculate_ndvi.py ───────
from config import load_config
cfg = load_config()

report_data = {
    "client_email":  cfg["client_email"],
    "aoi_name":      cfg.get("aoi_name", "AOI"),
    "scene_date":    cfg["scene_date"],
    "mean_ndvi":     0.198,
    "loss_pct":      15.32,
    "loss_patches":  6093,
    "alert":         True,
}


# ─── Read and compress PDF for email attachment ───────────────────────────
from PIL import Image
import io

pdf_path = "output/report.pdf"

# Compress the three map images before generating the final email PDF
# Resend limit is 40MB — we resize maps to email-friendly dimensions
def compress_image(path, max_width=800):
    img = Image.open(path)
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    
    # Handle transparent/RGBA modes by pasting onto a white background
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
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
compress_image("output/ndvi_t1_map.png").read()  # pre-warm

# Save compressed versions for the email PDF
for fname, outname in [
    ("output/ndvi_t1_map.png",    "output/ndvi_t1_map_sm.png"),
    ("output/loss_contours.png",  "output/loss_contours_sm.png"),
    ("output/true_color.png",     "output/true_color_sm.png"),
]:
    buf = compress_image(fname)
    with open(outname, "wb") as f:
        f.write(buf.read())

print("Compressed maps saved.")

# Regenerate PDF with compressed images for email
import pdfkit, sys, os
if sys.platform == "win32":
    wk_path = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
else:
    wk_path = os.environ.get("WKHTMLTOPDF_PATH", "/usr/bin/wkhtmltopdf")

config = pdfkit.configuration(wkhtmltopdf=wk_path)
options = {"enable-local-file-access": "", "quiet": ""}

# Read report HTML and swap image paths to compressed versions
with open("output/report.html", "r", encoding="utf-8") as f:
    html = f.read()

html_sm = html \
    .replace("ndvi_t1_map.png",   "ndvi_t1_map_sm.png") \
    .replace("loss_contours.png", "loss_contours_sm.png") \
    .replace("true_color.png",    "true_color_sm.png")

with open("output/report_email.html", "w", encoding="utf-8") as f:
    f.write(html_sm)

email_pdf = "output/report_email.pdf"
pdfkit.from_file("output/report_email.html", email_pdf, configuration=config, options=options)
print(f"Email PDF saved -> {email_pdf}")

# Attach the compressed PDF
with open(email_pdf, "rb") as f:
    pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

# ─── Build email subject and intro ───────────────────────────────────────
if report_data["alert"]:
    subject = f"⚠ ALERT: Canopy Loss Detected — {report_data['aoi_name']}"
    intro = f"""
    <p>A significant vegetation change has been detected on your monitored land parcel.</p>
    <ul>
        <li><strong>AOI:</strong> {report_data['aoi_name']}</li>
        <li><strong>Scene date:</strong> {report_data['scene_date']}</li>
        <li><strong>Mean NDVI:</strong> {report_data['mean_ndvi']:.3f}</li>
        <li><strong>Loss area:</strong> {report_data['loss_pct']:.1f}% of AOI</li>
        <li><strong>Loss patches:</strong> {report_data['loss_patches']}</li>
    </ul>
    <p>The full analysis report is attached as a PDF.</p>
    """
else:
    subject = f"✓ Monthly Report — {report_data['aoi_name']} — No Change Detected"
    intro = f"""
    <p>Your monthly land monitoring report is ready. No significant vegetation change was detected.</p>
    <ul>
        <li><strong>AOI:</strong> {report_data['aoi_name']}</li>
        <li><strong>Scene date:</strong> {report_data['scene_date']}</li>
        <li><strong>Mean NDVI:</strong> {report_data['mean_ndvi']:.3f}</li>
    </ul>
    <p>The full analysis report is attached as a PDF.</p>
    """

# ─── Build full HTML email body ───────────────────────────────────────────
email_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #1a1a1a;">

  <div style="border-left: 4px solid {'#c0392b' if report_data['alert'] else '#27ae60'}; padding-left: 16px; margin-bottom: 24px;">
    <h2 style="margin: 0 0 4px; font-size: 18px;">DocSentinel Land Monitoring</h2>
    <p style="margin: 0; color: #666; font-size: 13px;">Automated satellite analysis report</p>
  </div>

  {intro}

  <p style="font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 16px; margin-top: 32px;">
    Powered by Sentinel-2 (ESA Copernicus) · 10m resolution · DocSentinel
  </p>

</body>
</html>
"""

# ─── Send the email ───────────────────────────────────────────────────────
print(f"Sending report to {report_data['client_email']}...")

params = {
    "from": "DocSentinel <onboarding@resend.dev>",  # use resend's test sender for now
    "to": [report_data["client_email"]],
    "subject": subject,
    "html": email_html,
    "attachments": [
        {
            "filename": f"DocSentinel_Report_{report_data['scene_date']}.pdf",
            "content": pdf_base64,
        }
    ],
}

response = resend.Emails.send(params)
print(f"Email sent! ID: {response['id']}")