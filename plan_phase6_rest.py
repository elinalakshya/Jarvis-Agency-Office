from core.planner import plan_goal

goal = (
    "Complete Phase 6: Full Orchestrator. "
    "Include: escalation system (when to ask user vs act alone), "
    "repo manager (clone approved GitHub repos safely), "
    "and orchestrator __init__.py that ties everything together."
)

tasks = plan_goal(goal)
print(f"TOTAL TASKS: {len(tasks)}")
for t in tasks:
    print(f"  {t['id']}. {t['title']} -> {t['target_file']}")