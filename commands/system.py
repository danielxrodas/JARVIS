from livekit.agents import function_tool
import os
import asyncio
import subprocess
import signal

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
    os.kill(os.getpid(), signal.SIGINT)
    return "JARVIS is powering down..."