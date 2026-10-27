import json
from pathlib import Path

tasks = [
    {
        "id": 1,
        "title": "Create Avenger Registry (19 Avengers, 9 active)",
        "target_file": "config/avengers.json",
        "prompt": "Create a JSON registry of 19 Avengers. Active: PEPPER_POTTS, CAP, HAPPY, IRON_MAN, THOR, DOCTOR_STRANGE, HAWK_EYE, SPIDER_MAN, BLACK_PANTHER. Inactive: ANT_MAN, WASP, VISION, SCARLET_WITCH, WAR_MACHINE, FALCON, WINTER_SOLDIER, SHURI, OKOYE, M_BAKU. Each entry must have: id, name, status (active/inactive), repo_path, api_key_env, income_ytd, last_run."
    },
    {
        "id": 2,
        "title": "Activate PEPPER POTTS (Finance Tracker)",
        "target_file": "avengers/pepper_potts.py",
        "prompt": "Create a Python module that connects the Finance ledger to the Avenger registry. Add functions: log_avenger_income(avenger_id, amount, description) and log_avenger_cost(avenger_id, amount, description). Both must write to finance/ledger.py and update the avenger's income_ytd."
    },
    {
        "id": 3,
        "title": "Build the 8 Active Connectors",
        "target_file": "avengers/connectors.py",
        "prompt": "Create a single Python file with 8 functions: run_cap(task), run_happy(task), run_iron_man(task), run_thor(task), run_doctor_strange(task), run_hawk_eye(task), run_spider_man(task), run_black_panther(task). Each function should read the avenger's repo_path from config/avengers.json, execute it via subprocess, and return a status string. Add safety checks: only run if status is 'active'."
    },
    {
        "id": 4,
        "title": "Build the Router",
        "target_file": "actions/router.py",
        "prompt": "Create a JARVIS action tool called router. It accepts parameters: avenger_id and task. It looks up the avenger in config/avengers.json, then calls the corresponding function in avengers/connectors.py. Return the result. Include a TOOL dict so it auto-registers."
    },
    {
        "id": 5,
        "title": "Build the Visual Dashboard",
        "target_file": "dashboard/app.py",
        "prompt": "Create a Flask app with a single route '/' that renders an HTML dashboard. It must read config/avengers.json and display 19 avenger cards (green for active, grey for inactive). Also read finance/ledger.py and display total revenue and last 5 transactions. Include inline HTML/CSS in the same file."
    }
]

plan = {
    "goal": "Final Build: 9 Active Avengers + Router + Dashboard",
    "tasks": tasks,
    "completed": [],
    "current": 0
}

plan_file = Path("memory/current_plan.json")
plan_file.parent.mkdir(parents=True, exist_ok=True)
plan_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")
print(f"Plan saved with {len(tasks)} tasks. File: {plan_file}")