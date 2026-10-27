from core.planner import plan_goal

prompt = (
    "Build Phase 3: Finance and Compliance layer. "
    "Include: ledger, invoice generator, bill vault, bill collector, "
    "bill matcher, bill verifier, payment tracker, follow-up scheduler, "
    "market-rate pricing, tax calculator, monthly CA report, "
    "YoY growth tracker, and approval gatekeeper. Enforce 8 agency rules."
)

tasks = plan_goal(prompt)
print(f"TOTAL TASKS: {len(tasks)}")
for t in tasks:
    print(f"  {t['id']}. {t['title']} -> {t['target_file']}")