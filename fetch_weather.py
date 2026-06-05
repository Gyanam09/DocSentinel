import requests
from config import load_config

def fetch_weather(cfg):
    bbox = cfg["bbox_tuple"]
    min_lat, min_lon, max_lat, max_lon = bbox
    lat = (min_lat + max_lat) / 2
    lon = (min_lon + max_lon) / 2

    print(f"Fetching weather data for ({lat:.4f}, {lon:.4f})...")

    # ── Current weather ───────────────────────────────────────────────────
    current_r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
            "timezone": "auto",
        },
        timeout=15
    )
    current = {}
    if current_r.status_code == 200:
        c = current_r.json().get("current", {})
        current = {
            "temperature":  c.get("temperature_2m", 0),
            "humidity":     c.get("relative_humidity_2m", 0),
            "wind_speed":   c.get("wind_speed_10m", 0),
            "precipitation": c.get("precipitation", 0),
            "weather_code": c.get("weather_code", 0),
        }
        print(f"  Current: {current['temperature']}°C, {current['humidity']}% humidity")

    # ── Historical climate (last 20 years) ────────────────────────────────
    hist_r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat, "longitude": lon,
            "start_date": "2005-01-01",
            "end_date":   "2024-12-31",
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "auto",
        },
        timeout=30
    )
    climate = {}
    if hist_r.status_code == 200:
        data = hist_r.json().get("daily", {})
        temps = [t for t in data.get("temperature_2m_mean", []) if t is not None]
        rains = [r for r in data.get("precipitation_sum", []) if r is not None]

        if temps:
            # Split into first 5 years vs last 5 years for trend
            chunk = len(temps) // 4
            early_temp = sum(temps[:chunk]) / chunk
            late_temp  = sum(temps[-chunk:]) / chunk
            temp_trend = round(late_temp - early_temp, 2)

            early_rain = sum(rains[:chunk]) / chunk * 365
            late_rain  = sum(rains[-chunk:]) / chunk * 365
            rain_trend_pct = round((late_rain - early_rain) / max(early_rain, 1) * 100, 1)

            annual_rain = round(sum(rains) / 20, 1)
            avg_temp    = round(sum(temps) / len(temps), 1)
            rainy_days  = sum(1 for r in rains if r > 1) // 20

            climate = {
                "annual_rainfall_mm":  annual_rain,
                "avg_temperature_c":   avg_temp,
                "temp_trend_20yr":     temp_trend,
                "rainfall_trend_pct":  rain_trend_pct,
                "rainy_days_per_year": rainy_days,
            }
            print(f"  Climate: {avg_temp}°C avg, {annual_rain}mm/yr rain")
            print(f"  Trends: temp {'+' if temp_trend>0 else ''}{temp_trend}°C, rain {rain_trend_pct}%")

    # ── NASA POWER — solar & wind ─────────────────────────────────────────
    power_r = requests.get(
        "https://power.larc.nasa.gov/api/temporal/climatology/point",
        params={
            "parameters": "ALLSKY_SFC_SW_DWN,WS2M",
            "community":  "RE",
            "longitude":  lon,
            "latitude":   lat,
            "format":     "JSON",
        },
        timeout=20
    )
    energy = {}
    if power_r.status_code == 200:
        props = power_r.json().get("properties", {}).get("parameter", {})
        solar_vals = props.get("ALLSKY_SFC_SW_DWN", {})
        wind_vals  = props.get("WS2M", {})
        ann_solar  = solar_vals.get("ANN", 0)
        ann_wind   = wind_vals.get("ANN", 0)
        energy = {
            "solar_kwh_m2_day": round(ann_solar, 2),
            "wind_speed_ms":    round(ann_wind, 2),
        }
        print(f"  Energy: {ann_solar} kWh/m²/day solar, {ann_wind} m/s wind")

    return {
        "current":  current,
        "climate":  climate,
        "energy":   energy,
        "lat":      lat,
        "lon":      lon,
    }


if __name__ == "__main__":
    cfg = load_config()
    data = fetch_weather(cfg)
    print("\nWeather summary:")
    print(f"  Temperature:  {data['current'].get('temperature')}°C")
    print(f"  Humidity:     {data['current'].get('humidity')}%")
    print(f"  Wind:         {data['current'].get('wind_speed')} km/h")
    print(f"  Annual rain:  {data['climate'].get('annual_rainfall_mm')} mm")
    print(f"  Temp trend:   {data['climate'].get('temp_trend_20yr')}°C over 20yr")
    print(f"  Solar:        {data['energy'].get('solar_kwh_m2_day')} kWh/m²/day")
    print(f"  Wind energy:  {data['energy'].get('wind_speed_ms')} m/s")