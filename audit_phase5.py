from actions.run_security_audit import run_security_audit
from pathlib import Path
import json

plan = json.loads(Path("memory/current_plan.json").read_text())
files = list(set(t["target_file"] for t in plan["tasks"]))

for f in files:
    result = run_security_audit({"target_file": f})
    print(f"{f}: {result}")