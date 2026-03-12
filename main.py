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
GEMINI_API_KEY = "AIzaSyDKvhEpuYYlJDFAscL0jUgmjwGi70B23L0"  
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

# --- 🚨 THE PREMIUM LOCAL GUIDE AI ENGINE 🚨 ---
@app.get("/api/search")
def search_place(place: str):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    current_time_str = now.strftime('%A, %I:%M %p') 
    
    # We explicitly tell Gemini to mimic the exact style you want
    prompt = f"""
    You are a premium, highly knowledgeable local tourism AI for Goa. The current local time is {current_time_str}.
    A tourist wants to visit '{place}' right now.
    
    You MUST respond with a strict JSON object exactly in this format. 
    Make the content rich, descriptive, and formatted like a high-end travel guide.
    
    {{
      "crowd_level": "High", (or Medium or Low)
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
        # We use Native JSON Mode to guarantee perfect formatting
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_data = json.loads(response.text)
        
        # Extract the detailed data safely
        crowd_level = ai_data.get("crowd_level", "Medium").capitalize()
        suggested_place = ai_data.get("suggested_place", "None needed")
        
        # Generate the smart Google Maps Directions URL
        # Format: https://www.google.com/maps/dir/?api=1&destination=Place+Name
        # By leaving the origin blank, it automatically uses the user's live phone GPS!
        if suggested_place.lower() != "none needed" and suggested_place.lower() != "none":
            encoded_destination = urllib.parse.quote(f"{suggested_place}, Goa, India")
            google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={encoded_destination}"
        else:
            google_maps_url = ""
                
        # Send everything to the frontend
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
            "prediction_type": "Gemini Premium Guide" 
        }
        
    except Exception as e:
        print(f"🚨 GEMINI ERROR: {e} 🚨")
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