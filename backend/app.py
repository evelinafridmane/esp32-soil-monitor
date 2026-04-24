import os

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

app = FastAPI()


class ReadingIn(BaseModel):
    plant_id: int
    moisture_raw: int


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
