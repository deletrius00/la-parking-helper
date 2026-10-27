"""Fetch street-level photos of LA parking signs from Mapillary.

Run: python -m parking.mapillary LAT LON [count]
Mapillary images are generally CC BY-SA 4.0: keep photos/mapillary/ATTRIBUTION.csv with them.
"""
import csv
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
API = "https://graph.mapillary.com"
OUT = Path("photos/mapillary")
BOX = 0.0015  # ~150 m half-width in degrees


def _get(path: str, **params) -> dict:
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        raise SystemExit("MAPILLARY_TOKEN missing in .env")
    r = httpx.get(f"{API}/{path}", params={"access_token": token, **params}, timeout=60)
    r.raise_for_status()
    return r.json()


def bbox(lat: float, lon: float, half: float = BOX) -> str:
    return f"{lon - half},{lat - half},{lon + half},{lat + half}"


def parking_sign_locations(lat: float, lon: float) -> list[tuple[float, float, str]]:
    """Mapillary map features whose class mentions parking, as (lat, lon, class)."""
    data = _get("map_features", fields="id,object_value,geometry", bbox=bbox(lat, lon), limit=500)
    out = []
    for f in data.get("data", []):
        if "parking" in f["object_value"]:
            lon_, lat_ = f["geometry"]["coordinates"]
            out.append((lat_, lon_, f["object_value"]))
    return out


def download_near(lat: float, lon: float, count: int = 10) -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    seen, saved = set(), []
    with open(OUT / "ATTRIBUTION.csv", "a", newline="") as fh:
        log = csv.writer(fh)
        for slat, slon, cls in parking_sign_locations(lat, lon) or [(lat, lon, "area")]:
            imgs = _get("images", fields="id,thumb_2048_url,creator", bbox=bbox(slat, slon, 0.0002), limit=2)
            for im in imgs.get("data", []):
                if im["id"] in seen or "thumb_2048_url" not in im:
                    continue
                seen.add(im["id"])
                dest = OUT / f"{im['id']}.jpg"
                dest.write_bytes(httpx.get(im["thumb_2048_url"], timeout=60).content)
                log.writerow([dest.name, cls, im.get("creator", {}).get("username", ""), slat, slon])
                saved.append(dest)
                if len(saved) >= count:
                    return saved
    return saved


if __name__ == "__main__":
    la, lo = float(sys.argv[1]), float(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    for p in download_near(la, lo, n):
        print(p)


# --- targeted crops: map feature -> detection polygon -> crop of the original photo ---
import base64

import mapbox_vector_tile
from PIL import Image

SIGN_CLASSES = ("parking-restrictions", "no-parking", "no-stopping", "parking-reservation",
                "street-cleaning", "information-parking")
CROPS = Path("photos/mapillary_crops")


def _poly_box(geometry_b64: str) -> tuple[float, float, float, float] | None:
    """Decode a Mapillary detection (base64 vector tile) to (x0, y0, x1, y1) as 0-1 fractions."""
    tile = mapbox_vector_tile.decode(base64.b64decode(geometry_b64))
    xs, ys, extent = [], [], 4096
    for layer in tile.values():
        extent = layer.get("extent", extent)
        for feat in layer["features"]:
            g = feat["geometry"]
            rings = g["coordinates"] if g["type"] == "Polygon" else [g["coordinates"]]
            for ring in rings:
                for x, y in ring:
                    xs.append(x), ys.append(y)
    if not xs:
        return None
    return min(xs) / extent, min(ys) / extent, max(xs) / extent, max(ys) / extent


def sign_crops(lat: float, lon: float, half: float = 0.004, count: int = 10, pad: float = 0.35) -> list[Path]:
    CROPS.mkdir(parents=True, exist_ok=True)
    feats = _get("map_features", fields="id,object_value", bbox=bbox(lat, lon, half), limit=2000)["data"]
    feats = [f for f in feats if any(c in f["object_value"] for c in SIGN_CLASSES)]
    saved = []
    with open(CROPS / "ATTRIBUTION.csv", "a", newline="") as fh:
        log = csv.writer(fh)
        for f in feats:
            if len(saved) >= count:
                break
            dets = _get(f"{f['id']}/detections", fields="id,image,geometry").get("data", [])
            boxes = [(d, _poly_box(d["geometry"])) for d in dets]
            boxes = [(d, b) for d, b in boxes if b]
            if not boxes:
                continue
            d, (x0, y0, x1, y1) = max(boxes, key=lambda db: (db[1][2] - db[1][0]) * (db[1][3] - db[1][1]))
            im = _get(d["image"]["id"], fields="id,width,height,thumb_original_url,creator")
            w, h = im["width"], im["height"]
            px, py = (x1 - x0) * pad, (y1 - y0) * pad
            box = (max(x0 - px, 0) * w, max(y0 - py, 0) * h, min(x1 + px, 1) * w, min(y1 + py, 1) * h)
            full = Image.open(__import__("io").BytesIO(httpx.get(im["thumb_original_url"], timeout=120).content))
            crop = full.crop(tuple(int(v) for v in box))
            dest = CROPS / f"{f['id']}.jpg"
            crop.convert("RGB").save(dest, quality=92)
            log.writerow([dest.name, f["object_value"], im.get("creator", {}).get("username", ""), im["id"]])
            saved.append(dest)
    return saved
