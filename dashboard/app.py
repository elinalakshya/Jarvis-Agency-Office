import os
import json
import sys
from pathlib import Path
from flask import Flask, render_template_string

# Add project root to path to import finance.ledger
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from finance.ledger import get_total_revenue, get_recent_transactions

app = Flask(__name__)

# Path to avengers config file
AVENGERS_CONFIG_PATH = PROJECT_ROOT / "config" / "avengers.json"

# Inline HTML template with embedded CSS for a clean, responsive dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Avengers Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: #f4f6f9;
            color: #1a1a2e;
            line-height: 1.6;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }
        header {
            text-align: center;
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 2px solid #e0e4eb;
        }
        header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1a1a2e;
            letter-spacing: -0.5px;
        }
        header p {
            color: #6b7280;
            margin-top: 0.5rem;
            font-size: 1.1rem;
        }
        .section {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .section-title::before {
            content: "";
            width: 4px;
            height: 24px;
            background: #3b82f6;
            border-radius: 2px;
        }
        /* Finance Section */
        .finance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .finance-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .finance-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .finance-card.revenue {
            border-left: 4px solid #10b981;
        }
        .finance-card.transactions {
            border-left: 4px solid #3b82f6;
        }
        .finance-label {
            font-size: 0.875rem;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }
        .finance-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e;
        }
        .finance-value.revenue {
            color: #10b981;
        }
        .transactions-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .transactions-table th,
        .transactions-table td {
            padding: 0.875rem 1rem;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        .transactions-table th {
            background: #f8fafc;
            font-weight: 600;
            color: #374151;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .transactions-table tr:last-child td {
            border-bottom: none;
        }
        .transactions-table tr:hover td {
            background: #f8fafc;
        }
        .amount-positive { color: #10b981; font-weight: 600; }
        .amount-negative { color: #ef4444; font-weight: 600; }
        /* Avengers Grid */
        .avengers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 1.25rem;
        }
        .avenger-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 1.25rem;
            text-align: center;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }
        .avenger-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
        }
        .avenger-card.active::before {
            background: #10b981;
        }
        .avenger-card.inactive::before {
            background: #9ca3af;
        }
        .avenger-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
            border-color: #d1d5db;
        }
        .avenger-name {
            font-weight: 600;
            font-size: 1rem;
            color: #1a1a2e;
            margin-bottom: 0.5rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .avenger-status {
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
            font-size: 0.8rem;
            font-weight: 500;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
        }
        .avenger-status.active {
            background: #d1fae5;
            color: #065f46;
        }
        .avenger-status.inactive {
            background: #f3f4f6;
            color: #4b5563;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .status-dot.active { background: #10b981; }
        .status-dot.inactive { background: #9ca3af; }
        /* Responsive */
        @media (max-width: 640px) {
            .container { padding: 1.5rem 1rem; }
            header h1 { font-size: 2rem; }
            .avengers-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 480px) {
            .avengers-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Avengers Operations Dashboard</h1>
            <p>Real-time team status & financial overview</p>
        </header>

        <!-- Finance Section -->
        <section class="section" aria-labelledby="finance-title">
            <h2 class="section-title" id="finance-title">Financial Overview</h2>
            <div class="finance-grid">
                <div class="finance-card revenue">
                    <div class="finance-label">Total Revenue</div>
                    <div class="finance-value revenue">${{ "{:,.2f}".format(total_revenue) }}</div>
                </div>
                <div class="finance-card transactions">
                    <div class="finance-label">Recent Transactions</div>
                    <div class="finance-value">{{ recent_transactions|length }}</div>
                </div>
            </div>
            <table class="transactions-table" role="table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Category</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {% for txn in recent_transactions %}
                    <tr>
                        <td>{{ txn.date }}</td>
                        <td>{{ txn.description }}</td>
                        <td>{{ txn.category }}</td>
                        <td class="{{ 'amount-positive' if txn.amount >= 0 else 'amount-negative' }}">
                            {{ "{:,.2f}".format(txn.amount) }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>

        <!-- Avengers Section -->
        <section class="section" aria-labelledby="avengers-title">
            <h2 class="section-title" id="avengers-title">Team Roster ({{ avengers|length }} Members)</h2>
            <div class="avengers-grid" role="list">
                {% for avenger in avengers %}
                <article class="avenger-card {{ 'active' if avenger.active else 'inactive' }}" role="listitem">
                    <div class="avenger-name">{{ avenger.name }}</div>
                    <div class="avenger-status {{ 'active' if avenger.active else 'inactive' }}">
                        <span class="status-dot {{ 'active' if avenger.active else 'inactive' }}"></span>
                        {{ 'Active' if avenger.active else 'Inactive' }}
                    </div>
                </article>
                {% endfor %}
            </div>
        </section>
    </div>
</body>
</html>
"""


def load_avengers():
    """Load avengers data from JSON config file."""
    try:
        with open(AVENGERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Ensure we have a list of avengers with name and active fields
        avengers = data.get('avengers', [])
        # Validate each entry has required fields
        for avenger in avengers:
            avenger.setdefault('name', 'Unknown')
            avenger['active'] = (avenger.get('status', 'inactive').lower() == 'active')
        return avengers
    except (FileNotFoundError, json.JSONDecodeError) as e:
        app.logger.error(f"Failed to load avengers config: {e}")
        return []


@app.route('/')
def dashboard():
    """Render the main dashboard with avengers roster and financial data."""
    avengers = load_avengers()
    total_revenue = get_total_revenue()
    recent_transactions = get_recent_transactions(limit=5)
    
    return render_template_string(
        DASHBOARD_TEMPLATE,
        avengers=avengers,
        total_revenue=total_revenue,
        recent_transactions=recent_transactions
    )


@app.route('/health')
def health_check():
    """Health check endpoint for container orchestration."""
    return {'status': 'healthy', 'service': 'avengers-dashboard'}, 200


if __name__ == '__main__':
    # Production settings: debug=False, host=0.0.0.0 for container compatibility
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)