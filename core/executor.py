"""
core/executor.py — Execute one task from the plan.
"""

from core.planner import get_next_task, mark_task_complete


def execute_next() -> str:
    """Run the next task in the plan. Returns a status message."""
    task = get_next_task()
    if not task:
        return "No pending tasks. Plan complete or no plan exists."

    task_id = task["id"]
    title = task["title"]
    target_file = task["target_file"]
    prompt = task["prompt"]

    print(f"[Executor] Task {task_id}: {title} → {target_file}")

    try:
        from actions.run_claude_code import run_claude_code
        result = run_claude_code({"prompt": prompt, "target_file": target_file})
        print(f"[Executor] Result: {result}")

        if result.startswith("Success") or result.startswith("Success ("):
            mark_task_complete(task_id, result)
            return f"Task {task_id} complete: {target_file} written. {result}"
        else:
            return f"Task {task_id} failed: {result}"
    except Exception as e:
        print(f"[Executor] Error: {e}")
        return f"Task {task_id} error: {e}"