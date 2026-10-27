# finance/analytics.py
import datetime

class MarketPricing:
    def __init__(self, symbol, price, currency):
        self.symbol = symbol
        self.price = price
        self.currency = currency

    def get_price(self):
        return self.price

    def update_price(self, new_price):
        self.price = new_price

class TaxCalculator:
    def calculate_tax(self, amount, tax_rate):
        return amount * tax_rate

class GrowthTracker:
    def __init__(self, initial_value):
        self.initial_value = initial_value
        self.history = [(datetime.datetime.now(), initial_value)]

    def record_growth(self, new_value):
        current_time = datetime.datetime.now()
        self.history.append((current_time, new_value))

    def get_growth_history(self):
        return self.history

class CAReport:
    def __init__(self, initial_investment, annual_growth_rate, years):
        self.initial_investment = initial_investment
        self.annual_growth_rate = annual_growth_rate
        self.years = years

    def calculate_compound_growth(self):
        future_value = self.initial_investment * (1 + self.annual_growth_rate) ** self.years
        return future_value

# Example usage
if __name__ == "__main__":
    # Market Pricing
    apple = MarketPricing("AAPL", 150.75, "USD")
    print(f"Current price of {apple.symbol}: {apple.get_price()}")
    apple.update_price(155.00)
    print(f"Updated price of {apple.symbol}: {apple.get_price()}")

    # Tax Calculator
    tax_calc = TaxCalculator()
    taxable_amount = 5000
    tax_rate = 0.15
    tax_amount = tax_calc.calculate_tax(taxable_amount, tax_rate)
    print(f"Tax amount for {taxable_amount} at {tax_rate * 100}% rate: {tax_amount}")

    # Growth Tracker
    growth_tracker = GrowthTracker(1000)
    growth_tracker.record_growth(1200)
    growth_tracker.record_growth(1350)
    print("Growth History:")
    for timestamp, value in growth_tracker.get_growth_history():
        print(f"{timestamp}: {value}")

    # CA Report
    ca_report = CAReport(10000, 0.05, 5)
    future_value = ca_report.calculate_compound_growth()
    print(f"Future value of initial investment after 5 years: {future_value}")