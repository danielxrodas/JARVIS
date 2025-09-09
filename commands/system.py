from livekit.agents import function_tool
import os
import asyncio
import subprocess

@function_tool
async def mute_microphone() -> str:
    """Mute system audio and store previous volume."""
    global previous_volume
    try:
        # Get current volume
        proc_get = await asyncio.create_subprocess_exec(
            'osascript', '-e', 'output volume of (get volume settings)',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc_get.communicate()
        previous_volume = int(stdout.decode().strip())

        # Mute audio
        proc_mute = await asyncio.create_subprocess_exec(
            'osascript', '-e', 'set volume output volume 0',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc_mute.communicate()
        return "System audio muted, sir."
    except Exception as e:
        return f"Could not mute system audio: {e}"

# ---------------------------------------------------------------------------------------------
# Unmute
# ---------------------------------------------------------------------------------------------
@function_tool
async def unmute_microphone() -> str:
    """Restores system audio to previous volume."""
    global previous_volume
    try:
        if previous_volume is None:
            previous_volume = 50  # default if unknown

        proc = await asyncio.create_subprocess_exec(
            'osascript', '-e', f'set volume output volume {previous_volume}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        return f"System audio restored to {previous_volume}%, sir."
    except Exception as e:
        return f"Could not restore system audio: {e}"

PATH = os.getenv("PATH")    
@function_tool
async def start_a_new_project(folder_name: str, path: str = PATH) -> str:
    """
    Creates a new folder at the default path unless a custom path is specified.
    """
    try:
        # Ensure folder name is safe for AppleScript
        safe_name = folder_name.replace('"', '\\"')

        applescript = f'''
        tell application "Finder"
            if not (exists folder "{safe_name}" of POSIX file "{path}") then
                make new folder at POSIX file "{path}" with properties {{name:"{safe_name}"}}
            end if
        end tell
        '''

        proc = await asyncio.create_subprocess_exec(
            'osascript', '-e', applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return f"✅ Folder '{folder_name}' created at {path}"
        else:
            return f"❌ Failed to create folder: {stderr.decode().strip()}"
    except Exception as e:
        return f"❌ Exception occurred: {e}"

# System Restart
@function_tool()
async def restart_system():
    """
    Triggers a restart of the AI process.
    """
    # Optional: save any memory or state here
    print("Restarting ARTIS now...")
    # Save memory or state if needed
    os._exit(42)



@function_tool
async def power_down() -> str:
    """Immediately stops ARTIS."""
    os._exit(0)