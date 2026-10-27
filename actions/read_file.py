"""
actions/read_file.py — JARVIS tool: read the content of a file in the project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def read_file(parameters=None, **kwargs):
    file_path = (parameters or {}).get("file_path", "").strip()
    if not file_path:
        return "Error: No file_path provided."

    full_path = BASE_DIR / file_path
    if not str(full_path).lower().startswith(str(BASE_DIR).lower()):
        return f"BOUNDARY VIOLATION: {file_path} is outside the project folder."

    if not full_path.exists():
        return f"File not found: {file_path}"

    try:
        content = full_path.read_text(encoding="utf-8")
        # Limit to 5000 chars to avoid flooding the model
        if len(content) > 5000:
            content = content[:5000] + "\n\n... (truncated)"
        return f"Content of {file_path}:\n\n{content}"
    except Exception as e:
        return f"Error reading {file_path}: {e}"


TOOL = {
    "name": "read_file",
    "description": "Read the content of a file in the project. Call when the user says 'show me the file', 'read X', 'what's in Y', or asks about the content of an existing file.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {"type": "STRING", "description": "Relative path like 'core/backup.py'"}
        },
        "required": ["file_path"]
    },
    "handler": read_file
}