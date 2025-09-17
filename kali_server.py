# kali_server.py

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path

# --- Driver Import ---
venv_path = Path(__file__).resolve().parents[1]
site_packages_path = venv_path / ".venv/lib/python3.13/site-packages"
sys.path.insert(0, str(site_packages_path.resolve()))
try:
    from al1s.drivers.kali.driver import KaliManager
except ImportError as e:
    print(f"FATAL ERROR: Could not import KaliManager. {e}")
    sys.exit(1)

app = FastAPI(title="Kali Driver Server")
print("Initializing Kali Docker Manager...")
kali_manager = KaliManager()
print("Kali Docker Manager initialized.")

class TaskRequest(BaseModel):
    prompt: str

@app.post("/")
def execute_task(request: TaskRequest):
    container = None
    uuid_str = None
    try:
        command_to_run = request.prompt.strip()
        print(f"\n--- Received command: '{command_to_run}' ---")

        print("  [+] Creating Kali container...")
        uuid_str, container = kali_manager.create_container()
        print(f"  [+] Container {uuid_str} created.")

        print(f"  [+] Sending command and waiting for result...")
        # --- THE CRITICAL CHANGE: Use our new robust method ---
        output = container.send_command_and_get_output(command_to_run)
        print(f"--- Command execution finished ---")

        return {"result": output}

    except Exception as e:
        print(f"!!! An error occurred: {e}")
        # Add the full traceback for better debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if container and uuid_str:
            print(f"  [+] Destroying container {uuid_str}...")
            kali_manager.destroy_container(uuid_str)
            print("  [+] Container destroyed.")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)