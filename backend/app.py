import os
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


STATUS_LABELS = {
    "happy": "Happy",
    "getting_dry": "Getting dry",
    "dry": "Needs water",
    "too_wet": "Too wet",
    "no_data": "No data yet",
}


def compute_status(moisture_raw, t_dry, t_getting_dry, t_too_wet):
    if moisture_raw is None:
        return "no_data"
    if moisture_raw >= t_dry:
        return "dry"
    if moisture_raw >= t_getting_dry:
        return "getting_dry"
    if moisture_raw >= t_too_wet:
        return "happy"
    return "too_wet"


def humanize_time_ago(dt):
    if dt is None:
        return None
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


@app.get("/")
async def home(request: Request):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT
                    p.id, p.name, p.plant_type,
                    p.threshold_dry, p.threshold_getting_dry, p.threshold_too_wet,
                    r.moisture_raw, r.recorded_at
                FROM plants p
                LEFT JOIN LATERAL (
                    SELECT moisture_raw, recorded_at
                    FROM readings
                    WHERE plant_id = p.id
                    ORDER BY recorded_at DESC
                    LIMIT 1
                ) r ON true
                ORDER BY p.id
            """)
            rows = await cur.fetchall()

    plants = []
    for (pid, name, ptype, t_dry, t_gd, t_tw, mraw, recorded_at) in rows:
        status = compute_status(mraw, t_dry, t_gd, t_tw)
        plants.append({
            "id": pid,
            "name": name,
            "plant_type": ptype,
            "moisture_raw": mraw,
            "last_reading_text": humanize_time_ago(recorded_at),
            "status": status,
            "status_label": STATUS_LABELS[status],
        })

    return templates.TemplateResponse(request, "home.html", {"plants": plants})


class ReadingIn(BaseModel):
    plant_id: int
    moisture_raw: int


@app.get("/plants/new")
async def new_plant_form(request: Request):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT name FROM plant_types ORDER BY name")
            plant_types = [row[0] for row in await cur.fetchall()]
    return templates.TemplateResponse(request, "plant_new.html", {"plant_types": plant_types})


@app.post("/plants")
async def create_plant(
    name: str = Form(...),
    plant_type: str = Form(""),
    threshold_dry: int = Form(...),
    threshold_getting_dry: int = Form(...),
    threshold_too_wet: int = Form(...),
):
    plant_type_clean = plant_type.strip() or None

    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO plants
                    (name, plant_type, threshold_dry, threshold_getting_dry, threshold_too_wet)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (name.strip(), plant_type_clean, threshold_dry, threshold_getting_dry, threshold_too_wet))
            row = await cur.fetchone()

    return RedirectResponse(url=f"/plants/{row[0]}", status_code=303)


@app.get("/plants/{plant_id}/edit")
async def edit_plant_form(request: Request, plant_id: int):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, name, plant_type,
                       threshold_dry, threshold_getting_dry, threshold_too_wet
                FROM plants WHERE id = %s
            """, (plant_id,))
            plant_row = await cur.fetchone()
            if plant_row is None:
                raise HTTPException(status_code=404, detail="Plant not found")
            await cur.execute("SELECT name FROM plant_types ORDER BY name")
            plant_types = [row[0] for row in await cur.fetchall()]

    (pid, name, ptype, t_dry, t_gd, t_tw) = plant_row
    return templates.TemplateResponse(request, "plant_edit.html", {
        "plant": {
            "id": pid,
            "name": name,
            "plant_type": ptype or "",
            "threshold_dry": t_dry,
            "threshold_getting_dry": t_gd,
            "threshold_too_wet": t_tw,
        },
        "plant_types": plant_types,
    })


@app.post("/plants/{plant_id}")
async def update_plant(
    plant_id: int,
    name: str = Form(...),
    plant_type: str = Form(""),
    threshold_dry: int = Form(...),
    threshold_getting_dry: int = Form(...),
    threshold_too_wet: int = Form(...),
):
    plant_type_clean = plant_type.strip() or None

    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE plants
                SET name = %s,
                    plant_type = %s,
                    threshold_dry = %s,
                    threshold_getting_dry = %s,
                    threshold_too_wet = %s
                WHERE id = %s
            """, (name.strip(), plant_type_clean, threshold_dry,
                  threshold_getting_dry, threshold_too_wet, plant_id))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Plant not found")

    return RedirectResponse(url=f"/plants/{plant_id}", status_code=303)


@app.get("/plants/{plant_id}")
async def plant_detail(request: Request, plant_id: int):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT p.id, p.name, p.plant_type,
                       p.threshold_dry, p.threshold_getting_dry, p.threshold_too_wet,
                       pt.description, pt.watering_habits
                FROM plants p
                LEFT JOIN plant_types pt ON pt.name = p.plant_type
                WHERE p.id = %s
            """, (plant_id,))
            plant_row = await cur.fetchone()

            if plant_row is None:
                raise HTTPException(status_code=404, detail="Plant not found")

            await cur.execute("""
                SELECT moisture_raw, recorded_at
                FROM readings
                WHERE plant_id = %s
                ORDER BY recorded_at DESC
                LIMIT 200
            """, (plant_id,))
            recent_rows = list(reversed(await cur.fetchall()))

    (pid, name, ptype, t_dry, t_gd, t_tw, description, watering_habits) = plant_row
    latest_raw, latest_time = recent_rows[-1] if recent_rows else (None, None)
    status = compute_status(latest_raw, t_dry, t_gd, t_tw)

    chart_data = [
        {"x": recorded_at.isoformat(), "y": moisture_raw}
        for moisture_raw, recorded_at in recent_rows
    ]

    return templates.TemplateResponse(request, "plant_detail.html", {
        "plant": {
            "id": pid,
            "name": name,
            "plant_type": ptype,
            "threshold_dry": t_dry,
            "threshold_getting_dry": t_gd,
            "threshold_too_wet": t_tw,
            "description": description,
            "watering_habits": watering_habits,
        },
        "status": status,
        "status_label": STATUS_LABELS[status],
        "latest_raw": latest_raw,
        "last_reading_text": humanize_time_ago(latest_time),
        "chart_data": chart_data,
    })


@app.post("/readings")
async def create_reading(reading: ReadingIn):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO readings (plant_id, moisture_raw) "
                "VALUES (%s, %s) RETURNING id, recorded_at",
                (reading.plant_id, reading.moisture_raw),
            )
            row = await cur.fetchone()
    return {"id": row[0], "recorded_at": row[1].isoformat()}
