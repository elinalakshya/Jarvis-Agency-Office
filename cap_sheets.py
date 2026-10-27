import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import sys
from datetime import datetime

# 1. Authenticate
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("/opt/agency/youtube-automation-agent-master/config/google_sheets_key.json", scope)
client = gspread.authorize(creds)

SHEET_ID = "15t2x8TAnvw4KgSVdpViCZmFQ0oEBZk2DDD7AOS0dwcE"
API_URL = "http://localhost:3456/generate"
API_KEY = "jarvis-secret-key-2026"

def trigger_cap(topic, video_type):
    print(f"Found {video_type} topic: {topic}")
    headers = {"x-api-key": API_KEY}
    data = {"topic": topic, "length": "long" if video_type == "LONG" else "short"}
    
    try:
        response = requests.post(API_URL, json=data, headers=headers)
        if response.status_code == 202:
            print("Successfully triggered CAP!")
            return True
        else:
            print(f"Failed to trigger CAP: {response.text}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

# --- CHECK WEEKLY LONG VIDEO (gid=0) ---
print("Checking Weekly Long Video sheet...")
long_sheet = client.open_by_key(SHEET_ID).get_worksheet(0) # 0 is the first tab (gid=0)
long_rows = long_sheet.get_all_values()

for i, row in enumerate(long_rows[1:], start=2): # Skip header
    if len(row) >= 11:
        date_val = row[4].strip()  # Column E
        topic = row[7].strip()     # Column H
        status = row[10].strip()   # Column K
        
        if status == "Pending" and topic:
            if trigger_cap(topic, "LONG"):
                long_sheet.update_cell(i, 11, "Generated") # Update Column K
                sys.exit(0) # Stop after one job to avoid overloading

# --- CHECK DAILY SHORTS (gid=877804106) ---
print("Checking Daily Shorts sheet...")
try:
    short_sheet = client.open_by_key(SHEET_ID).worksheet("Bhagavad_Gita_700_Day_YouTube_Shorts_Scripts")
    short_rows = short_sheet.get_all_values()

    for i, row in enumerate(short_rows[1:], start=2):
        if len(row) >= 7:
            date_val = row[0].strip() # Column A
            topic = row[5].strip()    # Column F (Sanskrit Sloka)
            status = row[6].strip()   # Column G
            
            if status == "Pending" and topic:
                if trigger_cap(topic, "SHORT"):
                    short_sheet.update_cell(i, 7, "Generated") # Update Column G
                    sys.exit(0)
except Exception as e:
    print(f"Could not read Shorts sheet: {e}")

print("No pending topics found for today.")