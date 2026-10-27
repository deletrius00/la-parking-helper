import json
from datetime import datetime

from parking import meters

MON_9AM = datetime(2026, 11, 2, 9, 0)


def _m(sid, block, lat, lon, limit="2HR", rate="$2.00"):
    return {"spaceid": sid, "blockface": block, "latlng": {"latitude": str(lat), "longitude": str(lon)},
            "timelimit": limit, "raterange": rate}


def test_miles_zero_and_known_distance():
    assert meters.miles(34.05, -118.24, 34.05, -118.24) == 0
    assert 68 < meters.miles(34.0, -118.0, 35.0, -118.0) < 70  # one degree of latitude


def test_limit_and_rate_parsing():
    assert meters._limit_min("2HR") == 120
    assert meters._limit_min("30MIN") == 30
    assert meters._limit_min("NO LIMIT") is None
    assert meters._rate("$0.50 - $6.00") == 6.0
    assert meters._rate("") == 0.0


def test_search_sorts_legal_cheap_first_and_filters_radius(monkeypatch):
    data = [
        _m("a", "1 CHEAP ST", 34.0500, -118.2400, "4HR", "$1.00"),
        _m("b", "2 PRICEY ST", 34.0501, -118.2400, "4HR", "$6.00"),
        _m("c", "3 SHORT ST", 34.0502, -118.2400, "30MIN", "$1.00"),
        _m("d", "4 FAR ST", 35.0, -118.2400),
    ]
    monkeypatch.setattr(meters, "load_meters", lambda: data)
    monkeypatch.setattr(meters, "occupancy", lambda: {"a": "VACANT"})
    out = meters.search(34.05, -118.24, 1.0, MON_9AM, 90)
    assert [b["street"] for b in out] == ["1 CHEAP ST", "2 PRICEY ST", "3 SHORT ST"]
    assert out[0]["legal"] and out[0]["cost"] == 1.5 and out[0]["free_now"] == 1
    assert not out[2]["legal"] and out[2]["reasons"]


def test_load_meters_drops_placeholder_coordinates(tmp_path, monkeypatch):
    rows = [_m(str(i), f"{i} OTHER BLVD", 34.0522, -118.2437) for i in range(3)]
    rows.append(_m("ok", "9 REAL ST", 34.06, -118.25))
    cache = tmp_path / "meters.json"
    cache.write_text(json.dumps(rows))
    monkeypatch.setattr(meters, "CACHE", cache)
    assert [m["spaceid"] for m in meters.load_meters()] == ["ok"]
