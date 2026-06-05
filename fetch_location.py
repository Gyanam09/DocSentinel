import requests
from config import load_config

def fetch_location_name(cfg):
    """
    Nominatim reverse geocoder — converts coordinates to human-readable
    location name. No auth needed.
    """
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox

    # Use center point of AOI
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    print(f"Reverse geocoding ({center_lat:.4f}, {center_lon:.4f})...")

    r = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={
            "lat": center_lat,
            "lon": center_lon,
            "format": "json",
            "zoom": 10,
        },
        headers={"User-Agent": "DocSentinel/1.0"},
        timeout=10
    )

    if r.status_code != 200:
        print(f"Nominatim error: {r.status_code}")
        return cfg.get("aoi_name", "Unknown Location"), {}

    data = r.json()
    addr = data.get("address", {})

    # Build readable name from components
    parts = []
    for key in ["suburb", "city", "town", "village", "county",
                "state_district", "state", "country"]:
        val = addr.get(key)
        if val and val not in parts:
            parts.append(val)
        if len(parts) == 3:
            break

    location_name = ", ".join(parts) if parts else cfg.get("aoi_name", "Unknown")

    print(f"Location identified: {location_name}")
    print(f"Full address: {data.get('display_name', '')}")

    return location_name, addr


if __name__ == "__main__":
    cfg = load_config()
    name, addr = fetch_location_name(cfg)
    print(f"\nAOI Name: {name}")
    print(f"State: {addr.get('state', 'N/A')}")
    print(f"Country: {addr.get('country', 'N/A')}")