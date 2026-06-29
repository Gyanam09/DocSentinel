import requests
import time

def fetch_soil(cfg):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox
    lat = (min_lat + max_lat) / 2
    lon = (min_lon + max_lon) / 2

    print(f"Fetching soil data for ({lat:.4f}, {lon:.4f})...")

    # SoilGrids v2 — correct endpoint and parameter format
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"

    for attempt in range(3):
        try:
            print(f"  SoilGrids attempt {attempt+1}/3...")
            r = requests.get(
                url,
                params={
                    "lon":      lon,
                    "lat":      lat,
                    "property": ["phh2o", "nitrogen", "soc", "clay", "sand", "silt", "bdod"],
                    "depth":    "0-5cm",
                    "value":    "mean",
                },
                timeout=30
            )

            if r.status_code != 200:
                print(f"  SoilGrids HTTP {r.status_code}")
                time.sleep(5)
                continue

            data = r.json()
            layers = data.get("properties", {}).get("layers", [])

            raw = {}
            for layer in layers:
                name = layer.get("name", "")
                depths = layer.get("depths", [])
                for depth in depths:
                    val = depth.get("values", {}).get("mean")
                    if val is not None and val != -32768:  # -32768 = nodata
                        raw[name] = val
                        break

            print(f"  Raw values: {raw}")

            # Validate we got real data
            if not raw or all(v == 0 for v in raw.values()):
                print(f"  Empty response on attempt {attempt+1}")
                time.sleep(5)
                continue

            # Convert units
            soil = {
                "ph":             round(raw.get("phh2o", 70) / 10, 1),
                "nitrogen_mg_kg": raw.get("nitrogen", 150),
                "organic_carbon": round(raw.get("soc", 15) / 10, 1),
                "clay_pct":       round(raw.get("clay", 250) / 10, 1),
                "sand_pct":       round(raw.get("sand", 400) / 10, 1),
                "silt_pct":       round(raw.get("silt", 350) / 10, 1),
                "bulk_density":   round(raw.get("bdod", 140) / 100, 2),
            }

            # Classify
            clay = soil["clay_pct"]
            sand = soil["sand_pct"]
            soil["texture"]        = "Clay" if clay>40 else "Clay Loam" if clay>27 and sand<45 else "Sandy Loam" if sand>50 and clay<20 else "Sandy" if sand>70 else "Loam"
            soil["nitrogen_level"] = "High" if soil["nitrogen_mg_kg"]>200 else "Moderate" if soil["nitrogen_mg_kg"]>100 else "Low"
            soil["ph_class"]       = "Acidic" if soil["ph"]<6.5 else "Neutral" if soil["ph"]<7.5 else "Alkaline"
            soil["drainage"]       = "Poor" if clay>40 else "Good" if sand>50 else "Moderate"

            print(f"  pH: {soil['ph']} ({soil['ph_class']})")
            print(f"  Texture: {soil['texture']}, Clay: {soil['clay_pct']}%")
            return soil

        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(5)

    # Regional fallback for central India
    print("  Using regional fallback for central India")
    return {
        "ph": 7.2, "ph_class": "Neutral",
        "texture": "Clay Loam", "nitrogen_level": "Moderate",
        "clay_pct": 35.0, "sand_pct": 32.0, "silt_pct": 33.0,
        "organic_carbon": 1.8, "bulk_density": 1.42,
        "drainage": "Moderate", "nitrogen_mg_kg": 145,
    }