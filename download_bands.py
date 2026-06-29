import json
import os
import time

import requests
from dotenv import load_dotenv

from config import load_config


load_dotenv()
cfg = load_config()

BASE_URL = "https://download.dataspace.copernicus.eu/odata/v1"
CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
REQUIRED_BANDS = {"B04", "B08"}


def robust_get(url, headers=None, params=None, max_retries=4, timeout=60):
    for attempt in range(max_retries):
        try:
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
        ) as exc:
            wait = 5 * (attempt + 1)
            print(f"  Connection error (attempt {attempt + 1}/{max_retries}): {exc}")
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)
    raise Exception(f"Failed after {max_retries} attempts: {url}")


def get_token():
    for attempt in range(3):
        try:
            response = requests.post(
                "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "username": os.getenv("CDSE_USERNAME"),
                    "password": os.getenv("CDSE_PASSWORD"),
                    "client_id": "cdse-public",
                },
                timeout=60,
            )
            if response.status_code == 200:
                print("Token OK")
                return response.json()["access_token"]
            raise Exception(f"Token failed: {response.text}")
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
        ) as exc:
            wait = 10 * (attempt + 1)
            print(f"  Token request failed (attempt {attempt + 1}/3): {exc}")
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)
    raise Exception("Could not obtain token after 3 attempts")


def scene_date_from_name(scene_name):
    parts = scene_name.split("_")
    if len(parts) < 3:
        return cfg["scene_date"]
    date_str = parts[2][:8]
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"


def find_scene(token):
    bbox = cfg["bbox_tuple"]
    min_lon, min_lat, max_lon, max_lat = bbox[1], bbox[0], bbox[3], bbox[2]

    wkt = (
        "POLYGON(("
        f"{min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, "
        f"{min_lon} {min_lat}))"
    )

    cloud_cover_max = float(cfg.get("cloud_cover_max", 5.0))
    filters = [
        (
            "Collection/Name eq 'SENTINEL-2' and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') and "
            "Attributes/OData.CSC.DoubleAttribute/any("
            "att:att/Name eq 'cloudCover' and "
            f"att/OData.CSC.DoubleAttribute/Value lt {cloud_cover_max})"
        )
    ]

    last_error = None
    for filter_expr in filters:
        params = {"$filter": filter_expr, "$orderby": "ContentDate/Start desc", "$top": "1"}
        print("\nRequesting scene search:")
        for attempt in range(3):
            try:
                r = requests.get(CATALOG_URL, params=params, timeout=30)
                print(r.url)
                print(f"Status code: {r.status_code}")
                print(f"Response text (first 500 chars):\n{r.text[:500]}")

                if r.status_code != 200:
                    raise Exception(f"Search failed: {r.status_code}")

                scenes = r.json().get("value", [])
                if not scenes:
                    last_error = "No scenes found for this filter."
                    break

                scene = scenes[0]
                print(f"\nScene found: {scene['Name']}")
                print(f"Scene ID:    {scene['Id']}")
                return scene["Id"], scene["Name"]
            except requests.exceptions.ConnectionError:
                wait = 5 * (attempt + 1)
                print(f"  Scene search connection error (attempt {attempt + 1}/3)")
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)

    raise Exception(last_error or "Scene search failed after 3 attempts")


def node_path_url(scene_id, segments):
    path = f"{BASE_URL}/Products({scene_id})"
    for segment in segments:
        path += f"/Nodes({segment})"
    return path


def list_nodes(scene_id, segments, headers):
    url = node_path_url(scene_id, segments) + "/Nodes"
    r = robust_get(url, headers=headers)
    if r.status_code != 200:
        print(f"  Could not list {'/'.join(segments)}: HTTP {r.status_code}")
        return []
    return r.json().get("result", [])


def find_band_paths(scene_id, scene_name, token):
    headers = {"Authorization": f"Bearer {token}"}
    safe_name = scene_name

    print("\nInside .SAFE folder:")
    for node in list_nodes(scene_id, [safe_name], headers):
        print(f"  {node['Name']}")

    granule_nodes = list_nodes(scene_id, [safe_name, "GRANULE"], headers)
    print("\nGranule nodes:")
    for node in granule_nodes:
        print(f"  {node['Name']}")

    if not granule_nodes:
        raise Exception("No GRANULE nodes found in scene.")

    granule_name = granule_nodes[0]["Name"]
    candidate_dirs = [
        [safe_name, "GRANULE", granule_name, "IMG_DATA", "R10m"],
        [safe_name, "GRANULE", granule_name, "IMG_DATA"],
    ]

    bands = {}
    for directory in candidate_dirs:
        band_files = list_nodes(scene_id, directory, headers)
        if not band_files:
            continue

        print(f"\nBand files at {'/'.join(directory[-2:])}:")
        for item in band_files:
            print(f"  {item['Name']}")

        for item in band_files:
            name = item["Name"]
            band_path = directory + [name]
            if "B04" in name and "B04" not in bands:
                bands["B04"] = band_path
            elif "B08" in name and "B08" not in bands:
                bands["B08"] = band_path
            elif "TCI" in name and "TCI" not in bands:
                bands["TCI"] = band_path

        if REQUIRED_BANDS.issubset(bands):
            break

    missing = REQUIRED_BANDS - set(bands)
    if missing:
        raise Exception(f"Required band(s) not found: {', '.join(sorted(missing))}")

    if "TCI" not in bands:
        print("  TCI not found; true-color image can fall back to NASA GIBS.")

    print(f"\nFound bands: {list(bands.keys())}")
    return granule_name, bands


def download_band(scene_id, band_path, band_label, token):
    download_url = node_path_url(scene_id, band_path) + "/$value"
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(3):
        temp_filepath = f"bands/{band_label}.jp2.download"
        try:
            r = requests.get(download_url, headers=headers, stream=True, timeout=120)
            if r.status_code != 200:
                raise Exception(f"Download failed for {band_label}: {r.status_code} {r.text}")

            os.makedirs("bands", exist_ok=True)
            filepath = f"bands/{band_label}.jp2"
            with open(temp_filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            os.replace(temp_filepath, filepath)

            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"Downloaded {band_label} -> {filepath} ({size_mb:.1f} MB)")
            return filepath
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
        ) as exc:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            wait = 10 * (attempt + 1)
            print(f"  Download error for {band_label} (attempt {attempt + 1}/3): {exc}")
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)

    raise Exception(f"Failed to download {band_label} after 3 attempts")


def save_band_metadata(scene_id, scene_name, granule_name, downloaded):
    metadata = {
        "scene_id": scene_id,
        "scene_name": scene_name,
        "granule_name": granule_name,
        "scene_date": scene_date_from_name(scene_name),
        "bands": downloaded,
    }
    os.makedirs("bands", exist_ok=True)
    with open("bands/scene_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")
    print("Saved band metadata -> bands/scene_metadata.json")
    return metadata


def update_config_scene_date(scene_date):
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg_data = json.load(f)
        cfg_data["scene_date"] = scene_date
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg_data, f, indent=2)
            f.write("\n")
        print(f"Updated config.json scene_date to {scene_date}.")
    except Exception as exc:
        print(f"Warning: Could not update config.json: {exc}")


if __name__ == "__main__":
    token = get_token()
    scene_id, scene_name = find_scene(token)
    granule_name, bands = find_band_paths(scene_id, scene_name, token)

    downloaded = {
        "B04": download_band(scene_id, bands["B04"], "B04", token),
        "B08": download_band(scene_id, bands["B08"], "B08", token),
    }
    if "TCI" in bands:
        downloaded["TCI"] = download_band(scene_id, bands["TCI"], "TCI", token)

    metadata = save_band_metadata(scene_id, scene_name, granule_name, downloaded)
    update_config_scene_date(metadata["scene_date"])

    print("\nReady for NDVI calculation:")
    print(f"  Scene:     {scene_name}")
    print(f"  Scene date:{metadata['scene_date']}")
    print(f"  Red (B04): {downloaded['B04']}")
    print(f"  NIR (B08): {downloaded['B08']}")
    if "TCI" in downloaded:
        print(f"  TCI (RGB): {downloaded['TCI']}")
