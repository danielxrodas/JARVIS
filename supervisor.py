import subprocess
import time

venv_path = "/Users/daniel/Documents/Projects/JARVIS/venv/bin/activate"
agent_path = "/Users/daniel/Documents/Projects/JARVIS/agent.py"

try:
    while True:
        proc = subprocess.run(
            f"source {venv_path} && python3 {agent_path} console",
            shell=True
        )
        if proc.returncode != 42:  # normal exit, not a crash/restart request
            print("Agent exited. Stopping supervisor.")
            break
        print("Agent requested restart. Restarting in 3 seconds...")
        time.sleep(3)

except KeyboardInterrupt:
    print("\nSupervisor stopped by user.")