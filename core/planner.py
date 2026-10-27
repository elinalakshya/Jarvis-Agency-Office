"""
core/planner.py — Break a goal into 5 tasks using the LLM.
"""

import json
import re
from pathlib import Path
from core import gemini

PLAN_FILE = Path(__file__).resolve().parent.parent / "memory" / "current_plan.json"


def _extract_json_array(text: str) -> list | None:
    """Find the first valid JSON array in `text`."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    start = text.find("[")
    if start == -1:
        return None

    decoder = json.JSONDecoder()
    try:
        result, _ = decoder.raw_decode(text[start:])
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: try to repair by finding last complete object
    last_close = text.rfind("}")
    if last_close > start:
        repaired = text[start:last_close+1] + "]"
        try:
            result = json.loads(repaired)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    return None


def plan_goal(goal: str) -> list[dict]:
    """Ask the brain to break `goal` into 5 tasks. Returns list of tasks."""
    
    prompt = (
        "OUTPUT JSON ONLY. NO THINKING. NO EXPLANATION.\n\n"
        "Break this goal into exactly 5 tasks.\n\n"
        "Goal: " + goal + "\n\n"
        "Output this exact JSON structure (replace the placeholder values):\n"
        "[\n"
        '  {"id": 1, "title": "Title here", "target_file": "path/file.py", "prompt": "Short prompt under 100 chars"},\n'
        '  {"id": 2, "title": "Title here", "target_file": "path/file.py", "prompt": "Short prompt under 100 chars"},\n'
        '  {"id": 3, "title": "Title here", "target_file": "path/file.py", "prompt": "Short prompt under 100 chars"},\n'
        '  {"id": 4, "title": "Title here", "target_file": "path/file.py", "prompt": "Short prompt under 100 chars"},\n'
        '  {"id": 5, "title": "Title here", "target_file": "path/file.py", "prompt": "Short prompt under 100 chars"}\n'
        "]\n\n"
        "START YOUR RESPONSE WITH [ AND END WITH ]. NO OTHER TEXT."
    )

    try:
        response = gemini.text(prompt, tier=gemini.SMART, timeout_ms=60_000)
        if not response:
            print("[Planner] Empty response")
            return []

        tasks = _extract_json_array(response)

        if not tasks:
            print(f"[Planner] No JSON found. Raw (first 200): {response[:200]}")
            return []

        # Validate and trim
        valid = []
        for i, t in enumerate(tasks):
            if isinstance(t, dict) and all(k in t for k in ("id", "title", "target_file", "prompt")):
                valid.append({
                    "id": int(t["id"]),
                    "title": str(t["title"])[:60],
                    "target_file": str(t["target_file"]),
                    "prompt": str(t["prompt"])[:300],
                })

        if not valid:
            print("[Planner] No valid tasks")
            return []

        # Save
        PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        PLAN_FILE.write_text(
            json.dumps({"goal": goal, "tasks": valid, "completed": [], "current": 0}, indent=2),
            encoding="utf-8",
        )
        return valid

    except Exception as e:
        print(f"[Planner] Error: {e}")
        return []


def load_current_plan() -> dict:
    try:
        return json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_next_task() -> dict | None:
    plan = load_current_plan()
    tasks = plan.get("tasks", [])
    current = plan.get("current", 0)
    if current >= len(tasks):
        return None
    return tasks[current]


def mark_task_complete(task_id: int, result: str) -> None:
    plan = load_current_plan()
    if not plan:
        return
    completed = plan.get("completed", [])
    completed.append({"id": task_id, "result": result})
    plan["completed"] = completed
    plan["current"] = plan.get("current", 0) + 1
    PLAN_FILE.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def format_plan_summary() -> str:
    plan = load_current_plan()
    if not plan:
        return "No active plan."
    tasks = plan.get("tasks", [])
    current = plan.get("current", 0)
    lines = [f"Goal: {plan.get('goal', 'unknown')}", f"Progress: {current}/{len(tasks)} tasks complete"]
    for t in tasks:
        status = "✓" if t["id"] <= current else "○"
        lines.append(f"  {status} Task {t['id']}: {t['title']} → {t['target_file']}")
    return "\n".join(lines)