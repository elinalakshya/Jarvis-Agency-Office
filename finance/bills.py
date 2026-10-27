# finance/bills.py

class BillVerifier:
    """
    The BillVerifier class is responsible for verifying the validity of bills.
    
    Args:
        collector (Collector): An instance of the Collector class used for collecting data.
    """
    
    def __init__(self, collector):
        """
        Initializes the BillVerifier with a collector instance.
        
        Args:
            collector (Collector): An instance of the Collector class used for collecting data.
        """
        self.collector = collector
    
    def verify_bill(self, bill_id):
        """
        Verifies the validity of a bill.
        
        Args:
            bill_id (str): The ID of the bill to verify.
        
        Returns:
            bool: True if the bill is valid, False otherwise.
        """
        # Example verification logic
        data = self.collector.get_bill_data(bill_id)
        if data and data['status'] == 'paid':
            return True
        return False

class Collector:
    """
    The Collector class is responsible for collecting data.
    """
    
    def get_bill_data(self, bill_id):
        """
        Retrieves data for a bill.
        
        Args:
            bill_id (str): The ID of the bill.
        
        Returns:
            dict: The data for the bill if found, None otherwise.
        """
        # Example data retrieval logic
        bills = {
            '12345': {'status': 'paid'},
            '67890': {'status': 'pending'}
        }
        return bills.get(bill_id)