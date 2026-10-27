import datetime

def check_gst_readiness():
    """
    Check GST readiness by ensuring GST is not expired.
    
    Returns:
        bool: True if GST is ready, False otherwise.
    """
    current_date = datetime.datetime.now().date()
    gst_expiry_date = datetime.date(2023, 6, 30)  # Example expiry date
    
    if current_date <= gst_expiry_date:
        return True
    else:
        return False

def check_tds_readiness():
    """
    Check TDS readiness by ensuring TDS is not expired.
    
    Returns:
        bool: True if TDS is ready, False otherwise.
    """
    current_date = datetime.datetime.now().date()
    tds_expiry_date = datetime.date(2023, 9, 30)  # Example expiry date
    
    if current_date <= tds_expiry_date:
        return True
    else:
        return False

def check_income_tax_readiness():
    """
    Check Income Tax readiness by ensuring Income Tax is not expired.
    
    Returns:
        bool: True if Income Tax is ready, False otherwise.
    """
    current_date = datetime.datetime.now().date()
    income_tax_expiry_date = datetime.date(2024, 3, 31)  # Example expiry date
    
    if current_date <= income_tax_expiry_date:
        return True
    else:
        return False

# Example usage
if __name__ == "__main__":
    print("GST Readiness:", check_gst_readiness())
    print("TDS Readiness:", check_tds_readiness())
    print("Income Tax Readiness:", check_income_tax_readiness())