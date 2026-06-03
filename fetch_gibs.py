import requests
import os
from PIL import Image
from io import BytesIO
import math

# ─── Convert lat/lon bbox to Web Mercator tile coordinates ───────────────
def deg2num(lat, lon, zoom):
    """Convert lat/lon to tile x/y at a given zoom level."""
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def fetch_gibs_thumbnail(bbox, output_path="output/true_color.png", zoom=9):
    """
    Fetch a true-color MODIS composite tile from NASA GIBS.
    bbox: (min_lat, min_lon, max_lat, max_lon)
    """
    min_lat, min_lon, max_lat, max_lon = bbox

    # Get tile range
    x_min, y_max = deg2num(min_lat, min_lon, zoom)
    x_max, y_min = deg2num(max_lat, max_lon, zoom)

    # Clamp to a reasonable number of tiles (max 3x3 grid)
    x_min = max(x_min, x_max - 2)
    y_min = max(y_min, y_max - 2)

    tile_size = 256
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1

    print(f"Fetching {cols}x{rows} tiles at zoom {zoom}...")
    print(f"Tile range: x={x_min}-{x_max}, y={y_min}-{y_max}")

    # NASA GIBS WMTS — zoom level in URL must match request zoom
    # GoogleMapsCompatible_Level9 = max zoom 9 for this layer
    def make_url(tx, ty, tz):
        return (
            f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
            f"MODIS_Terra_CorrectedReflectance_TrueColor/default/"
            f"2026-05-01/"  # use start of month — more likely to have data
            f"GoogleMapsCompatible_Level9/{tz}/{ty}/{tx}.jpg"
        )

    # Stitch tiles into one image
    canvas = Image.new("RGB", (cols * tile_size, rows * tile_size), color=(30, 30, 30))

    success = 0
    for row_i, ty in enumerate(range(y_min, y_max + 1)):
        for col_i, tx in enumerate(range(x_min, x_max + 1)):
            url = make_url(tx, ty, zoom)
            print(f"  Requesting: {url}")
            try:
                r = requests.get(url, timeout=10)
                print(f"  → HTTP {r.status_code}")
                if r.status_code == 200:
                    tile_img = Image.open(BytesIO(r.content))
                    canvas.paste(tile_img, (col_i * tile_size, row_i * tile_size))
                    success += 1
            except Exception as e:
                print(f"  → Error: {e}")

    os.makedirs("output", exist_ok=True)
    canvas.save(output_path)
    print(f"\n{success}/{cols*rows} tiles fetched successfully")
    print(f"Saved → {output_path}")
    return output_path

# ─── Test run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    BBOX = (23.15, 77.35, 23.35, 77.55)  # Bhopal AOI

    print("Fetching NASA GIBS true-color imagery...")
    path = fetch_gibs_thumbnail(BBOX)
    print(f"Done — open {path} to preview")