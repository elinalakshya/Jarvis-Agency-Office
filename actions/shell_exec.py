"""Shell execution tool."""
import subprocess

def shell_exec(command: str, timeout: int = 120) -> dict:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
        )
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": f"timeout after {timeout}s"}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}

TOOL = {
    "name": "shell_exec",
    "description": "Run a PowerShell command and return stdout/stderr/returncode.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "PowerShell command to run"},
            "timeout": {"type": "INTEGER", "description": "Timeout in seconds (default 120)"},
        },
        "required": ["command"],
    },
}
