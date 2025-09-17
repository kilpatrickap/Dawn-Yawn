# kali_server.py
# The definitive, streamlined server that ONLY handles command execution.

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
import traceback

# --- Driver Import ---
# This block correctly finds and imports the KaliManager from your virtual environment.
try:
    # We assume this script is in the root 'Villager' directory, and the venv is './.venv'
    venv_path = Path(__file__).resolve().parent
    site_packages_path = venv_path / ".venv/lib/python3.13/site-packages"
    sys.path.insert(0, str(site_packages_path.resolve()))

    from al1s.drivers.kali.driver import KaliManager

    print("✅ Successfully imported KaliManager.")
except ImportError as e:
    print("=" * 80)
    print("FATAL ERROR: Could not import KaliManager.")
    print(f"Attempted to look in: '{site_packages_path}'")
    print(f"Original error: {e}")
    print("=" * 80)
    sys.exit(1)
# --------------------


# --- FastAPI Server Setup ---
app = FastAPI(title="Kali Driver Server")

print("Initializing Kali Docker Manager...")
kali_manager = KaliManager()
print("Kali Docker Manager initialized.")


class TaskRequest(BaseModel):
    prompt: str  # The client will send a JSON with a "prompt" key


@app.post("/")
def execute_task(request: TaskRequest):
    """
    Receives a PRE-CLEANED command from the Villager agent,
    executes it in a Kali container, and returns the RAW text result.
    """
    container = None
    uuid_str = None
    try:
        command_to_run = request.prompt.strip()
        print(f"\n--- [1/2] Received command: '{command_to_run}' ---")

        # Part 1: Execution
        print("  [+] Creating Kali container from 'villager-kali-agent' image...")
        uuid_str, container = kali_manager.create_container()
        print(f"  [+] Container '{uuid_str}' created.")

        print("  [+] Sending command and waiting for result...")
        raw_tool_output = container.send_command_and_get_output(command_to_run)
        print("--- ✅ [2/2] Execution Complete ---")

        # The server's only job is to return the raw result.
        # The Villager agent's brain will handle summarization.
        return {"result": raw_tool_output}

    except Exception as e:
        print(f"!!! An error occurred: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Crucial cleanup step
        if container and uuid_str:
            print(f"\n  [+] Cleaning up container '{uuid_str}'...")
            kali_manager.destroy_container(uuid_str)
            print("  [+] Cleanup complete.")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)