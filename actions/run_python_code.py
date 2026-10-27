import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def run_python_code(parameters=None, **kwargs):
    target_file = (parameters or {}).get("target_file", "").strip()
    
    if not target_file:
        return "Error: No target_file provided."

    full_path = BASE_DIR / target_file
    if not str(full_path).lower().startswith(str(BASE_DIR).lower()):
        return f"BOUNDARY VIOLATION: {target_file} is outside allowed folder"
        
    if not full_path.exists():
        return f"Error: File {target_file} does not exist yet."

    try:
        # Run the file using the current Python environment
        result = subprocess.run(
            [sys.executable, str(full_path)],
            capture_output=True,
            text=True,
            timeout=30,  # 30 seconds max execution time
            cwd=str(BASE_DIR)
        )
        
        if result.returncode == 0:
            output = result.stdout.strip() or "(No output)"
            return f"SUCCESS: Code ran perfectly.\nOutput:\n{output}"
        else:
            error = result.stderr.strip()
            # If stderr is empty but it failed, something weird happened
            if not error:
                error = result.stdout.strip() or "Unknown error"
            return f"FAILED: Code crashed.\nError traceback:\n{error}"
            
    except subprocess.TimeoutExpired:
        return "FAILED: Execution timed out after 30 seconds."
    except Exception as e:
        return f"FAILED: Execution error: {e}"


TOOL = {
    "name": "run_python_code",
    "description": "Run a Python file to test if it works. Use this IMMEDIATELY after writing a Python file to verify it. If it returns FAILED, read the error and fix the code.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_file": {"type": "STRING", "description": "Relative path to the file, e.g. 'core/backup.py'"}
        },
        "required": ["target_file"]
    },
    "handler": run_python_code
}