# Soil Monitor

An ESP32-C3 + MicroPython soil moisture monitor for houseplants, with a planned
Python backend for long-term storage and a web dashboard.

## What it does

- Reads soil moisture from a capacitive sensor on an ESP32-C3 Super Mini.
- Drives an RGBW status LED so moisture level is visible at a glance
  (red = dry, yellow = getting dry, green = happy, off = too wet).
- POSTs readings over WiFi to a FastAPI backend, which stores them in
  PostgreSQL. (Backend currently runs on a laptop on the LAN; will move to
  a cloud VM once the dashboard is in place.)
- *Planned:* Web dashboard rendering recent readings as a chart.
- *Planned:* Per-plant thresholds — the LED color uses values configured per
  device so it reflects what's right for that specific plant (a succulent and
  a fern have very different "happy" ranges).

## Hardware

- ESP32-C3 Super Mini running MicroPython v1.28.0
- Capacitive Soil Moisture Sensor v1.2 — powered from 3.3V, AOUT on GPIO 3
- RGBW LED strip driven through NPN transistors (red = GPIO 4, green = GPIO 10;
  blue and white not yet wired)

## Repo layout

- `firmware/` — MicroPython code that runs on the ESP32
- `backend/` — FastAPI + PostgreSQL backend that receives readings and will serve the dashboard

## Backend stack

- **FastAPI** — web framework (routes, async, auto JSON handling)
- **Pydantic** — request body validation
- **psycopg** (v3) — PostgreSQL driver
- **PostgreSQL 16** — database
- **python-dotenv** — loads `.env` so credentials stay out of code

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

Early development. End-to-end pipeline works: the chip reads moisture every
second, drives the LED locally, and POSTs a reading to the FastAPI backend
every 5 minutes. Readings land in PostgreSQL. Web dashboard and a cloud
deployment are the next milestones.

## License

TBD
