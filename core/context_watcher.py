from commands.utilities import get_time, get_weather, get_daily_forecast
from commands.calendar import get_reminders, get_next_calendar_event, get_eta_to_event
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import timedelta

scheduler = AsyncIOScheduler()                
async def morning_routine(session=None):
    """
    Runs every morning and makes Jarvis speak out the time & weather.
    """
    class DummyContext:
        pass
    context = DummyContext()

    # Get time & weather
    time = await get_time(context)
    weather = await get_daily_forecast(context)

    message = f"Good morning. {time} {weather}"

    # ✅ Speak via LiveKit if session is active
    if session:
        await session.say(message)
    else:
        print(f"[Morning Routine] {message}")  # Fallback for debugging

async def notify_reminder(reminder, session=None):
    """
    Announces a single reminder when triggered.
    """
    title = reminder.get("title", "something important")
    reminder_time = reminder.get("time")
    formatted_time = reminder_time.strftime("%I:%M %p") if reminder_time else "sometime soon"

    message = f"Sir, I believe you asked me to remind you to {title} at {formatted_time}."
    if session:
        await session.say(message)
    else:
        print(f"[Reminder] {message}")

async def schedule_reminders(session=None):
    """
    Fetches all reminders and schedules them dynamically.
    """
    reminders = await get_reminders()  # Should return [{'title': 'Call Katherine', 'time': datetime_obj}, ...]

    if not reminders:
        return

    now = datetime.now()

    for reminder in reminders:
        reminder_time = reminder.get("time")
        if not reminder_time or reminder_time < now:
            continue  # Skip invalid or past reminders

        # ✅ Schedule the job at the exact reminder time
        scheduler.add_job(
            notify_reminder,
            "date",  # Run once, exactly at the reminder time
            run_date=reminder_time,
            kwargs={"reminder": reminder, "session": session}
        )

async def check_events(session=None):
    """
    Checks for upcoming events, announces them 1 hour before, and gives ETA if location exists.
    """
    event = await get_next_calendar_event()
    if not event:
        return  # No events today

    now = datetime.now()
    start_time = event["start_time"]

    if not start_time:
        return

    time_diff = start_time - now

    # ✅ Notify only if within 1 hour before start
    if timedelta(minutes=55) < time_diff <= timedelta(hours=1):
        title = event["title"]
        formatted_time = start_time.strftime("%I:%M %p")

        if event["location"]:
            eta_info = await get_eta_to_event(event["location"])
            if "error" not in eta_info:
                message = (
                    f"Sir, you have '{title}' at {formatted_time} in {event['location']}. "
                    f"It is {eta_info['distance']} away, approximately {eta_info['duration']} by car."
                )
            else:
                message = f"Sir, you have '{title}' at {formatted_time} in {event['location']}."
        else:
            message = f"Sir, you have '{title}' at {formatted_time}."

        # Speak or print
        if session:
            await session.say(message)
        else:
            print(f"[Event] {message}")

def start_scheduler(session):
    """
    Starts the scheduler and passes the session for TTS.
    """
    # Morning routine at 8:30 AM
    scheduler.add_job(
        morning_routine,
        "cron",
        hour=7,
        minute=00,
        kwargs={"session": session}
    )

    # Schedule all future reminders immediately
    import asyncio
    asyncio.create_task(schedule_reminders(session=session))

    # Refresh every 30 minutes to catch new reminders added while running
    scheduler.add_job(
        schedule_reminders,
        "interval",
        minutes=5,
        kwargs={"session": session}
    )
    
    scheduler.add_job(
    check_events,
    "interval",
    minutes=5,
    kwargs={"session": session}
    )

    scheduler.start()