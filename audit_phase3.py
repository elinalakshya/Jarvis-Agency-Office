from actions.run_security_audit import run_security_audit

files = [
    "finance/models/transaction.py",
    "compliance/rules/engine.py",
    "compliance/audit/logger.py",
    "finance/reporting/regulatory.py",
    "finance/security/encryption.py",
]

for f in files:
    result = run_security_audit({"target_file": f})
    print(f"{f}: {result}")