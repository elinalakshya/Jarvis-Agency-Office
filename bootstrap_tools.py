# bootstrap_tools.py
# One-time installer: creates actions/shell_exec.py and actions/process_control.py,
# wires them into main.py, and verifies syntax.
import re, sys
from pathlib import Path

ROOT = Path(r"D:\business\AI\Github\Jarvis Agency Office")

SHELL_EXEC = '''"""Shell execution tool."""
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
'''

PROCESS_CONTROL = '''"""Process control tool: kill ports, start background processes."""
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
            "\\"" + cmd_ps + " *> " + log_ps + "\\" "
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
'''

def write(path, content):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"[write] {path} ({len(content)} chars)")

def wire_main():
    main = ROOT / "main.py"
    src = main.read_text(encoding="utf-8")

    # 1) Add tool declarations if missing
    if '"name": "shell_exec"' not in src:
        decl = '''    {
        "name": "shell_exec",
        "description": "Run a PowerShell command. Use for any shell/CLI task: git, npm, python, dir, Get-Process, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "PowerShell command"},
                "timeout": {"type": "INTEGER", "description": "Timeout seconds, default 120"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "process_control",
        "description": "Kill a process on a port, or start a background process with log redirect.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "kill_port or start_background"},
                "port": {"type": "INTEGER"},
                "command": {"type": "STRING"},
                "cwd": {"type": "STRING"},
                "log_file": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
'''
        # Insert just before the closing ']' of TOOL_DECLARATIONS
        m = re.search(r'(TOOL_DECLARATIONS\s*=\s*\[)', src)
        if not m:
            print("[FAIL] TOOL_DECLARATIONS not found"); return False
        # Find matching ']' by bracket counting from the '[' position
        start = m.end() - 1
        depth = 0
        end = -1
        for i in range(start, len(src)):
            if src[i] == '[':
                depth += 1
            elif src[i] == ']':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            print("[FAIL] Could not find end of TOOL_DECLARATIONS"); return False
        src = src[:end] + decl + src[end:]
        print("[wire] added tool declarations")
    else:
        print("[skip] declarations already present")

    # 2) Add handlers if missing
    if 'name == "shell_exec"' not in src:
        handler = '''
            elif name == "shell_exec":
                from actions.shell_exec import shell_exec
                result = shell_exec(args.get("command", ""), int(args.get("timeout", 120) or 120))
            elif name == "process_control":
                from actions.process_control import kill_port, start_background
                action = args.get("action", "")
                if action == "kill_port":
                    result = kill_port(int(args.get("port", 0) or 0))
                elif action == "start_background":
                    result = start_background(
                        args.get("command", ""),
                        args.get("cwd", ""),
                        args.get("log_file", ""),
                    )
                else:
                    result = {"error": f"unknown action: {action}"}
'''
        # Find the end of _execute_tool by locating 'name == "undo"'
        anchor = re.search(r'elif\s+name\s*==\s*"undo"', src)
        if not anchor:
            print("[FAIL] could not locate undo handler to anchor insertion"); return False
        # Insert BEFORE the undo elif
        src = src[:anchor.start()] + handler.lstrip('\n') + "\n            " + src[anchor.start():]
        print("[wire] added handlers")
    else:
        print("[skip] handlers already present")

    main.write_text(src, encoding="utf-8")
    return True

def verify():
    r = subprocess_run_import()

def subprocess_run_import():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-c", "import main; print('main.py syntax OK')"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print("[FAIL] main.py did not import:\n", r.stderr)
        return False
    # Also verify the two new modules
    for mod in ("actions.shell_exec", "actions.process_control"):
        r2 = subprocess.run(
            [sys.executable, "-c", f"import {mod}; print('{mod} OK')"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        print(r2.stdout.strip() or r2.stderr.strip())
        if r2.returncode != 0:
            return False
    return True

if __name__ == "__main__":
    write("actions/shell_exec.py", SHELL_EXEC)
    write("actions/process_control.py", PROCESS_CONTROL)
    ok = wire_main()
    if not ok:
        sys.exit(1)
    if not subprocess_run_import():
        sys.exit(1)
    print("\n[BOOTSTRAP COMPLETE] JARVIS now has shell_exec + process_control.")