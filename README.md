# LA Parking Helper

Meta Global AI Developer Hackathon project. Read LA parking signs from photos, say when and how long
you'll park, and see whether you can park there, what it costs and when you must move.

## Meta models used
- **SAM 3.1** finds signs in a photo.
- **Muse Spark 1.3** reads each sign into structured rules.
- **Muse Voice Transcribe 1.0** takes spoken trips ("Tuesday at 6pm for two hours").
- **Muse Image 1.0** draws a verdict overlay on the sign photo.

The yes/no decision is made by plain code (`parking/rules.py`), not by a model.

## Data
- [LADOT metered parking inventory](https://data.lacity.org) (blocks, rates, limits) and live meter occupancy.
  Metered blocks only; meter hours are assumed 8am-6pm Mon-Sat. Posted signs always control.
- Sample photos in `photos/` come from Wikimedia Commons, see `photos/SOURCES.md` for licences.

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
