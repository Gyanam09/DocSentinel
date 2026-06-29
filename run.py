import argparse
import json
import math
import os
import subprocess
import sys


os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_SCENE_DATE = "2026-05-28"
DEFAULT_CLIENT_EMAIL = "aisebanai@gmail.com"
CRITICAL_STEPS = {"download_bands.py", "calculate_ndvi.py"}


def parse_lat_lon_pair(raw):
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        raise ValueError("Expected 'lat, lon'.")
    return float(parts[0]), float(parts[1])


def validate_bbox(min_lat, max_lat, min_lon, max_lon):
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError("Latitude must be between -90 and 90.")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise ValueError("Longitude must be between -180 and 180.")
    if min_lat >= max_lat:
        raise ValueError("Minimum latitude must be less than maximum latitude.")
    if min_lon >= max_lon:
        raise ValueError("Minimum longitude must be less than maximum longitude.")


def bbox_from_point(center_lat, center_lon, radius_km):
    if radius_km <= 0:
        raise ValueError("Radius must be greater than zero.")
    if abs(center_lat) >= 89.9:
        raise ValueError("Point is too close to the poles for automatic bbox generation.")

    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * abs(math.cos(math.radians(center_lat))))
    min_lat = round(center_lat - delta_lat, 6)
    max_lat = round(center_lat + delta_lat, 6)
    min_lon = round(center_lon - delta_lon, 6)
    max_lon = round(center_lon + delta_lon, 6)
    validate_bbox(min_lat, max_lat, min_lon, max_lon)
    return min_lat, max_lat, min_lon, max_lon


def bbox_area_km2(min_lat, max_lat, min_lon, max_lon):
    center_lat = (min_lat + max_lat) / 2
    lat_km = abs(max_lat - min_lat) * 111.0
    lon_km = abs(max_lon - min_lon) * 111.0 * abs(math.cos(math.radians(center_lat)))
    return lat_km * lon_km


def get_coordinates_cli():
    print("\n" + "=" * 55)
    print("  DOCSENTINEL - Land Intelligence Platform")
    print("  Satellite Analysis Pipeline")
    print("=" * 55)
    print()
    print("Choose how to enter your area of interest:")
    print("  1. Paste a single point (auto-generates bounding box)")
    print("  2. Enter full bounding box manually")
    print()

    mode = input("  Enter 1 or 2: ").strip()

    while True:
        try:
            if mode == "1":
                print()
                print("-- Single Point Input ------------------------------")
                print("  Right-click on Google Maps, then copy the coordinates")
                raw = input("  Paste coordinates (e.g. 23.188, 75.781): ").strip()
                center_lat, center_lon = parse_lat_lon_pair(raw)

                print(f"\n  Center point: {center_lat}, {center_lon}")
                print("  How large should the analysis area be?")
                print("    1. Small  - ~5x5 km   (single farm / forest patch)")
                print("    2. Medium - ~10x10 km  (village / town area)")
                print("    3. Large  - ~20x20 km  (district level)")
                print("    4. Custom - enter radius in km")

                size = input("\n  Enter 1-4: ").strip()
                radius_km = {"1": 2.5, "2": 5.0, "3": 10.0}.get(size)
                if radius_km is None:
                    radius_km = float(input("  Radius in km: ").strip())

                min_lat, max_lat, min_lon, max_lon = bbox_from_point(
                    center_lat, center_lon, radius_km
                )
                area_km2 = (radius_km * 2) ** 2

                print("\n  Generated bounding box:")
                print(f"    SW: {min_lat}, {min_lon}")
                print(f"    NE: {max_lat}, {max_lon}")
                print(f"    Area: ~{area_km2:.0f} km2")
            else:
                print()
                print("-- Bounding Box Input ------------------------------")
                print("  Enter SW corner (bottom-left) then NE corner (top-right)")

                raw = input("\n  SW corner - paste 'lat, lon': ").strip()
                min_lat, min_lon = parse_lat_lon_pair(raw)
                raw = input("  NE corner - paste 'lat, lon': ").strip()
                max_lat, max_lon = parse_lat_lon_pair(raw)

                validate_bbox(min_lat, max_lat, min_lon, max_lon)
                area_km2 = bbox_area_km2(min_lat, max_lat, min_lon, max_lon)

            validate_bbox(min_lat, max_lat, min_lon, max_lon)

            if area_km2 > 10000:
                print(f"\n  Warning: area is {area_km2:.0f} km2 - very large, will take longer.")
                if input("  Continue? (y/n): ").strip().lower() != "y":
                    continue

            break
        except (ValueError, IndexError) as exc:
            print(f"  Invalid input: {exc}\n")
            continue

    print()
    scene_date = input(f"  Scene date (YYYY-MM-DD, Enter for {DEFAULT_SCENE_DATE}): ").strip()
    if not scene_date:
        scene_date = DEFAULT_SCENE_DATE

    client_email = input("  Client email for report: ").strip()
    if not client_email:
        client_email = DEFAULT_CLIENT_EMAIL

    aoi_name = input("  AOI name (Enter to auto-detect from coordinates): ").strip()

    print()
    print("-- Confirmation ------------------------------------")
    print(f"  SW: {min_lat}, {min_lon}")
    print(f"  NE: {max_lat}, {max_lon}")
    print(f"  Area: ~{area_km2:.0f} km2")
    print(f"  Scene date: {scene_date}")
    print(f"  Report to:  {client_email}")
    print()

    if input("  Run pipeline? (y/n): ").strip().lower() != "y":
        print("  Cancelled.")
        sys.exit(0)

    return {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lon": min_lon,
        "max_lon": max_lon,
        "scene_date": scene_date,
        "client_email": client_email,
        "aoi_name": aoi_name if aoi_name else "Auto-detect",
    }


def update_config(coords):
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}

    cfg["bbox"] = {
        "min_lat": coords["min_lat"],
        "max_lat": coords["max_lat"],
        "min_lon": coords["min_lon"],
        "max_lon": coords["max_lon"],
    }
    cfg["scene_date"] = coords.get("scene_date") or DEFAULT_SCENE_DATE
    cfg["client_email"] = coords.get("client_email") or DEFAULT_CLIENT_EMAIL

    if coords.get("aoi_name") and coords["aoi_name"] != "Auto-detect":
        cfg["aoi_name"] = coords["aoi_name"]
    else:
        cfg.pop("aoi_name", None)

    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")

    print("  config.json updated")
    if "aoi_name" in cfg:
        print(f"  AOI name set to {cfg['aoi_name']}")
    else:
        print("  AOI name cleared - will auto-detect from coordinates")


def run_pipeline():
    steps = [
        ("Downloading Sentinel-2 bands", "download_bands.py"),
        ("Calculating NDVI", "calculate_ndvi.py"),
        ("Fetching NASA GIBS imagery", "fetch_gibs.py"),
        ("Fetching OSM land-use", "fetch_osm.py"),
        ("Fetching elevation data", "fetch_elevation.py"),
        ("Fetching fire data", "fetch_fire.py"),
        ("Fetching weather & climate", "fetch_weather.py"),
        ("Fetching soil intelligence", "fetch_soil.py"),
        ("Fetching infrastructure data", "fetch_infrastructure.py"),
        ("Generating report", "generate_report.py"),
        ("Generating 3D terrain", "generate_3d_terrain.py"),
        ("Sending report via email", "send_report.py"),
    ]

    print("\n" + "=" * 55)
    print("  Running DocSentinel Pipeline")
    print("=" * 55)

    failed = []
    non_interactive = not sys.stdin.isatty()
    for i, (label, script) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {label}...")
        result = subprocess.run([sys.executable, script], capture_output=False)
        if result.returncode != 0:
            print(f"  {script} failed (exit code {result.returncode})")
            failed.append(script)
            if script in CRITICAL_STEPS:
                print("  Critical step failed. Stopping to avoid stale or invalid report data.")
                break
            if non_interactive:
                break
            cont = input("  Continue anyway? (y/n): ").strip().lower()
            if cont != "y":
                break
        else:
            print("  Done")

    print("\n" + "=" * 55)
    if not failed:
        print("  Pipeline complete!")
        print("  Output files:")
        print("    output/report.html      - full interactive report")
        print("    output/report.pdf       - PDF report")
        print("    output/terrain_3d.html  - 3D terrain viewer")
        print("    output/docsentinel_report.zip - portable package")
    else:
        print(f"  Pipeline finished with {len(failed)} failed step(s):")
        for failed_script in failed:
            print(f"    {failed_script}")
    print("=" * 55)
    return 1 if failed else 0


def parse_args():
    parser = argparse.ArgumentParser(description="Run the DocSentinel pipeline for a bounding box.")
    parser.add_argument("coords", nargs="*", help="min_lat max_lat min_lon max_lon")
    parser.add_argument("--scene-date", default=DEFAULT_SCENE_DATE)
    parser.add_argument("--client-email", default=DEFAULT_CLIENT_EMAIL)
    parser.add_argument("--aoi-name", default="Auto-detect")
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Update config.json from arguments, then exit without running the pipeline.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.coords:
        if len(args.coords) != 4:
            raise SystemExit("Expected exactly four coordinates: min_lat max_lat min_lon max_lon")
        min_lat, max_lat, min_lon, max_lon = [float(value) for value in args.coords]
        validate_bbox(min_lat, max_lat, min_lon, max_lon)
        coords = {
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon,
            "scene_date": args.scene_date,
            "client_email": args.client_email,
            "aoi_name": args.aoi_name,
        }
        print(
            "Using coordinates from arguments: "
            f"{coords['min_lat']},{coords['min_lon']} -> {coords['max_lat']},{coords['max_lon']}"
        )
    else:
        coords = get_coordinates_cli()

    update_config(coords)
    if args.config_only:
        raise SystemExit(0)
    raise SystemExit(run_pipeline())
