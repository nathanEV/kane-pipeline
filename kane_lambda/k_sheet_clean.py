import pytz
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateutil import parser as date_parser
import os
import re
# Import feature toggle
from kane_lambda.config import ENABLE_K_SHEET_CLEAN

# === CONFIG ===
CREDS_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "service_account.json"))
SPREADSHEET_ID = "11hRH6mnlTGO1qIQUsqkSZawigy1LQlzBPYnJNbpb_RQ"
INPUT_SHEET_1 = "headscanner"
INPUT_SHEET_2 = "prioritizer"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def parse_date_safe(date_str):
    try:
        if not date_str or not date_str.strip():
            return None
            
        # Try to handle Excel/Google Sheets date serial numbers
        if re.match(r'^\d{5}$', str(date_str).strip()):
            try:
                # Convert Excel/Google Sheets date serial to datetime
                # Excel dates start from December 30, 1899
                excel_epoch = datetime(1899, 12, 30, tzinfo=pytz.UTC)
                days_since_epoch = int(date_str)
                dt = excel_epoch + timedelta(days=days_since_epoch)
                print(f"✅ Converted date serial {date_str} to {dt}")
                return dt
            except Exception as e:
                print(f"⚠️ Failed to convert date serial: '{date_str}' → {e}")
        
        # Regular date parsing
        dt = date_parser.parse(date_str)
        return dt.astimezone(pytz.UTC) if dt.tzinfo else dt.replace(tzinfo=pytz.UTC)
    except Exception as e:
        print(f"⚠️ Failed to parse date: '{date_str}' → {e}")
        return None

def load_sheet(service, sheet_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A1:Z").execute()
    values = result.get("values", [])
    if not values:
        return [], []
    headers = values[0]
    rows = [dict(zip(headers, row)) for row in values[1:]]
    return headers, rows

def write_sheet(service, sheet_name, headers, rows):
    # Clear existing data
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1:Z",
        body={}
    ).execute()

    # Prepare new data
    new_values = [headers]
    for i, row in enumerate(rows, start=1):
        row_data = []
        for h in headers:
            if h == "story_id":
                row_data.append(str(i))  # Write as string to avoid ' being added
            else:
                row_data.append(row.get(h, ""))
        new_values.append(row_data)

    # Write cleaned values
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": new_values}
    ).execute()
    print(f"✅ Cleaned & updated '{sheet_name}' with {len(rows)} valid rows.")

def should_keep(row):
    pub_date = parse_date_safe(row.get("publication_date", ""))
    # Debug print for dates
    if pub_date:
        print(f"📅 Story ID: {row.get('story_id', 'unknown')}, Date: {pub_date}, Keeping: {pub_date >= datetime.now(pytz.UTC) - timedelta(days=7)}")
    
    if not pub_date or pub_date < datetime.now(pytz.UTC) - timedelta(days=7):
        return False
    
    # Check for significance score with more flexible parsing
    score_str = row.get("significance_score", "0")
    if not score_str or score_str.strip() == "":
        score_str = "0"
    try:
        score = int(score_str)
    except (ValueError, TypeError):
        try:
            score = float(score_str)
        except (ValueError, TypeError):
            score = 0
    
    return score >= 3

def clean_sheets():
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)

    # Load both sheets
    headers_1, rows_1 = load_sheet(service, INPUT_SHEET_1)
    headers_2, rows_2 = load_sheet(service, INPUT_SHEET_2)

    # Filter valid rows from Sheet2
    valid_rows_2 = []
    valid_story_ids = set()
    for row in rows_2:
        story_id = row.get("story_id", "").strip()
        if should_keep(row):
            valid_rows_2.append(row)
            valid_story_ids.add(story_id)

    # Filter and de-duplicate Sheet1
    seen_ids = set()
    valid_rows_1 = []
    for row in rows_1:
        story_id = row.get("story_id", "").strip()
        if story_id in valid_story_ids and story_id not in seen_ids:
            seen_ids.add(story_id)
            valid_rows_1.append(row)

    # Normalize story_id numbers for both sheets consistently
    id_map = {}
    for i, row in enumerate(valid_rows_2, start=1):
        old_id = row["story_id"]
        new_id = str(i)
        id_map[old_id] = new_id
        row["story_id"] = new_id

    for row in valid_rows_1:
        old_id = row["story_id"]
        if old_id in id_map:
            row["story_id"] = id_map[old_id]

    # Write cleaned and re-IDed sheets
    write_sheet(service, INPUT_SHEET_2, headers_2, valid_rows_2)
    write_sheet(service, INPUT_SHEET_1, headers_1, valid_rows_1)
    print("✅ Cleaned & normalized both sheets without duplicates.")

if __name__ == "__main__":
    if not ENABLE_K_SHEET_CLEAN:
        print("⚠️ k_sheet_clean disabled by config")
    else:
        clean_sheets()