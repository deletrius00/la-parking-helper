from parking.voice import _find_text


def test_find_text_walks_nested_response():
    resp = {"id": 1, "turns": [{"text": "park tuesday"}, {"alt": {"transcript": "at six pm"}}]}
    assert _find_text(resp) == "park tuesday at six pm"


def test_find_text_empty():
    assert _find_text({"turns": []}) == ""
