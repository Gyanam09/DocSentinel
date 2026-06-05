import json

def load_config():
    with open("config.json", "r") as f:
        cfg = json.load(f)
    bbox = cfg["bbox"]
    cfg["bbox_tuple"] = (
        bbox["min_lat"],
        bbox["min_lon"],
        bbox["max_lat"],
        bbox["max_lon"]
    )
    return cfg