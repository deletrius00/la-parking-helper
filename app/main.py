import io
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from PIL import Image
from pydantic import BaseModel

from parking.mapillary import sign_crops
from parking.rules import Rule, evaluate
from parking import civic, meters
from src import config
from parking.overlay import overlay
from parking.signs import read_image, read_sign, to_rules
from parking.voice import parse_trip, transcribe

app = FastAPI()


def _need_ai() -> None:
    """Public deployments run without a Meta key, so the model-backed endpoints are switched off."""
    if not config.API_KEY:
        raise HTTPException(503, "AI features are disabled on this deployment (no MODEL_API_KEY).")


@app.get("/api/config")
def cfg():
    return {"ai": bool(config.API_KEY)}


@app.on_event("startup")
def warm():
    try:
        meters.load_meters()
    except Exception:
        pass


def _dump(rules: list[Rule]) -> list[dict]:
    return [{**asdict(r), "days": sorted(r.days)} for r in rules]


@app.post("/api/read")
async def read(file: UploadFile = File(...)):
    _need_ai()
    r = read_image(Image.open(io.BytesIO(await file.read())))
    return {**r, "rules": _dump(r["rules"])}


@app.post("/api/voice")
async def voice(file: UploadFile = File(...)):
    _need_ai()
    text = transcribe(await file.read())
    return {"heard": text, **parse_trip(text)}


@app.post("/api/overlay")
async def overlay_ep(status: str, caption: str, file: UploadFile = File(...)):
    _need_ai()
    return Response(overlay(await file.read(), status, caption), media_type="image/jpeg")


@app.get("/api/mapillary")
def mapillary(lat: float, lon: float, count: int = 4):
    _need_ai()
    out = []
    for p in sign_crops(lat, lon, count=count):
        sign = read_sign(Image.open(p))
        out.append({"image": p.name, "text": sign["transcription"], "legible": sign["legible"],
                    "rules": _dump(to_rules(sign))})
    return out


@app.get("/api/geocode")
def geocode(q: str):
    g = meters.geocode(q)
    return {"lat": g[0], "lon": g[1]} if g else {"error": "address not found"}


@app.get("/api/nearby")
def nearby(lat: float, lon: float, miles: float = 1.0, when: str = "", minutes: int = 60):
    t = datetime.fromisoformat(when) if when else datetime.now()
    blocks = meters.search(lat, lon, min(miles, 10.0), t, minutes)
    flags = civic.sweep_flags([b["street"] for b in blocks])
    for b in blocks:
        b["sweep"] = flags.get(b["street"], [])
    return blocks


@app.get("/api/risk")
def risk(lat: float, lon: float, radius_m: int = 400):
    return civic.citation_risk(lat, lon, min(radius_m, 2000))


@app.get("/api/heat")
def heat(lat: float, lon: float, radius_m: int = 800):
    r = min(radius_m, 1600)
    return {"cells": civic.ticket_grid(lat, lon, r), "hours": civic.ticket_hours(lat, lon, r)}


@app.get("/api/sweeping")
def sweeping(streets: str):
    return civic.sweeping_for([x for x in streets.split("|") if x])


class Ask(BaseModel):
    rules: list[dict]
    when: str
    minutes: int


@app.post("/api/evaluate")
def ask(a: Ask):
    rules = [Rule(**{**r, "days": frozenset(r["days"])}) for r in a.rules]
    v = evaluate(rules, datetime.fromisoformat(a.when), a.minutes)
    return {k: (x.isoformat() if isinstance(x, datetime) else x) for k, x in asdict(v).items()}


@app.get("/mapillary_crops/{name}")
def crop(name: str):
    from fastapi.responses import FileResponse
    return FileResponse(f"photos/mapillary_crops/{name}")


@app.get("/", response_class=HTMLResponse)
def home():
    return Path("app/index.html").read_text()
