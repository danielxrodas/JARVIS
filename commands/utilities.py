from livekit.agents import function_tool
import os
from openai import OpenAI
from dotenv import load_dotenv
import re
from livekit.agents import function_tool, RunContext
import requests
from dotenv import load_dotenv
from livekit.agents import function_tool, RunContext
import subprocess
from datetime import datetime, timedelta

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def convert_text_to_comments(ai_output: str) -> str:
    """
    Converts explanatory text outside of ```python``` code blocks
    into Python comments.
    """
    result_lines = []
    in_code_block = False
    for line in ai_output.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            # Only include ```python``` if code block starts
            if in_code_block:
                continue
            else:
                continue  # skip closing ```
        if in_code_block:
            result_lines.append(line)
        else:
            if line.strip() == "":
                result_lines.append("")  # keep empty lines
            else:
                result_lines.append(f"# {line}")
    return "\n".join(result_lines)

@function_tool
async def generate_code(prompt: str) -> str:
    """
    Generates code from a natural language prompt using OpenAI,
    converts any explanatory text to comments, and opens in VSCode.
    Saves in ~/Documents/Code Generation with a filename related to the prompt.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        ai_output = response.choices[0].message.content.strip()

        # Convert any non-code text to comments
        processed_code = convert_text_to_comments(ai_output)

        # Folder path
        folder_path = os.path.expanduser("~/Documents/Code Generation")
        os.makedirs(folder_path, exist_ok=True)

        # Create a sanitized filename from the prompt
        sanitized_prompt = re.sub(r'[^0-9a-zA-Z]+', '_', prompt)[:50]
        file_name = f"{sanitized_prompt}.py"
        file_path = os.path.join(folder_path, file_name)

        # Write processed code to file
        with open(file_path, "w") as f:
            f.write(processed_code)

        # Open in VSCode

        return processed_code

    except Exception as e:
        error_msg = f"❌ Failed to generate code: {e}"
        print(error_msg)
        return error_msg
    
# ---------------------------------------------------------------------------------------------
# Get time
# ---------------------------------------------------------------------------------------------
@function_tool()
async def get_time(context: RunContext) -> str:
    """
    Get the current time in a user-friendly format.
    """
    current_time = datetime.now().time()
    return f"The current time is {current_time.strftime('%I:%M %p')}."
# ---------------------------------------------------------------------------------------------
# Get Date
# ---------------------------------------------------------------------------------------------
@function_tool()
async def get_date(context: RunContext) -> str:
    """
    Get the current date in a user-friendly format.
    """
    current_date = datetime.now().date()
    return f"Today's date is {current_date.strftime('%B %d, %Y')}."

# ---------------------------------------------------------------------------------------------
# Get weather for current city
# ---------------------------------------------------------------------------------------------
def get_current_city():
    try:
        response = requests.get("http://ip-api.com/json/")
        data = response.json()
        if data["status"] == "success":
            return data["city"]
        else:
            return None
    except Exception as e:
        print(f"Error getting location: {e}")
        return None

@function_tool()
async def get_weather(context: RunContext) -> str:
    """
    Get the current weather for the user’s current city using OpenWeatherMap with Jarvis-style commentary.
    """
    city = get_current_city()
    if not city:
        return "Could not determine your location, sir."

    try:
        api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        if not api_key:
            return "Weather service unavailable, sir: API key not configured."
        
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=imperial"
        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            return f"Could not retrieve weather for {city}, sir. Error: {data.get('message', 'Unknown error')}"

        temp = data["main"]["temp"]
        description = data["weather"][0]["description"].capitalize()
        humidity = data["main"]["humidity"]

        # Jarvis-style commentary
        commentary = ""
        if "rain" in description.lower():
            commentary = "You might want an umbrella, sir."
        elif temp > 85:
            commentary = "It appears rather warm, sir. Perhaps stay hydrated."
        elif temp < 50:
            commentary = "Quite chilly, sir. A jacket may be prudent."
        else:
            commentary = "Weather seems quite agreeable, sir."

        return f"The current weather in {city} is {description} with a temperature of {temp}°F and humidity at {humidity}%. {commentary}"
    
    except Exception as e:
        return f"An error occurred while retrieving weather for {city}, sir: {str(e)}"
    


@function_tool()
async def get_daily_forecast(context: RunContext) -> str:
    """
    Get today's weather forecast including high, low, visibility, and air quality,
    with Jarvis-style commentary. Uses the free OpenWeatherMap APIs.
    """
    city = get_current_city()
    if not city:
        return "Could not determine your location, sir."

    try:
        api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        if not api_key:
            return "Weather service unavailable, sir: API key not configured."

        # Step 1: Get today's forecast using the free forecast API
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=imperial"
        response = requests.get(forecast_url)
        data = response.json()

        if response.status_code != 200 or "list" not in data:
            return f"Could not retrieve forecast for {city}, sir. Error: {data.get('message', 'Unknown error')}"

        # Step 2: Filter forecasts for today only
        today = datetime.now().date()
        today_forecasts = [
            entry for entry in data["list"]
            if datetime.fromtimestamp(entry["dt"]).date() == today
        ]

        if not today_forecasts:
            return f"No forecast data available for {city}, sir."

        # Step 3: Get today's high, low, visibility, and description
        temps = [entry["main"]["temp"] for entry in today_forecasts]
        high = round(max(temps))
        low = round(min(temps))

        # Use the closest forecast block to now for visibility and description
        current_forecast = today_forecasts[0]
        description = current_forecast["weather"][0]["description"].capitalize()
        visibility_meters = current_forecast.get("visibility", 10000)
        visibility_km = visibility_meters / 1000

        # Categorize visibility
        if visibility_km >= 10:
            visibility_status = "excellent"
        elif 6 <= visibility_km < 10:
            visibility_status = "good"
        elif 3 <= visibility_km < 6:
            visibility_status = "moderate"
        elif 1 <= visibility_km < 3:
            visibility_status = "poor"
        else:
            visibility_status = "very poor"

        # Step 4: Get Air Quality Index (AQI)
        geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"
        geo_response = requests.get(geocode_url)
        geo_data = geo_response.json()
        if not geo_data:
            return f"Could not retrieve coordinates for {city}, sir."

        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        aqi_response = requests.get(aqi_url)
        aqi_data = aqi_response.json()

        if aqi_response.status_code != 200 or "list" not in aqi_data:
            aqi_text = "unavailable"
        else:
            aqi = aqi_data["list"][0]["main"]["aqi"]
            aqi_levels = {
                1: "Good",
                2: "Fair",
                3: "Moderate",
                4: "Poor",
                5: "Very Poor"
            }
            aqi_text = aqi_levels.get(aqi, "Unknown")

        # Jarvis-style commentary
        if "rain" in description.lower():
            remark = "An umbrella would be wise, sir."
        elif "storm" in description.lower():
            remark = "I advise remaining indoors, sir."
        elif "clear" in description.lower():
            remark = "Perfect conditions, sir."
        elif "cloud" in description.lower():
            remark = "Partly cloudy, sir. Nothing concerning."
        elif high > 90:
            remark = "It will be quite hot, sir. Stay hydrated."
        elif low < 45:
            remark = "Rather cold tonight, sir. A jacket may be required."
        else:
            remark = "Conditions appear stable, sir."

        return (
            f"The weather in {city} is {description}. "
            f"Expect a high of {high}°F and a low of {low}°F. "
            f"Visibility is {visibility_status} and the air quality is {aqi_text}. "
            f"{remark} "
        )

    except Exception as e:
        return f"An error occurred while retrieving today's forecast for {city}, sir: {str(e)}"

@function_tool()
async def get_eta(destination: str, origin: str = None, mode: str = "driving"):
    """
    Returns ETA using Google Maps API.
    If origin is None, automatically uses the current city from get_current_city().
    """
    API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    if not API_KEY:
        return {"success": False, "commentary": "Google Maps API key not set."}

    if not origin:
        origin = get_current_city()
        if not origin:
            return {
                "success": False,
                "commentary": "Unable to determine your current location. Please provide an origin address."
            }

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": origin, "destination": destination, "mode": mode, "key": API_KEY}

    try:
        res = requests.get(url, params=params).json()
        if res.get("status") != "OK" or not res.get("routes"):
            return {"success": False, "commentary": f"Failed to get directions: {res.get('status')}"}

        duration_sec = res["routes"][0]["legs"][0]["duration"]["value"]
        eta_minutes = round(duration_sec / 60)

        # Calculate expected arrival time
        arrival_time = datetime.now() + timedelta(minutes=eta_minutes)
        arrival_time_str = arrival_time.strftime("%I:%M %p")

        commentary = f"ETA to {destination} is {eta_minutes} minutes. You should arrive by {arrival_time_str}."
        return {
            "success": True,
            "eta_minutes": eta_minutes,
            "arrival_time": arrival_time_str,
            "commentary": commentary
        }

    except Exception as e:
        return {"success": False, "commentary": f"Error retrieving ETA: {str(e)}"}


from kasa import SmartPlug
from livekit.agents import function_tool
import os

# Map lamp names to IPs
LAMP_IPS = {
    "lamp one": os.getenv("LAMP_ONE_IP"),
    "lamp two": os.getenv("LAMP_TWO_IP"),
    "lamp three": os.getenv("LAMP_THREE_IP"),
    "lamp four": os.getenv("LAMP_FOUR_IP"),
}

# Map rooms to lamps
ROOMS = {
    "bedroom": ["lamp one", "lamp two"],
    "living room": ["lamp three", "lamp four"],
}

async def _get_plug(lamp_name: str) -> SmartPlug:
    """Helper function to fetch and initialize the SmartPlug."""
    lamp_name = lamp_name.lower()
    if lamp_name not in LAMP_IPS:
        raise ValueError(f"'{lamp_name}' not found. Available: {', '.join(LAMP_IPS.keys())}")

    plug = SmartPlug(LAMP_IPS[lamp_name])
    await plug.update()
    return plug

async def _turn_lamps(lamp_names: list[str], turn_on: bool = True) -> str:
    """
    Helper function to turn multiple lamps on/off.
    """
    results = []
    for name in lamp_names:
        try:
            plug = await _get_plug(name)
            if turn_on:
                await plug.turn_on()
                results.append(f"✅ Turned ON {name}")
            else:
                await plug.turn_off()
                results.append(f"✅ Turned OFF {name}")
        except Exception as e:
            results.append(f"❌ Error with {name}: {str(e)}")
        finally:
            try:
                await plug.disconnect()
            except:
                pass
    return "\n".join(results)

@function_tool
async def turn_on_lamp(lamp_or_room: str) -> str:
    """
    Turn ON a specific lamp or all lamps in a room.
    """
    lamp_or_room = lamp_or_room.lower()
    if lamp_or_room in ROOMS:
        lamp_names = ROOMS[lamp_or_room]
    else:
        lamp_names = [lamp_or_room]
    return await _turn_lamps(lamp_names, turn_on=True)

@function_tool
async def turn_off_lamp(lamp_or_room: str) -> str:
    """
    Turn OFF a specific lamp or all lamps in a room.
    """
    lamp_or_room = lamp_or_room.lower()
    if lamp_or_room in ROOMS:
        lamp_names = ROOMS[lamp_or_room]
    else:
        lamp_names = [lamp_or_room]
    return await _turn_lamps(lamp_names, turn_on=False)