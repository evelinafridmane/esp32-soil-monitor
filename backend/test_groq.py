import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

PLANT_TYPE = "calathea"

system_prompt = (
    "You write care notes for common houseplants. "
    "Always reply with a JSON object containing exactly two keys: "
    '"description" (about 3 sentences about the plant) and '
    '"watering_habits" (a short paragraph specifically about watering needs). '
    "Plain text only inside the strings, no markdown."
)

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Plant type: {PLANT_TYPE}"},
    ],
)

raw = response.choices[0].message.content
data = json.loads(raw)

print("DESCRIPTION:")
print(data["description"])
print()
print("WATERING_HABITS:")
print(data["watering_habits"])
