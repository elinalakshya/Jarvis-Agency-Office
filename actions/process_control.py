"""Process control tool: kill ports, start background processes."""
import subprocess
from pathlib import Path

def kill_port(port: int) -> dict:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
             f"Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | "
             f"ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; $_ }}"],
            capture_output=True, text=True, timeout=30,
        )
        killed = [x.strip() for x in r.stdout.splitlines() if x.strip().isdigit()]
        return {"port": port, "killed_pids": killed}
    except Exception as e:
        return {"port": port, "error": str(e)}

def start_background(command: str, cwd: str, log_file: str) -> dict:
    try:
        Path(cwd).mkdir(parents=True, exist_ok=True)
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Escape single quotes in paths for PowerShell
        cwd_ps = str(cwd).replace("'", "''")
        log_ps = str(log_path).replace("'", "''")
        cmd_ps = command.replace("'", "''")
        script = (
            "$p = Start-Process powershell -ArgumentList "
            "'-NoProfile','-Command',"
            "\"" + cmd_ps + " *> " + log_ps + "\" "
            "-WorkingDirectory '" + cwd_ps + "' -WindowStyle Hidden -PassThru; "
            "$p.Id"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=30,
        )
        pid = r.stdout.strip()
        return {"pid": pid, "log_file": str(log_path), "cwd": cwd, "stderr": r.stderr.strip()}
    except Exception as e:
        return {"error": str(e)}

TOOL = {
    "name": "process_control",
    "description": "Kill a process on a port, or start a background process with log redirect.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "kill_port or start_background"},
            "port": {"type": "INTEGER", "description": "For kill_port: port to free"},
            "command": {"type": "STRING", "description": "For start_background: command to run"},
            "cwd": {"type": "STRING", "description": "For start_background: working directory"},
            "log_file": {"type": "STRING", "description": "For start_background: log file path"},
        },
        "required": ["action"],
    },
}
