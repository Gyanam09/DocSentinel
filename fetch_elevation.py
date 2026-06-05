import requests
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import os
from config import load_config

def fetch_elevation(cfg):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox
    GRID = cfg.get("elevation_grid_size", 50)

    lats = np.linspace(min_lat, max_lat, GRID)
    lons = np.linspace(min_lon, max_lon, GRID)

    print(f"Fetching {GRID}x{GRID} elevation grid ({GRID*GRID} points)...")
    all_points = [(lats[i], lons[j]) for i in range(GRID) for j in range(GRID)]
    elevations = []

    for batch_start in range(0, len(all_points), 100):
        batch = all_points[batch_start:batch_start+100]
        locations = "|".join([f"{lat},{lon}" for lat, lon in batch])
        r = requests.get(
            "https://api.opentopodata.org/v1/srtm30m",
            params={"locations": locations},
            timeout=30
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            for res in results:
                elev = res.get("elevation")
                elevations.append(float(elev) if elev is not None else 0.0)
            print(f"  Batch {batch_start//100 + 1}/{(len(all_points)+99)//100} done")
        else:
            print(f"  Batch failed: HTTP {r.status_code}")
            elevations.extend([0.0] * len(batch))

    elev_grid = np.array(elevations[:GRID*GRID]).reshape(GRID, GRID)

    # Smooth out any spike artifacts using a simple 3x3 median filter
    from scipy.ndimage import median_filter
    elev_grid = median_filter(elev_grid, size=3)

    print(f"Elevation range: {elev_grid.min():.0f}m — {elev_grid.max():.0f}m")
    print(f"Mean elevation:  {elev_grid.mean():.0f}m")
    return elev_grid, lats, lons


def render_elevation_map(elev_grid, lats, lons, output_path="output/elevation_map.png"):
    fig, ax = plt.subplots(1, 1, figsize=(8, 8), facecolor="#0a1628")
    ax.set_facecolor("#0a1628")

    cmap = plt.cm.terrain
    im = ax.imshow(
        elev_grid,
        cmap=cmap,
        extent=[lons.min(), lons.max(), lats.min(), lats.max()],
        origin="lower",
        aspect="auto",
        interpolation="bilinear"
    )

    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("Elevation (m)", color="white", fontsize=10)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=8)

    elev_min = int(elev_grid.min())
    elev_max = int(elev_grid.max())
    elev_range = elev_max - elev_min
    bands = []
    n_bands = 6
    for i in range(n_bands):
        lo = elev_min + int(i * elev_range / n_bands)
        hi = elev_min + int((i+1) * elev_range / n_bands)
        color = cmap(i / (n_bands-1))
        bands.append(Patch(facecolor=color, label=f"{lo}–{hi} m"))

    legend = ax.legend(handles=bands, loc="lower left", fontsize=8,
                       title="Elevation (m)", title_fontsize=9,
                       facecolor="#0d2137", edgecolor="#1e3a5f", labelcolor="white")
    legend.get_title().set_color("white")

    ax.grid(True, color="#1e3a5f", linewidth=0.5, linestyle="--", alpha=0.7)
    ax.set_xlabel("Longitude", color="white", fontsize=9)
    ax.set_ylabel("Latitude", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1e3a5f")
    ax.set_title("Digital Elevation Model (SRTM 30m)", color="white", fontsize=11, pad=10)

    stats_text = (f"Min: {elev_grid.min():.0f}m\n"
                  f"Max: {elev_grid.max():.0f}m\n"
                  f"Mean: {elev_grid.mean():.0f}m")
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, color="white",
            fontsize=8, verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="#0d2137",
                      edgecolor="#1e3a5f", alpha=0.8))

    os.makedirs("output", exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor="#0a1628", edgecolor="none")
    plt.close()
    print(f"Saved -> {output_path}")
    return output_path


if __name__ == "__main__":
    cfg = load_config()
    elev_grid, lats, lons = fetch_elevation(cfg)
    render_elevation_map(elev_grid, lats, lons)
    print("Done")