from parking.rules import NO_PARKING
from parking.signs import parse_boxes, to_rules


def test_parse_boxes():
    text = "<0f>0<|box;x1=10;y1=20;x2=110;y2=220;w=640;h=480|>,0<|mask;x=0;y=0;data=1,1,~abc|>"
    b = parse_boxes(text)[0]
    assert (b.x1, b.y1, b.x2, b.y2) == (10, 20, 110, 220)


def test_to_rules_skips_info_and_illegible():
    info = {"kind": "info", "days": [], "start": "00:00", "end": "24:00"}
    np = {"kind": NO_PARKING, "days": ["Mon"], "start": "08:00", "end": "10:00"}
    assert to_rules({"transcription": "x", "legible": False, "rules": [np]}) == []
    rules = to_rules({"transcription": "x", "legible": True, "rules": [info, np]})
    assert len(rules) == 1 and rules[0].days == frozenset({0}) and rules[0].start_min == 480
