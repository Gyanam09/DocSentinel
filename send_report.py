import os
import base64
import resend
from dotenv import load_dotenv

load_dotenv()

# ─── Configure Resend ────────────────────────────────────────────────────
resend.api_key = os.getenv("RESEND_API_KEY")

# ─── Report data — in production this comes from calculate_ndvi.py ───────
report_data = {
    "client_email":  "aisebanai@gmail.com",  # replace with real client email
    "aoi_name":      "Bhopal Test AOI",
    "scene_date":    "2026-05-25",
    "mean_ndvi":     0.198,
    "loss_pct":      15.32,
    "loss_patches":  6093,
    "alert":         True,
}

# ─── Read the PDF as base64 attachment ───────────────────────────────────
pdf_path = "output/report.pdf"
with open(pdf_path, "rb") as f:
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