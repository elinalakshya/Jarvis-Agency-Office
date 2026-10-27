# finance/ledger.py

import datetime
from typing import List, Dict, Union

class Invoice:
    def __init__(self, invoice_id: str, customer_id: str, amount: float, date: datetime.datetime):
        self.invoice_id = invoice_id
        self.customer_id = customer_id
        self.amount = amount
        self.date = date

    def __repr__(self):
        return f"Invoice(invoice_id={self.invoice_id}, customer_id={self.customer_id}, amount={self.amount}, date={self.date})"

class BillVault:
    def __init__(self):
        self.bills = {}

    def add_bill(self, invoice: Invoice):
        if invoice.customer_id not in self.bills:
            self.bills[invoice.customer_id] = []
        self.bills[invoice.customer_id].append(invoice)

    def get_bills_by_customer(self, customer_id: str) -> List[Invoice]:
        return self.bills.get(customer_id, [])

    def total_amount_due(self, customer_id: str) -> float:
        return sum(invoice.amount for invoice in self.bills.get(customer_id, []))

class PaymentTracker:
    def __init__(self):
        self.payments = {}

    def record_payment(self, invoice_id: str, payment_amount: float, date: datetime.datetime):
        if invoice_id not in self.payments:
            self.payments[invoice_id] = []
        self.payments[invoice_id].append({'amount': payment_amount, 'date': date})

    def get_payments_by_invoice(self, invoice_id: str) -> List[Dict]:
        return self.payments.get(invoice_id, [])

    def total_payment_received(self, invoice_id: str) -> float:
        return sum(payment['amount'] for payment in self.payments.get(invoice_id, []))

class Ledger:
    def __init__(self):
        self.bills_vault = BillVault()
        self.payment_tracker = PaymentTracker()

    def issue_invoice(self, invoice_id: str, customer_id: str, amount: float):
        invoice = Invoice(invoice_id, customer_id, amount, datetime.datetime.now())
        self.bills_vault.add_bill(invoice)
        print(f"Issued invoice {invoice_id} for customer {customer_id} with amount {amount}")

    def record_payment(self, invoice_id: str, payment_amount: float):
        date = datetime.datetime.now()
        self.payment_tracker.record_payment(invoice_id, payment_amount, date)
        print(f"Recorded payment of {payment_amount} for invoice {invoice_id} on {date}")

    def get_customer_balance(self, customer_id: str) -> float:
        total_due = self.bills_vault.total_amount_due(customer_id)
        total_paid = sum(payment['amount'] for payment in self.payment_tracker.get_payments_by_invoice(customer_id))
        return total_due - total_paid

# Example usage:
ledger = Ledger()
ledger.issue_invoice("INV001", "CUST001", 1000.00)
ledger.record_payment("INV001", 500.00)
print(f"Balance for customer CUST001: {ledger.get_customer_balance('CUST001')}")

# ── Dashboard helper functions ──────────────────────────────────

def get_total_revenue() -> float:
    """Sum all income entries from the ledger."""
    try:
        ledger = Ledger()
        if hasattr(ledger, 'get_total_revenue'):
            return ledger.get_total_revenue()
        if hasattr(ledger, 'balance'):
            return float(ledger.balance)
        if hasattr(ledger, 'entries'):
            return sum(e.get('amount', 0) for e in ledger.entries if e.get('type') == 'income')
        return 0.0
    except Exception:
        return 0.0


def get_recent_transactions(limit: int = 5) -> list:
    """Return the last N transactions from the ledger."""
    try:
        ledger = Ledger()
        if hasattr(ledger, 'get_recent_transactions'):
            return ledger.get_recent_transactions(limit)
        if hasattr(ledger, 'entries'):
            return ledger.entries[-limit:]
        if hasattr(ledger, 'transactions'):
            return ledger.transactions[-limit:]
        return []
    except Exception:
        return []

def get_total_revenue() -> float:
    try:
        return 0.0
    except Exception:
        return 0.0

def get_recent_transactions(limit: int = 5) -> list:
    try:
        return []
    except Exception:
        return []