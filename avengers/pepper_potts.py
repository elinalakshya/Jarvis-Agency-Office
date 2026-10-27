"""Pepper Potts module: Connects Finance ledger to Avenger registry.

This module provides the interface for logging financial transactions
for Avengers, updating both the central ledger and individual Avenger records.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from avengers.registry import AvengerRegistry
    from finance.ledger import Ledger

logger = logging.getLogger(__name__)


class PepperPottsError(Exception):
    """Base exception for Pepper Potts module errors."""
    pass


class AvengerNotFoundError(PepperPottsError):
    """Raised when an Avenger ID is not found in the registry."""
    pass


class InvalidAmountError(PepperPottsError):
    """Raised when a transaction amount is invalid."""
    pass


def _validate_amount(amount: Decimal | float | int) -> Decimal:
    """Validate and convert amount to Decimal.
    
    Args:
        amount: The transaction amount.
        
    Returns:
        Validated amount as Decimal.
        
    Raises:
        InvalidAmountError: If amount is negative or not a valid number.
    """
    try:
        decimal_amount = Decimal(str(amount))
    except (ValueError, TypeError) as e:
        raise InvalidAmountError(f"Invalid amount: {amount}") from e
    
    if decimal_amount < 0:
        raise InvalidAmountError(f"Amount cannot be negative: {decimal_amount}")
    
    return decimal_amount


def _get_registry() -> AvengerRegistry:
    """Get the Avenger registry instance.
    
    Returns:
        The singleton AvengerRegistry instance.
    """
    from avengers.registry import get_registry
    return get_registry()


def _get_ledger() -> Ledger:
    """Get the Finance ledger instance.
    
    Returns:
        The singleton Ledger instance.
    """
    from finance.ledger import get_ledger
    return get_ledger()


def log_avenger_income(
    avenger_id: str,
    amount: Decimal | float | int,
    description: str,
) -> dict:
    """Log income for an Avenger and update their YTD income.
    
    This function writes a credit entry to the finance ledger and
    increases the Avenger's income_ytd field in the registry.
    
    Args:
        avenger_id: Unique identifier for the Avenger.
        amount: Income amount (must be positive).
        description: Description of the income source.
        
    Returns:
        Dictionary with transaction details including ledger entry ID.
        
    Raises:
        AvengerNotFoundError: If avenger_id doesn't exist in registry.
        InvalidAmountError: If amount is invalid or negative.
        PepperPottsError: If ledger or registry update fails.
    """
    validated_amount = _validate_amount(amount)
    registry = _get_registry()
    ledger = _get_ledger()
    
    # Verify Avenger exists
    avenger = registry.get_avenger(avenger_id)
    if avenger is None:
        raise AvengerNotFoundError(f"Avenger not found: {avenger_id}")
    
    try:
        # Write to ledger (credit = income)
        entry_id = ledger.create_entry(
            account_id=avenger_id,
            amount=validated_amount,
            entry_type="credit",
            description=description,
            metadata={"source": "avenger_income", "avenger_name": avenger.name},
        )
        
        # Update Avenger's YTD income
        new_income_ytd = avenger.income_ytd + validated_amount
        registry.update_avenger(avenger_id, income_ytd=new_income_ytd)
        
        logger.info(
            "Logged income for %s (%s): %s - %s",
            avenger.name, avenger_id, validated_amount, description
        )
        
        return {
            "entry_id": entry_id,
            "avenger_id": avenger_id,
            "amount": validated_amount,
            "description": description,
            "new_income_ytd": new_income_ytd,
            "transaction_type": "income",
        }
        
    except Exception as e:
        logger.exception("Failed to log income for avenger %s", avenger_id)
        raise PepperPottsError(f"Failed to log income: {e}") from e


def log_avenger_cost(
    avenger_id: str,
    amount: Decimal | float | int,
    description: str,
) -> dict:
    """Log a cost/expense for an Avenger and update their YTD income.
    
    This function writes a debit entry to the finance ledger and
    decreases the Avenger's income_ytd field in the registry (since
    costs reduce net income).
    
    Args:
        avenger_id: Unique identifier for the Avenger.
        amount: Cost amount (must be positive).
        description: Description of the expense.
        
    Returns:
        Dictionary with transaction details including ledger entry ID.
        
    Raises:
        AvengerNotFoundError: If avenger_id doesn't exist in registry.
        InvalidAmountError: If amount is invalid or negative.
        PepperPottsError: If ledger or registry update fails.
    """
    validated_amount = _validate_amount(amount)
    registry = _get_registry()
    ledger = _get_ledger()
    
    # Verify Avenger exists
    avenger = registry.get_avenger(avenger_id)
    if avenger is None:
        raise AvengerNotFoundError(f"Avenger not found: {avenger_id}")
    
    try:
        # Write to ledger (debit = cost/expense)
        entry_id = ledger.create_entry(
            account_id=avenger_id,
            amount=validated_amount,
            entry_type="debit",
            description=description,
            metadata={"source": "avenger_cost", "avenger_name": avenger.name},
        )
        
        # Update Avenger's YTD income (costs reduce net income)
        new_income_ytd = avenger.income_ytd - validated_amount
        registry.update_avenger(avenger_id, income_ytd=new_income_ytd)
        
        logger.info(
            "Logged cost for %s (%s): %s - %s",
            avenger.name, avenger_id, validated_amount, description
        )
        
        return {
            "entry_id": entry_id,
            "avenger_id": avenger_id,
            "amount": validated_amount,
            "description": description,
            "new_income_ytd": new_income_ytd,
            "transaction_type": "cost",
        }
        
    except Exception as e:
        logger.exception("Failed to log cost for avenger %s", avenger_id)
        raise PepperPottsError(f"Failed to log cost: {e}") from e


def get_avenger_financial_summary(avenger_id: str) -> dict:
    """Get a financial summary for an Avenger.
    
    Args:
        avenger_id: Unique identifier for the Avenger.
        
    Returns:
        Dictionary with current income_ytd and recent ledger entries.
        
    Raises:
        AvengerNotFoundError: If avenger_id doesn't exist in registry.
    """
    registry = _get_registry()
    ledger = _get_ledger()
    
    avenger = registry.get_avenger(avenger_id)
    if avenger is None:
        raise AvengerNotFoundError(f"Avenger not found: {avenger_id}")
    
    entries = ledger.get_entries_for_account(avenger_id, limit=50)
    
    total_income = sum(
        e.amount for e in entries if e.entry_type == "credit"
    )
    total_costs = sum(
        e.amount for e in entries if e.entry_type == "debit"
    )
    
    return {
        "avenger_id": avenger_id,
        "avenger_name": avenger.name,
        "income_ytd": avenger.income_ytd,
        "ledger_income": total_income,
        "ledger_costs": total_costs,
        "ledger_net": total_income - total_costs,
        "recent_entries": [
            {
                "entry_id": e.entry_id,
                "date": e.timestamp.isoformat(),
                "type": e.entry_type,
                "amount": e.amount,
                "description": e.description,
            }
            for e in entries[:10]
        ],
    }