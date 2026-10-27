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
