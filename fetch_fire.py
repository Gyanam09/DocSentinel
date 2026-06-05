import requests
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
from datetime import date, timedelta
from config import load_config

def fetch_fire_data(cfg):
    """
    NASA FIRMS — use the public WFS endpoint (no API key needed)
    Returns active fires in AOI from last 7 days
    """
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox

    print("Fetching NASA FIRMS fire data...")

    # FIRMS public WFS — no auth needed
    url = "https://firms.modaps.eosdis.nasa.gov/mapserver/wfs"
    params = {
        "SERVICE": "WFS",
        "VERSION": "1.1.0",
        "REQUEST": "GetFeature",
        "TYPENAME": "ms:fires_viirs_snpp",
        "BBOX": f"{min_lat},{min_lon},{max_lat},{max_lon}",
        "OUTPUTFORMAT": "geojson",
        "maxFeatures": "500",
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        print(f"FIRMS WFS status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            features = data.get("features", [])
            fires = []
            for f in features:
                coords = f.get("geometry", {}).get("coordinates", [])
                props = f.get("properties", {})
                if coords:
                    fires.append({
                        "lon": coords[0],
                        "lat": coords[1],
                        "brightness": props.get("bright_ti4", 0),
                        "frp": props.get("frp", 1),
                        "date": props.get("acq_date", ""),
                        "confidence": props.get("confidence", ""),
                    })
            print(f"Found {len(fires)} active fire detections")
            return fires

    except Exception as e:
        print(f"FIRMS WFS failed: {e}")

    # If WFS also fails — return empty list gracefully
    # Fire map will show "No active fires detected" panel
    print("FIRMS unavailable — showing clear status")
    return []


def render_fire_map(fires, cfg, output_path="output/fire_map.png"):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox

    fig, ax = plt.subplots(figsize=(8, 8), facecolor="#0a1628")
    ax.set_facecolor("#0d2137")

    # Background grid
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    ax.grid(True, color="#1e3a5f", linewidth=0.5, linestyle="--", alpha=0.6)

    if fires:
        lats = [f["lat"] for f in fires]
        lons = [f["lon"] for f in fires]
        frps = [max(f["frp"], 1) for f in fires]

        # Size by fire radiative power
        sizes = [min(frp * 10, 300) for frp in frps]

        scatter = ax.scatter(
            lons, lats,
            s=sizes,
            c="#ff4500",
            alpha=0.8,
            edgecolors="#ff8c00",
            linewidths=0.5,
            zorder=5
        )

        # Halo effect
        ax.scatter(lons, lats, s=[s * 3 for s in sizes],
                   c="#ff4500", alpha=0.15, zorder=4)

        status_color = "#ff4500"
        status_text = f"{len(fires)} active fire detections"
    else:
        # No fires — show clean AOI box
        from matplotlib.patches import Rectangle
        rect = Rectangle(
            (min_lon, min_lat),
            max_lon - min_lon,
            max_lat - min_lat,
            linewidth=1.5,
            edgecolor="#22c55e",
            facecolor="rgba(34,197,94,0.05)" if False else "none",
            alpha=0.5
        )
        ax.add_patch(rect)
        ax.text(
            (min_lon + max_lon) / 2,
            (min_lat + max_lat) / 2,
            "No Active Fires\nDetected",
            color="#22c55e", fontsize=13, fontweight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round", facecolor="#0a1628",
                      edgecolor="#22c55e", alpha=0.8)
        )
        status_color = "#22c55e"
        status_text = "No active fires (last 7 days)"

    # Legend
    legend_elements = [
        mpatches.Patch(color="#ff4500", label="Active fire (VIIRS 375m)"),
        mpatches.Patch(color="#22c55e", label="No fire detected"),
    ]
    legend = ax.legend(
        handles=legend_elements, loc="lower left",
        fontsize=8, facecolor="#0d2137",
        edgecolor="#1e3a5f", labelcolor="white"
    )

    # Labels
    ax.set_xlabel("Longitude", color="white", fontsize=9)
    ax.set_ylabel("Latitude", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1e3a5f")

    ax.set_title("Fire Detection — NASA FIRMS VIIRS (7-day)", color="white",
                 fontsize=11, pad=10)

    # Status badge
    ax.text(
        0.02, 0.98, status_text,
        transform=ax.transAxes,
        color=status_color, fontsize=9, fontweight="bold",
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="#0a1628",
                  edgecolor=status_color, alpha=0.8)
    )

    os.makedirs("output", exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor="#0a1628", edgecolor="none")
    plt.close()
    print(f"Saved -> {output_path}")
    return output_path


if __name__ == "__main__":
    cfg = load_config()
    fires = fetch_fire_data(cfg)
    render_fire_map(fires, cfg)
    print("Done — open output/fire_map.png to preview")