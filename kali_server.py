# kali_server.py
# The final, intelligent server that handles execution, pre-processing, and result digestion.

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
import json
import re

# --- Component Imports ---
# We now need all the components from our successful test script.
try:
    venv_path = Path(__file__).resolve().parents[1]
    site_packages_path = venv_path / ".venv/lib/python3.13/site-packages"
    sys.path.insert(0, str(site_packages_path.resolve()))

    from al1s.drivers.kali.driver import KaliManager
    from config import Master
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from scheduler.core.schemas.schemas import TaskModelOut

    print("✅ Successfully imported all required components.")
except ImportError as e:
    print(f"❌ ERROR: Could not import a required component. Error: {e}")
    sys.exit(1)
# ------------------------------------


# --- Server and Manager Initialization ---
app = FastAPI(title="Intelligent Kali Driver Server")
print("Initializing Kali Docker Manager...")
kali_manager = KaliManager()
print("Kali Docker Manager initialized.")
# ------------------------------------


# --- LLM Setup for Result Digestion ---
print("Initializing command digestion LLM...")
llm = ChatOpenAI(
    model=Master.get("default_model"),
    base_url=Master.get("openai_api_endpoint"),
    api_key=Master.get("openai_api_key"),
    temperature=0,
)
pydantic_object = TaskModelOut
parser = PydanticOutputParser(pydantic_object=pydantic_object)
promptTemplate = ChatPromptTemplate.from_messages([
    ("system", "{format_instructions}\n"
               "You are a summarizer. Your task is to summarize the following result report into valuable content. "
               "Provide a brief, one-sentence summary in the 'result_abstract' field. "
               "For the 'result' field, you MUST format all the detailed findings as a single, multi-line string. Do NOT use a nested JSON object for the 'result' field."
     ),
    ("user", "Result Report:\n```{result_report}```\n\nCorresponding Task: {task_description}")
])
chain = promptTemplate | llm | parser
print("✅ Command digestion LLM initialized.")


# ------------------------------------


# --- Pre-processing Function ---
def preprocess_nmap_output(raw_output: str) -> str:
    important_lines = []
    for line in raw_output.splitlines():
        if line.strip().startswith("PORT") or "/tcp" in line or line.strip().startswith("Service Info:"):
            important_lines.append(line)
    if not important_lines:
        return "No open ports or service information found."
    summary = "Nmap scan summary:\n" + "\n".join(important_lines)
    return summary


# ------------------------------------


# --- API Endpoint ---
class TaskRequest(BaseModel):
    prompt: str


@app.post("/")
def execute_task(request: TaskRequest):
    container = None
    uuid_str = None
    try:
        command_to_run = request.prompt.strip()
        print(f"\n--- [1/4] Received command: '{command_to_run}' ---")

        # Part 1: Execution
        print("  [+] Creating Kali container...")
        uuid_str, container = kali_manager.create_container()
        print(f"  [+] Container '{uuid_str}' created.")

        print("  [+] Sending command and waiting for result...")
        raw_tool_output = container.send_command_and_get_output(command_to_run)
        print("--- ✅ [2/4] Execution Complete ---")

        # Part 2: Pre-processing
        print("\n--- [3/4] Pre-processing result... ---")
        pre_processed_summary = preprocess_nmap_output(raw_tool_output)
        print("--- ✅ Pre-processing Complete ---")

        # Part 3: LLM Digestion
        print("\n--- [4/4] Digesting result with LLM... ---")
        input_args = {
            "result_report": pre_processed_summary,
            "task_description": command_to_run,  # Use the command as the description
            "format_instructions": parser.get_format_instructions(),
        }
        final_structured_result = chain.invoke(input_args)
        print("--- ✅ Digestion Complete ---")

        # We return the Pydantic model, FastAPI will handle serialization
        return final_structured_result

    except Exception as e:
        print(f"!!! An error occurred: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if container and uuid_str:
            print(f"\n  [+] Cleaning up container '{uuid_str}'...")
            kali_manager.destroy_container(uuid_str)
            print("  [+] Cleanup complete.")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)