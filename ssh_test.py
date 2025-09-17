# ssh_test.py
# The definitive, standalone script to test the FULL agent pipeline:
# 1. Kali Docker Driver Execution to get RAW TEXT.
# 2. Python-based pre-processing of the raw text.
# 3. LLM digestion of the summary into the final, CORRECTLY FORMATTED JSON.

import time
import sys
from pathlib import Path
import json

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
    # Import the specific Pydantic model Villager expects for the final result
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

# == PART 2: PRE-PROCESSING ==
print("\n\n--- Starting Python Pre-Processing ---")
if not raw_tool_output:
    print("--- ❌ PRE-PROCESSING SKIPPED: No output from execution. ---")
    sys.exit(1)


def preprocess_nmap_output(raw_output: str) -> str:
    important_lines = []
    for line in raw_output.splitlines():
        if line.strip().startswith("PORT") or "/tcp" in line or line.strip().startswith("Service Info:"):
            important_lines.append(line)
    if not important_lines:
        return "No open ports or service information found."
    summary = "Nmap scan summary:\n" + "\n".join(important_lines)
    print(f"✅ Pre-processing complete. Reduced output to:\n{summary}")
    return summary


pre_processed_summary = preprocess_nmap_output(raw_tool_output)
# ------------------------------------


# == PART 3: LLM DIGESTION ==
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

    # --- THIS IS THE FINAL, CORRECTED PROMPT ---
    # It explicitly tells the LLM to format the 'result' field as a single string.
    promptTemplate = ChatPromptTemplate.from_messages([
        ("system", "{format_instructions}\n"
                   "You are a summarizer. Your task is to summarize the following result report into valuable content. "
                   "Provide a brief, one-sentence summary in the 'result_abstract' field. "
                   "For the 'result' field, you MUST format all the detailed findings as a single, multi-line string. Do NOT use a nested JSON object for the 'result' field."
         ),
        ("user", "Result Report:\n```{result_report}```\n\nCorresponding Task: {task_description}")
    ])

    input_args = {
        "result_report": pre_processed_summary,
        "task_description": "Gather information about www.pentest-ground.com using nmap and whatweb",
        "format_instructions": parser.get_format_instructions(),
    }

    chain = promptTemplate | llm | parser
    print("\n[DIGESTION] Sending PRE-PROCESSED summary to LLM for formatting...")
    final_structured_result = chain.invoke(input_args)
    print("  [+] LLM processing finished.")

    # --- CRITICAL VERIFICATION ---
    # Check if the 'result' field is actually a string.
    if isinstance(final_structured_result.result, str):
        print("\n--- ✅ DIGESTION COMPLETE: SUCCESS! ---")
        print("   The LLM correctly produced a JSON object where the 'result' field is a STRING.")
    else:
        print("\n--- ❌ DIGESTION FAILED: DATA TYPE MISMATCH ---")
        print(
            f"   The LLM produced a '{type(final_structured_result.result)}' for the 'result' field instead of a 'str'.")

    print("\n--- Final Structured Output (What Villager Expects) ---")
    print(final_structured_result.model_dump_json(indent=2))
    print("------------------------------------------------------")

except Exception as e:
    print(f"\n--- ❌ DIGESTION FAILED ---")
    print(f"An error occurred during digestion: {e}")
    import traceback

    traceback.print_exc()