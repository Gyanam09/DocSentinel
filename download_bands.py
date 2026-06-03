import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Step 1: Get access token ───────────────────────────────────────────
def get_token():
    response = requests.post(
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "username": os.getenv("CDSE_USERNAME"),
            "password": os.getenv("CDSE_PASSWORD"),
            "client_id": "cdse-public",
        }
    )
    if response.status_code == 200:
        print("Token OK")
        return response.json()["access_token"]
    else:
        raise Exception(f"Token failed: {response.text}")


# ─── Step 2: Search for a scene and get its ID ──────────────────────────
def find_scene(token):
    BBOX = (77.35, 23.15, 77.55, 23.35)
    min_lon, min_lat, max_lon, max_lat = BBOX

    wkt = (
        f"POLYGON(("
        f"{min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, "
        f"{min_lon} {min_lat}))"
    )

    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    params = {
        "$filter": (
            f"Collection/Name eq 'SENTINEL-2' and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') and "
            "Attributes/OData.CSC.DoubleAttribute/any("
            "att:att/Name eq 'cloudCover' and "
            "att/OData.CSC.DoubleAttribute/Value lt 5.0)"
        ),
        "$orderby": "ContentDate/Start desc",
        "$top": "1"
    }

    # Print exactly what we're sending
    r = requests.get(url, params=params)
    print("\nRequesting URL:")
    print(r.url if hasattr(r, 'url') else url)


    # Print raw response before trying to parse it
    print(f"\nStatus code: {r.status_code}")
    print(f"Response text (first 500 chars):\n{r.text[:500]}")

    if r.status_code != 200:
        raise Exception(f"Search failed with status {r.status_code}")

    scenes = r.json().get("value", [])

    if not scenes:
        raise Exception("No scenes found.")

    scene = scenes[0]
    print(f"\nScene found: {scene['Name']}")
    print(f"Scene ID:    {scene['Id']}")
    return scene['Id'], scene['Name']


# ─── Step 3: List files inside the scene, find B04 and B08 ──────────────
def find_band_paths(scene_id, scene_name, token):
    headers = {"Authorization": f"Bearer {token}"}
    base = "https://download.dataspace.copernicus.eu/odata/v1"

    # The .SAFE folder IS the scene name itself
    safe_name = scene_name  # e.g. S2B_MSIL2A_....SAFE

    # Step 1: List inside the .SAFE folder
    url = f"{base}/Products({scene_id})/Nodes({safe_name})/Nodes"
    r = requests.get(url, headers=headers)
    nodes = r.json().get("result", [])

    print("\nInside .SAFE folder:")
    for n in nodes:
        print(f"  {n['Name']}")

    # Step 2: Drill into GRANULE
    granule_url = f"{base}/Products({scene_id})/Nodes({safe_name})/Nodes(GRANULE)/Nodes"
    r2 = requests.get(granule_url, headers=headers)
    granule_nodes = r2.json().get("result", [])

    print("\nGranule nodes:")
    for n in granule_nodes:
        print(f"  {n['Name']}")

    granule_name = granule_nodes[0]["Name"]

    # Step 3: List R10m band files
    img_url = (
        f"{base}/Products({scene_id})/Nodes({safe_name})/Nodes(GRANULE)"
        f"/Nodes({granule_name})/Nodes(IMG_DATA)/Nodes(R10m)/Nodes"
    )
    r3 = requests.get(img_url, headers=headers)
    band_files = r3.json().get("result", [])

    print("\nBand files at R10m:")
    for f in band_files:
        print(f"  {f['Name']}")

    # Filter for B04 and B08
    bands = {}
    for f in band_files:
        name = f["Name"]
        if "B04" in name:
            bands["B04"] = name
        if "B08" in name:
            bands["B08"] = name

    if not bands:
        raise Exception("B04/B08 not found. Check band files printed above.")

    print(f"\nFound bands: {list(bands.keys())}")
    return safe_name, granule_name, bands


# ─── Step 4: Download a single band file ────────────────────────────────
def download_band(scene_id, safe_name, granule_name, band_filename, band_label, token):
    download_url = (
        f"https://download.dataspace.copernicus.eu/odata/v1/"
        f"Products({scene_id})/Nodes({safe_name})/Nodes(GRANULE)"
        f"/Nodes({granule_name})/Nodes(IMG_DATA)/Nodes(R10m)"
        f"/Nodes({band_filename})/$value"
    )

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(download_url, headers=headers, stream=True)

    if r.status_code != 200:
        raise Exception(f"Download failed for {band_label}: {r.status_code} {r.text}")

    os.makedirs("bands", exist_ok=True)
    filepath = f"bands/{band_label}.jp2"

    with open(filepath, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"Downloaded {band_label} → {filepath} ({size_mb:.1f} MB)")
    return filepath


# ─── Main: run everything ────────────────────────────────────────────────
if __name__ == "__main__":
    token = get_token()
    scene_id, scene_name = find_scene(token)
    safe_name, granule_name, bands = find_band_paths(scene_id, scene_name, token)

    b04_path = download_band(scene_id, safe_name, granule_name, bands["B04"], "B04", token)
    b08_path = download_band(scene_id, safe_name, granule_name, bands["B08"], "B08", token)

    print("\nReady for NDVI calculation:")
    print(f"  Red (B04): {b04_path}")
    print(f"  NIR (B08): {b08_path}")