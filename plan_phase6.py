from core.planner import plan_goal

goal = (
    "Build Phase 6: Full Orchestrator layer. "
    "Include: role dispatcher (Sales, Dev, Support, Finance, CEO modes), "
    "full orchestrator loop (goal to tasks to execution), "
    "escalation system (when to ask user vs act alone), "
    "and repo manager (clone approved GitHub repos)."
)

tasks = plan_goal(goal)
print(f"TOTAL TASKS: {len(tasks)}")
for t in tasks:
    print(f"  {t['id']}. {t['title']} -> {t['target_file']}")