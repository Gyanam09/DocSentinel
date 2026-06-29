import json
import os
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import transform

from config import load_config


cfg = load_config()


def load_band_metadata():
    metadata_path = "bands/scene_metadata.json"
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(
            "Missing bands/scene_metadata.json. Run download_bands.py successfully before NDVI."
        )
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    bands = metadata.get("bands", {})
    missing = [band for band in ("B04", "B08") if not bands.get(band)]
    if missing:
        raise FileNotFoundError(f"Missing required downloaded band metadata: {', '.join(missing)}")

    for band in ("B04", "B08"):
        if not os.path.exists(bands[band]):
            raise FileNotFoundError(f"Downloaded {band} file not found: {bands[band]}")

    return metadata


def load_band(filepath, bbox=None):
    with rasterio.open(filepath) as src:
        if bbox is not None:
            min_lat, min_lon, max_lat, max_lon = bbox
            xs, ys = transform("EPSG:4326", src.crs, [min_lon, max_lon], [min_lat, max_lat])

            inv_trans = ~src.transform
            col_min, row_max = inv_trans * (xs[0], ys[0])
            col_max, row_min = inv_trans * (xs[1], ys[1])

            col_start = max(0, int(np.floor(min(col_min, col_max))))
            col_end = min(src.width, int(np.ceil(max(col_min, col_max))))
            row_start = max(0, int(np.floor(min(row_min, row_max))))
            row_end = min(src.height, int(np.ceil(max(row_min, row_max))))

            if col_start < col_end and row_start < row_end:
                window = rasterio.windows.Window(
                    col_start,
                    row_start,
                    col_end - col_start,
                    row_end - row_start,
                )
                band = src.read(1, window=window).astype("float32")
                profile = src.profile
                new_transform = rasterio.windows.transform(window, src.transform)
                profile.update(
                    {
                        "height": window.height,
                        "width": window.width,
                        "transform": new_transform,
                    }
                )
                return band, profile

        band = src.read(1).astype("float32")
        profile = src.profile
    return band, profile


def crop_and_save_tci(filepath, bbox, output_path="output/true_color.png"):
    from PIL import Image

    with rasterio.open(filepath) as src:
        min_lat, min_lon, max_lat, max_lon = bbox
        xs, ys = transform("EPSG:4326", src.crs, [min_lon, max_lon], [min_lat, max_lat])

        inv_trans = ~src.transform
        col_min, row_max = inv_trans * (xs[0], ys[0])
        col_max, row_min = inv_trans * (xs[1], ys[1])

        col_start = max(0, int(np.floor(min(col_min, col_max))))
        col_end = min(src.width, int(np.ceil(max(col_min, col_max))))
        row_start = max(0, int(np.floor(min(row_min, row_max))))
        row_end = min(src.height, int(np.ceil(max(row_min, row_max))))

        if col_start < col_end and row_start < row_end:
            window = rasterio.windows.Window(
                col_start,
                row_start,
                col_end - col_start,
                row_end - row_start,
            )
            rgb = src.read([1, 2, 3], window=window)
            rgb = np.moveaxis(rgb, 0, -1)
            img = Image.fromarray(rgb.astype("uint8"))
            img.save(output_path)
            print(f"Saved cropped high-resolution TCI -> {output_path}")
            return True
    return False


def main():
    metadata = load_band_metadata()
    bbox = cfg.get("bbox_tuple")
    bands = metadata["bands"]

    print("Loading bands...")
    print(f"  Scene: {metadata.get('scene_name', 'unknown')}")
    print(f"  Scene date: {metadata.get('scene_date', cfg['scene_date'])}")
    red, profile = load_band(bands["B04"], bbox)
    nir, _ = load_band(bands["B08"], bbox)
    print(f"Band shape: {red.shape}")

    print("Calculating NDVI...")
    np.seterr(divide="ignore", invalid="ignore")
    ndvi = np.where((nir + red) == 0, 0, (nir - red) / (nir + red))

    print(f"NDVI range: {ndvi.min():.3f} to {ndvi.max():.3f}")
    print(f"Mean NDVI:  {ndvi.mean():.3f}")

    os.makedirs("output", exist_ok=True)
    ndvi_profile = profile.copy()
    ndvi_profile.update(dtype="float32", count=1, driver="GTiff")

    with rasterio.open("output/ndvi_t1.tif", "w", **ndvi_profile) as dst:
        dst.write(ndvi, 1)
    print("Saved -> output/ndvi_t1.tif")

    print("Generating NDVI map image...")
    ndvi_display = np.clip(ndvi, -0.2, 0.8)
    plt.figure(figsize=(10, 10))
    plt.imshow(ndvi_display, cmap="RdYlGn")
    plt.colorbar(label="NDVI value")
    plt.title("NDVI Map - T1 (current)")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig("output/ndvi_t1_map.png", dpi=150)
    plt.close()
    print("Saved -> output/ndvi_t1_map.png")

    print("\nSimulating T0 (baseline) for change detection test...")
    ndvi_t0 = np.clip(ndvi + 0.15, -1, 1)

    print("Running change detection...")
    delta = ndvi - ndvi_t0
    threshold = float(cfg.get("ndvi_loss_threshold", -0.15))
    loss_mask = (delta < threshold).astype("uint8")

    loss_pixels = int(loss_mask.sum())
    total_pixels = loss_mask.size
    loss_pct = (loss_pixels / total_pixels) * 100
    print(f"Loss pixels detected: {loss_pixels:,} ({loss_pct:.2f}% of AOI)")

    print("Drawing loss contours...")
    ndvi_gray = ((np.clip(ndvi, -1, 1) + 1) / 2 * 255).astype("uint8")
    display_img = cv2.cvtColor(ndvi_gray, cv2.COLOR_GRAY2BGR)
    contours, _ = cv2.findContours(loss_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    significant = [c for c in contours if cv2.contourArea(c) > 50]
    cv2.drawContours(display_img, significant, -1, (0, 0, 255), 2)

    print(f"Significant loss patches: {len(significant)}")
    cv2.imwrite("output/loss_contours.png", display_img)
    print("Saved -> output/loss_contours.png")

    scene_date = metadata.get("scene_date", cfg["scene_date"])
    print("\n" + "=" * 50)
    print("NDVI ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"  Scene date   : {scene_date}")
    print(f"  Mean NDVI    : {ndvi.mean():.3f}")
    print(f"  Loss pixels  : {loss_pixels:,}")
    print(f"  Loss area    : {loss_pct:.2f}% of AOI")
    print(f"  Loss patches : {len(significant)}")
    print("\n  ALERT: Significant canopy loss detected!" if loss_pct > 1.0 else "\n  No significant change detected.")

    print("\nOutput files:")
    print("  output/ndvi_t1.tif       <- raw NDVI data")
    print("  output/ndvi_t1_map.png   <- color NDVI map")
    print("  output/loss_contours.png <- annotated loss map")

    ndvi_results = {
        "mean_ndvi": round(float(ndvi.mean()), 4),
        "ndvi_min": round(float(ndvi.min()), 4),
        "ndvi_max": round(float(ndvi.max()), 4),
        "loss_pct": round(loss_pct, 2),
        "loss_patches": len(significant),
        "loss_pixels": loss_pixels,
        "alert": loss_pct > 1.0,
        "scene_date": scene_date,
        "scene_name": metadata.get("scene_name"),
        "scene_id": metadata.get("scene_id"),
    }

    with open("output/ndvi_results.json", "w", encoding="utf-8") as f:
        json.dump(ndvi_results, f, indent=2)
        f.write("\n")
    print("Results saved -> output/ndvi_results.json")

    if bands.get("TCI") and os.path.exists(bands["TCI"]):
        print("Generating cropped high-resolution true-color image from Sentinel-2 TCI...")
        crop_and_save_tci(bands["TCI"], bbox, "output/true_color.png")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"NDVI calculation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
