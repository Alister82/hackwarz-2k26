from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import json
import math
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
    c.execute('''CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY, place TEXT, timestamp TEXT, crowd_level TEXT)''')
    try:
        c.execute('''ALTER TABLE searches ADD COLUMN suggested_place TEXT''')
    except sqlite3.OperationalError:
        pass
    
    # Mock data seeding
    c.execute("SELECT COUNT(*) FROM searches")
    if c.fetchone()[0] == 0:
        mock_places = [
            ("Baga Beach", "High", 145),
            ("Calangute Beach", "High", 112),
            ("Dudhsagar Waterfalls", "Medium", 68),
            ("Aguada Fort", "Medium", 45),
            ("Butterfly Beach", "Low", 14),
            ("Divar Island", "Low", 6)
        ]
        now_str = datetime.now().isoformat()
        for place, level, count in mock_places:
            c.executemany("INSERT INTO searches (place, timestamp, crowd_level) VALUES (?, ?, ?)", [(place, now_str, level)] * count)
            
    conn.commit()
    conn.close()

init_db()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class Driver(BaseModel):
    name: str; phone: str; zone: str

class Tourist(BaseModel):
    name: str; phone: str

class GovLogin(BaseModel):
    username: str; password: str

# ── LOGIN & CAB ROUTES ─────────────────────────────────────────────────────
@app.post("/api/tourist/login")
def login_tourist(tourist: Tourist):
    return {"message": f"Welcome {tourist.name}!"}

@app.post("/api/drivers/register")
def register_driver(driver: Driver):
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    # Ensure zones are a comma-separated string for simpler dashboard management
    # and compatibility with search
    zones = driver.zone.strip()

    # Check if a driver with this phone already exists to update instead
    c.execute("SELECT id FROM drivers WHERE phone = ?", (driver.phone,))
    existing = c.fetchone()
    
    if existing:
        c.execute("UPDATE drivers SET name = ?, zone = ? WHERE phone = ?", (driver.name, zones, driver.phone))
        msg = "Driver details updated successfully!"
    else:
        c.execute("INSERT INTO drivers (name, phone, zone) VALUES (?, ?, ?)", (driver.name, driver.phone, zones))
        msg = "Driver registered successfully!"
            
    conn.commit()
    conn.close()
    return {"message": msg}

@app.post("/api/drivers/login")
def login_driver(driver: Tourist): # Name and Phone used as login
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute("SELECT id FROM drivers WHERE phone = ?", (driver.phone,))
    existing = c.fetchone()
    conn.close()
    
    if existing:
        return {"message": "Success"}
    return {"message": "Invalid credentials", "status": "error"}

@app.get("/api/drivers/details")
def get_driver_details(phone: str):
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute("SELECT name, phone, zone FROM drivers WHERE phone = ?", (phone,))
    driver = c.fetchone()
    conn.close()
    
    if not driver:
        return {"status": "error", "message": "Driver not found."}
    
    return {"name": driver[0], "phone": driver[1], "zone": driver[2]}

@app.get("/api/drivers/search")
def search_drivers(zone: str):
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute("SELECT name, phone FROM drivers WHERE zone LIKE ?", ('%' + zone.lower() + '%',))
    drivers = c.fetchall()
    conn.close()
    if not drivers:
        return {"drivers": [], "message": "No cabs found nearby."}
    return {"drivers": [{"name": d[0], "phone": d[1]} for d in drivers]}

# ── GOV DASHBOARD ROUTES ───────────────────────────────────────────────────
@app.post("/api/gov/login")
def login_gov(creds: GovLogin):
    if creds.username == "gov" and creds.password == "gov123":
        return {"message": "Success"}
    return {"message": "Invalid username or password", "status": "error"}

@app.get("/api/gov/dashboard")
def gov_dashboard():
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute('''
        SELECT place, COUNT(*) as search_count, 
               (SELECT crowd_level FROM searches s2 WHERE s2.place = searches.place ORDER BY id DESC LIMIT 1) as latest_level
        FROM searches
        GROUP BY place
        ORDER BY search_count DESC
    ''')
    results = c.fetchall()
    conn.close()
    
    dashboard_data = []
    for row in results:
        place, count, level = row
        
        if level == "High" or count > 100:
            police_action = "🚧 Deploy Traffic Police & Crowd Control"
            clean_action = "🗑️ Schedule Heavy Bin Emptying Tomorrow Morning"
        elif level == "Medium" or count > 50:
            police_action = "👮 Deploy Normal Patrol"
            clean_action = "🧹 Routine Bin Maintenance Tomorrow"
        else:
            police_action = "✅ No Additional Police Needed"
            clean_action = "✨ Normal Cleaning Schedule"
            
        dashboard_data.append({
            "place": place,
            "searches": count,
            "crowd_level": level,
            "police_suggestion": police_action,
            "cleaning_suggestion": clean_action
        })
        
    return {"data": dashboard_data}

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
    Determine the actual crowd_level based on the location and current time. If it's a popular place like Baga Beach during the day or evening, it should probably be High.
    
    {{
      "crowd_level": "High", (Choose strictly one: "Low", "Medium", or "High")
      "headline": "[Generate a short headline stating explicitly if the place is CROWDED or CALM right now]",
      "description": "[A rich 2-3 sentence description explaining why it is or isn't crowded based on the current time and location]",
      "feature_1_title": "[Name of a feature]",
      "feature_1_desc": "[Description of the feature]",
      "feature_2_title": "[Name of another feature]",
      "feature_2_desc": "[Description of the feature]",
      "trends": "[Explain the general crowd trends for this place throughout the day]",
      "place_lat": 15.55, (Latitude of '{place}' as float)
      "place_lon": 73.75, (Longitude of '{place}' as float)
      "alternatives": [
        {{
          "name": "[Name of nearby alternative]",
          "lat": 15.58, (Latitude of alternative as float)
          "lon": 73.74, (Longitude of alternative as float)
          "reason": "[Why to go here instead]"
        }}
      ] (Provide up to 3 nearby alternatives if crowd is High/Medium)
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
        suggested_place = "None needed"
        suggestion_reason = ""

        conn = sqlite3.connect('hackathon.db')
        c = conn.cursor()

        if crowd_level in ("High", "Medium"):
            place_lat = ai_data.get("place_lat", 0.0)
            place_lon = ai_data.get("place_lon", 0.0)
            alternatives = ai_data.get("alternatives", [])
            
            valid_alternatives = []
            for alt in alternatives:
                try:
                    alt_lat = float(alt.get("lat", 0.0))
                    alt_lon = float(alt.get("lon", 0.0))
                    dist = haversine(float(place_lat), float(place_lon), alt_lat, alt_lon)
                    if dist <= 20.0: # Filter to only keep nearby places (within 20km)
                        valid_alternatives.append((alt, dist))
                except (ValueError, TypeError):
                    continue
                    
            if valid_alternatives:
                best_alt = None
                min_suggestions = float('inf')
                
                for alt, dist in valid_alternatives:
                    alt_name = alt.get("name", "")
                    c.execute("SELECT COUNT(*) FROM searches WHERE place = ? AND suggested_place = ?", (place, alt_name))
                    res = c.fetchone()
                    count = res[0] if res else 0
                    
                    if count < min_suggestions:
                        min_suggestions = count
                        best_alt = alt
                
                if best_alt:
                    suggested_place = best_alt.get("name", "")
                    suggestion_reason = best_alt.get("reason", "")
                else:
                    suggested_place = "None nearby"

        # Insert search record with suggested alternative to track distribution
        c.execute("INSERT INTO searches (place, timestamp, crowd_level, suggested_place) VALUES (?, ?, ?, ?)", 
                 (place, datetime.now().isoformat(), crowd_level, suggested_place))
        conn.commit()
        conn.close()

        if suggested_place.lower() not in ("none needed", "none", "none nearby", ""):
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
            "suggestion_reason": suggestion_reason,
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