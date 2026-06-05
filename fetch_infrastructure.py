import requests
import math
from config import load_config

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def fetch_infrastructure(cfg):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox
    lat = (min_lat + max_lat) / 2
    lon = (min_lon + max_lon) / 2

    print("Fetching infrastructure data from OSM...")

    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    # Search radius in degrees (~15km)
    r = 0.15
    query = f"""
    [out:json][timeout:20][maxsize:2097152];
    (
      way["highway"~"^(motorway|trunk|primary|secondary)$"]
        ({min_lat-r},{min_lon-r},{max_lat+r},{max_lon+r});
      node["amenity"="hospital"]
        ({min_lat-r},{min_lon-r},{max_lat+r},{max_lon+r});
      node["amenity"="school"]
        ({min_lat-r},{min_lon-r},{max_lat+r},{max_lon+r});
      node["railway"="station"]
        ({min_lat-r},{min_lon-r},{max_lat+r},{max_lon+r});
      node["place"~"^(city|town|village)$"]
        ({min_lat-r},{min_lon-r},{max_lat+r},{max_lon+r});
    );
    out center;
    """

    data = None
    for mirror in mirrors:
        try:
            resp = requests.get(mirror, params={"data": query}, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  OSM data fetched from {mirror}")
                break
        except Exception:
            continue

    infra = {
        "nearest_highway_km":  None,
        "nearest_hospital_km": None,
        "nearest_school_km":   None,
        "nearest_railway_km":  None,
        "nearest_city":        None,
        "settlements_count":   0,
        "road_density":        "Unknown",
        "building_density":    "Unknown",
    }

    if not data:
        print("  OSM unavailable — using fallback")
        return infra

    highway_dists, hospital_dists = [], []
    school_dists, railway_dists   = [], []
    settlements = []
    road_count  = 0

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        etype = el.get("type")

        # Get coordinates
        if etype == "node":
            elat = el.get("lat", 0)
            elon = el.get("lon", 0)
        elif etype == "way":
            center = el.get("center", {})
            elat = center.get("lat", 0)
            elon = center.get("lon", 0)
        else:
            continue

        dist = haversine(lat, lon, elat, elon)
        highway = tags.get("highway", "")
        amenity = tags.get("amenity", "")
        railway = tags.get("railway", "")
        place   = tags.get("place", "")

        if highway in ("motorway","trunk","primary","secondary"):
            highway_dists.append(dist)
            road_count += 1
        if amenity == "hospital":
            hospital_dists.append(dist)
        if amenity == "school":
            school_dists.append(dist)
        if railway == "station":
            railway_dists.append(dist)
        if place in ("city","town","village"):
            settlements.append((dist, tags.get("name","Unknown")))

    if highway_dists:
        infra["nearest_highway_km"] = round(min(highway_dists), 1)
    if hospital_dists:
        infra["nearest_hospital_km"] = round(min(hospital_dists), 1)
    if school_dists:
        infra["nearest_school_km"] = round(min(school_dists), 1)
    if railway_dists:
        infra["nearest_railway_km"] = round(min(railway_dists), 1)

    settlements.sort()
    infra["settlements_count"] = len(settlements)
    if settlements:
        infra["nearest_city"] = settlements[0][1]

    # Road density classification
    infra["road_density"] = "High" if road_count > 10 else "Medium" if road_count > 4 else "Low"

    print(f"  Highway: {infra['nearest_highway_km']}km")
    print(f"  Hospital: {infra['nearest_hospital_km']}km")
    print(f"  School: {infra['nearest_school_km']}km")
    print(f"  Settlements: {infra['settlements_count']}")

    return infra


if __name__ == "__main__":
    cfg = load_config()
    infra = fetch_infrastructure(cfg)
    print("\nInfrastructure summary:")
    for k, v in infra.items():
        print(f"  {k}: {v}")