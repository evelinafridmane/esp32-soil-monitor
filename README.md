# Soil Monitor

An ESP32-C3 + MicroPython soil moisture monitor for houseplants, with a planned
Python backend for long-term storage and a web dashboard.

## What it does

- Reads soil moisture from a capacitive sensor on an ESP32-C3 Super Mini.
- Drives an RGBW status LED so moisture level is visible at a glance
  (red = dry, yellow = getting dry, green = happy, off = too wet).
- *Planned:* POSTs readings over WiFi to a backend running on a cloud VM.
- *Planned:* Stores readings in PostgreSQL and serves a small dashboard.
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
2. Copy the application code to the chip:
   ```
   mpremote cp firmware/main.py :
   ```
3. Reset the chip (`mpremote reset`) and the code runs automatically on boot.

## Status

Early development. The device currently reads moisture and drives the LED
locally. WiFi, backend, database, and dashboard are the next milestones.

## License

TBD
