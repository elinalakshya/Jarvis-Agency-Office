import json
from pathlib import Path

# 1. Update the JSON with the missing fields
p = Path("config/avengers.json")
data = json.loads(p.read_text())

connectors = {
    "PEPPER_POTTS": "pepper_potts",
    "CAP": "cap",
    "HAPPY": "happy",
    "IRON_MAN": "iron_man",
    "THOR": "thor",
    "DOCTOR_STRANGE": "doctor_strange",
    "HAWK_EYE": "hawk_eye",
    "SPIDER_MAN": "spider_man",
    "BLACK_PANTHER": "black_panther"
}

for a in data["avengers"]:
    if a["id"] in connectors:
        a["connector_module"] = connectors[a["id"]]
        a["connector_function"] = "execute"

p.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("Updated config/avengers.json with connector modules.")

# 2. Create the wrapper files for the router to find
connectors_dir = Path("avengers/connectors")
connectors_dir.mkdir(exist_ok=True)

for avenger_id, module_name in connectors.items():
    wrapper_path = connectors_dir / f"{module_name}.py"
    wrapper_code = f"""
from avengers.connectors import run_{module_name}

def execute(task: str):
    return run_{module_name}(task)
"""
    wrapper_path.write_text(wrapper_code.strip(), encoding="utf-8")
    print(f"Created {wrapper_path}")

print("Done. Router should now find all 9 active Avengers.")