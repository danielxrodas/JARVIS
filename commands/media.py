from livekit.agents import function_tool
import asyncio
from livekit.agents import function_tool
import subprocess
import os
import httpx
from dotenv import load_dotenv
from newspaper import Article


load_dotenv()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

@function_tool()
async def play_music(
    action: str, 
    playlist: str = None, 
    song: str = None, 
    artist: str = None, 
    shuffle: bool = False
):
    """
    Controls Apple Music on macOS.

    Args:
        action: 'play', 'pause', 'next', 'previous', 'playlist', 'song', or 'artist'
        playlist: optional, name of playlist to play
        song: optional, name of song to play
        artist: optional, name of artist/band to play
        shuffle: whether to enable shuffle when playing a playlist, song, or artist
    """
    try:
        applescript = None
        shuffle_script = 'set shuffle enabled to true' if shuffle else 'set shuffle enabled to false'

        if action.lower() == "playlist" and playlist:
            applescript = f'''
            tell application "Music"
                {shuffle_script}
                play playlist "{playlist}"
            end tell
            '''

        elif action.lower() == "song" and song:
            applescript = f'''
            tell application "Music"
                {shuffle_script}
                play track "{song}"
            end tell
            '''

        elif action.lower() == "artist" and artist:
            # plays the first track found by that artist in your library
            applescript = f'''
            tell application "Music"
                {shuffle_script}
                play (some track of library playlist 1 whose artist is "{artist}")
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
            return "Invalid action. Use play, pause, next, previous, playlist, song, or artist."

        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            if playlist:
                return f"Playing playlist '{playlist}' {'with shuffle' if shuffle else ''}."
            elif song:
                return f"Playing song '{song}' {'with shuffle' if shuffle else ''}."
            elif artist:
                return f"Playing songs by '{artist}' {'with shuffle' if shuffle else ''}."
            else:
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
async def close_app(app_name: str = "all", except_apps: list[str] = None):
    """
    Closes macOS applications.
    - app_name: name of the app to quit, or "all" to quit everything.
    - except_apps: list of apps to exclude when quitting all.
    """
    try:
        except_apps = set(except_apps or []) | {"Finder", "Dock"}  # always protect core apps

        if app_name.lower() != "all":
            # Quit a single app
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", f'tell application "{app_name}" to quit',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                return f"{app_name} closed successfully."
            else:
                return f"Failed to close {app_name}: {stderr.decode().strip()}"
        else:
            # Quit all apps except exclusions
            list_process = await asyncio.create_subprocess_exec(
                "osascript", "-e",
                'tell application "System Events" to get name of (processes where background only is false)',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await list_process.communicate()
            if list_process.returncode != 0:
                return f"Error listing applications: {stderr.decode().strip()}"

            apps = [app.strip() for app in stdout.decode().split(",")]
            apps_to_quit = [app for app in apps if app not in except_apps]

            results = []
            for app in apps_to_quit:
                proc = await asyncio.create_subprocess_exec(
                    "osascript", "-e", f'tell application "{app}" to quit',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                if proc.returncode == 0:
                    results.append(f"Closed {app}")
                else:
                    results.append(f"Failed to close {app}")

            if not results:
                return "No apps to close."
            return "; ".join(results)

    except Exception as e:
        return f"Error: {str(e)}"
    
    

@function_tool()
async def search_web(query: str, num_results: int = 1, summarize: bool = True):
    """
    Searches using SerpApi, opens top results in Chrome,
    and returns clean snippets + optional 3–4 sentence summaries.
    """
    try:
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
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")

            summary = snippet
            if summarize and link:
                try:
                    article = Article(link)
                    article.download()
                    article.parse()
                    text = article.text[:3000]  # keep it short for processing

                    # Ask Jarvis to generate a paragraph summary
                    summary = await summarize_text(text)
                except Exception:
                    summary = snippet  # fallback to snippet if parsing fails

            results.append({
                "title": title,
                "summary": summary,
                "link": link
            })

        if not results:
            return [{"title": "", "summary": "No results found.", "link": ""}]

        # Auto-open links in Chrome
        for result in results:
            if result["link"]:
                asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        "open", "-a", "Google Chrome", result["link"]
                    )
                )

        return [{"title": r["title"], "summary": r["summary"]} for r in results]

    except Exception as e:
        return [{"title": "", "summary": f"Error in search_web: {str(e)}"}]


async def summarize_text(text: str) -> str:
    """
    Helper that asks the LLM (Jarvis) to summarize into a paragraph.
    """
    prompt = f"Summarize the following article into 3-4 sentences:\n\n{text}"
    # 🔹 You’d call your LLM here. For example:
    # response = await call_openai(prompt)
    # return response
    return text[:400]  # <-- placeholder