import requests, os, json
from dotenv import load_dotenv
load_dotenv()

# --- Paste your bounding box here ---
# Format: (min_lon, min_lat, max_lon, max_lat)
BBOX = (77.35, 23.15, 77.55, 23.35) # example: near Bhopal

# Build WKT polygon from bounding box
min_lon, min_lat, max_lon, max_lat = BBOX
wkt = (f"POLYGON(("
       f"{min_lon} {min_lat}, {max_lon} {min_lat}, "
       f"{max_lon} {max_lat}, {min_lon} {max_lat}, "
       f"{min_lon} {min_lat}))")

# Search CDSE for scenes with <5% cloud cover
url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
params = {
  "$filter": (
    f"Collection/Name eq 'SENTINEL-2' and "
    f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') and "
    "Attributes/OData.CSC.DoubleAttribute/any("
    "att:att/Name eq 'cloudCover' and "
    "att/OData.CSC.DoubleAttribute/Value lt 5.0)"
  ),
  "$orderby": "ContentDate/Start desc", # newest first
  "$top": "3" # get 3 most recent results
}

r = requests.get(url, params=params)
scenes = r.json().get("value", [])

print(f"Found {len(scenes)} scenes:")
for s in scenes:
  print(f" - {s['Name']} | date: {s['ContentDate']['Start'][:10]}")