"""Muse Voice Transcribe (WAV only) and Spark parsing of 'Tuesday 6pm for two hours'."""
import json
import os
from datetime import datetime

import httpx

from src import config
from src.client import get_client


def transcribe(wav: bytes) -> str:
    r = httpx.post(
        f"{config.API_BASE}/asr/transcribe",
        headers={"Authorization": f"Bearer {config.API_KEY}", "Accept": "application/json"},
        files={
            "request": (None, json.dumps({"model": config.TRANSCRIBE_MODEL, "audioEncoding": "WAV",
                                          "mode": "PUSH_TO_TALK"}), "application/json"),
            "audio": ("clip.wav", wav, "audio/wav"),
        },
        timeout=120,
    )
    r.raise_for_status()
    return _find_text(r.json())


def _find_text(obj) -> str:
    """The transcript field name is undocumented: join every 'text'/'transcript' string found."""
    out = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in ("text", "transcript") and isinstance(v, str):
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return " ".join(out).strip()


SCHEMA = {"type": "object", "properties": {
    "when": {"type": "string", "description": "ISO local datetime YYYY-MM-DDTHH:MM"},
    "minutes": {"type": "integer"}}, "required": ["when", "minutes"]}


def parse_trip(text: str, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    resp = get_client().chat.completions.create(
        model=config.TEXT_MODEL,
        messages=[{"role": "user", "content":
                   f"Now is {now:%A %Y-%m-%d %H:%M}. From this request, give the arrival time and "
                   f"stay length in minutes (default 60, arrival now if unspecified): {text!r}"}],
        response_format={"type": "json_schema", "json_schema": {"name": "Trip", "schema": SCHEMA}},
    )
    return json.loads(resp.choices[0].message.content)
