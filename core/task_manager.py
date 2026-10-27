"""
task_manager.py — task database for JARVIS orchestration.

Stored as JSON at memory/tasks.json. Each task is a dict:
{
    "id":          "task_0001",
    "title":       "Find 50 local plumbers",
    "priority":    "high",         # high | medium | low
    "status":      "pending",      # pending | in_progress | done | blocked
    "role":        "sales",        # sales | dev | support | finance | ceo | ""
    "due":         "",             # YYYY-MM-DD or natural language
    "notes":       "",             # free-form notes
    "created":     "2026-10-16T10:30:00",
    "updated":     "2026-10-16T10:30:00",
}
"""

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
import sys


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


TASKS_PATH = _base_dir() / "memory" / "tasks.json"
_lock = Lock()

VALID_STATUS   = {"pending", "in_progress", "done", "blocked"}
VALID_PRIORITY = {"high", "medium", "low"}
VALID_ROLES    = {"sales", "dev", "support", "finance", "ceo", ""}


def _empty() -> dict:
    return {"tasks": [], "next_id": 1}


def _load() -> dict:
    if not TASKS_PATH.exists():
        return _empty()
    with _lock:
        try:
            data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "tasks" in data:
                return data
            return _empty()
        except Exception as e:
            print(f"[Tasks] load error: {e}")
            return _empty()


def _save(data: dict) -> None:
    TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        TASKS_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def create_task(title: str, priority: str = "medium", due: str = "",
                role: str = "", notes: str = "") -> dict:
    title = (title or "").strip()
    if not title:
        return {"error": "title is required"}
    priority = priority.lower().strip() or "medium"
    if priority not in VALID_PRIORITY:
        priority = "medium"
    role = role.lower().strip()
    if role not in VALID_ROLES:
        role = ""

    data = _load()
    task_id = f"task_{data['next_id']:04d}"
    data["next_id"] += 1

    task = {
        "id":       task_id,
        "title":    title,
        "priority": priority,
        "status":   "pending",
        "role":     role,
        "due":      (due or "").strip(),
        "notes":    (notes or "").strip(),
        "created":  _now(),
        "updated":  _now(),
    }
    data["tasks"].append(task)
    _save(data)
    print(f"[Tasks] ➕ created {task_id}: {title}")
    return task


def list_tasks(status: str = "pending", role: str = "") -> str:
    data = _load()
    tasks = data.get("tasks", [])

    status_filter = (status or "pending").lower().strip()
    role_filter   = (role or "").lower().strip()

    if status_filter and status_filter != "all":
        tasks = [t for t in tasks if t.get("status") == status_filter]
    if role_filter:
        tasks = [t for t in tasks if t.get("role") == role_filter]

    if not tasks:
        return f"No {status_filter} tasks." if status_filter != "all" else "No tasks yet."

    # Sort: high priority first, then oldest
    order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda t: (order.get(t.get("priority", "medium"), 1),
                              t.get("created", "")))

    lines = []
    for t in tasks:
        bits = [f"[{t['id']}]", f"({t['priority']})", t["title"]]
        if t.get("role"):
            bits.append(f"@{t['role']}")
        if t.get("due"):
            bits.append(f"due {t['due']}")
        lines.append("  " + " ".join(bits))

    header = f"{len(tasks)} {status_filter} task(s):"
    return header + "\n" + "\n".join(lines)


def update_task(task_id: str, status: str = "", priority: str = "",
                role: str = "", notes: str = "") -> str:
    task_id = (task_id or "").strip()
    if not task_id:
        return "No task_id provided."

    data = _load()
    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            if status:
                s = status.lower().strip()
                if s in VALID_STATUS:
                    t["status"] = s
            if priority:
                p = priority.lower().strip()
                if p in VALID_PRIORITY:
                    t["priority"] = p
            if role:
                r = role.lower().strip()
                if r in VALID_ROLES:
                    t["role"] = r
            if notes:
                existing = t.get("notes", "")
                t["notes"] = (existing + "\n" + notes).strip() if existing else notes.strip()
            t["updated"] = _now()
            _save(data)
            print(f"[Tasks] ✏️ updated {task_id}: status={t['status']}")
            return f"Updated {task_id}: {t['title']} — status={t['status']}, priority={t['priority']}"

    return f"Task not found: {task_id}"