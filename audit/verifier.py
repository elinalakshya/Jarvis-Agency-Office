import hashlib
import json

class TransactionVerifier:
    """
    Class to verify transactions against a bill.
    """

    def __init__(self, bill):
        """
        Initialize the verifier with a bill.

        Args:
        bill (dict): A dictionary representing the bill containing transactions.
        """
        self.bill = bill
        self.transactions = bill.get('transactions', [])

    def verify_transactions(self):
        """
        Verify each transaction in the bill.

        Returns:
        bool: True if all transactions are valid, False otherwise.
        """
        for transaction in self.transactions:
            if not self._is_valid_transaction(transaction):
                return False
        return True

    def _is_valid_transaction(self, transaction):
        """
        Check if a single transaction is valid.

        Args:
        transaction (dict): A dictionary representing a transaction.

        Returns:
        bool: True if the transaction is valid, False otherwise.
        """
        if not self._has_required_fields(transaction):
            return False
        if not self._hash_matches(transaction):
            return False
        return True

    def _has_required_fields(self, transaction):
        """
        Check if the transaction dictionary has the required fields.

        Args:
        transaction (dict): A dictionary representing a transaction.

        Returns:
        bool: True if the required fields are present, False otherwise.
        """
        required_fields = {'id', 'amount', 'description', 'timestamp', 'hash'}
        return required_fields.issubset(transaction.keys())

    def _hash_matches(self, transaction):
        """
        Check if the hash of the transaction data matches the stored hash.

        Args:
        transaction (dict): A dictionary representing a transaction.

        Returns:
        bool: True if the hashes match, False otherwise.
        """
        stored_hash = transaction.get('hash')
        data_to_hash = json.dumps(transaction, sort_keys=True).encode('utf-8')
        calculated_hash = hashlib.sha256(data_to_hash).hexdigest()
        return calculated_hash == stored_hash

# Example usage:
if __name__ == "__main__":
    bill = {
        "id": "12345",
        "date": "2023-10-01",
        "transactions": [
            {
                "id": "trans1",
                "amount": 100.00,
                "description": "Groceries",
                "timestamp": "2023-10-01T12:34:56Z",
                "hash": "abc123def456"
            },
            {
                "id": "trans2",
                "amount": 50.00,
                "description": "Gas",
                "timestamp": "2023-10-01T18:34:56Z",
                "hash": "def456abc123"
            }
        ]
    }

    verifier = TransactionVerifier(bill)
    is_valid = verifier.verify_transactions()
    print(f"All transactions valid: {is_valid}")