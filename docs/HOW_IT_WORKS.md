# How it works

## Request flow
1. **Search**: an address is geocoded (OpenStreetMap Nominatim) or a pin is dropped with the *Drop pin* button.
2. **Trip**: arrival time plus a stay of days, hours and minutes (or spoken, see Voice).
3. `GET /api/nearby` finds metered blocks within the radius (max 10 miles) from the LADOT inventory and, for each block,
   - evaluates the trip with the rules engine (`parking/rules.py`): legal or not, total cost, move-by time, when charging starts;
   - reads live sensor data: spots open, sensors, and the time of the newest report;
   - attaches street-sweeping status: the first sweep that overlaps the stay (**move by**) and the next sweep.
4. Blocks are sorted: can park first, free before cheap before expensive, then nearest.
5. `GET /api/risk` and `GET /api/heat` add ticket statistics, map hotspots and the 24 hour chart.

## Data sources (data.lacity.org, Socrata)
| Dataset | ID | Used for |
|---|---|---|
| LADOT Metered Parking Inventory & Policies | `s49e-q6j2` | blocks, rates, time limits, coordinates |
| LADOT Parking Meter Occupancy | `e7h6-4a3e` | live vacant/occupied per sensor meter |
| Parking Citations | `4f5p-udkv` | ticket totals, violation mix, hourly pattern, hotspots (aggregated, no plates) |
| Posted Street Sweeping Routes | `krk7-ayq2` | sweeping times; the weekday is the suffix of `route_no` (M, Tu, W, Th, F) |

## Live data: what it means
- Only about 3,800 of 35,000 meters have a sensor. Blocks without sensors show no count; that is not "full".
- Sensors report on change, so a quiet sensor can show an old reading. The card shows the newest report time.
- Report times are UTC; the page shows relative ages ("3 min ago"). *Live refresh* re-queries every 60 s.

## Limits and assumptions
- Meter hours are assumed 8am to 6pm Monday to Saturday (the inventory has none). Signs always control.
- A time limit applies inside each active window, so a multi-day stay on a limited meter is flagged illegal.
- Sweeping is matched by street name only (the dataset has no geometry) and can give false matches.
- Metered blocks only. Unmetered curbs, permits and one-off restrictions are not covered.
- Coordinates shared by 3+ unrelated blocks are placeholders and are dropped.

## Meta models
SAM 3.1 finds signs in a photo, Muse Spark 1.3 turns each crop into structured rules, Muse Voice Transcribe 1.0
(WAV only; the page converts the recording to 16 kHz WAV) takes spoken trips, and Muse Image 1.0 draws the verdict
overlay. These need `MODEL_API_KEY`; without it the endpoints return 503 and the page hides the controls.

## Hosting
`render.yaml` is a Render blueprint (free plan). Pushing to `main` redeploys. No secrets are set on the public site.

## Tests
`python -m pytest` runs the rules engine, meter search and sorting, sweeping and live-data logic, civic data queries
(network mocked), voice parsing and the API. No test calls the Meta API.
