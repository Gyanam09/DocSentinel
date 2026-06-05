import requests
import json

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

def query_overpass(query):
    """Try each mirror in order until one works."""
    for mirror in OVERPASS_MIRRORS:
        try:
            print(f"Trying {mirror}...")
            response = requests.get(
                mirror,
                params={"data": query},
                timeout=20
            )
            if response.status_code == 200:
                print(f"Success with {mirror}")
                return response.json()
            else:
                print(f"Got {response.status_code}, trying next mirror...")
        except requests.exceptions.Timeout:
            print(f"Timed out, trying next mirror...")
        except requests.exceptions.ConnectionError:
            print(f"Connection failed, trying next mirror...")

    # All mirrors failed — return fallback data
    print("All Overpass mirrors unavailable. Using fallback land-use data.")
    return None


def get_land_use(bbox):
    min_lat, min_lon, max_lat, max_lon = bbox

    query = f"""
    [out:json][timeout:10][maxsize:1048576];
    way["landuse"]({min_lat},{min_lon},{max_lat},{max_lon});
    out tags;
    """

    data = query_overpass(query)

    # If all mirrors failed, return a sensible fallback
    if data is None:
        return {"unavailable": 100.0}, False

    elements = data.get("elements", [])
    print(f"OSM returned {len(elements)} land-use features")

    if not elements:
        return {"unknown": 100.0}, False

    # Count by land-use type
    land_counts = {}
    for el in elements:
        tag = el.get("tags", {}).get("landuse", "other")
        land_counts[tag] = land_counts.get(tag, 0) + 1

    total = sum(land_counts.values())
    land_pct = {k: round((v / total) * 100, 1) for k, v in land_counts.items()}
    land_pct = dict(sorted(land_pct.items(), key=lambda x: x[1], reverse=True))

    # Check if AOI has vegetation
    vegetated_types = {
        "forest", "farmland", "meadow", "orchard", "vineyard",
        "grass", "village_green", "nature_reserve", "scrub",
        "heath", "allotments", "greenhouse_horticulture"
    }
    found = [k for k in land_pct if k in vegetated_types]
    validated = len(found) > 0

    return land_pct, validated


# ─── Test run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from config import load_config
    cfg = load_config()
    BBOX = cfg["bbox_tuple"]

    print("Querying OSM Overpass API...")
    land_use, validated = get_land_use(BBOX)

    print("\nLand-use breakdown:")
    for land_type, pct in land_use.items():
        bar = "█" * int(pct / 5)
        print(f"  {land_type:<25} {bar} {pct}%")

    print(f"\nAOI valid for monitoring: {validated}")