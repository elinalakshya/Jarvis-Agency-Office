"""
actions/execute_task.py — JARVIS tool: execute the next task in the plan.
"""

from core.executor import execute_next
from core.planner import format_plan_summary


def execute_task(parameters=None, **kwargs):
    result = execute_next()
    return f"{result}\n\n{format_plan_summary()}"


TOOL = {
    "name": "execute_task",
    "description": "Execute the next task in the current plan. Call when the user says 'execute task', 'continue with the plan', or 'next step'.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    },
    "handler": execute_task
}