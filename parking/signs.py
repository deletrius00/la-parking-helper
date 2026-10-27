"""Read parking signs from a photo: SAM 3.1 finds sign boxes, Spark turns each crop into rules."""
import base64
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from src import config
from src.client import get_client

from .rules import (ALL_DAYS, METERED, NO_PARKING, NO_STOPPING, PERMIT,
                    TIME_LIMIT, Rule)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
KINDS = [NO_PARKING, NO_STOPPING, PERMIT, TIME_LIMIT, METERED, "info"]

RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": KINDS},
        "days": {"type": "array", "items": {"type": "string", "enum": DAYS}},
        "start": {"type": "string", "description": "HH:MM 24h, 00:00 if all day"},
        "end": {"type": "string", "description": "HH:MM 24h, 24:00 if all day"},
        "limit_min": {"type": ["integer", "null"]},
        "price_per_hour": {"type": ["number", "null"]},
    },
    "required": ["kind", "days", "start", "end"],
}

SIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "transcription": {"type": "string"},
        "legible": {"type": "boolean"},
        "rules": {"type": "array", "items": RULE_SCHEMA},
    },
    "required": ["transcription", "legible", "rules"],
}

PROMPT = (
    "This is a US parking sign or a stack of signs (Los Angeles). Transcribe every word exactly, then "
    "convert it to SEPARATE rules, one per distinct restriction (e.g. no parking 8-10am Tue AND "
    "2 hour parking other times). Skip non-restrictions such as street names. "
    "days: all days the rule applies, empty list means every day. Times in 24h HH:MM. "
    "Set legible=false if you cannot read it confidently."
)

_BOX = re.compile(r"<\|box;(.*?)\|>")


@dataclass
class SignBox:
    x1: int
    y1: int
    x2: int
    y2: int


def _data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_boxes(text: str) -> list[SignBox]:
    boxes = []
    for m in _BOX.finditer(text):
        kv = dict(p.split("=", 1) for p in m.group(1).split(";") if "=" in p)
        boxes.append(SignBox(*(int(float(kv[k])) for k in ("x1", "y1", "x2", "y2"))))
    return boxes


def find_signs(img: Image.Image, prompt: str = "sign", min_frac: float = 0.004) -> list[SignBox]:
    """SAM 3.1 returns nothing for "parking sign" but works for "sign"; drop tiny boxes."""
    client = get_client()
    chunks = []
    with client.responses.stream(
        model=config.SEGMENT_MODEL,
        input=[{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": _data_url(img)},
        ]}],
    ) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                chunks.append(event.delta)
    min_area = min_frac * img.width * img.height
    return [b for b in parse_boxes("".join(chunks)) if (b.x2 - b.x1) * (b.y2 - b.y1) >= min_area]


def read_sign(crop: Image.Image) -> dict:
    client = get_client()
    resp = client.chat.completions.create(
        model=config.TEXT_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": _data_url(crop)}},
        ]}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "ParkingSign", "schema": SIGN_SCHEMA}},
    )
    return json.loads(resp.choices[0].message.content)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def to_rules(sign: dict) -> list[Rule]:
    if not sign["legible"]:
        return []
    out = []
    for r in sign["rules"]:
        if r["kind"] == "info":
            continue
        out.append(Rule(
            kind=r["kind"], days=frozenset(DAYS.index(d) for d in r["days"]) or ALL_DAYS,
            start_min=_minutes(r["start"]), end_min=_minutes(r["end"]),
            limit_min=r.get("limit_min"), price_per_hour=r.get("price_per_hour") or 0.0,
            note=sign["transcription"],
        ))
    return out


def read_photo(path: Path, pad: float = 0.08) -> list[dict]:
    """Return one dict per detected sign: box, parsed sign dict and its rules."""
    img = Image.open(path)
    out = []
    for b in find_signs(img):
        px, py = int((b.x2 - b.x1) * pad), int((b.y2 - b.y1) * pad)
        crop = img.crop((max(b.x1 - px, 0), max(b.y1 - py, 0),
                         min(b.x2 + px, img.width), min(b.y2 + py, img.height)))
        sign = read_sign(crop)
        out.append({"box": b, "sign": sign, "rules": to_rules(sign)})
    return out


def read_image(img: Image.Image, pad: float = 0.08) -> dict:
    """SAM finds signs, Spark reads each crop; falls back to the whole photo if SAM finds none."""
    crops = []
    for b in find_signs(img):
        px, py = int((b.x2 - b.x1) * pad), int((b.y2 - b.y1) * pad)
        crops.append(img.crop((max(b.x1 - px, 0), max(b.y1 - py, 0),
                               min(b.x2 + px, img.width), min(b.y2 + py, img.height))))
    signs = [read_sign(c) for c in crops] or [read_sign(img)]
    return {
        "text": " | ".join(s["transcription"] for s in signs if s["transcription"]),
        "legible": any(s["legible"] for s in signs),
        "rules": [r for s in signs for r in to_rules(s)],
        "sam_boxes": len(crops),
    }
