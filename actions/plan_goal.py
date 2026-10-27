"""
actions/plan_goal.py — JARVIS tool: break a goal into tasks.
"""

from core.planner import plan_goal as _plan_goal, format_plan_summary


def plan_goal(parameters=None, **kwargs):
    goal = (parameters or {}).get("goal", "").strip()
    if not goal:
        return "Error: No goal provided."
    tasks = _plan_goal(goal)
    if not tasks:
        return "Failed to create a plan. The brain returned no tasks."
    return f"Plan created with {len(tasks)} tasks.\n{format_plan_summary()}"


TOOL = {
    "name": "plan_goal",
    "description": "Break a high-level goal into a sequence of tasks. Call when the user says 'plan how to build X', 'create a plan for Y', or 'what would it take to Z'.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {"type": "STRING", "description": "The high-level goal to break into tasks"}
        },
        "required": ["goal"]
    },
    "handler": plan_goal
}