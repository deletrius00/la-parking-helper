"""LA open data beyond meters: parking-citation risk and posted street-sweeping routes."""
import re
from datetime import date, timedelta

import httpx

BASE = "https://data.lacity.org/resource"
_SUFFIX = r"\b(ST|AVE|BLVD|DR|RD|PL|WAY|LN|CT|HWY|PKWY|N|S|E|W)\b\.?"


def citation_risk(lat: float, lon: float, meters_radius: int = 400, top: int = 6) -> dict:
    """Aggregated last-12-month tickets near a point. Only violation type and fine are used, never plates."""
    since = (date.today() - timedelta(days=365)).isoformat()
    r = httpx.get(f"{BASE}/4f5p-udkv.json", timeout=60, params={
        "$select": "violation_description,count(*) as n,avg(fine_amount) as fine",
        "$where": f"within_circle(geocodelocation,{lat},{lon},{meters_radius}) AND issue_date > '{since}'",
        "$group": "violation_description", "$order": "n DESC", "$limit": 40})
    r.raise_for_status()
    rows = [x for x in r.json() if x["violation_description"] != "NO VIOLATION CODE"]
    total = sum(int(x["n"]) for x in rows)
    return {"total": total, "radius_m": meters_radius, "top": [
        {"violation": x["violation_description"].title(), "tickets": int(x["n"]),
         "avg_fine": round(float(x["fine"]))} for x in rows[:top]]}


def street_core(blockface: str) -> str:
    s = re.sub(r"^\d+\s+", "", blockface.upper())
    return re.sub(_SUFFIX, "", s).strip()


def sweeping_for(blockfaces: list[str], limit: int = 12) -> list[dict]:
    names = sorted({street_core(b) for b in blockfaces if len(street_core(b)) > 2})[:8]
    if not names:
        return []
    where = " OR ".join(f"upper(boundaries) like '%{n.replace(chr(39), '')}%'" for n in names)
    r = httpx.get(f"{BASE}/krk7-ayq2.json", params={"$where": where, "$limit": 200}, timeout=60)
    r.raise_for_status()
    seen, out = set(), []
    for x in r.json():
        k = (x["boundaries"], x["time_start"], x["time_end"])
        if k not in seen:
            seen.add(k)
            out.append({"route": x["route_no"].strip("* "), "start": x["time_start"],
                        "end": x["time_end"], "boundaries": x["boundaries"]})
    return out[:limit]


def _citation_where(lat: float, lon: float, meters_radius: int) -> str:
    since = (date.today() - timedelta(days=365)).isoformat()
    return f"within_circle(geocodelocation,{lat},{lon},{meters_radius}) AND issue_date > '{since}'"


def ticket_grid(lat: float, lon: float, meters_radius: int = 800, cells: int = 400) -> list[dict]:
    """Ticket counts per ~100 m grid cell, for a map heat layer."""
    r = httpx.get(f"{BASE}/4f5p-udkv.json", timeout=60, params={
        "$select": "round(loc_lat,3) as la,round(loc_long,3) as lo,count(*) as n",
        "$where": _citation_where(lat, lon, meters_radius), "$group": "la,lo", "$order": "n DESC", "$limit": cells})
    r.raise_for_status()
    return [{"lat": float(x["la"]), "lon": float(x["lo"]), "n": int(x["n"])} for x in r.json() if x.get("la")]


def ticket_hours(lat: float, lon: float, meters_radius: int = 800) -> list[int]:
    """24 hourly ticket counts (index = hour of day)."""
    r = httpx.get(f"{BASE}/4f5p-udkv.json", timeout=60, params={
        "$select": "floor(issue_time::number/100) as h,count(*) as n",
        "$where": _citation_where(lat, lon, meters_radius) + " AND issue_time IS NOT NULL",
        "$group": "h", "$limit": 30})
    r.raise_for_status()
    hours = [0] * 24
    for x in r.json():
        h = int(float(x["h"]))
        if 0 <= h < 24:
            hours[h] = int(x["n"])
    return hours


_routes: list[dict] = []


def sweep_flags(blockfaces: list[str]) -> dict[str, list[str]]:
    """Blocks whose street name appears in a posted sweeping route, with the sweep time windows.
    Name match only (the dataset has no geometry), so treat as 'may have sweeping'."""
    if not _routes:
        r = httpx.get(f"{BASE}/krk7-ayq2.json", params={"$limit": 2000}, timeout=60)
        r.raise_for_status()
        _routes.extend(r.json())
    out = {}
    for b in blockfaces:
        core = street_core(b)
        if len(core) < 4:
            continue
        times = sorted({f"{x['time_start']}-{x['time_end']}" for x in _routes if core in x["boundaries"].upper()})
        if times:
            out[b] = times[:3]
    return out
