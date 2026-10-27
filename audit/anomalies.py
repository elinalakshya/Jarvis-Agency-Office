import pandas as pd
import numpy as np

def load_data(file_path):
    """
    Load transaction data from a CSV file.
    
    :param file_path: str, path to the CSV file
    :return: pandas DataFrame
    """
    return pd.read_csv(file_path)

def detect_anomalies(data):
    """
    Detect anomalies in the transaction data based on predefined rules.
    
    :param data: pandas DataFrame containing transaction data
    :return: pandas DataFrame with anomalies flagged
    """
    # Rule 1: Transactions with amount greater than $1000
    data['anomaly_rule1'] = data['amount'] > 1000
    
    # Rule 2: Transactions with negative amounts
    data['anomaly_rule2'] = data['amount'] < 0
    
    # Rule 3: Transactions with unusually high frequency
    # Assuming 'timestamp' is in the format 'YYYY-MM-DD HH:MM:SS'
    data['transaction_date'] = pd.to_datetime(data['timestamp']).dt.date
    daily_transactions = data['transaction_date'].value_counts()
    data['daily_avg_transactions'] = data['transaction_date'].map(daily_transactions / len(daily_transactions))
    data['anomaly_rule3'] = data['daily_avg_transactions'] < data['daily_avg_transactions'].quantile(0.05)
    
    # Flagging any transaction with at least one anomaly
    data['anomaly'] = data[['anomaly_rule1', 'anomaly_rule2', 'anomaly_rule3']].any(axis=1)
    
    return data

def save_anomalies(data, output_path):
    """
    Save the flagged anomalies to a CSV file.
    
    :param data: pandas DataFrame with anomalies flagged
    :param output_path: str, path to the output CSV file
    """
    data.to_csv(output_path, index=False)

def main(input_file, output_file):
    """
    Main function to load data, detect anomalies, and save the results.
    
    :param input_file: str, path to the input CSV file
    :param output_file: str, path to the output CSV file
    """
    data = load_data(input_file)
    anomalies = detect_anomalies(data)
    save_anomalies(anomalies, output_file)

if __name__ == "__main__":
    input_csv = 'path/to/input/transactions.csv'
    output_csv = 'path/to/output/anomalies.csv'
    main(input_csv, output_csv)