import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def patch_file(parameters=None, **kwargs):
    """
    Read a file, send it to the local Ollama LLM with an error message, 
    and write back the fixed version.
    """
    target_file = (parameters or {}).get("target_file", "").strip()
    error_msg = (parameters or {}).get("error", "").strip()

    if not target_file:
        return "Error: No target_file provided."

    full_path = Path(target_file)
    if not full_path.exists():
        full_path = BASE_DIR / target_file
        if not full_path.exists():
            return f"Error: File {target_file} does not exist."

    original_code = full_path.read_text(encoding="utf-8")

    prompt = (
        f"You are a senior developer. "
        f"Fix the error in this file.\n\n"
        f"Error:\n{error_msg}\n\n"
        f"File content:\n```\n{original_code}\n```\n\n"
        f"Return ONLY the complete, fixed file content. No markdown fences. No explanation."
    )

    # Use LOCAL OLLAMA (no rate limits, always free)
    try:
        payload = {
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 4000}
        }
        r = requests.post("http://localhost:11434/api/chat", json=payload, timeout=300)
        r.raise_for_status()
        
        content = r.json().get("message", {}).get("content", "").strip()

        # Strip markdown fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:])
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        if not content:
            return "Error: Ollama returned empty content."

        full_path.write_text(content, encoding="utf-8")
        return f"SUCCESS: Patched {target_file} using Ollama"

    except Exception as e:
        return f"FAILED: {e}"


TOOL = {
    "name": "patch_file",
    "description": "Fix a file by sending its content and an error message to the local Ollama LLM. Use this when a script fails.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_file": {"type": "STRING", "description": "Absolute or relative path to the file"},
            "error": {"type": "STRING", "description": "The error message to fix"}
        },
        "required": ["target_file", "error"]
    },
    "handler": patch_file
}