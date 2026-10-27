from core.planner import plan_goal

goal = (
    "Build Phase 7: Complete Company Audit Engine. "
    "Include: audit engine (runs every 15 days), "
    "bill verification pass (every transaction to bill check), "
    "anomaly detection (flags unusual transactions), "
    "compliance checklist (GST/TDS/income tax readiness), "
    "and audit report generator (PDF + spoken + email)."
)

tasks = plan_goal(goal)
print(f"TOTAL TASKS: {len(tasks)}")
for t in tasks:
    print(f"  {t['id']}. {t['title']} -> {t['target_file']}")