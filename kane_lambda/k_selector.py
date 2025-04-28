import os
from datetime import datetime, timedelta
from collections import defaultdict
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateutil import parser as date_parser
import re
from kane_lambda.config import ENABLE_K_SELECTOR

# === CONFIG ===
CREDS_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "service_account.json"))
SPREADSHEET_ID = "11hRH6mnlTGO1qIQUsqkSZawigy1LQlzBPYnJNbpb_RQ"
INPUT_SHEET = "prioritizer"  # Prioritized stories
EXISTING_DOC_ID = "1aTV78mQpel4ihw5slFKn_iBR5fcvF1H1_boQl72GLBg"  # 🔁 Replace with your doc ID

CATEGORY_ORDER = [
    "Product_Research",
    "Capital_Corporate_Moves",
    "Infrastructure_Supply",
    "Market_Financial_Signals",
    "Policy_Geopolitics"
]

# === FUNCTIONS ===
def newsletter_already_exists(service, doc_id, title_text):
    doc = service.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])

    for element in content:
        if "paragraph" in element:
            elements = element["paragraph"].get("elements", [])
            for e in elements:
                text_run = e.get("textRun", {})
                text = text_run.get("content", "").strip()
                if text == title_text:
                    print(f"⚠️ Newsletter with title already exists: {text}")
                    return True
    return False


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

def filter_recent_stories(stories):
    now_utc = datetime.now(pytz.UTC)
    cutoff = now_utc - timedelta(days=1)
    recent_stories = []
    skipped = 0

    for s in stories:
        raw_date = s.get("publication_date", "").strip()
        pub_date = parse_date_safe(raw_date)

        if not pub_date:
            print(f"⏭️ Skipping (invalid date): '{raw_date}'")
            skipped += 1
            continue

        # Check if date is in the future - always keep future dates
        if pub_date > now_utc:
            print(f"✅ Keeping future article dated {pub_date}")
            recent_stories.append(s)
        # Otherwise apply the normal 1-day cutoff rule
        elif pub_date >= cutoff:
            recent_stories.append(s)
        else:
            print(f"⏭️ Skipping old article dated {pub_date} (cutoff {cutoff})")

    print(f"✅ Filtered {len(recent_stories)} recent stories (⏭️ Skipped {skipped})")
    return recent_stories

def load_sheet_data():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    service = build('sheets', 'v4', credentials=creds)
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{INPUT_SHEET}!A1:Z"
    ).execute()

    values = result.get('values', [])
    if not values:
        print("No data found in sheet.")
        return []

    headers = values[0]
    rows = values[1:]
    stories = [dict(zip(headers, row)) for row in rows]
    return stories

def group_by_category(stories):
    grouped = defaultdict(list)
    for story in stories:
        category = story.get("category", "Uncategorized")
        grouped[category].append(story)
    return grouped

def get_doc_end_index(service, doc_id):
    doc = service.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])
    
    # Walk through backwards to find the last non-empty element with an endIndex
    for element in reversed(content):
        if "endIndex" in element:
            return element["endIndex"] -1
    
    return 1

def insert_formatted_content(service, doc_id, grouped):
    now_str = datetime.now().strftime("%B %d, %Y")
    index = get_doc_end_index(service, doc_id)
    requests = []

    # Title
    title = f"Exponential View Special AI Daily Newsletter — {now_str}"
    requests.append({
        "insertText": {"location": {"index": index}, "text": title + "\n\n"}
    })
    requests.append({
        "updateTextStyle": {
            "range": {"startIndex": index, "endIndex": index + len(title)},
            "textStyle": {"bold": True, "fontSize": {"magnitude": 16, "unit": "PT"}},
            "fields": "bold,fontSize"
        }
    })
    index += len(title) + 2

    for category in CATEGORY_ORDER:
        stories = grouped.get(category, [])[:6]
        if not stories:
            continue

        # Insert Category Header
        requests.append({
            "insertText": {"location": {"index": index}, "text": category + "\n\n"}
        })
        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": index, "endIndex": index + len(category)},
                "textStyle": {"bold": True, "fontSize": {"magnitude": 14, "unit": "PT"}},
                "fields": "bold,fontSize"
            }
        })
        index += len(category) + 1

        # Track where the bullet section starts
        bullet_start = index

        for story in stories:
            text = f"{story.get('fact_summary', '').strip()}\n"
            requests.append({
                "insertText": {"location": {"index": index}, "text": text}
            })
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": index + len(text)},
                    "textStyle": {"fontSize": {"magnitude": 11, "unit": "PT"}},
                    "fields": "fontSize"
                }
            })
            index += len(text)

        # Apply bullet style to the entire inserted block
        requests.append({
            "createParagraphBullets": {
                "range": {"startIndex": bullet_start, "endIndex": index},
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"
            }
        })

        # Add a newline between sections
        requests.append({
            "insertText": {"location": {"index": index}, "text": "\n"}
        })
        index += 1

    # Final batch update
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests}
    ).execute()

def build_html_email_body(grouped_stories):
    now_str = datetime.now().strftime("%B %d, %Y")
    html = f"""
    <div style="font-family:Arial, sans-serif;">
        <h1 style="font-size:16px; font-weight:bold;">Exponential View Special AI Daily Newsletter — {now_str}</h1>
    """

    for category in CATEGORY_ORDER:
        stories = grouped_stories.get(category, [])[:6]
        if not stories:
            continue

        html += f'<h2 style="font-size:14px; font-weight:bold; margin-top:20px;">{category}</h2><ul>'
        for story in stories:
            summary = story.get('fact_summary', '').strip()
            html += f'<li style="font-size:11px; margin-bottom:8px;">{summary}</li>'
        html += "</ul>"

    html += "</div>"
    return html


# === MAIN ===
def run_selector():
    print("📥 Reading prioritized stories from Google Sheet...")
    stories = load_sheet_data()
    stories = filter_recent_stories(stories)
    if not stories:
        exit()

    print("📊 Grouping stories by category...")
    grouped_stories = group_by_category(stories)

    print("📝 Appending to existing Google Doc...")
    creds = service_account.Credentials.from_service_account_file(
        CREDS_FILE, scopes=["https://www.googleapis.com/auth/documents"]
    )
    doc_service = build('docs', 'v1', credentials=creds)

    html_body = build_html_email_body(grouped_stories)
    now_str = datetime.now().strftime("%B %d, %Y")
    title_text = f"Exponential View Special AI Daily Newsletter — {now_str}"

    if newsletter_already_exists(doc_service, EXISTING_DOC_ID, title_text):
        print("⏭️ Newsletter already exists in the document. Skipping insertion.")
    else:
        insert_formatted_content(doc_service, EXISTING_DOC_ID, grouped_stories)
        print(f"✅ Draft appended successfully: https://docs.google.com/document/d/{EXISTING_DOC_ID}/edit")

if __name__ == "__main__":
    if not ENABLE_K_SELECTOR:
        print("⚠️ k_selector disabled by config")
    else:
        run_selector()
