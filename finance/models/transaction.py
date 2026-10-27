from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TransactionType(str, Enum):
    """Enumeration of supported transaction types."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"
    ADJUSTMENT = "adjustment"


class TransactionStatus(str, Enum):
    """Enumeration of transaction lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


class AccountType(str, Enum):
    """Enumeration of account types."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"
    INVESTMENT = "investment"
    LOAN = "loan"
    CASH = "cash"


class AccountStatus(str, Enum):
    """Enumeration of account statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    FROZEN = "frozen"
    CLOSED = "closed"
    PENDING_VERIFICATION = "pending_verification"


class Currency(str, Enum):
    """Supported currencies (ISO 4217 subset)."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNY = "CNY"


def _validate_decimal_precision(value: Decimal, max_decimal_places: int = 2) -> Decimal:
    """Validate and quantize decimal to specified precision."""
    if value.is_nan() or value.is_infinite():
        raise ValueError("Amount cannot be NaN or infinite")
    # Quantize to prevent floating point issues
    quantize_exp = Decimal(f"0.{'0' * max_decimal_places}1")
    return value.quantize(quantize_exp)


class Account(BaseModel):
    """
    Represents a financial account with balance tracking.

    Invariants:
    - Account ID is immutable after creation
    - Balance cannot go negative for non-credit accounts without overdraft
    - Currency is fixed per account
    """

    id: str = Field(default_factory=lambda: f"acc_{uuid.uuid4().hex[:12]}")
    name: str = Field(min_length=1, max_length=255)
    account_type: AccountType
    status: AccountStatus = AccountStatus.ACTIVE
    currency: Currency = Currency.USD
    balance: Decimal = Field(default=Decimal("0"), ge=Decimal("-999999999.99"))
    available_balance: Decimal = Field(default=Decimal("0"), ge=Decimal("-999999999.99"))
    overdraft_limit: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    interest_rate: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "arbitrary_types_allowed": False,
    }

    @field_validator("balance", "available_balance", "overdraft_limit", "interest_rate", mode="before")
    @classmethod
    def _parse_decimal(cls, v: str | Decimal | float | int) -> Decimal:
        """Parse and validate decimal values."""
        if isinstance(v, Decimal):
            return _validate_decimal_precision(v)
        try:
            return _validate_decimal_precision(Decimal(str(v)))
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid decimal value: {v}") from e

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        """Validate account name."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Account name cannot be empty or whitespace")
        return stripped

    @model_validator(mode="after")
    def _validate_balances(self) -> Account:
        """Ensure available balance doesn't exceed actual balance + overdraft."""
        max_available = self.balance + self.overdraft_limit
        if self.available_balance > max_available:
            raise ValueError(
                f"Available balance ({self.available_balance}) cannot exceed "
                f"balance + overdraft limit ({max_available})"
            )
        return self

    @model_validator(mode="after")
    def _validate_closed_account(self) -> Account:
        """Validate closed account constraints."""
        if self.status == AccountStatus.CLOSED:
            if self.closed_at is None:
                self.closed_at = datetime.utcnow()
            if self.balance != Decimal("0"):
                raise ValueError("Cannot close account with non-zero balance")
        return self

    def can_withdraw(self, amount: Decimal) -> bool:
        """Check if withdrawal is possible given current balance and overdraft."""
        return (self.available_balance - amount) >= -self.overdraft_limit

    def apply_transaction(self, amount: Decimal, is_debit: bool) -> None:
        """Apply a transaction amount to the account balance."""
        if is_debit:
            if not self.can_withdraw(amount):
                raise ValueError("Insufficient funds")
            self.balance -= amount
            self.available_balance -= amount
        else:
            self.balance += amount
            self.available_balance += amount
        self.updated_at = datetime.utcnow()


class Transaction(BaseModel):
    """
    Represents a financial transaction between accounts.

    Invariants:
    - Transaction ID is immutable
    - Amount must be positive
    - Source and destination cannot be the same for transfers
    - Status transitions follow valid lifecycle
    """

    id: str = Field(default_factory=lambda: f"txn_{uuid.uuid4().hex[:16]}")
    type: TransactionType
    status: TransactionStatus = TransactionStatus.PENDING
    amount: Decimal = Field(gt=Decimal("0"))
    currency: Currency = Currency.USD
    source_account_id: Optional[str] = None
    destination_account_id: Optional[str] = None
    description: str = Field(default="", max_length=1000)
    reference_id: Optional[str] = None  # External reference (e.g., invoice ID)
    idempotency_key: Optional[str] = Field(default=None, max_length=255)
    metadata: dict = Field(default_factory=dict)
    fees: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    net_amount: Optional[Decimal] = None  # Calculated: amount - fees
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_reason: Optional[str] = None

    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
    }

    @field_validator("amount", "fees", mode="before")
    @classmethod
    def _parse_decimal(cls, v: str | Decimal | float | int) -> Decimal:
        """Parse and validate decimal values."""
        if isinstance(v, Decimal):
            return _validate_decimal_precision(v)
        try:
            return _validate_decimal_precision(Decimal(str(v)))
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid decimal value: {v}") from e

    @field_validator("description")
    @classmethod
    def _validate_description(cls, v: str) -> str:
        """Validate description."""
        return v.strip()

    @model_validator(mode="after")
    def _validate_accounts(self) -> Transaction:
        """Validate account references based on transaction type."""
        if self.type == TransactionType.TRANSFER:
            if not self.source_account_id or not self.destination_account_id:
                raise ValueError("Transfer requires both source and destination accounts")
            if self.source_account_id == self.destination_account_id:
                raise ValueError("Source and destination accounts cannot be the same")
        elif self.type in (TransactionType.DEPOSIT, TransactionType.INTEREST, TransactionType.REFUND):
            if not self.destination_account_id:
                raise ValueError(f"{self.type.value} requires a destination account")
            if self.source_account_id:
                raise ValueError(f"{self.type.value} should not have a source account")
        elif self.type in (TransactionType.WITHDRAWAL, TransactionType.FEE, TransactionType.PAYMENT):
            if not self.source_account_id:
                raise ValueError(f"{self.type.value} requires a source account")
            if self.destination_account_id:
                raise ValueError(f"{self.type.value} should not have a destination account")
        elif self.type == TransactionType.ADJUSTMENT:
            if not self.source_account_id and not self.destination_account_id:
                raise ValueError("Adjustment requires at least one account")
        return self

    @model_validator(mode="after")
    def _calculate_net_amount(self) -> Transaction:
        """Calculate net amount after fees."""
        self.net_amount = self.amount - self.fees
        return self

    @model_validator(mode="after")
    def _validate_status_transitions(self) -> Transaction:
        """Validate timestamp consistency with status."""
        if self.status in (TransactionStatus.COMPLETED, TransactionStatus.FAILED, TransactionStatus.REVERSED):
            if self.completed_at is None:
                self.completed_at = datetime.utcnow()
        if self.status == TransactionStatus.PROCESSING and self.processed_at is None:
            self.processed_at = datetime.utcnow()
        return self

    def mark_processing(self) -> None:
        """Mark transaction as processing."""
        if self.status != TransactionStatus.PENDING:
            raise ValueError(f"Cannot mark as processing from {self.status}")
        self.status = TransactionStatus.PROCESSING
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_completed(self) -> None:
        """Mark transaction as completed."""
        if self.status not in (TransactionStatus.PENDING, TransactionStatus.PROCESSING):
            raise ValueError(f"Cannot mark as completed from {self.status}")
        self.status = TransactionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self, reason: str) -> None:
        """Mark transaction as failed."""
        if self.status in (TransactionStatus.COMPLETED, TransactionStatus.CANCELLED, TransactionStatus.REVERSED):
            raise ValueError(f"Cannot mark as failed from {self.status}")
        self.status = TransactionStatus.FAILED
        self.failed_reason = reason
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_cancelled(self) -> None:
        """Mark transaction as cancelled."""
        if self.status not in (TransactionStatus.PENDING, TransactionStatus.PROCESSING):
            raise ValueError(f"Cannot cancel from {self.status}")
        self.status = TransactionStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_reversed(self) -> None:
        """Mark transaction as reversed."""
        if self.status != TransactionStatus.COMPLETED:
            raise ValueError(f"Can only reverse completed transactions, current: {self.status}")
        self.status = TransactionStatus.REVERSED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class LedgerEntry(BaseModel):
    """
    Immutable ledger entry for double-entry bookkeeping.

    Each entry represents one side of a transaction (debit or credit).
    The sum of all debits must equal the sum of all credits for a transaction.
    """

    id: str = Field(default_factory=lambda: f"ledger_{uuid.uuid4().hex[:16]}")
    transaction_id: str
    account_id: str
    entry_type: str = Field(pattern="^(debit|credit)$")  # "debit" or "credit"
    amount: Decimal = Field(gt=Decimal("0"))
    currency: Currency = Currency.USD
    balance_after: Decimal  # Account balance after this entry
    description: str = Field(default="", max_length=500)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Immutable after creation
    _frozen: bool = Field(default=False, exclude=True)

    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "frozen": False,  # We'll handle freezing manually
    }

    @field_validator("amount", "balance_after", mode="before")
    @classmethod
    def _parse_decimal(cls, v: str | Decimal | float | int) -> Decimal:
        """Parse and validate decimal values."""
        if isinstance(v, Decimal):
            return _validate_decimal_precision(v)
        try:
            return _validate_decimal_precision(Decimal(str(v)))
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid decimal value: {v}") from e

    @field_validator("entry_type")
    @classmethod
    def _validate_entry_type(cls, v: str) -> str:
        """Validate entry type."""
        v = v.lower().strip()
        if v not in ("debit", "credit"):
            raise ValueError("entry_type must be 'debit' or 'credit'")
        return v

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent modification after creation (immutable ledger)."""
        if getattr(self, "_frozen", False) and name not in ("_frozen",):
            raise AttributeError("LedgerEntry is immutable after creation")
        super().__setattr__(name, value)

    def freeze(self) -> None:
        """Mark this entry as immutable."""
        self._frozen = True

    @property
    def is_debit(self) -> bool:
        """Check if this is a debit entry."""
        return self.entry_type == "debit"

    @property
    def is_credit(self) -> bool:
        """Check if this is a credit entry."""
        return self.entry_type == "credit"

    def signed_amount(self) -> Decimal:
        """Return amount with sign based on entry type (debit negative, credit positive)."""
        return -self.amount if self.is_debit else self.amount


class Ledger(BaseModel):
    """
    Collection of ledger entries for a transaction.

    Provides validation for double-entry bookkeeping principles.
    """

    transaction_id: str
    entries: list[LedgerEntry] = Field(default_factory=list, min_length=2)
    is_balanced: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "validate_assignment": True,
    }

    @model_validator(mode="after")
    def _validate_entries(self) -> Ledger:
        """Validate all entries belong to the same transaction."""
        for entry in self.entries:
            if entry.transaction_id != self.transaction_id:
                raise ValueError(
                    f"Entry {entry.id} has mismatched transaction_id: "
                    f"{entry.transaction_id} != {self.transaction_id}"
                )
        return self

    def add_entry(self, entry: LedgerEntry) -> None:
        """Add a ledger entry and freeze it."""
        if entry.transaction_id != self.transaction_id:
            raise ValueError("Entry transaction_id must match ledger")
        entry.freeze()
        self.entries.append(entry)
        self._recalculate_balance()

    def _recalculate_balance(self) -> None:
        """Recalculate if the ledger is balanced."""
        total_debits = sum(e.amount for e in self.entries if e.is_debit)
        total_credits = sum(e.amount for e in self.entries if e.is_credit)
        self.is_balanced = total_debits == total_credits

    def validate_double_entry(self) -> bool:
        """
        Validate double-entry bookkeeping: sum of debits equals sum of credits.

        Returns True if balanced, raises ValueError if not.
        """
        self._recalculate_balance()
        if not self.is_balanced:
            total_debits = sum(e.amount for e in self.entries if e.is_debit)
            total_credits = sum(e.amount for e in self.entries if e.is_credit)
            raise ValueError(
                f"Ledger not balanced: debits={total_debits}, credits={total_credits}"
            )
        return True

    def get_account_entries(self, account_id: str) -> list[LedgerEntry]:
        """Get all entries for a specific account."""
        return [e for e in self.entries if e.account_id == account_id]