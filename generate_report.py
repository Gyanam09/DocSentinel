import os
import sys
from datetime import date
import numpy as np
from jinja2 import Environment, FileSystemLoader

from fetch_gibs import fetch_gibs_thumbnail
import os
import sys
from datetime import date
import numpy as np
from jinja2 import Environment, FileSystemLoader

from fetch_gibs import fetch_gibs_thumbnail
from fetch_weather import fetch_weather
from fetch_soil import fetch_soil
from fetch_infrastructure import fetch_infrastructure
from score_land import compute_scores
from config import load_config
from fetch_location import fetch_location_name
from fetch_elevation import fetch_elevation, render_elevation_map
from fetch_fire import fetch_fire_data, render_fire_map
from fetch_osm import get_land_use


cfg = load_config()
BBOX = cfg["bbox_tuple"]

# ── Collect all data layers ───────────────────────────────────────────────
print("=" * 50)
print("DocSentinel — Report Generation Pipeline")
print("=" * 50)

print("\n[1/5] Fetching NASA GIBS true-color imagery...")
fetch_gibs_thumbnail(BBOX, output_path="output/true_color.png")

# Auto-detect location name, country, and state
try:
    location_name, addr = fetch_location_name(cfg)
    country = addr.get("country", "")
    state = addr.get("state", "")
except Exception as e:
    print(f"Location detection failed: {e}")
    location_name = cfg.get("aoi_name", "AOI")
    country = ""
    state = ""

print("\n[2/5] Fetching weather & climate data...")
weather = fetch_weather(cfg)

print("\n[3/5] Fetching soil data...")
try:
    soil = fetch_soil(cfg)
except Exception as e:
    print(f"  Soil fetch failed: {e} — using fallback")
    soil = {
        "ph": 7.0, "ph_class": "Neutral", "texture": "Loam",
        "nitrogen_level": "Moderate", "clay_pct": 25.0,
        "sand_pct": 40.0, "silt_pct": 35.0, "organic_carbon": 1.5,
        "bulk_density": 1.4, "drainage": "Moderate", "nitrogen_mg_kg": 150,
    }

print("\n[4/5] Fetching infrastructure data...")
try:
    infra = fetch_infrastructure(cfg)
except Exception as e:
    print(f"  Infrastructure fetch failed: {e} — using fallback")
    infra = {
        "nearest_highway_km": None, "nearest_hospital_km": None,
        "nearest_school_km": None, "nearest_railway_km": None,
        "nearest_city": "—", "road_density": "Unknown", "settlements_count": 0,
    }

# ── NDVI results from last calculate_ndvi.py run ─────────────────────────
# In production these come from calculate_ndvi.py output; hardcoded for now
ndvi_data = {
    "mean_ndvi":  0.198,
    "loss_pct":   15.32,
    "loss_patches": 6093,
    "ndvi_min":   -0.401,
    "ndvi_max":    0.667,
}

# Fetch elevation data and render map
try:
    print("\nFetching elevation data and rendering DEM map...")
    elev_grid, lats, lons = fetch_elevation(cfg)
    render_elevation_map(elev_grid, lats, lons, output_path="output/elevation_map.png")
    
    elev_min = float(elev_grid.min())
    elev_max = float(elev_grid.max())
    elev_range = elev_max - elev_min
    elev_mean = float(elev_grid.mean())
    
    rows, cols = elev_grid.shape
    slope_grid = np.zeros_like(elev_grid)
    for i in range(1, rows-1):
        for j in range(1, cols-1):
            dz_dx = (float(elev_grid[i, j+1]) - float(elev_grid[i, j-1])) / 2
            dz_dy = (float(elev_grid[i+1, j]) - float(elev_grid[i-1, j])) / 2
            slope_grid[i, j] = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2) / 30))
    slope_avg = float(np.mean(slope_grid))
    
    elev_data = {
        "elev_min":   round(elev_min, 1),
        "elev_max":   round(elev_max, 1),
        "elev_range": round(elev_range, 1),
        "elev_mean":  round(elev_mean, 1),
        "slope_avg":  round(slope_avg, 1),
    }
except Exception as e:
    print(f"Elevation fetch/render failed: {e} — using fallback")
    elev_data = {
        "elev_min":   446,
        "elev_max":   570,
        "elev_range": 124,
        "elev_mean":  508,
        "slope_avg":  4.8,
    }

# Fetch fire data and render map
try:
    print("\nFetching active fires and rendering fire map...")
    fires = fetch_fire_data(cfg)
    render_fire_map(fires, cfg, output_path="output/fire_map.png")
except Exception as e:
    print(f"Fire fetch/render failed: {e}")

# Fetch OSM land-use breakdown
try:
    print("\nFetching OSM land-use data...")
    osm_land_use, osm_validated = get_land_use(BBOX)
except Exception as e:
    print(f"OSM land-use fetch failed: {e} — using fallback")
    osm_land_use, osm_validated = None, False


print("\n[5/5] Computing intelligence scores...")
scores = compute_scores(ndvi_data, weather, soil, infra, elev_data)

# ── Build template context ────────────────────────────────────────────────
alert = ndvi_data["loss_pct"] > 1.0

# ─── Load NDVI results from calculate_ndvi.py output ─────────────────────
import json as _json

ndvi_results = {}
try:
    with open("output/ndvi_results.json", "r") as f:
        ndvi_results = _json.load(f)
    print(f"  NDVI results loaded: mean={ndvi_results.get('mean_ndvi')}, "
          f"loss={ndvi_results.get('loss_pct')}%")
except FileNotFoundError:
    print("  Warning: ndvi_results.json not found — using fallback values")
    ndvi_results = {
        "mean_ndvi": 0.198, "ndvi_min": -0.401, "ndvi_max": 0.667,
        "loss_pct": 15.32, "loss_patches": 6093, "alert": True,
        "scene_date": cfg["scene_date"],
    }

report_data = {
    "scene_date":    ndvi_results.get("scene_date", cfg["scene_date"]),
    "generated_date": str(date.today()),
    "aoi_name":      location_name,
    "country":       country,
    "state":         state,
    "mean_ndvi":     ndvi_results.get("mean_ndvi", 0),
    "ndvi_min":      ndvi_results.get("ndvi_min", 0),
    "ndvi_max":      ndvi_results.get("ndvi_max", 0),
    "loss_pct":      ndvi_results.get("loss_pct", 0),
    "loss_patches":  ndvi_results.get("loss_patches", 0),
    "alert":         ndvi_results.get("alert", False),
    "ndvi_map_path":    "ndvi_t1_map.png",
    "loss_map_path":    "loss_contours.png",
    "true_color_path":  "true_color.png",
    "elevation_path":   "elevation_map.png",
    "fire_map_path":    "fire_map.png",
    "osm_land_use":     osm_land_use,
    "bbox":             cfg["bbox"],

    # Elevation
    "elev_min":         elev_data.get("elev_min", "—"),
    "elev_max":         elev_data.get("elev_max", "—"),
    "elev_range":       elev_data.get("elev_range", "—"),
    "elev_mean":        elev_data.get("elev_mean", "—"),
    "slope_avg":        elev_data.get("slope_avg", "—"),

    # Weather — current
    "temp":             weather["current"].get("temperature", "—"),
    "humidity":         weather["current"].get("humidity", "—"),
    "wind_speed":       weather["current"].get("wind_speed", "—"),
    "precipitation":    weather["current"].get("precipitation", "—"),

    # Weather — climate
    "annual_rainfall":  weather["climate"].get("annual_rainfall_mm", "—"),
    "avg_temp":         weather["climate"].get("avg_temperature_c", "—"),
    "temp_trend":       weather["climate"].get("temp_trend_20yr", "—"),
    "rain_trend_pct":   weather["climate"].get("rainfall_trend_pct", "—"),
    "rainy_days":       weather["climate"].get("rainy_days_per_year", "—"),

    # Energy
    "solar_kwh":        weather["energy"].get("solar_kwh_m2_day", "—"),
    "wind_ms":          weather["energy"].get("wind_speed_ms", "—"),

    # Soil
    "soil_ph":          soil.get("ph", "—"),
    "soil_ph_class":    soil.get("ph_class", "—"),
    "soil_texture":     soil.get("texture", "—"),
    "soil_nitrogen":    soil.get("nitrogen_level", "—"),
    "soil_clay":        soil.get("clay_pct", "—"),
    "soil_sand":        soil.get("sand_pct", "—"),
    "soil_silt":        soil.get("silt_pct", "—"),
    "soil_oc":          soil.get("organic_carbon", "—"),
    "soil_drainage":    soil.get("drainage", "—"),
    "soil_bulk":        soil.get("bulk_density", "—"),

    # Infrastructure
    "nearest_highway":  infra.get("nearest_highway_km", "—"),
    "nearest_hospital": infra.get("nearest_hospital_km", "—"),
    "nearest_school":   infra.get("nearest_school_km", "—"),
    "nearest_railway":  infra.get("nearest_railway_km", "—"),
    "nearest_city":     infra.get("nearest_city", "—"),
    "road_density":     infra.get("road_density", "—"),
    "settlements":      infra.get("settlements_count", "—"),

    # Scores
    "score_overall":        scores["overall"],
    "score_vegetation":     scores["vegetation"],
    "score_water":          scores["water"],
    "score_terrain":        scores["terrain"],
    "score_disturbance":    scores["human_disturbance"],
    "score_fire":           scores["fire_risk"],
    "score_climate":        scores["climate_stress"],
    "score_investment":     scores["investment_score"],
    "investment_pros":      scores["investment_pros"],
    "investment_cons":      scores["investment_cons"],
    "crop_suitability":     scores["crop_suitability"],

    # Risk
    "flood_risk":           scores["flood_risk"],
    "landslide_risk":       scores["landslide_risk"],
    "drought_risk":         scores["drought_risk"],
}

# ── Render ────────────────────────────────────────────────────────────────
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("report.html")
html_output = template.render(**report_data)

output_path = "output/report.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_output)
print(f"\nReport saved -> {output_path}")

# ── PDF ───────────────────────────────────────────────────────────────────
import pdfkit
if sys.platform == "win32":
    wk_path = os.environ.get(
        "WKHTMLTOPDF_PATH",
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
    )
else:
    wk_path = os.environ.get("WKHTMLTOPDF_PATH", "/usr/bin/wkhtmltopdf")

config_pdf = pdfkit.configuration(wkhtmltopdf=wk_path)
pdfkit.from_file(output_path, "output/report.pdf",
                 configuration=config_pdf,
                 options={"enable-local-file-access": "", "quiet": ""})
print("PDF saved   -> output/report.pdf")
print("\nDone.")
