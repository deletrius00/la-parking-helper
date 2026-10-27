import io
from dataclasses import asdict
from datetime import datetime

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, Response
from PIL import Image
from pydantic import BaseModel

from parking.mapillary import sign_crops
from parking.rules import Rule, evaluate
from parking import meters
from parking.overlay import overlay
from parking.signs import read_image, read_sign, to_rules
from parking.voice import parse_trip, transcribe

app = FastAPI()


def _dump(rules: list[Rule]) -> list[dict]:
    return [{**asdict(r), "days": sorted(r.days)} for r in rules]


@app.post("/api/read")
async def read(file: UploadFile = File(...)):
    r = read_image(Image.open(io.BytesIO(await file.read())))
    return {**r, "rules": _dump(r["rules"])}


@app.post("/api/voice")
async def voice(file: UploadFile = File(...)):
    text = transcribe(await file.read())
    return {"heard": text, **parse_trip(text)}


@app.post("/api/overlay")
async def overlay_ep(status: str, caption: str, file: UploadFile = File(...)):
    return Response(overlay(await file.read(), status, caption), media_type="image/jpeg")


@app.get("/api/mapillary")
def mapillary(lat: float, lon: float, count: int = 4):
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
    return meters.search(lat, lon, min(miles, 10.0), t, minutes)


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


PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>LA Parking Helper</title>
<style>body{font:16px system-ui;max-width:680px;margin:2rem auto;padding:0 1rem}
section{border:1px solid #8884;border-radius:10px;padding:1rem;margin:1rem 0}
button,input,select{font:inherit;padding:.4rem .6rem;margin:.2rem 0}pre{white-space:pre-wrap}
.ok{color:#0a7d2c}.bad{color:#c0262d}img{max-width:160px}</style>
<link rel=stylesheet href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<h1>LA Parking Helper</h1>
<section><h3>Where can I park? (LADOT meter database)</h3>
<input id=addr placeholder="Street address, e.g. 200 N Spring St, Los Angeles" style="width:60%"> <button onclick=geo()>Go</button>
<p>Or click the map to drop a pin. Radius <select id=rad><option>0.25</option><option selected>0.5</option><option>1</option><option>2</option><option>5</option><option>10</option></select> miles
&nbsp;<button onclick=near()>Find parking</button></p>
<div id=map style="height:340px;border-radius:8px"></div><div id=nres></div>
<small>Uses the meter inventory only. Streets without meters are not covered, hours are assumed 8am-6pm Mon-Sat, and signs always control.</small></section>
<section><h3>1. Read signs</h3>
<p>Upload a close-up photo of a sign:<br><input type=file id=f accept="image/*"> <button onclick=up()>Read</button></p>
<p>Or Mapillary near
<select id=spot><option value="34.0577,-118.3004">Koreatown</option><option value="34.1016,-118.3267">Hollywood</option>
<option value="34.0446,-118.2512">Downtown</option></select> <button onclick=mly()>Fetch + read</button></p>
<div id=signs>No signs read yet.</div></section>
<section><h3>2. Can I park?</h3>
<button onclick=rec() id=mic>&#127908; Say it</button> <span id=heard></span><br>Arrive <input type=datetime-local id=when> Stay (min) <input type=number id=mins value=60 style=width:5em>
<button onclick=check()>Check</button><div id=out></div><div id=ov></div></section>
<script>
let pin=null,layer=null;const map=L.map('map').setView([34.0522,-118.2437],12);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap'}).addTo(map);
function setPin(a,b){pin?pin.setLatLng([a,b]):pin=L.marker([a,b]).addTo(map);map.setView([a,b],14)}
map.on('click',e=>setPin(e.latlng.lat,e.latlng.lng));
async function geo(){const r=await (await fetch('/api/geocode?q='+encodeURIComponent($('addr').value))).json();
 if(r.error)return $('nres').textContent=r.error;setPin(r.lat,r.lon);near()}
async function near(){if(!pin)return $('nres').textContent='Enter an address or click the map first.';
 $('nres').textContent='Searching...';const p=pin.getLatLng();
 const r=await (await fetch(`/api/nearby?lat=${p.lat}&lon=${p.lng}&miles=${$('rad').value}&when=${$('when').value}&minutes=${$('mins').value}`)).json();
 layer&&layer.remove();layer=L.layerGroup().addTo(map);
 r.forEach(b=>L.circleMarker([b.lat,b.lon],{radius:6,color:b.legal?'#0a7d2c':'#c0262d'}).bindPopup(b.street).addTo(layer));
 const ok=r.filter(b=>b.legal).length;
 $('nres').innerHTML=`<p><b>${ok}</b> blocks OK, <b>${r.length-ok}</b> not OK (nearest ${r.length} metered blocks)</p>`+r.slice(0,60).map(b=>
  `<p class=${b.legal?'ok':'bad'}>${b.legal?'&#10003;':'&#10007;'} <b>${b.street}</b> ${b.miles} mi - ${b.meters} meters, $${b.rate}/h, limit ${b.limit_min?b.limit_min+' min':'none'}`+
  (b.legal?` - est. $${b.cost}`:` - ${b.reasons[0]||''}`)+(b.free_now!=null?` - ${b.free_now} free now`:'')+
  (b.charging_starts?` - free until ${b.charging_starts.slice(5,16).replace('T',' ')}`:'')+'</p>').join('')}
let rules=[];const $=i=>document.getElementById(i);
$('when').value=new Date(Date.now()-new Date().getTimezoneOffset()*6e4).toISOString().slice(0,16);
const fmt=m=>String(m/60|0).padStart(2,'0')+':'+String(m%60).padStart(2,'0');
function show(items){$('signs').innerHTML=items.map(s=>`<p>${s.image?`<img src="/mapillary_crops/${s.image}"><br>`:''}<b>${s.legible?'':'(unclear) '}</b>${s.text||'nothing readable'}<br>`+
 s.rules.map(r=>`&rarr; ${r.kind} ${fmt(r.start_min)}-${fmt(r.end_min)} limit=${r.limit_min??'-'} $${r.price_per_hour}/h`).join('<br>')+'</p>').join('')||'No signs found.';
 rules=items.flatMap(s=>s.rules)}
async function up(){const f=$('f').files[0];if(!f)return;$('signs').textContent='Reading...';
 const fd=new FormData();fd.append('file',f);const r=await (await fetch('/api/read',{method:'POST',body:fd})).json();show([r]);if(r.sam_boxes!=null)$('signs').insertAdjacentHTML('beforeend',`<small>SAM 3.1 found ${r.sam_boxes} sign(s)</small>`)}
async function mly(){$('signs').textContent='Fetching from Mapillary (slow)...';const [a,b]=$('spot').value.split(',');
 show(await (await fetch(`/api/mapillary?lat=${a}&lon=${b}`)).json())}
async function check(){const r=await (await fetch('/api/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({rules,when:$('when').value,minutes:+$('mins').value})})).json();
 $('out').innerHTML=`<p class=${r.legal?'ok':'bad'}><b>${r.legal?'You can park':'Do not park'}</b> | cost $${r.cost}</p>`+
 (r.move_by?`<p>Move by ${r.move_by}</p>`:'')+(r.charging_starts?`<p>Free now; charging starts ${r.charging_starts}</p>`:'')+
 r.reasons.map(x=>`<p>${x}</p>`).join('');
 const f=$('f').files[0];if(f){$('ov').textContent='Drawing overlay (Muse Image)...';const q=new URLSearchParams({status:r.legal?(r.move_by?'warn':'ok'):'bad',
 caption:r.legal?`OK - $${r.cost}`+(r.move_by?` - move by ${r.move_by.slice(11,16)}`:''):'DO NOT PARK'});const fd=new FormData();fd.append('file',f);
 const o=await fetch('/api/overlay?'+q,{method:'POST',body:fd});$('ov').innerHTML=o.ok?`<img style="max-width:100%" src="${URL.createObjectURL(await o.blob())}">`:'overlay failed'}}
async function rec(){const b=$('mic');if(window.mr&&mr.state=='recording'){mr.stop();return}
 const st=await navigator.mediaDevices.getUserMedia({audio:true});window.mr=new MediaRecorder(st);const ch=[];mr.ondataavailable=e=>ch.push(e.data);
 mr.onstop=async()=>{st.getTracks().forEach(t=>t.stop());b.textContent='Working...';
  const ac=new AudioContext({sampleRate:16000});const buf=await ac.decodeAudioData(await new Blob(ch).arrayBuffer());
  const d=buf.getChannelData(0),w=new DataView(new ArrayBuffer(44+d.length*2)),S=(o,t)=>[...t].forEach((c,i)=>w.setUint8(o+i,c.charCodeAt(0)));
  S(0,'RIFF');w.setUint32(4,36+d.length*2,true);S(8,'WAVEfmt ');w.setUint32(16,16,true);w.setUint16(20,1,true);w.setUint16(22,1,true);
  w.setUint32(24,16000,true);w.setUint32(28,32000,true);w.setUint16(32,2,true);w.setUint16(34,16,true);S(36,'data');w.setUint32(40,d.length*2,true);
  d.forEach((x,i)=>w.setInt16(44+i*2,Math.max(-1,Math.min(1,x))*32767,true));
  const fd=new FormData();fd.append('file',new Blob([w],{type:'audio/wav'}),'c.wav');
  const r=await (await fetch('/api/voice',{method:'POST',body:fd})).json();$('heard').textContent='"'+r.heard+'"';
  $('when').value=r.when.slice(0,16);$('mins').value=r.minutes;b.innerHTML='&#127908; Say it'};
 mr.start();b.textContent='Stop';}
</script>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE
