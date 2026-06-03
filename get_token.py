import requests
from dotenv import load_dotenv
import os

load_dotenv()

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
    token = response.json()["access_token"]
    print("Success! Token received.")
    print(f"Token preview: {token[:40]}...")
else:
    print(f"Error {response.status_code}: {response.text}")