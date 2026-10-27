import json
from pathlib import Path

active_ids = [
    "PEPPER_POTTS", "CAP", "HAPPY", "IRON_MAN", "THOR",
    "DOCTOR_STRANGE", "HAWK_EYE", "SPIDER_MAN", "BLACK_PANTHER"
]

p = Path("config/avengers.json")
data = json.loads(p.read_text())

# Update the status of each avenger
for avenger in data["avengers"]:
    if avenger["id"] in active_ids:
        avenger["status"] = "active"
    else:
        avenger["status"] = "inactive"

p.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Fixed {len(active_ids)} active Avengers.")