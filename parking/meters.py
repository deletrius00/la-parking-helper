"""LADOT metered-parking database (data.lacity.org): blocks within a radius, evaluated for a trip."""
import json
import math
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx

from .rules import METERED, Rule, evaluate

BASE = "https://data.lacity.org/resource"
CACHE = Path("data/meters.json")
# The inventory has no operating hours: assume LA's common 8am-6pm Mon-Sat. Signs control enforcement.
ASSUMED = dict(days=frozenset(range(6)), start_min=8 * 60, end_min=18 * 60)
_occ = {"t": 0.0, "d": {}}


def load_meters() -> list[dict]:
    if not CACHE.exists():
        r = httpx.get(f"{BASE}/s49e-q6j2.json", params={"$limit": 50000}, timeout=120)
        r.raise_for_status()
        CACHE.write_text(json.dumps(r.json()))
    rows = json.loads(CACHE.read_text())
    # Some records carry a placeholder coordinate (many unrelated blocks at one point): drop them.
    at = defaultdict(set)
    for m in rows:
        ll = m.get("latlng")
        if ll:
            at[(round(float(ll["latitude"]), 5), round(float(ll["longitude"]), 5))].add(m["blockface"])
    bad = {k for k, v in at.items() if len(v) >= 3}
    return [m for m in rows if m.get("latlng") and
            (round(float(m["latlng"]["latitude"]), 5), round(float(m["latlng"]["longitude"]), 5)) not in bad]


def occupancy() -> dict[str, str]:
    if time.time() - _occ["t"] > 60:
        r = httpx.get(f"{BASE}/e7h6-4a3e.json", params={"$limit": 50000}, timeout=120)
        _occ["d"] = {x["spaceid"]: x["occupancystate"] for x in r.json()} if r.status_code == 200 else {}
        _occ["t"] = time.time()
    return _occ["d"]


def miles(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.pi / 180
    h = (math.sin((b_lat - a_lat) * p / 2) ** 2
         + math.cos(a_lat * p) * math.cos(b_lat * p) * math.sin((b_lon - a_lon) * p / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def _limit_min(s: str) -> int | None:
    m = re.search(r"(\d+)\s*(HR|MIN)", s.upper())
    return int(m.group(1)) * (60 if m.group(2) == "HR" else 1) if m else None


def _rate(s: str) -> float:
    nums = [float(x) for x in re.findall(r"\d+\.?\d*", s or "")]
    return max(nums) if nums else 0.0


def search(lat: float, lon: float, radius_mi: float, when: datetime, minutes: int, limit: int = 300) -> list[dict]:
    blocks = defaultdict(list)
    for m in load_meters():
        ll = m.get("latlng")
        if not ll:
            continue
        d = miles(lat, lon, float(ll["latitude"]), float(ll["longitude"]))
        if d <= radius_mi:
            blocks[m["blockface"]].append((d, m))
    occ = occupancy()
    out = []
    for name, ms in blocks.items():
        d, first = min(ms, key=lambda x: x[0])
        rule = Rule(METERED, limit_min=_limit_min(first.get("timelimit", "")),
                    price_per_hour=_rate(first.get("raterange", "")), **ASSUMED)
        v = evaluate([rule], when, minutes)
        states = [occ.get(m["spaceid"]) for _, m in ms]
        free = sum(s == "VACANT" for s in states)
        out.append({
            "street": name, "miles": round(d, 2), "lat": float(first["latlng"]["latitude"]),
            "lon": float(first["latlng"]["longitude"]), "meters": len(ms),
            "limit_min": rule.limit_min, "rate": rule.price_per_hour, "legal": v.legal, "cost": v.cost,
            "move_by": v.move_by.isoformat() if v.move_by else None,
            "charging_starts": v.charging_starts.isoformat() if v.charging_starts else None,
            "free_now": free if any(states) else None, "reasons": v.reasons,
        })
    return sorted(out, key=lambda b: b["miles"])[:limit]


def geocode(q: str) -> tuple[float, float] | None:
    """OpenStreetMap Nominatim: free, 1 request/second, identify the app."""
    r = httpx.get("https://nominatim.openstreetmap.org/search", timeout=30,
                  params={"q": q, "format": "json", "limit": 1},
                  headers={"User-Agent": "MetaHackathonParkingHelper/0.1"})
    j = r.json()
    return (float(j[0]["lat"]), float(j[0]["lon"])) if j else None
