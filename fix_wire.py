# fix_wire.py — repair the shell_exec/process_control wiring in main.py
import re, sys, subprocess
from pathlib import Path

ROOT = Path(r"D:\business\AI\Github\Jarvis Agency Office")
main = ROOT / "main.py"
src = main.read_text(encoding="utf-8")

# 1) Remove any previously-injected (broken) handler block so we start clean.
#    We injected it just before the "undo" elif last time.
#    Match from the line containing 'elif name == "shell_exec":' back to
#    the preceding 'elif' line that starts the previous handler, and forward
#    to just before 'elif name == "undo"'.
pattern_handlers = re.compile(
    r'[ \t]*elif\s+name\s*==\s*"shell_exec".*?(?=[ \t]*elif\s+name\s*==\s*"undo")',
    re.DOTALL,
)
if pattern_handlers.search(src):
    src = pattern_handlers.sub('', src)
    print("[clean] removed previous shell_exec/process_control handlers")

# 2) Re-insert handlers with correct indentation, matching the surrounding block.
#    Find the 'undo' handler line and detect its leading whitespace.
undo_match = re.search(r'^([ \t]*)elif\s+name\s*==\s*"undo"', src, re.MULTILINE)
if not undo_match:
    print("[FAIL] cannot locate undo handler"); sys.exit(1)
indent = undo_match.group(1)
print(f"[info] handler indent detected: {len(indent)} spaces")

handler = (
    f'{indent}elif name == "shell_exec":\n'
    f'{indent}    from actions.shell_exec import shell_exec\n'
    f'{indent}    result = shell_exec(\n'
    f'{indent}        args.get("command", ""),\n'
    f'{indent}        int(args.get("timeout", 120) or 120),\n'
    f'{indent}    )\n'
    f'{indent}elif name == "process_control":\n'
    f'{indent}    from actions.process_control import kill_port, start_background\n'
    f'{indent}    _action = args.get("action", "")\n'
    f'{indent}    if _action == "kill_port":\n'
    f'{indent}        result = kill_port(int(args.get("port", 0) or 0))\n'
    f'{indent}    elif _action == "start_background":\n'
    f'{indent}        result = start_background(\n'
    f'{indent}            args.get("command", ""),\n'
    f'{indent}            args.get("cwd", ""),\n'
    f'{indent}            args.get("log_file", ""),\n'
    f'{indent}        )\n'
    f'{indent}    else:\n'
    f'{indent}        result = {{"error": f"unknown action: {{_action}}"}}\n'
)

src = src[:undo_match.start()] + handler + src[undo_match.start():]
main.write_text(src, encoding="utf-8")
print("[write] main.py updated")

# 3) Verify imports
r = subprocess.run(
    [sys.executable, "-c", "import main; print('main.py syntax OK')"],
    cwd=str(ROOT), capture_output=True, text=True, timeout=60,
)
print(r.stdout.strip() or r.stderr.strip())
if r.returncode != 0:
    sys.exit(1)

for mod in ("actions.shell_exec", "actions.process_control"):
    r2 = subprocess.run(
        [sys.executable, "-c", f"import {mod}; print('{mod} OK')"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30,
    )
    print(r2.stdout.strip() or r2.stderr.strip())
    if r2.returncode != 0:
        sys.exit(1)

print("\n[FIX COMPLETE] main.py wired, both tools import cleanly.")