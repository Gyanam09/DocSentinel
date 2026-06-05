from config import load_config

def compute_scores(ndvi_data, weather_data, soil_data, infra_data, elev_data):
    """
    Compute all intelligence scores from collected data layers.
    Returns a dict of sub-scores and the overall Land Health Score.
    """

    scores = {}

    # ── 1. Vegetation Score (from NDVI) ──────────────────────────────────
    mean_ndvi   = ndvi_data.get("mean_ndvi", 0.2)
    loss_pct    = ndvi_data.get("loss_pct", 0)
    veg_score   = max(0, min(100, int(mean_ndvi * 150) - int(loss_pct * 1.5)))
    scores["vegetation"] = veg_score

    # ── 2. Water Availability Score ───────────────────────────────────────
    rain = weather_data.get("climate", {}).get("annual_rainfall_mm", 800)
    rain_trend = weather_data.get("climate", {}).get("rainfall_trend_pct", 0)
    water_score = min(100, max(0, int(rain / 12) + (5 if rain_trend > 0 else -5)))
    scores["water"] = water_score

    # ── 3. Terrain Stability Score ────────────────────────────────────────
    elev_range = elev_data.get("elev_range", 100)
    # Flatter = more stable
    terrain_score = max(40, min(100, 100 - int(elev_range / 5)))
    scores["terrain"] = terrain_score

    # ── 4. Human Disturbance Score (inverse — lower disturbance = higher score) ──
    road_density = infra_data.get("road_density", "Medium")
    highway_km   = infra_data.get("nearest_highway_km") or 10
    rd_penalty   = {"High": 30, "Medium": 15, "Low": 5}.get(road_density, 15)
    dist_bonus   = min(20, int(highway_km))
    disturbance_score = max(0, min(100, 85 - rd_penalty + dist_bonus))
    scores["human_disturbance"] = disturbance_score

    # ── 5. Fire Risk Score (inverse — lower risk = higher score) ─────────
    temp = weather_data.get("current", {}).get("temperature", 25)
    wind = weather_data.get("current", {}).get("wind_speed", 10)
    fire_risk   = min(100, int(temp * 1.5) + int(wind * 0.5) - int(rain / 30))
    fire_score  = max(0, 100 - fire_risk)
    scores["fire_risk"] = fire_score

    # ── 6. Climate Stress Score ───────────────────────────────────────────
    temp_trend  = weather_data.get("climate", {}).get("temp_trend_20yr", 0)
    rain_trend  = weather_data.get("climate", {}).get("rainfall_trend_pct", 0)
    climate_score = max(0, min(100, 70 - int(temp_trend * 10) + int(rain_trend * 0.5)))
    scores["climate_stress"] = climate_score

    # ── Overall Land Health Score (weighted) ─────────────────────────────
    weights = {
        "vegetation":       0.25,
        "water":            0.20,
        "terrain":          0.15,
        "human_disturbance":0.15,
        "fire_risk":        0.10,
        "climate_stress":   0.15,
    }
    overall = int(sum(scores[k] * w for k, w in weights.items()))
    scores["overall"] = overall

    # ── Disaster Risk Levels ──────────────────────────────────────────────
    elev_mean = elev_data.get("elev_mean", 491)
    slope_avg = elev_data.get("slope_avg", 5)

    flood_score    = max(0, 60 - int(elev_mean / 10) + int(rain / 50))
    landslide_score = min(100, int(slope_avg * 8) + int(rain / 40))
    drought_score  = max(0, 80 - int(rain / 10) + int(temp_trend * 10))

    def risk_level(s):
        if s > 70: return "High"
        if s > 40: return "Moderate"
        return "Low"

    scores["flood_risk"]     = risk_level(flood_score)
    scores["landslide_risk"] = risk_level(landslide_score)
    scores["drought_risk"]   = risk_level(drought_score)

    # ── Agriculture Suitability ───────────────────────────────────────────
    ph   = soil_data.get("ph", 7.0)
    clay = soil_data.get("clay_pct", 25)

    crops = []
    if 6.0 <= ph <= 7.5 and rain > 600:
        crops.append(("Wheat", "✓"))
        crops.append(("Soybean", "✓"))
    if ph < 7.0 and rain > 800:
        crops.append(("Rice", "⚠"))
    if 6.5 <= ph <= 8.0:
        crops.append(("Gram / Chickpea", "✓"))
    if rain > 500 and clay < 35:
        crops.append(("Maize", "✓"))
    scores["crop_suitability"] = crops

    # ── Investment Score ──────────────────────────────────────────────────
    pros, cons = [], []
    inv = 50

    if (infra_data.get("nearest_highway_km") or 99) < 5:
        inv += 10; pros.append("Good road access")
    else:
        cons.append("Limited road access")

    if water_score > 60:
        inv += 10; pros.append("Good water availability")
    else:
        cons.append("Water scarcity risk")

    if terrain_score > 70:
        inv += 8; pros.append("Stable flat terrain")

    if veg_score > 60:
        inv += 8; pros.append("Healthy vegetation")
    else:
        cons.append("Vegetation loss detected")

    if (infra_data.get("nearest_hospital_km") or 99) < 10:
        inv += 5; pros.append("Healthcare nearby")

    if loss_pct > 10:
        inv -= 10; cons.append("Significant canopy loss")

    if disturbance_score < 40:
        inv -= 5; cons.append("High human disturbance")

    scores["investment_score"] = max(0, min(100, inv))
    scores["investment_pros"]  = pros
    scores["investment_cons"]  = cons

    return scores


if __name__ == "__main__":
    # Test with sample data
    cfg = load_config()
    test_scores = compute_scores(
        ndvi_data    = {"mean_ndvi": 0.198, "loss_pct": 15.32},
        weather_data = {"current": {"temperature": 32, "wind_speed": 12},
                        "climate": {"annual_rainfall_mm": 1150,
                                    "temp_trend_20yr": 1.8,
                                    "rainfall_trend_pct": -12}},
        soil_data    = {"ph": 7.1, "clay_pct": 28, "drainage": "Good"},
        infra_data   = {"nearest_highway_km": 3.2, "nearest_hospital_km": 6.1,
                        "road_density": "High"},
        elev_data    = {"elev_range": 148, "elev_mean": 491, "slope_avg": 4},
    )
    print("\nLand Intelligence Scores:")
    for k, v in test_scores.items():
        print(f"  {k}: {v}")