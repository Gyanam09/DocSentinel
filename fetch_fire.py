import csv
import io
import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import requests
from dotenv import load_dotenv

from config import load_config


load_dotenv()


def fetch_fire_data(cfg):
    """
    Fetch NASA FIRMS VIIRS S-NPP active fire detections for the AOI.
    Requires FIRMS_MAP_KEY in .env or GitHub Actions secrets.
    """
    map_key = os.getenv("FIRMS_MAP_KEY")
    if not map_key:
        print("FIRMS_MAP_KEY is not configured; skipping active fire lookup.")
        return []

    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox

    print("Fetching NASA FIRMS fire data...")
    url = f"https://firms.modaps.eosdis.nasa.gov/mapserver/wfs/South_Asia/{map_key}"
    params = {
        "SERVICE": "WFS",
        "VERSION": "1.1.0",
        "REQUEST": "GetFeature",
        "TYPENAME": "ms:fires_snpp_7days",
        "BBOX": f"{min_lat},{min_lon},{max_lat},{max_lon},urn:ogc:def:crs:EPSG::4326",
        "SRSNAME": "urn:ogc:def:crs:EPSG::4326",
        "OUTPUTFORMAT": "csv",
        "maxFeatures": "500",
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        print(f"FIRMS WFS status: {r.status_code}")
        if r.status_code != 200:
            print(f"FIRMS response: {r.text[:300]}")
            return []

        fires = []
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            try:
                lat = float(row.get("latitude") or row.get("LATITUDE"))
                lon = float(row.get("longitude") or row.get("LONGITUDE"))
            except (TypeError, ValueError):
                continue

            if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                continue

            fires.append(
                {
                    "lon": lon,
                    "lat": lat,
                    "brightness": float(row.get("bright_ti4") or row.get("BRIGHT_TI4") or 0),
                    "frp": float(row.get("frp") or row.get("FRP") or 1),
                    "date": row.get("acq_date") or row.get("ACQ_DATE") or "",
                    "confidence": row.get("confidence") or row.get("CONFIDENCE") or "",
                }
            )

        print(f"Found {len(fires)} active fire detections")
        return fires
    except Exception as exc:
        print(f"FIRMS lookup failed: {exc}")
        return []


def render_fire_map(fires, cfg, output_path="output/fire_map.png"):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox

    fig, ax = plt.subplots(figsize=(8, 8), facecolor="#0a1628")
    ax.set_facecolor("#0d2137")
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    ax.grid(True, color="#1e3a5f", linewidth=0.5, linestyle="--", alpha=0.6)

    if fires:
        lats = [f["lat"] for f in fires]
        lons = [f["lon"] for f in fires]
        frps = [max(f["frp"], 1) for f in fires]
        sizes = [min(frp * 10, 300) for frp in frps]

        ax.scatter(
            lons,
            lats,
            s=sizes,
            c="#ff4500",
            alpha=0.8,
            edgecolors="#ff8c00",
            linewidths=0.5,
            zorder=5,
        )
        ax.scatter(lons, lats, s=[s * 3 for s in sizes], c="#ff4500", alpha=0.15, zorder=4)

        status_color = "#ff4500"
        status_text = f"{len(fires)} active fire detections"
    else:
        rect = mpatches.Rectangle(
            (min_lon, min_lat),
            max_lon - min_lon,
            max_lat - min_lat,
            linewidth=1.5,
            edgecolor="#22c55e",
            facecolor="none",
            alpha=0.5,
        )
        ax.add_patch(rect)
        ax.text(
            (min_lon + max_lon) / 2,
            (min_lat + max_lat) / 2,
            "No Active Fires\nDetected",
            color="#22c55e",
            fontsize=13,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round", facecolor="#0a1628", edgecolor="#22c55e", alpha=0.8),
        )
        status_color = "#22c55e"
        status_text = "No active fires (last 7 days)"

    legend_elements = [
        mpatches.Patch(color="#ff4500", label="Active fire (VIIRS 375m)"),
        mpatches.Patch(color="#22c55e", label="No fire detected"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="lower left",
        fontsize=8,
        facecolor="#0d2137",
        edgecolor="#1e3a5f",
        labelcolor="white",
    )

    ax.set_xlabel("Longitude", color="white", fontsize=9)
    ax.set_ylabel("Latitude", color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1e3a5f")

    ax.set_title("Fire Detection - NASA FIRMS VIIRS (7-day)", color="white", fontsize=11, pad=10)
    ax.text(
        0.02,
        0.98,
        status_text,
        transform=ax.transAxes,
        color=status_color,
        fontsize=9,
        fontweight="bold",
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="#0a1628", edgecolor=status_color, alpha=0.8),
    )

    os.makedirs("output", exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0a1628", edgecolor="none")
    plt.close()
    print(f"Saved -> {output_path}")
    return output_path


if __name__ == "__main__":
    cfg = load_config()
    fires = fetch_fire_data(cfg)
    render_fire_map(fires, cfg)
    print("Done - open output/fire_map.png to preview")
