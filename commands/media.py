from livekit.agents import function_tool
import asyncio
from livekit.agents import function_tool
import subprocess
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

@function_tool()
async def play_music(action: str, playlist: str = None):
    """
    Controls Apple Music on macOS.
    action: 'play', 'pause', 'next', 'previous', or 'playlist'
    playlist: optional, name of playlist to play
    """
    try:
        if action.lower() == "playlist" and playlist:
            applescript = f'''
            tell application "Music"
                play playlist "{playlist}"
            end tell
            '''
        elif action.lower() == "play":
            applescript = 'tell application "Music" to play'
        elif action.lower() == "pause":
            applescript = 'tell application "Music" to pause'
        elif action.lower() == "next":
            applescript = 'tell application "Music" to next track'
        elif action.lower() == "previous":
            applescript = 'tell application "Music" to previous track'
        else:
            return "Invalid action. Use play, pause, next, previous, or playlist."

        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return f"Apple Music action '{action}' executed successfully."
        else:
            return f"Failed to execute music action: {result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"
    
@function_tool()
async def can_you_open_the_app(app_name: str):
    """Opens a macOS app by name."""
    try:
        # Use asyncio for non-blocking subprocess execution
        process = await asyncio.create_subprocess_exec(
            "open", "-a", app_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return f"{app_name} opened successfully."
        else:
            return f"Failed to open {app_name}: {stderr.decode().strip()}"
    except Exception as e:
        return f"Error: {str(e)}"
    
@function_tool()
async def search_web(query: str, num_results: int = 1):
    """
    Searches using SerpApi, opens top links in Chrome immediately,
    and returns raw snippets.
    """
    try:
        # Step 1: Search via SerpApi
        url = "https://serpapi.com/search.json"
        params = {
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "num": num_results
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()

        results = []
        for result in data.get("organic_results", []):
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            results.append({"snippet": snippet, "link": link})

        if not results:
            return [{"snippet": "No results found.", "link": ""}]

        # Step 2: Open Chrome if not already running
        await can_you_open_the_app("Google Chrome")

        # Step 3: Immediately open all top links in Chrome
        for result in results:
            if result["link"]:
                # Open each URL asynchronously without waiting
                asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        "open", "-a", "Google Chrome", result["link"]
                    )
                )

        # Step 4: Return the raw snippets for Artis to talk about
        return results

    except Exception as e:
        return [{"snippet": f"Error in search_and_open_auto: {str(e)}", "link": ""}]