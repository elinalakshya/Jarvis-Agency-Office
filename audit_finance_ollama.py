from actions.run_security_audit import run_security_audit

files = [
    "finance/ledger.py",
    "finance/bills.py",
    "finance/analytics.py",
    "finance/compliance.py",
    "finance/main.py",
]

for f in files:
    result = run_security_audit({"target_file": f})
    print(f"{f}: {result}")