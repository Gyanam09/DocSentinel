import requests
import math
import time
from config import load_config

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def search_nominatim(lat, lon, amenity, radius_km=15):
    """Use Nominatim search to find nearby amenities — no Overpass needed."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q":               amenity,
                "format":          "json",
                "limit":           5,
                "viewbox":         f"{lon-0.15},{lat+0.15},{lon+0.15},{lat-0.15}",
                "bounded":         1,
                "addressdetails":  0,
            },
            headers={"User-Agent": "DocSentinel/1.0"},
            timeout=15
        )
        if r.status_code == 200:
            results = r.json()
            dists = []
            for res in results:
                rlat = float(res.get("lat", 0))
                rlon = float(res.get("lon", 0))
                dist = haversine(lat, lon, rlat, rlon)
                if dist <= radius_km:
                    dists.append((dist, res.get("display_name", "")))
            dists.sort()
            return dists
    except Exception as e:
        print(f"  Nominatim search error for {amenity}: {e}")
    return []


def try_overpass(query, mirrors):
    """Try Overpass mirrors with POST requests."""
    for mirror in mirrors:
        try:
            name = mirror.split("/")[2]
            print(f"  Trying {name}...")
            r = requests.post(
                mirror,
                data=query,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20
            )
            if r.status_code == 200 and r.text.strip().startswith("{"):
                data = r.json()
                if data.get("elements"):
                    print(f"  ✓ Got {len(data['elements'])} elements from {name}")
                    return data
            else:
                print(f"  ✗ HTTP {r.status_code}")
        except Exception as e:
            print(f"  ✗ {e}")
        time.sleep(1)
    return None


def fetch_infrastructure(cfg):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox
    lat = (min_lat + max_lat) / 2
    lon = (min_lon + max_lon) / 2

    print(f"Fetching infrastructure for ({lat:.4f}, {lon:.4f})...")

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

    r = 0.15
    query = f"""
[out:json][timeout:20][maxsize:1048576];
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

    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    # ── Try Overpass first ────────────────────────────────────────────────
    data = try_overpass(query, mirrors)

    if data:
        highway_dists, hospital_dists = [], []
        school_dists, railway_dists   = [], []
        settlements = []
        road_count  = 0

        for el in data.get("elements", []):
            tags  = el.get("tags", {})
            etype = el.get("type")

            if etype == "node":
                elat, elon = el.get("lat", 0), el.get("lon", 0)
            elif etype == "way":
                center = el.get("center", {})
                elat, elon = center.get("lat", 0), center.get("lon", 0)
            else:
                continue

            dist    = haversine(lat, lon, elat, elon)
            highway = tags.get("highway", "")
            amenity = tags.get("amenity", "")
            railway = tags.get("railway", "")
            place   = tags.get("place", "")

            if highway in ("motorway","trunk","primary","secondary"):
                highway_dists.append(dist); road_count += 1
            if amenity == "hospital":
                hospital_dists.append(dist)
            if amenity == "school":
                school_dists.append(dist)
            if railway == "station":
                railway_dists.append(dist)
            if place in ("city","town","village"):
                settlements.append((dist, tags.get("name","Unknown")))

        if highway_dists:
            infra["nearest_highway_km"]  = round(min(highway_dists), 1)
        if hospital_dists:
            infra["nearest_hospital_km"] = round(min(hospital_dists), 1)
        if school_dists:
            infra["nearest_school_km"]   = round(min(school_dists), 1)
        if railway_dists:
            infra["nearest_railway_km"]  = round(min(railway_dists), 1)

        settlements.sort()
        infra["settlements_count"] = len(settlements)
        if settlements:
            infra["nearest_city"] = settlements[0][1]

        infra["road_density"] = (
            "High" if road_count > 10 else
            "Medium" if road_count > 4 else "Low"
        )

        print(f"  ✓ Overpass data: highway={infra['nearest_highway_km']}km, "
              f"hospital={infra['nearest_hospital_km']}km")
        return infra

    # ── Fallback: Nominatim search ────────────────────────────────────────
    print("  Overpass unavailable — using Nominatim search fallback...")
    time.sleep(1)  # respect rate limit

    # Highway
    roads = search_nominatim(lat, lon, "highway road", radius_km=15)
    if roads:
        infra["nearest_highway_km"] = round(roads[0][0], 1)
    time.sleep(1)

    # Hospital
    hospitals = search_nominatim(lat, lon, "hospital", radius_km=15)
    if hospitals:
        infra["nearest_hospital_km"] = round(hospitals[0][0], 1)
    time.sleep(1)

    # School
    schools = search_nominatim(lat, lon, "school", radius_km=15)
    if schools:
        infra["nearest_school_km"] = round(schools[0][0], 1)
    time.sleep(1)

    # Railway
    railways = search_nominatim(lat, lon, "railway station", radius_km=15)
    if railways:
        infra["nearest_railway_km"] = round(railways[0][0], 1)
    time.sleep(1)

    # Cities / towns
    cities = search_nominatim(lat, lon, "city town village", radius_km=20)
    infra["settlements_count"] = len(cities)
    if cities:
        # Extract just the city name from display_name
        name_parts = cities[0][1].split(",")
        infra["nearest_city"] = name_parts[0].strip()

    # Road density from count of road results
    road_results = search_nominatim(lat, lon, "road street", radius_km=5)
    infra["road_density"] = (
        "High" if len(road_results) > 5 else
        "Medium" if len(road_results) > 2 else "Low"
    )

    print(f"  Nominatim fallback results:")
    print(f"    Highway:    {infra['nearest_highway_km']}km")
    print(f"    Hospital:   {infra['nearest_hospital_km']}km")
    print(f"    School:     {infra['nearest_school_km']}km")
    print(f"    Railway:    {infra['nearest_railway_km']}km")
    print(f"    City:       {infra['nearest_city']}")
    print(f"    Settlements:{infra['settlements_count']}")

    return infra


if __name__ == "__main__":
    cfg = load_config()
    infra = fetch_infrastructure(cfg)
    print("\nInfrastructure summary:")
    for k, v in infra.items():
        print(f"  {k}: {v}")