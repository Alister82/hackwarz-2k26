from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import json
from datetime import datetime
import pytz
import urllib.parse
import google.generativeai as genai

# --- 🚨 PASTE YOUR REAL GEMINI KEY HERE 🚨 ---
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"  
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SETUP ---
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

# --- LOGIN & CAB ROUTES ---
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

# --- 🚨 THE DETAILED GEMINI PREDICTION ENGINE 🚨 ---
@app.get("/api/search")
def search_place(place: str):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    current_time_str = now.strftime('%A, %I:%M %p') 
    
    prompt = f"""
    You are a highly knowledgeable local tourism AI for Goa. The current local time is {current_time_str}.
    A tourist wants to visit '{place}' right now.
    
    Provide a highly detailed, realistic assessment of the crowd at this exact time. 
    Also, suggest ONE nearby, similar place that is guaranteed to be less crowded.
    
    You MUST respond with a strict JSON object exactly in this format:
    {{
      "crowd_level": "High", (or Medium or Low)
      "detailed_status": "A rich 2-3 sentence description of the current crowd vibe.",
      "features": ["Feature 1: description", "Feature 2: description"],
      "trends": "Description of how the crowd changes later in the day.",
      "suggested_place": "Name of the alternative spot",
      "suggestion_reason": "Why they should go here instead."
    }}
    """
    
    try:
        # We use Native JSON Mode to guarantee perfect formatting
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_data = json.loads(response.text)
        
        # Extract the detailed data
        crowd_level = ai_data.get("crowd_level", "Medium").capitalize()
        detailed_status = ai_data.get("detailed_status", "No detailed status available.")
        features = ai_data.get("features", [])
        trends = ai_data.get("trends", "No trend data available.")
        suggested_place = ai_data.get("suggested_place", "None")
        suggestion_reason = ai_data.get("suggestion_reason", "")
        
        # Generate the smart Google Maps Redirect URL
        # By leaving the origin blank, Google Maps automatically uses the tourist's live GPS location!
        encoded_destination = urllib.parse.quote(f"{suggested_place}, Goa, India")
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_destination}"
                
        return {
            "place": place, 
            "status": crowd_level,
            "detailed_status": detailed_status,
            "features": features,
            "trends": trends,
            "suggested_place": suggested_place,
            "suggestion_reason": suggestion_reason,
            "google_maps_url": google_maps_url,
            "prediction_type": "Gemini 1.5 Flash Detailed Analysis" 
        }
        
    except Exception as e:
        print(f"🚨 GEMINI ERROR: {e} 🚨")
        return {
            "place": place, 
            "status": "Error", 
            "detailed_status": f"🚨 FATAL ERROR: {str(e)} 🚨",
            "features": [],
            "trends": "",
            "suggested_place": "Error",
            "suggestion_reason": "",
            "google_maps_url": "",
            "prediction_type": "Failed" 
        }