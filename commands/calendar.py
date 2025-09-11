import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from livekit.agents import function_tool 
from livekit.agents import function_tool
import asyncio
from livekit.agents import function_tool
import subprocess
import dateparser
from datetime import datetime
from dateutil import parser
import os


@function_tool
async def get_next_calendar_event() -> dict:
    """
    Retrieves the next calendar event (within 24 hours) from the 'Work' calendar.
    Returns a dictionary with summary, start_time, and location.
    """
    applescript = '''
    tell application "Calendar"
        set theEvents to every event of calendar "Work" whose start date ≥ (current date) and start date ≤ ((current date) + (1 * days))
        if theEvents is not {} then
            set nextEvent to first item of theEvents
            set eventTitle to summary of nextEvent
            set eventStart to start date of nextEvent
            set eventLocation to ""
            try
                set eventLocation to location of nextEvent
            end try
            return eventTitle & "|" & eventStart & "|" & eventLocation
        else
            return "NO_EVENTS"
        end if
    end tell
    '''

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            ['osascript', '-e', applescript]
        )

        decoded = result.decode().strip()
        if decoded == "NO_EVENTS":
            return {}

        # Split the AppleScript response
        title, start_time, location = decoded.split("|")

        return {
            "title": title.strip(),
            "start_time": dateparser.parse(start_time.strip()),
            "location": location.strip() if location.strip() else None
        }
    except subprocess.CalledProcessError:
        return {}
    
@function_tool
async def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str,
    location: str = "",
    calendar_name: str = "Work"
) -> str:
    """
    Creates a new calendar event with optional location.
    """
    now = datetime.now()
    start_dt = dateparser.parse(
        start_time,
        settings={"RELATIVE_BASE": now, "PREFER_DATES_FROM": "future"}
    )
    end_dt = dateparser.parse(
        end_time,
        settings={"RELATIVE_BASE": now, "PREFER_DATES_FROM": "future"}
    )

    if not start_dt or not end_dt:
        return f"Could not parse provided times, sir."

    # Prepare AppleScript date formatting
    s_month = start_dt.strftime("%B")
    s_day = start_dt.day
    s_year = start_dt.year
    s_hour = start_dt.hour
    s_minute = start_dt.minute

    e_month = end_dt.strftime("%B")
    e_day = end_dt.day
    e_year = end_dt.year
    e_hour = end_dt.hour
    e_minute = end_dt.minute

    summary_escaped = summary.replace('"', '\\"')
    location_escaped = location.replace('"', '\\"')

    applescript = f'''
    tell application "Calendar"
        tell calendar "{calendar_name}"
            set startDate to current date
            set year of startDate to {s_year}
            set month of startDate to {s_month}
            set day of startDate to {s_day}
            set hours of startDate to {s_hour}
            set minutes of startDate to {s_minute}
            set seconds of startDate to 0

            set endDate to current date
            set year of endDate to {e_year}
            set month of endDate to {e_month}
            set day of endDate to {e_day}
            set hours of endDate to {e_hour}
            set minutes of endDate to {e_minute}
            set seconds of endDate to 0

            make new event with properties {{summary:"{summary_escaped}", start date:startDate, end date:endDate, location:"{location_escaped}"}}
        end tell
    end tell
    '''

    try:
        proc = await asyncio.create_subprocess_exec(
            'osascript', '-e', applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return f"Event '{summary}' created successfully, sir."
        else:
            return f"Error creating event: {stderr.decode().strip()}"
    except Exception as e:
        return f"Exception occurred: {e}"

import aiohttp
from urllib.parse import urlencode

@function_tool
async def get_eta_to_event(destination: str, origin: str = "Panorama City, CA") -> dict:
    """
    Fetches driving ETA to the event using Google Distance Matrix API.

    Args:
        destination (str): The event's location or address.
        origin (str, optional): Starting location. Defaults to "Panorama City, CA".

    Returns:
        dict: ETA details including duration, distance, and arrival time.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "Google Maps API key not found."}

    try:
        # Build URL for Google Distance Matrix API
        params = urlencode({
            "origins": origin,
            "destinations": destination,
            "mode": "driving",
            "units": "imperial",
            "key": api_key
        })
        url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{params}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        # Check response validity
        if data.get("status") != "OK":
            return {"error": f"Google API error: {data.get('status')}"}

        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return {"error": f"Could not fetch ETA for {destination}."}

        return {
            "duration": element["duration"]["text"],
            "distance": element["distance"]["text"]
        }

    except Exception as e:
        return {"error": str(e)}    

@function_tool
async def set_reminder(
    title: str,
    time: str,
    notes: str = "",
    list_name: str = "Reminders"
) -> str:
    """
    Sets a macOS reminder using natural language time (e.g., "today at 3 PM", "tomorrow at 9 AM")
    and schedules a verbal notification at the same time.

    Args:
        title (str): Reminder title
        time (str): Natural language time
        notes (str, optional): Body of the reminder
        list_name (str, optional): Reminder list name

    Returns:
        str: Success or error message
    """
    now = datetime.now()
    reminder_dt = dateparser.parse(time, settings={"RELATIVE_BASE": now, "PREFER_DATES_FROM": "future"})
    
    if not reminder_dt:
        return f"❌ Could not parse the provided time: {time}"

    month_str = reminder_dt.strftime("%B")
    day = reminder_dt.day
    year = reminder_dt.year
    hour = reminder_dt.hour
    minute = reminder_dt.minute

    title_escaped = title.replace('"', '\\"')
    notes_escaped = notes.replace('"', '\\"')

    applescript = f'''
    tell application "Reminders"
        tell list "{list_name}"
            set newReminder to make new reminder
            set name of newReminder to "{title_escaped}"
            
            set reminderDate to current date
            set year of reminderDate to {year}
            set month of reminderDate to {month_str}
            set day of reminderDate to {day}
            set hours of reminderDate to {hour}
            set minutes of reminderDate to {minute}
            set seconds of reminderDate to 0
            
            set remind me date of newReminder to reminderDate
            set body of newReminder to "{notes_escaped}"
        end tell
    end tell
    '''

    try:
        proc = await asyncio.create_subprocess_exec(
            'osascript', '-e', applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return f"❌ Failed to create reminder: {stderr.decode().strip()}"
    except Exception as e:
        return f"❌ Exception occurred: {e}"

    return f"✅ Reminder '{title}' set for {reminder_dt.strftime('%A, %B %d, %Y %I:%M %p')} in list '{list_name}'"

@function_tool
async def get_reminders(list_name: str = "Reminders") -> list:
    """
    Retrieves all future reminders from the specified list.

    Returns:
        list: A list of reminders, each with title and due datetime.
    """
    applescript = f'''
    tell application "Reminders"
        set nowDate to current date
        set futureReminders to every reminder of list "{list_name}" whose due date ≥ nowDate and completed is false
        set output to ""
        repeat with r in futureReminders
            set reminderName to name of r
            set reminderDate to due date of r
            set output to output & reminderName & "||" & reminderDate & ";;"
        end repeat
    end tell
    return output
    '''

    try:
        result = await asyncio.to_thread(
            subprocess.check_output,
            ['osascript', '-e', applescript]
        )

        reminders_raw = result.decode().strip()
        reminders = []

        if reminders_raw:
            for r in reminders_raw.split(";;"):
                if r.strip():
                    parts = r.split("||")
                    title = parts[0].strip()
                    due_date_str = parts[1].strip()
                    # ✅ Convert string to datetime
                    due_date = parser.parse(due_date_str)
                    reminders.append({
                        "title": title,
                        "time": due_date
                    })

        return reminders

    except subprocess.CalledProcessError as e:
        return []
    
@function_tool
async def delete_calendar_event(title: str, calendar_name: str = "Work") -> str:
    """
    Deletes the first calendar event matching the given title from the specified calendar.

    Args:
        title (str): Event title to delete
        calendar_name (str, optional): Calendar to delete from. Defaults to "Work".

    Returns:
        str: Success or error message
    """
    title_escaped = title.replace('"', '\\"')
    applescript = f'''
    tell application "Calendar"
        tell calendar "{calendar_name}"
            set theEvent to first event whose summary is "{title_escaped}"
            delete theEvent
        end tell
    end tell
    '''

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return f"✅ Calendar event '{title}' deleted from '{calendar_name}'"
        else:
            return f"❌ Failed to delete event '{title}': {stderr.decode().strip()}"
    except Exception as e:
        return f"❌ Exception occurred: {e}"
    
    
@function_tool
async def delete_reminder(title: str, list_name: str = "Reminders") -> str:
    """
    Deletes a reminder by title from the specified list.

    Args:
        title (str): The title of the reminder to delete
        list_name (str, optional): The list from which to delete. Defaults to "Reminders".

    Returns:
        str: Success or error message
    """
    title_escaped = title.replace('"', '\\"')
    applescript = f'''
    tell application "Reminders"
        tell list "{list_name}"
            set reminderToDelete to first reminder whose name is "{title_escaped}"
            delete reminderToDelete
        end tell
    end tell
    '''

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return f"✅ Reminder '{title}' deleted from list '{list_name}'"
        else:
            return f"❌ Failed to delete reminder '{title}': {stderr.decode().strip()}"
    except Exception as e:
        return f"❌ Exception occurred: {e}"