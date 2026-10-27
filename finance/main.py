# finance/main.py
import pandas as pd
from datetime import datetime

# Function to read financial data from a CSV file
def read_financial_data(file_path):
    try:
        data = pd.read_csv(file_path)
        return data
    except FileNotFoundError:
        print("File not found. Please check the file path.")
        return None

# Function to process financial data
def process_financial_data(data):
    if data is None:
        return None
    
    # Convert the 'date' column to datetime format
    data['date'] = pd.to_datetime(data['date'])
    
    # Calculate the moving average for the 'close' price
    data['moving_average'] = data['close'].rolling(window=5).mean()
    
    return data

# Function to save processed data to a new CSV file
def save_processed_data(data, output_path):
    if data is None:
        print("No data to save.")
        return
    
    try:
        data.to_csv(output_path, index=False)
        print(f"Data saved to {output_path}")
    except Exception as e:
        print(f"Error saving data: {e}")

# Main function to handle the workflow
def main():
    input_file_path = 'data/financial_data.csv'
    output_file_path = 'data/processed_financial_data.csv'
    
    # Read financial data
    financial_data = read_financial_data(input_file_path)
    
    # Process financial data
    processed_data = process_financial_data(financial_data)
    
    # Save processed data
    save_processed_data(processed_data, output_file_path)

if __name__ == "__main__":
    main()