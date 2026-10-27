import json
from pathlib import Path

data = json.loads(Path("config/avengers.json").read_text())
for a in data["avengers"]:
    print(f"{a['id']}: {a['status']}")