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
