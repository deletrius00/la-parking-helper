from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_home_serves_page():
    r = client.get("/")
    assert r.status_code == 200 and "LA Parking Helper" in r.text


def test_evaluate_endpoint():
    rule = {"kind": "metered", "days": [0, 1, 2, 3, 4], "start_min": 480, "end_min": 1080,
            "limit_min": 120, "price_per_hour": 4.0, "note": ""}
    r = client.post("/api/evaluate", json={"rules": [rule], "when": "2026-11-02T09:00", "minutes": 90}).json()
    assert r["legal"] and r["cost"] == 6.0 and r["move_by"] == "2026-11-02T11:00:00"


def test_geocode_not_found(monkeypatch):
    monkeypatch.setattr(main.meters, "geocode", lambda q: None)
    assert client.get("/api/geocode", params={"q": "nowhere"}).json() == {"error": "address not found"}


def test_nearby_caps_radius_at_ten_miles(monkeypatch):
    seen = {}
    monkeypatch.setattr(main.meters, "search", lambda lat, lon, mi, t, m: seen.setdefault("mi", mi) and [])
    client.get("/api/nearby", params={"lat": 34, "lon": -118, "miles": 50})
    assert seen["mi"] == 10.0
