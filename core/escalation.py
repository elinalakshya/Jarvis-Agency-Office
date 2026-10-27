"""
core/escalation.py — Rules for when JARVIS should ask the user vs act autonomously.
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Escalation:
    """Handles the escalation logic based on thresholds."""

    def __init__(self, threshold: int = 100):
        self.threshold = threshold

    def should_escalate(self, current_value: int) -> bool:
        """Returns True if the current value exceeds the threshold."""
        if current_value > self.threshold:
            logging.info(f"Escalation needed: {current_value} > {self.threshold}")
            return True
        logging.info(f"No escalation: {current_value} <= {self.threshold}")
        return False


if __name__ == "__main__":
    handler = Escalation(threshold=100)
    print(f"Escalation required: {handler.should_escalate(150)}")
    print(f"Escalation required: {handler.should_escalate(50)}")