from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import json
from datetime import datetime
import pytz
import urllib.parse
import os
from groq import Groq

# ── Load .env from the same directory as this script (absolute path) ──────
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
def _load_env(path=_ENV_PATH):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        print(f"WARNING: .env not found at {path}")
_load_env()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not set! Add it to your .env file.")

# ── Groq client (replaces Gemini due to rate limits) ──────
client = Groq(api_key=GROQ_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DATABASE SETUP ─────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS drivers (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, zone TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tourists (id INTEGER PRIMARY KEY, name TEXT, phone TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, tourist_name TEXT, place TEXT)''')
    conn.commit()
    conn.close()

init_db()

class Driver(BaseModel):
    name: str; phone: str; zone: str

class Tourist(BaseModel):
    name: str; phone: str

# ── LOGIN & CAB ROUTES ─────────────────────────────────────────────────────
@app.post("/api/tourist/login")
def login_tourist(tourist: Tourist):
    return {"message": f"Welcome {tourist.name}!"}

@app.post("/api/drivers/register")
def register_driver(driver: Driver):
    return {"message": "Driver registered successfully!"}

@app.get("/api/drivers/search")
def search_drivers(zone: str):
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute("SELECT name, phone FROM drivers WHERE zone = ?", (zone.lower(),))
    drivers = c.fetchall()
    conn.close()
    if not drivers:
        return {"drivers": [], "message": "No cabs found nearby."}
    return {"drivers": [{"name": d[0], "phone": d[1]} for d in drivers]}

# ── AI CROWD GUIDE ENGINE ──────────────────────────────────────────────────
@app.get("/api/search")
def search_place(place: str):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    current_time_str = now.strftime('%A, %I:%M %p')

    prompt = f"""
    You are a premium, highly knowledgeable local tourism AI for Goa. The current local time is {current_time_str}.
    A tourist wants to visit '{place}' right now.
    
    You MUST respond with a strict JSON object exactly in this format.
    Make the content rich, descriptive, and formatted like a high-end travel guide.
    
    {{
      "crowd_level": "High",
      "headline": "Example: {place} is highly unlikely to be crowded right now.",
      "description": "A rich 2-3 sentence description of why it is crowded or not right now based on the location and time.",
      "feature_1_title": "Relaxed environment",
      "feature_1_desc": "Features a wide, peaceful stretch of white sand...",
      "feature_2_title": "Laid-back shacks",
      "feature_2_desc": "The beach shacks here maintain an authentic vibe...",
      "trends": "While it remains quiet during the early afternoon, there is usually...",
      "suggested_place": "Name of ONE nearby alternative spot (ONLY if the main place is High/Medium. If Low, say 'None needed')",
      "suggestion_reason": "Why they should go here instead."
    }}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful travel guide API. You always output perfectly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        ai_data = json.loads(response.choices[0].message.content)

        crowd_level = ai_data.get("crowd_level", "Medium").capitalize()
        suggested_place = ai_data.get("suggested_place", "None needed")

        if suggested_place.lower() not in ("none needed", "none"):
            encoded_destination = urllib.parse.quote(f"{suggested_place}, Goa, India")
            google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_destination}"
        else:
            google_maps_url = ""

        return {
            "place": place,
            "status": crowd_level,
            "headline": ai_data.get("headline", ""),
            "description": ai_data.get("description", ""),
            "feature_1_title": ai_data.get("feature_1_title", ""),
            "feature_1_desc": ai_data.get("feature_1_desc", ""),
            "feature_2_title": ai_data.get("feature_2_title", ""),
            "feature_2_desc": ai_data.get("feature_2_desc", ""),
            "trends": ai_data.get("trends", ""),
            "suggested_place": suggested_place,
            "suggestion_reason": ai_data.get("suggestion_reason", ""),
            "google_maps_url": google_maps_url,
            "prediction_type": "Groq Premium Guide"
        }

    except Exception as e:
        print(f"🚨 GROQ ERROR: {e} 🚨")
        return {
            "place": place,
            "status": "Error",
            "headline": "🚨 System Error Occurred 🚨",
            "description": f"Error details: {str(e)}",
            "feature_1_title": "", "feature_1_desc": "",
            "feature_2_title": "", "feature_2_desc": "",
            "trends": "",
            "suggested_place": "",
            "suggestion_reason": "",
            "google_maps_url": "",
            "prediction_type": "Failed"
        }