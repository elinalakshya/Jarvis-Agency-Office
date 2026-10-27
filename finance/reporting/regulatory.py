"""Regulatory reporting module for financial compliance.

Generates SAR (Suspicious Activity Reports), CTR (Currency Transaction Reports),
and periodic compliance reports per FinCEN/BSA requirements.
"""

from __future__ import annotations

import csv
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of regulatory reports."""
    SAR = "SAR"
    CTR = "CTR"
    PERIODIC_COMPLIANCE = "PERIODIC_COMPLIANCE"
    DOEP = "DOEP"  # Designation of Exempt Person
    CMIR = "CMIR"  # Report of International Transportation of Currency


class FilingStatus(Enum):
    """Report filing status."""
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    FILED = "FILED"
    REJECTED = "REJECTED"
    AMENDED = "AMENDED"


class SuspiciousActivityCategory(Enum):
    """FinCEN SAR suspicious activity categories."""
    STRUCTURING = "structuring"
    TERRORIST_FINANCING = "terrorist_financing"
    FRAUD = "fraud"
    MONEY_LAUNDERING = "money_laundering"
    BRIBERY = "bribery"
    TAX_EVASION = "tax_evasion"
    IDENTITY_THEFT = "identity_theft"
    CYBER_EVENT = "cyber_event"
    OTHER = "other"


class TransactionType(Enum):
    """Transaction types for CTR reporting."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    EXCHANGE = "exchange"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    PAYMENT = "payment"
    PURCHASE = "purchase"
    SALE = "sale"
    OTHER = "other"


@dataclass
class Party:
    """Party involved in a transaction (individual or entity)."""
    name: str
    ssn_tin: str | None = None
    date_of_birth: date | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"
    phone: str | None = None
    email: str | None = None
    occupation: str | None = None
    id_type: str | None = None  # DL, PP, etc.
    id_number: str | None = None
    id_issuing_state: str | None = None
    id_issuing_country: str = "US"
    is_entity: bool = False
    entity_type: str | None = None  # corporation, LLC, trust, etc.

    def to_fincen_dict(self, prefix: str = "") -> dict[str, Any]:
        """Convert to FinCEN-compatible dictionary with prefixed keys."""
        prefix = f"{prefix}_" if prefix else ""
        data = {
            f"{prefix}name": self.name,
            f"{prefix}ssn_tin": self.ssn_tin,
            f"{prefix}dob": self.date_of_birth.isoformat() if self.date_of_birth else None,
            f"{prefix}address": self.address,
            f"{prefix}city": self.city,
            f"{prefix}state": self.state,
            f"{prefix}zip": self.zip_code,
            f"{prefix}country": self.country,
            f"{prefix}phone": self.phone,
            f"{prefix}email": self.email,
            f"{prefix}occupation": self.occupation,
            f"{prefix}id_type": self.id_type,
            f"{prefix}id_number": self.id_number,
            f"{prefix}id_issuing_state": self.id_issuing_state,
            f"{prefix}id_issuing_country": self.id_issuing_country,
            f"{prefix}is_entity": self.is_entity,
            f"{prefix}entity_type": self.entity_type,
        }
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class FinancialInstitution:
    """Filing financial institution details."""
    name: str
    rssd_id: str  # RSSD ID from Federal Reserve
    lei: str | None = None  # Legal Entity Identifier
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"
    phone: str | None = None
    primary_regulator: str | None = None  # OCC, FDIC, FRB, etc.


@dataclass
class Transaction:
    """Individual transaction record."""
    transaction_id: str
    transaction_date: date
    transaction_type: TransactionType
    amount: Decimal
    currency: str = "USD"
    description: str | None = None
    account_number: str | None = None
    account_type: str | None = None  # checking, savings, etc.
    counterparty: Party | None = None
    branch_id: str | None = None
    channel: str | None = None  # branch, atm, online, wire, etc.
    reference_number: str | None = None

    def __post_init__(self):
        if isinstance(self.amount, (int, float, str)):
            self.amount = Decimal(str(self.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if isinstance(self.transaction_type, str):
            self.transaction_type = TransactionType(self.transaction_type)


@dataclass
class BaseReport(ABC):
    """Base class for all regulatory reports."""
    report_id: str = field(default_factory=lambda: str(uuid4()))
    report_type: ReportType = field(init=False)
    filing_institution: FinancialInstitution | None = None
    filing_date: date = field(default_factory=date.today)
    status: FilingStatus = FilingStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    filed_at: datetime | None = None
    filed_by: str | None = None
    prior_report_id: str | None = None  # For amended reports
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def validate(self) -> list[str]:
        """Validate report data. Returns list of validation errors."""
        pass

    @abstractmethod
    def to_fincen_format(self) -> dict[str, Any]:
        """Convert to FinCEN BSA E-Filing format."""
        pass

    def mark_filed(self, filed_by: str) -> None:
        """Mark report as filed."""
        self.status = FilingStatus.FILED
        self.filed_at = datetime.utcnow()
        self.filed_by = filed_by
        self.updated_at = datetime.utcnow()

    def to_json(self) -> str:
        """Serialize report to JSON."""
        data = asdict(self)
        # Convert enums to values
        data["report_type"] = self.report_type.value
        data["status"] = self.status.value
        # Convert dates/datetimes
        data["filing_date"] = self.filing_date.isoformat()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        if self.filed_at:
            data["filed_at"] = self.filed_at.isoformat()
        # Handle nested objects
        return json.dumps(data, default=str, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> BaseReport:
        """Deserialize report from JSON."""
        data = json.loads(json_str)
        # This is a simplified version - real implementation would need proper reconstruction
        raise NotImplementedError("Use specific report class from_json")


@dataclass
class SARReport(BaseReport):
    """Suspicious Activity Report (FinCEN SAR)."""
    report_type: ReportType = ReportType.SAR

    # Subject information
    subject: Party | None = None
    subject_account_numbers: list[str] = field(default_factory=list)

    # Suspicious activity details
    activity_categories: list[SuspiciousActivityCategory] = field(default_factory=list)
    activity_start_date: date | None = None
    activity_end_date: date | None = None
    total_suspicious_amount: Decimal = Decimal("0")
    transaction_count: int = 0

    # Narrative (required for SAR)
    narrative: str = ""
    narrative_attachment_path: str | None = None

    # Law enforcement
    law_enforcement_contacted: bool = False
    law_enforcement_agency: str | None = None
    law_enforcement_contact_date: date | None = None
    law_enforcement_case_number: str | None = None

    # Supporting transactions
    transactions: list[Transaction] = field(default_factory=list)

    # Filing institution contact
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None

    def __post_init__(self):
        if isinstance(self.total_suspicious_amount, (int, float, str)):
            self.total_suspicious_amount = Decimal(str(self.total_suspicious_amount)).quantize(Decimal("0.01"))

    def validate(self) -> list[str]:
        """Validate SAR report per FinCEN requirements."""
        errors = []

        if not self.filing_institution:
            errors.append("Filing institution is required")
        elif not self.filing_institution.rssd_id:
            errors.append("Filing institution RSSD ID is required")

        if not self.subject:
            errors.append("Subject (suspect) information is required")
        else:
            if not self.subject.name:
                errors.append("Subject name is required")
            if not self.subject.ssn_tin and not self.subject.date_of_birth:
                errors.append("Subject SSN/TIN or date of birth is required")

        if not self.activity_categories:
            errors.append("At least one suspicious activity category is required")

        if not self.activity_start_date:
            errors.append("Activity start date is required")

        if self.total_suspicious_amount <= 0:
            errors.append("Total suspicious amount must be greater than zero")

        if not self.narrative or len(self.narrative.strip()) < 50:
            errors.append("Narrative is required and must be at least 50 characters")

        if len(self.narrative) > 16000:
            errors.append("Narrative exceeds maximum length of 16,000 characters")

        if not self.contact_name:
            errors.append("Contact name is required")

        if not self.contact_phone:
            errors.append("Contact phone is required")

        # Validate transactions
        for i, txn in enumerate(self.transactions):
            if txn.amount <= 0:
                errors.append(f"Transaction {i}: amount must be positive")
            if not txn.transaction_date:
                errors.append(f"Transaction {i}: date is required")

        return errors

    def to_fincen_format(self) -> dict[str, Any]:
        """Convert to FinCEN SAR XML/JSON format."""
        data = {
            "report_type": "SAR",
            "report_id": self.report_id,
            "filing_date": self.filing_date.isoformat(),
            "filing_institution": {
                "name": self.filing_institution.name if self.filing_institution else None,
                "rssd_id": self.filing_institution.rssd_id if self.filing_institution else None,
                "lei": self.filing_institution.lei if self.filing_institution else None,
            },
            "subject": self.subject.to_fincen_dict("subject") if self.subject else {},
            "subject_accounts": self.subject_account_numbers,
            "activity_categories": [cat.value for cat in self.activity_categories],
            "activity_start_date": self.activity_start_date.isoformat() if self.activity_start_date else None,
            "activity_end_date": self.activity_end_date.isoformat() if self.activity_end_date else None,
            "total_suspicious_amount": str(self.total_suspicious_amount),
            "transaction_count": self.transaction_count or len(self.transactions),
            "narrative": self.narrative,
            "law_enforcement_contacted": self.law_enforcement_contacted,
            "law_enforcement_agency": self.law_enforcement_agency,
            "law_enforcement_contact_date": self.law_enforcement_contact_date.isoformat() if self.law_enforcement_contact_date else None,
            "law_enforcement_case_number": self.law_enforcement_case_number,
            "contact": {
                "name": self.contact_name,
                "phone": self.contact_phone,
                "email": self.contact_email,
            },
            "transactions": [
                {
                    "transaction_id": txn.transaction_id,
                    "date": txn.transaction_date.isoformat(),
                    "type": txn.transaction_type.value,
                    "amount": str(txn.amount),
                    "currency": txn.currency,
                    "account_number": txn.account_number,
                    "description": txn.description,
                    "channel": txn.channel,
                    "counterparty": txn.counterparty.to_fincen_dict("counterparty") if txn.counterparty else None,
                }
                for txn in self.transactions
            ],
            "status": self.status.value,
            "prior_report_id": self.prior_report_id,
        }
        return {k: v for k, v in data.items() if v is not None and v != [] and v != {}}


@dataclass
class CTRReport(BaseReport):
    """Currency Transaction Report (FinCEN CTR - Form 112)."""
    report_type: ReportType = ReportType.CTR

    # Transaction aggregation
    transaction_date: date | None = None
    total_cash_in: Decimal = Decimal("0")
    total_cash_out: Decimal = Decimal("0")
    transaction_count: int = 0

    # Person conducting transaction
    conductor: Party | None = None

    # Person on whose behalf transaction is conducted
    beneficiary: Party | None = None

    # Account(s) involved
    account_numbers: list[str] = field(default_factory=list)

    # Individual transactions
    transactions: list[Transaction] = field(default_factory=list)

    # Multiple persons indicator
    multiple_persons: bool = False
    additional_conductors: list[Party] = field(default_factory=list)

    # Exempt person indicator
    exempt_person: bool = False
    exempt_person_type: str | None = None  # bank, government, listed_entity, etc.

    def __post_init__(self):
        if isinstance(self.total_cash_in, (int, float, str)):
            self.total_cash_in = Decimal(str(self.total_cash_in)).quantize(Decimal("0.01"))
        if isinstance(self.total_cash_out, (int, float, str)):
            self.total_cash_out = Decimal(str(self.total_cash_out)).quantize(Decimal("0.01"))

    @property
    def total_cash_amount(self) -> Decimal:
        """Total cash amount (in + out)."""
        return self.total_cash_in + self.total_cash_out

    def validate(self) -> list[str]:
        """Validate CTR report per FinCEN requirements."""
        errors = []

        if not self.filing_institution:
            errors.append("Filing institution is required")
        elif not self.filing_institution.rssd_id:
            errors.append("Filing institution RSSD ID is required")

        if not self.transaction_date:
            errors.append("Transaction date is required")

        # CTR threshold check ($10,000)
        if self.total_cash_amount < Decimal("10000"):
            errors.append(f"Total cash amount ${self.total_cash_amount} below CTR threshold of $10,000")

        if not self.conductor:
            errors.append("Conductor (person conducting transaction) is required")
        else:
            if not self.conductor.name:
                errors.append("Conductor name is required")
            if not self.conductor.ssn_tin and not self.conductor.date_of_birth:
                errors.append("Conductor SSN/TIN or date of birth is required")

        if self.multiple_persons and not self.additional_conductors:
            errors.append("Multiple persons indicated but no additional conductors provided")

        if not self.account_numbers:
            errors.append("At least one account number is required")

        if not self.transactions:
            errors.append("At least one transaction is required")

        # Validate transactions sum matches totals
        calc_cash_in = sum(
            txn.amount for txn in self.transactions
            if txn.transaction_type in (TransactionType.DEPOSIT, TransactionType.EXCHANGE, TransactionType.TRANSFER_IN, TransactionType.PAYMENT, TransactionType.PURCHASE)
        )
        calc_cash_out = sum(
            txn.amount for txn in self.transactions
            if txn.transaction_type in (TransactionType.WITHDRAWAL, TransactionType