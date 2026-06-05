import requests
from config import load_config

def fetch_soil(cfg):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox
    lat = (min_lat + max_lat) / 2
    lon = (min_lon + max_lon) / 2

    print(f"Fetching soil data for ({lat:.4f}, {lon:.4f})...")

    # SoilGrids REST API — free, no auth
    props = ["phh2o", "nitrogen", "soc", "clay", "sand", "silt", "bdod"]
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"

    r = None
    for attempt in range(3):
        try:
            print(f"  SoilGrids attempt {attempt + 1}/3...")
            r = requests.get(
                url,
                params={
                    "lon": lon, "lat": lat,
                    "property": props,
                    "depth": ["0-5cm"],
                    "value": ["mean"],
                },
                timeout=60   # bumped from 30 to 60
            )
            break  # success — exit retry loop
        except requests.exceptions.Timeout:
            print(f"  Timed out on attempt {attempt + 1}")
            if attempt == 2:
                print("  All attempts failed — using fallback soil data")
                r = None
        except Exception as e:
            print(f"  Error: {e}")
            r = None
            break

    soil = {}
    if r is not None and r.status_code == 200:
        layers = r.json().get("properties", {}).get("layers", [])
        raw = {}
        for layer in layers:
            name = layer.get("name")
            depths = layer.get("depths", [])
            if depths:
                val = depths[0].get("values", {}).get("mean")
                if val is not None:
                    raw[name] = val

        # SoilGrids returns values in units that need conversion
        soil = {
            "ph":             round(raw.get("phh2o", 0) / 10, 1),   # ×0.1 → pH
            "nitrogen_mg_kg": raw.get("nitrogen", 0),                # cg/kg → already usable
            "organic_carbon": round(raw.get("soc", 0) / 10, 1),     # dg/kg → g/kg ÷10
            "clay_pct":       round(raw.get("clay", 0) / 10, 1),    # g/kg → %
            "sand_pct":       round(raw.get("sand", 0) / 10, 1),
            "silt_pct":       round(raw.get("silt", 0) / 10, 1),
            "bulk_density":   round(raw.get("bdod", 0) / 100, 2),   # cg/cm³ → g/cm³
        }

        # Classify soil texture
        clay = soil["clay_pct"]
        sand = soil["sand_pct"]
        if clay > 40:
            soil["texture"] = "Clay"
        elif clay > 27 and sand < 45:
            soil["texture"] = "Clay Loam"
        elif sand > 70:
            soil["texture"] = "Sandy"
        elif sand > 50 and clay < 20:
            soil["texture"] = "Sandy Loam"
        else:
            soil["texture"] = "Loam"

        # Nitrogen level
        n = soil["nitrogen_mg_kg"]
        soil["nitrogen_level"] = "High" if n > 200 else "Moderate" if n > 100 else "Low"

        # pH interpretation
        ph = soil["ph"]
        soil["ph_class"] = "Acidic" if ph < 6.5 else "Neutral" if ph < 7.5 else "Alkaline"

        # Drainage estimate
        soil["drainage"] = "Poor" if clay > 40 else "Good" if sand > 50 else "Moderate"

        print(f"  pH: {soil['ph']} ({soil['ph_class']})")
        print(f"  Texture: {soil['texture']}")
        print(f"  Clay: {soil['clay_pct']}%, Sand: {soil['sand_pct']}%")
        print(f"  Organic Carbon: {soil['organic_carbon']} g/kg")
        print(f"  Nitrogen: {soil['nitrogen_level']}")
    else:
        status = r.status_code if r is not None else "Timeout/Connection Error"
        print(f"  SoilGrids error: {status}")
        soil = {
            "ph": 7.0, "ph_class": "Neutral",
            "texture": "Loam", "nitrogen_level": "Moderate",
            "clay_pct": 25.0, "sand_pct": 40.0, "silt_pct": 35.0,
            "organic_carbon": 1.5, "bulk_density": 1.4,
            "drainage": "Moderate", "nitrogen_mg_kg": 150,
        }
        print("  Using fallback soil data")

    return soil


if __name__ == "__main__":
    cfg = load_config()
    soil = fetch_soil(cfg)
    print("\nSoil summary:")
    for k, v in soil.items():
        print(f"  {k}: {v}")