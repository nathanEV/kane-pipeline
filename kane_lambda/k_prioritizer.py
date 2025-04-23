import requests
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re
from urllib.parse import urlparse
import os


API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

MODEL = "google/gemini-2.0-flash-001"

SHEET_ID = "11hRH6mnlTGO1qIQUsqkSZawigy1LQlzBPYnJNbpb_RQ"
INPUT_SHEET_NAME = "headscanner"  
OUTPUT_SHEET_NAME = "prioritizer"  
CREDS_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "service_account.json"))
OUTPUT_HEADERS = [
    "story_id", "author", "publication_date", "source", 
    "FactSummary", "sourceURL", "category", "significance_score", "HumanPriority"
]



CATEGORIES = [
    "Product & Research", "Deals & Partnerships", "M&A", "Funding", 
    "Market Pulse", "Chips & Infrastructure", "Policy & Geopolitics", 
    "People Moves", "From the Calls", "Look Ahead"
]

def read_stories_from_sheet(spreadsheet_id, sheet_name, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)

    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    range_str = f"{sheet_name}!A1:Z"
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_str).execute()
    values = result.get('values', [])

    if not values:
        print("No data found.")
        return []

    headers = values[0]
    rows = values[1:]

    # Convert to list of dicts
    story_batch = []
    for row in rows:
        story = dict(zip(headers, row))
        # Normalize fields so all are present
        story_batch.append({
            "story_id": story.get("story_id", ""),
            "author": story.get("author", ""),
            "headline": story.get("headline", ""),
            "context_snippet": story.get("context_snippet", ""),
            "source": story.get("source", ""),
            "publication_date": story.get("publication_date", ""),
            "HumanPriority": int(story.get("HumanPriority", "0") or 0)
        })  

    return story_batch

def build_prompt(story_batch):
    return f"""
You are a News Analysis Agent. For each story object in the following JSON list, perform the following three steps:

1. Write a 1-sentence **factual summary** (10–40 words). Use specific numbers, names, and data where available. Do not editorialize.
2. Choose a single **category** from the list below:
3. Assign a **significance_score** from 1 (low) to 10 (high) using the detailed editorial criteria.Be generous in assigning scores of 9–10 for stories with clear importance to AI, enterprise tech, investment trends, geopolitics, or strategic impact.

### Categories:
- **Product & Research**: Major launches, updates, project results, or benchmarks from significant AI/ML efforts.
- **Deals & Partnerships**: Strategic alliances, collaborations, or joint ventures.
- **M&A**: Mergers, acquisitions, or notable talent acquisitions.
- **Funding**: Significant venture rounds, growth rounds, or grants.
- **Market Pulse**: Major stock moves (include tickers), analyst upgrades/downgrades, or sector signals.
- **Chips & Infrastructure**: Semiconductor advances, data center builds, power/energy systems relevant to AI.
- **Policy & Geopolitics**: Regulation, government statements, export controls, privacy rulings, industrial policy.
- **People Moves**: Notable hires/departures (e.g. C-suite, prominent researchers) that imply strategy shifts.
- **From the Calls**: AI insights from public earnings calls or investor day presentations.
- **Look Ahead**: Confirmed upcoming events, launches, deadlines, or earnings within the next 2 weeks.

### Significance Criteria Highlights:
- **Funding**: >$250M in AI/Robotics, or $50M–$250M if strategic (semis, models, novel tech).
- **Product/Research**: SOTA, capability jumps, cost/licensing impacts from major players.
- **Deals**: Structural market implications, pricing/access changes, strategic innovation.
- **M&A**: >$1B value or meaningful talent acquisition.
- **Infra/Geo**: Fabs, compute power, policy moves, export controls, industrial strategy.
- **People Moves**: Only if C-level, strategy-indicating, or highly influential (e.g. H-index, past roles).
- **Human Priority**: If HumanPriority is 1 it means a human has flagged it as important so reflect in the Significane Criteria.

### Format:
Return a JSON list like this:
[
  {{
    "story_id": "123",
    "fact_summary": "...",
    "category": "M&A",
    "significance_score": 7
  }},
  ...
]

### Input:
{json.dumps(story_batch, indent=2)}
"""
def call_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def parse_source_from_url(url):
    try:
        netloc = urlparse(url).netloc  # e.g. 'www.cnbc.com'
        domain = netloc.replace("www.", "").split(".")[0]  # 'cnbc'
        return domain.upper()
    except Exception:
        return ""

def get_processed_story_ids(spreadsheet_id, sheet_name, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    range_str = f"{sheet_name}!A2:A"  # Story IDs are in col A, skip header
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_str).execute()
    values = result.get('values', [])
    return {row[0] for row in values if row}  # Set of existing story_ids

def process_story_batch(story_batch, batch_size=5):
    results = []
    for i in range(0, len(story_batch), batch_size):
        batch = story_batch[i:i+batch_size]
        print(f"\n🔄 Processing batch {i//batch_size + 1} ({len(batch)} stories)...")

        prompt = build_prompt(batch)
        raw_response = call_openrouter(prompt)

        try:
            cleaned_response = re.sub(r"^```(?:json)?\n|\n```$", "", raw_response.strip())
            parsed = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print("❌ Failed to parse response:", e)
            print("🔍 Raw response:", raw_response)
            continue

        for result in parsed:
            sid = result.get("story_id")
            original = next((item for item in batch if item["story_id"] == sid), None)
            if original:
                source_url = original.get("source", "")
                readable_source = parse_source_from_url(source_url)
                results.append({
                    "story_id": sid,
                    "Author": original.get("author", ""),
                    "Date": original.get("publication_date", ""),
                    "Source": readable_source,
                    "FactSummary": result.get("fact_summary", ""),
                    "SourceURL": source_url,
                    "Category": result.get("category", ""),
                    "SignificanceScore": result.get("significance_score", ""),
                    "HumanPriority": original.get("HumanPriority", 0),
                })
    return results

def write_results_to_sheet(spreadsheet_id, sheet_name, results, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    values = []
    for row in results:
        values.append([
            row.get("story_id", ""),
            row.get("Author", ""),
            row.get("Date", ""),
            row.get("Source", ""),
            row.get("FactSummary", ""),
            row.get("SourceURL", ""),
            row.get("Category", ""),
            row.get("SignificanceScore", ""),
            row.get("HumanPriority", "")
        ])

    if not values:
        print("⚠️ No new rows to write.")
        return

    body = {"values": values}

    sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=sheet_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

    print(f"✅ Appended {len(values)} new rows to '{sheet_name}'.")

def run_prioritizer():
    print("📥 Reading stories from input sheet...")
    story_batch = read_stories_from_sheet(SHEET_ID, INPUT_SHEET_NAME, CREDS_FILE)

    if not story_batch:
        print("🚫 No input stories found.")
        exit()

    print("📤 Checking processed stories in output sheet...")
    processed_ids = get_processed_story_ids(SHEET_ID, OUTPUT_SHEET_NAME, CREDS_FILE)

    # ⚡ NEW LOGIC: Only keep stories that are NOT yet processed
    unprocessed_batch = [s for s in story_batch if s["story_id"] not in processed_ids]

    if not unprocessed_batch:
        print("✅ All stories already processed. Exiting prioritizer...")
        return

    print(f"⚙️ Processing {len(unprocessed_batch)} unprocessed stories...")
    results = process_story_batch(unprocessed_batch, batch_size=5)

    if results:
        print(f"\n✍️ Writing {len(results)} new results to output sheet...")
        write_results_to_sheet(SHEET_ID, OUTPUT_SHEET_NAME, results, CREDS_FILE)
    else:
        print("✅ No new results to write.")

if __name__ == "__main__":
    run_prioritizer()