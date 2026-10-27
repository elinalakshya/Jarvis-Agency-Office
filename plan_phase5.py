from core.planner import plan_goal

goal = (
    "Build Phase 5: Avengers and Delivery layer. "
    "Include: avenger registry, run_avenger tool, check_avenger_status tool, "
    "collect_bills tool, and central brain dispatcher."
)

tasks = plan_goal(goal)
print(f"TOTAL TASKS: {len(tasks)}")
for t in tasks:
    print(f"  {t['id']}. {t['title']} -> {t['target_file']}")