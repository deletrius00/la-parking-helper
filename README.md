# LA Parking Helper

Meta Global AI Developer Hackathon project. Read LA parking signs from photos, say when and how long
you'll park, and see whether you can park there, what it costs and when you must move.

## Meta models used
- **SAM 3.1** finds signs in a photo.
- **Muse Spark 1.3** reads each sign into structured rules.
- **Muse Voice Transcribe 1.0** takes spoken trips ("Tuesday at 6pm for two hours").
- **Muse Image 1.0** draws a verdict overlay on the sign photo.

The yes/no decision is made by plain code (`parking/rules.py`), not by a model.

## Features
- Address search or map pin, radius up to 10 miles, stay length and arrival time (or say it by voice).
- Blocks ranked free, then cheapest, with the total cost for your stay, move-by time and live free spots.
- Ticket risk from LA parking citations (12 months, aggregated) and posted street-sweeping routes.
- Read a sign photo (SAM 3.1 + Spark), check it against your trip, get a Muse Image verdict overlay.

## Data
- [LADOT metered parking inventory](https://data.lacity.org) (blocks, rates, limits) and live meter occupancy.
  Metered blocks only; meter hours are assumed 8am-6pm Mon-Sat. Posted signs always control.
- Sample photos in `photos/` come from Wikimedia Commons, see `photos/SOURCES.md` for licences.

## Live demo
**Live: https://la-parking-helper.onrender.com/** (free plan, first visit may take ~30 s to wake). The public site runs the meter search, map, ticket risk and sweeping layers.
The Meta-model features (sign photo, voice, overlay) are off there to protect the API credit; run locally with a key to use them.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/deletrius00/la-parking-helper)

## Run
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add MODEL_API_KEY (Meta Model API)
.venv/bin/uvicorn app.main:app --port 8000
.venv/bin/python -m pytest
```

## Limits
Not legal advice. Street-level imagery from Mapillary was too low resolution to read signs, so signs
are read from close-up photos. Address search needs a street address, not an intersection.
