import schedule
import time
from datetime import datetime, timedelta

def run_audit_engine():
    """
    Function to execute the audit engine.
    This function will be scheduled to run every 15 days.
    """
    # Placeholder for audit engine logic
    print("Audit engine running at:", datetime.now())

# Schedule the audit engine to run every 15 days
schedule.every(15).days.do(run_audit_engine)

# Keep the script running (only when executed directly, not on import)
if __name__ == "__main__":
    print("Audit scheduler started. Will run every 15 days.")
    while True:
        schedule.run_pending()
        time.sleep(1)