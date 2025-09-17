# ssh_test.py
# A standalone script to test the FINAL robust pipeline:
# 1. Kali Docker Driver Execution
# 2. Python-based pre-processing of the raw output
# 3. LLM digestion of the PRE-PROCESSED summary

import time
import sys
from pathlib import Path
import re

# --- Self-Contained Configuration ---
Master = {
    "default_model": "llama3.1:8b",
    "openai_api_endpoint": "http://localhost:11434/v1",
    "openai_api_key": "ollama",
}
# ------------------------------------

# --- Component Imports ---
try:
    venv_path = Path(__file__).resolve().parents[1]
    site_packages_path = venv_path / ".venv/lib/python3.13/site-packages"
    sys.path.insert(0, str(site_packages_path.resolve()))

    from al1s.drivers.kali.driver import KaliManager
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from scheduler.core.schemas.schemas import TaskModelOut

    print("✅ Successfully imported all required components.")
except ImportError as e:
    print(f"❌ ERROR: Could not import a required component. Error: {e}")
    sys.exit(1)
# ------------------------------------

# --- The Test Script ---
print("\n--- Starting Full Pipeline Test ---")

# == PART 1: EXECUTION ==
manager = KaliManager()
command_to_test = "nmap -sV www.pentest-ground.com"
raw_tool_output = ""
container, uuid_str = None, None

try:
    print(f"\n[EXECUTION] Will execute: '{command_to_test}'")
    uuid_str, container = manager.create_container()
    raw_tool_output = container.send_command_and_get_output(command_to_test)
    print("\n--- ✅ EXECUTION COMPLETE: SUCCESS! ---")
finally:
    if container and uuid_str:
        manager.destroy_container(uuid_str)

# == PART 2: PRE-PROCESSING (The New Smart Step) ==
print("\n\n--- Starting Python Pre-Processing ---")
if not raw_tool_output:
    print("--- ❌ PRE-PROCESSING SKIPPED: No output from execution. ---")
    sys.exit(1)


# This function will extract only the most important lines from the nmap scan.
def preprocess_nmap_output(raw_output: str) -> str:
    important_lines = []
    for line in raw_output.splitlines():
        # Keep lines that start with "PORT", contain "/tcp", or start with "Service Info:"
        if line.strip().startswith("PORT") or "/tcp" in line or line.strip().startswith("Service Info:"):
            important_lines.append(line)

    if not important_lines:
        return "No open ports or service information found."

    summary = "Nmap scan summary:\n" + "\n".join(important_lines)
    print(f"✅ Pre-processing complete. Reduced output to:\n{summary}")
    return summary


pre_processed_summary = preprocess_nmap_output(raw_tool_output)
# ----------------------------------------------------


# == PART 3: LLM DIGESTION (Now with simple input) ==
print("\n\n--- Starting Result Digestion Test ---")

try:
    llm = ChatOpenAI(
        model=Master.get("default_model"),
        base_url=Master.get("openai_api_endpoint"),
        api_key=Master.get("openai_api_key"),
        temperature=0,
    )
    pydantic_object = TaskModelOut
    parser = PydanticOutputParser(pydantic_object=pydantic_object)

    promptTemplate = ChatPromptTemplate.from_messages([
        ("system", "{format_instructions};"
                   "You are a summarizer. Your task is to summarize the following pre-processed report into valuable content. Strictly follow the format requirements."),
        ("user", "Result Report:{result_report}; Corresponding Task: {task_description}")
    ])

    input_args = {
        "result_report": pre_processed_summary,  # <-- We send the SHORT summary, not the raw output
        "task_description": "Gather information about www.pentest-ground.com using nmap and whatweb",
        "format_instructions": parser.get_format_instructions(),
    }

    chain = promptTemplate | llm | parser
    print("\n[DIGESTION] Sending PRE-PROCESSED summary to LLM for formatting...")
    final_structured_result = chain.invoke(input_args)
    print("  [+] LLM processing finished.")

    print("\n--- ✅ DIGESTION COMPLETE: SUCCESS! ---")
    print("\n--- Final Structured Output (What Villager Expects) ---")
    print(final_structured_result.model_dump_json(indent=2))
    print("------------------------------------------------------")

except Exception as e:
    print(f"\n--- ❌ DIGESTION FAILED ---")
    print(f"An error occurred during digestion: {e}")
    import traceback

    traceback.print_exc()