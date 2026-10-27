from parking import civic


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_street_core_strips_number_and_suffix():
    assert civic.street_core("101 TEMPLE ST") == "TEMPLE"
    assert civic.street_core("2801 JAMES M. WOOD BLVD") == "JAMES M. WOOD"


def test_citation_risk_ignores_no_violation_code(monkeypatch):
    rows = [{"violation_description": "RED ZONE", "n": "10", "fine": "93.4"},
            {"violation_description": "NO VIOLATION CODE", "n": "99", "fine": "0"}]
    monkeypatch.setattr(civic.httpx, "get", lambda *a, **k: _Resp(rows))
    r = civic.citation_risk(34.05, -118.24)
    assert r["total"] == 10 and r["top"] == [{"violation": "Red Zone", "tickets": 10, "avg_fine": 93}]


def test_sweeping_dedupes_and_builds_query(monkeypatch):
    seen = {}
    row = {"route_no": "* 4P1 M", "time_start": "10:00 AM", "time_end": "1:00 PM", "boundaries": "Temple St to 3rd St"}

    def fake(url, params=None, **k):
        seen.update(params)
        return _Resp([row, dict(row)])

    monkeypatch.setattr(civic.httpx, "get", fake)
    out = civic.sweeping_for(["101 TEMPLE ST"])
    assert len(out) == 1 and out[0]["route"] == "4P1 M"
    assert "like '%TEMPLE%'" in seen["$where"]


def test_sweeping_with_no_streets_makes_no_request(monkeypatch):
    monkeypatch.setattr(civic.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert civic.sweeping_for([]) == []


def test_ticket_grid_and_hours_parse(monkeypatch):
    calls = []

    def fake(url, params=None, **k):
        calls.append(params["$select"])
        if "round" in params["$select"]:
            return _Resp([{"la": "34.047", "lo": "-118.252", "n": "7"}, {"n": "1"}])
        return _Resp([{"h": "8", "n": "5"}, {"h": "25", "n": "9"}])

    monkeypatch.setattr(civic.httpx, "get", fake)
    assert civic.ticket_grid(34.05, -118.24) == [{"lat": 34.047, "lon": -118.252, "n": 7}]
    hours = civic.ticket_hours(34.05, -118.24)
    assert len(hours) == 24 and hours[8] == 5 and sum(hours) == 5


def test_route_day_and_clock_parsing():
    assert civic._route_day("4P182 Tu") == 1 and civic._route_day("10P142 Th") == 3
    assert civic._route_day("* 17P100") is None
    assert civic._clock("10:00 AM") == 600 and civic._clock("1:00 PM") == 780 and civic._clock("12:00 AM") == 0


def test_sweep_windows_match_street_name_and_day(monkeypatch):
    monkeypatch.setattr(civic, "_routes", [
        {"route_no": "4P1 Tu", "time_start": "10:00 AM", "time_end": "1:00 PM", "boundaries": "Temple St to 3rd St"},
        {"route_no": "9P9 M", "time_start": "8:00 AM", "time_end": "10:00 AM", "boundaries": "Adams Blvd to Jefferson Blvd"},
        {"route_no": "* 17P100", "time_start": "8:00 AM", "time_end": "10:00 AM", "boundaries": "Temple St"}])
    wins = civic.sweep_windows(["101 TEMPLE ST", "5 OAK ST", "9 X ST"])
    assert wins == {"101 TEMPLE ST": [{"day": 1, "start": 600, "end": 780}]}  # no-weekday route skipped


def test_sweep_status_move_by_vs_next():
    from datetime import datetime
    w = [{"day": 1, "start": 600, "end": 720}]  # Tuesday 10:00-12:00
    mon9 = datetime(2026, 11, 2, 9, 0)
    assert civic.sweep_status(w, mon9, 60) == {"move_by": None, "next": "2026-11-03T10:00:00"}
    assert civic.sweep_status(w, mon9, 3 * 1440)["move_by"] == "2026-11-03T10:00:00"
    during = datetime(2026, 11, 3, 11, 0)  # parked during the sweep window: move now
    assert civic.sweep_status(w, during, 30)["move_by"] == "2026-11-03T11:00:00"
    assert civic.sweep_status([], mon9, 60) is None
