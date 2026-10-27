from typing import List, Dict

class ComplianceRule:
    def __init__(self, rule_id: str, description: str):
        self.rule_id = rule_id
        self.description = description

    def is_compliant(self, data: Dict) -> bool:
        raise NotImplementedError("Subclasses should implement this method")

class Rule1(ComplianceRule):
    def __init__(self):
        super().__init__("Rule1", "Ensure all transactions are logged")

    def is_compliant(self, data: Dict) -> bool:
        return "transaction_id" in data and "timestamp" in data

class Rule2(ComplianceRule):
    def __init__(self):
        super().__init__("Rule2", "Verify transaction amounts are within legal limits")

    def is_compliant(self, data: Dict) -> bool:
        return data.get("amount", 0) <= 10000  # Assuming $10,000 is the legal limit

class Rule3(ComplianceRule):
    def __init__(self):
        super().__init__("Rule3", "Ensure all transactions are authorized")

    def is_compliant(self, data: Dict) -> bool:
        return "is_authorized" in data and data["is_authorized"]

class Rule4(ComplianceRule):
    def __init__(self):
        super().__init__("Rule4", "Monitor transactions for suspicious activity")

    def is_compliant(self, data: Dict) -> bool:
        return data.get("suspicious_activity", False) == False

class Rule5(ComplianceRule):
    def __init__(self):
        super().__init__("Rule5", "Ensure compliance with data protection regulations")

    def is_compliant(self, data: Dict) -> bool:
        return "customer_data" in data and "encrypted" in data["customer_data"]

class Rule6(ComplianceRule):
    def __init__(self):
        super().__init__("Rule6", "Maintain a record of all compliance checks")

    def is_compliant(self, data: Dict) -> bool:
        return "compliance_log" in data

class Rule7(ComplianceRule):
    def __init__(self):
        super().__init__("Rule7", "Ensure all transactions are reported to the appropriate authorities")

    def is_compliant(self, data: Dict) -> bool:
        return "reported_to_authorities" in data

class Rule8(ComplianceRule):
    def __init__(self):
        super().__init__("Rule8", "Require periodic audits to verify compliance")

    def is_compliant(self, data: Dict) -> bool:
        return "last_audit" in data and data["last_audit"] >= 30  # Assuming audit every 30 days

class ComplianceGatekeeper:
    def __init__(self):
        self.rules = [
            Rule1(),
            Rule2(),
            Rule3(),
            Rule4(),
            Rule5(),
            Rule6(),
            Rule7(),
            Rule8()
        ]

    def check_compliance(self, data: Dict) -> bool:
        for rule in self.rules:
            if not rule.is_compliant(data):
                return False
        return True

    def approve_transaction(self, transaction_data: Dict) -> bool:
        if self.check_compliance(transaction_data):
            print("Transaction approved.")
            return True
        else:
            print("Transaction rejected due to non-compliance.")
            return False

# Example usage:
gatekeeper = ComplianceGatekeeper()
transaction_data = {
    "transaction_id": "TX12345",
    "timestamp": "2023-10-01T12:34:56Z",
    "amount": 5000,
    "is_authorized": True,
    "suspicious_activity": False,
    "customer_data": {"encrypted": True},
    "compliance_log": True,
    "reported_to_authorities": True,
    "last_audit": 30
}

gatekeeper.approve_transaction(transaction_data)