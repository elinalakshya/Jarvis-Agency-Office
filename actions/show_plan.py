"""
actions/show_plan.py — JARVIS tool: show the current plan.
"""

from core.planner import format_plan_summary


def show_plan(parameters=None, **kwargs):
    return format_plan_summary()


TOOL = {
    "name": "show_plan",
    "description": "Show the current plan and progress. Call when the user asks 'what's the plan', 'how far along', or 'show progress'.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    },
    "handler": show_plan
}