import json
import os
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from groq import AsyncGroq
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

groq_client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

PLANT_TYPE_SYSTEM_PROMPT = (
    "You write care notes for common houseplants. "
    "Always reply with a JSON object containing exactly two keys: "
    '"description" (about 3 sentences about the plant) and '
    '"watering_habits" (a short paragraph specifically about watering needs). '
    "Plain text only inside the strings, no markdown."
)


async def ensure_plant_type_info(plant_type_name: str):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM plant_types WHERE name = %s", (plant_type_name,))
            if await cur.fetchone() is not None:
                return

    description = ""
    watering_habits = ""
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PLANT_TYPE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Plant type: {plant_type_name}"},
            ],
        )
        data = json.loads(response.choices[0].message.content)
        description = (data.get("description") or "").strip()
        watering_habits = (data.get("watering_habits") or "").strip()
    except Exception as e:
        print(f"Groq call failed for plant_type={plant_type_name!r}: {e}")

    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO plant_types (name, description, watering_habits) "
                "VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING",
                (plant_type_name, description, watering_habits),
            )


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
@limiter.limit("5/minute")
async def create_plant(
    request: Request,
    background_tasks: BackgroundTasks,
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

    if plant_type_clean:
        background_tasks.add_task(ensure_plant_type_info, plant_type_clean)

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
@limiter.limit("10/minute")
async def update_plant(
    request: Request,
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


@app.post("/plants/{plant_id}/delete")
@limiter.limit("5/minute")
async def delete_plant(request: Request, plant_id: int):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM plants WHERE id = %s", (plant_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Plant not found")
    return RedirectResponse(url="/", status_code=303)


@app.post("/plants/{plant_id}/water")
@limiter.limit("30/minute")
async def log_watering(request: Request, plant_id: int):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM plants WHERE id = %s", (plant_id,))
            if await cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Plant not found")
            await cur.execute(
                "INSERT INTO waterings (plant_id) VALUES (%s)",
                (plant_id,),
            )
    redirect_url = request.headers.get("referer", f"/plants/{plant_id}")
    return RedirectResponse(url=redirect_url, status_code=303)


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

            if recent_rows:
                earliest_reading_time = recent_rows[0][1]
                await cur.execute("""
                    SELECT watered_at FROM waterings
                    WHERE plant_id = %s AND watered_at >= %s
                    ORDER BY watered_at
                """, (plant_id, earliest_reading_time))
                watering_rows = await cur.fetchall()
            else:
                watering_rows = []

            await cur.execute("""
                SELECT watered_at FROM waterings
                WHERE plant_id = %s
                ORDER BY watered_at DESC
                LIMIT 1
            """, (plant_id,))
            last_watering_row = await cur.fetchone()

            await cur.execute("""
                SELECT COUNT(*) FROM waterings
                WHERE plant_id = %s
                  AND watered_at >= NOW() - INTERVAL '30 days'
            """, (plant_id,))
            watering_count_row = await cur.fetchone()

    (pid, name, ptype, t_dry, t_gd, t_tw, description, watering_habits) = plant_row
    latest_raw, latest_time = recent_rows[-1] if recent_rows else (None, None)
    status = compute_status(latest_raw, t_dry, t_gd, t_tw)

    chart_data = [
        {"x": recorded_at.isoformat(), "y": moisture_raw}
        for moisture_raw, recorded_at in recent_rows
    ]
    watering_times = [w[0].isoformat() for w in watering_rows]

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
        "watering_times": watering_times,
        "last_watered_text": humanize_time_ago(last_watering_row[0]) if last_watering_row else None,
        "watering_count_30d": watering_count_row[0],
    })


@app.post("/readings")
@limiter.limit("60/minute")
async def create_reading(request: Request, reading: ReadingIn):
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO readings (plant_id, moisture_raw) "
                "VALUES (%s, %s) RETURNING id, recorded_at",
                (reading.plant_id, reading.moisture_raw),
            )
            row = await cur.fetchone()
    return {"id": row[0], "recorded_at": row[1].isoformat()}
