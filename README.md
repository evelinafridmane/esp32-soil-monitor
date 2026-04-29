# Soil Monitor

An ESP32-C3 + MicroPython soil moisture monitor for houseplants, with a
Python backend for long-term storage and a web dashboard.

## What it does

- Reads soil moisture from a capacitive sensor on an ESP32-C3 Super Mini.
- Drives an RGBW status LED so moisture level is visible at a glance
  (red = dry, yellow = getting dry, green = happy, off = too wet).
- POSTs readings over WiFi to a FastAPI backend, which stores them in
  PostgreSQL. (Backend currently runs on a laptop on the LAN; will move
  to a cloud VM later.)
- Web dashboard at `/` — one card per plant with current status. Click a
  plant for a Chart.js graph of moisture over time, plus per-type care
  info (description + watering habits) joined from a `plant_types` table.
- Add new plants from the web (`/plants/new`) — pick the type from a
  dropdown of existing types, or type a new one in the text field.
- Edit existing plants (`/plants/{id}/edit`) — rename, change type,
  retune moisture thresholds without writing SQL. Same page also has
  a **Delete plant** button (with a confirmation dialog) that removes
  the plant along with all its readings and waterings.
- Log waterings — a "💧 Just watered" button on each home card and on
  the plant detail page records the event. The detail page shows the
  most recent watering and the count over the last 30 days. The
  moisture chart overlays blue dots on watering timestamps so you can
  see how the soil responded.
- AI-generated care info: when a new `plant_type` is added, the
  backend calls Groq (`llama-3.1-8b-instant`) in the background and
  fills in `description` + `watering_habits` automatically.
- Per-IP rate limiting on all mutating endpoints via `slowapi` — for
  example `POST /readings` is capped at 60/min and `POST /plants` at
  5/min (the latter both prevents spam plant creation and protects
  the Groq quota). Over-limit requests get HTTP 429.
- *Planned:* Per-plant thresholds fetched by the chip on boot, so each
  plant's LED reflects values appropriate for that species (a succulent
  and a fern have very different "happy" ranges).
- *Planned:* API token on `POST /readings` and basic auth on the
  human-facing mutating endpoints, before the backend goes on a
  public cloud VM.

## Hardware

- ESP32-C3 Super Mini running MicroPython v1.28.0
- Capacitive Soil Moisture Sensor v1.2 — powered from 3.3V, AOUT on GPIO 3
- RGBW LED strip driven through NPN transistors (red = GPIO 4, green = GPIO 10;
  blue and white not yet wired)

## Repo layout

- `firmware/` — MicroPython code that runs on the ESP32
- `backend/` — FastAPI + PostgreSQL backend that receives readings and serves the dashboard
  - `app.py` — routes (POST readings, home grid, plant detail, add/edit plant forms)
  - `templates/` — Jinja templates (`base.html`, `home.html`, `plant_detail.html`, `plant_new.html`, `plant_edit.html`)
  - `static/css/custom.css` — theme overrides for Pico

## Backend stack

- **FastAPI** — web framework (routes, async, auto JSON handling, form parsing via `Form(...)`)
- **Jinja2** — server-side HTML templating
- **Pico.css v2** + custom CSS variables — styling, no build step
- **Chart.js v4** + `chartjs-adapter-date-fns` — moisture chart on the detail page (with watering-event overlay)
- **Lottie player** (`@lottiefiles/lottie-player`) — animated plant illustration
- **Outfit + Fraunces + JetBrains Mono** (Google Fonts) — body / serif headings / numeric data
- **Pydantic** — request body validation
- **psycopg** (v3) — async PostgreSQL driver
- **python-multipart** — form-data parsing
- **PostgreSQL 16** — database
- **python-dotenv** — loads `.env` so credentials stay out of code
- **groq** (Python SDK) — AI calls for auto-generated plant care info
- **slowapi** — per-IP rate limiting on POST endpoints

## Database schema

- `plants` — id, name, plant_type, three threshold columns, created_at
- `readings` — id, plant_id (FK), moisture_raw, recorded_at; indexed on `(plant_id, recorded_at DESC)`
- `plant_types` — name (PK), description, watering_habits, created_at — care info shared across all plants of a type
- `waterings` — id, plant_id (FK), watered_at, notes; indexed on `(plant_id, watered_at DESC)`

## Flashing & uploading

1. Flash MicroPython v1.28.0 for `ESP32_GENERIC_C3` once, using the
   [ESP Web Tool](https://espressif.github.io/esptool-js/).
2. In `firmware/`, create your local config files (both are gitignored):
   - `secrets.py` with `WIFI_SSID` and `WIFI_PASSWORD`.
   - `config.py` — copy `config.example.py` and fill in `BACKEND_URL`
     (e.g. `http://<your-laptop-LAN-IP>:8000/readings`), `PLANT_ID`, and
     `POST_EVERY_N_READS`.
3. Copy all three files to the chip:
   ```
   mpremote cp firmware/main.py :main.py
   mpremote cp firmware/secrets.py :secrets.py
   mpremote cp firmware/config.py :config.py
   ```
4. Reset the chip (`mpremote reset`) and the code runs automatically on boot.

## Status

Local pipeline complete: chip reads moisture every second, drives the LED
locally, and POSTs a reading to FastAPI every 5 minutes. Readings land in
PostgreSQL. The web dashboard is live (home grid + plant detail page with
Chart.js graph and watering-event overlay). Plants can be added, edited,
and deleted via the web. Watering events can be logged from any page.
New plant types get auto-generated care info via Groq. All mutating
endpoints are rate-limited per-IP.

Next: API token on `POST /readings`, then basic auth on human-facing
mutating endpoints, then cloud deployment.

## License

TBD
