import numpy as np
import rasterio
from rasterio.enums import Resampling
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cv2
import os

# ─── Step 1: Load the two band files ────────────────────────────────────
def load_band(filepath):
    with rasterio.open(filepath) as src:
        # Read as float so division works correctly
        band = src.read(1).astype("float32")
        profile = src.profile  # saves metadata like CRS, transform
    return band, profile

print("Loading bands...")
red, profile = load_band("bands/B04.jp2")
nir, _       = load_band("bands/B08.jp2")
print(f"Band shape: {red.shape}")  # e.g. (10980, 10980) pixels


# ─── Step 2: Calculate NDVI ──────────────────────────────────────────────
print("Calculating NDVI...")

# Avoid division by zero where both bands are 0
np.seterr(divide="ignore", invalid="ignore")

ndvi = np.where(
    (nir + red) == 0,
    0,                            # if both are 0, NDVI = 0
    (nir - red) / (nir + red)    # the actual formula
)

print(f"NDVI range: {ndvi.min():.3f} to {ndvi.max():.3f}")
print(f"Mean NDVI:  {ndvi.mean():.3f}")


# ─── Step 3: Save NDVI as a GeoTIFF ─────────────────────────────────────
os.makedirs("output", exist_ok=True)

ndvi_profile = profile.copy()
ndvi_profile.update(dtype="float32", count=1, driver="GTiff")

with rasterio.open("output/ndvi_t1.tif", "w", **ndvi_profile) as dst:
    dst.write(ndvi, 1)

print("Saved → output/ndvi_t1.tif")


# ─── Step 4: Visualize NDVI as a color map ──────────────────────────────
print("Generating NDVI map image...")

# Clip to valid vegetation range for better contrast
ndvi_display = np.clip(ndvi, -0.2, 0.8)

plt.figure(figsize=(10, 10))
plt.imshow(ndvi_display, cmap="RdYlGn")  # Red = dead, Green = healthy
plt.colorbar(label="NDVI value")
plt.title("NDVI Map — T1 (current)")
plt.axis("off")
plt.tight_layout()
plt.savefig("output/ndvi_t1_map.png", dpi=150)
plt.close()

print("Saved → output/ndvi_t1_map.png")


# ─── Step 5: Simulate T0 (last month) for change detection ──────────────
# In production this will be a real previous scene.
# For now we simulate a "healthier" past state to test the pipeline.
print("\nSimulating T0 (baseline) for change detection test...")

ndvi_t0 = np.clip(ndvi + 0.15, -1, 1)  # pretend last month was greener


# ─── Step 6: Change detection — find canopy loss areas ──────────────────
print("Running change detection...")

delta = ndvi - ndvi_t0  # negative = vegetation loss

# Threshold: flag pixels where NDVI dropped more than 0.15
THRESHOLD = -0.15
loss_mask = (delta < THRESHOLD).astype("uint8")  # 1 = loss, 0 = no change

loss_pixels = int(loss_mask.sum())
total_pixels = loss_mask.size
loss_pct = (loss_pixels / total_pixels) * 100

print(f"Loss pixels detected: {loss_pixels:,} ({loss_pct:.2f}% of AOI)")


# ─── Step 7: Draw contours around loss areas using OpenCV ───────────────
print("Drawing loss contours...")

# Scale NDVI to 0–255 grayscale image for display
ndvi_gray = ((np.clip(ndvi, -1, 1) + 1) / 2 * 255).astype("uint8")
display_img = cv2.cvtColor(ndvi_gray, cv2.COLOR_GRAY2BGR)

# Find contours around flagged loss regions
contours, _ = cv2.findContours(loss_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Only draw contours larger than 50 pixels (filter noise)
significant = [c for c in contours if cv2.contourArea(c) > 50]
cv2.drawContours(display_img, significant, -1, (0, 0, 255), 2)  # red outlines

print(f"Significant loss patches: {len(significant)}")

cv2.imwrite("output/loss_contours.png", display_img)
print("Saved → output/loss_contours.png")


# ─── Step 8: Print final summary ────────────────────────────────────────
print("\n" + "="*50)
print("NDVI ANALYSIS COMPLETE")
print("="*50)
print(f"  Scene date   : 2026-05-25")
print(f"  Mean NDVI    : {ndvi.mean():.3f}")
print(f"  Loss pixels  : {loss_pixels:,}")
print(f"  Loss area    : {loss_pct:.2f}% of AOI")
print(f"  Loss patches : {len(significant)}")

if loss_pct > 1.0:
    print("\n  ⚠ ALERT: Significant canopy loss detected!")
else:
    print("\n  ✓ No significant change detected.")

print("\nOutput files:")
print("  output/ndvi_t1.tif       ← raw NDVI data")
print("  output/ndvi_t1_map.png   ← color NDVI map")
print("  output/loss_contours.png ← annotated loss map")