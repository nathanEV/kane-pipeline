import requests
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re
from urllib.parse import urlparse
import os
from dateutil import parser as date_parser
import pytz


API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

MODEL = "google/gemini-2.0-flash-001"

SHEET_ID = "11hRH6mnlTGO1qIQUsqkSZawigy1LQlzBPYnJNbpb_RQ"
INPUT_SHEET_NAME = "headscanner"  
OUTPUT_SHEET_NAME = "prioritizer"  
CREDS_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "service_account.json"))
OUTPUT_HEADERS = [
    "story_id",
    "author",
    "headline",
    "fact_summary",
    "source_url",
    "source_name",
    "publication_date",
    "category",
    "significance_score",
    "human_priority",
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
Role: AI Content Curator for "The One AI Email".
Audience: Senior Execs, Investors (Public & VC). Focus strictly on AI, Semiconductors, Enterprise Software, Cloud Infra, related Energy (data centers/tech demand), Capital Markets ($50M+ deals, M&A, IPOs, major AI/Tech stock moves), and specific AI/Tech Policy/Geopolitics.
Task: Process input "fact records". Filter ruthlessly based on audience relevance; exclude general news, minor updates, consumer reviews, etc. If unsure, exclude.
Output: Return a JSON list like this:
[
  {{
    "story_id": "123",
    "fact_summary": "...",
    "category": "M&A",
    "significance_score": 7
  }},
  ...
]

Field Generation Rules:
Category: Assign ONE category based on primary focus using this priority: [M&A, Funding, Policy & Geopolitics, Chips & Infrastructure, Market Pulse, Product & Research, Deals & Partnerships, People Moves, From the Calls, Look Ahead].
fact_summary: 25-35 words, neutral, factual summary of brief_factual_sentence. Include key numbers/metrics. Include ticker only if explicit or one of: (MSFT, GOOGL, AAPL, AMZN, NVDA, META, TSLA, TSM, INTC, AMD). End with "(Source: [source_name])". No markdown.
significance_score: Integer 1-10 based on importance to audience. Assess Relevance (Core AI/Tech focus?) & Scale/Impact (Major players/funds/policy?).
Not Relevant: 1-2
Relevant & Low Impact: 3-4
Relevant & Medium Impact: 5-7
Relevant & High Impact: 8-10

Input:
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
                # Normalize publication_date to YYYY-MM-DD UTC
                raw_pub = original.get("publication_date", "")
                try:
                    dt = date_parser.parse(raw_pub)
                    dt_utc = dt.astimezone(pytz.UTC) if dt.tzinfo else dt.replace(tzinfo=pytz.UTC)
                    pub_date_str = dt_utc.strftime("%Y-%m-%d")
                except Exception:
                    pub_date_str = raw_pub

                results.append({
                    "story_id": sid,
                    "author": original.get("author", ""),
                    "headline": original.get("headline", ""),
                    "fact_summary": result.get("fact_summary", ""),
                    "source_url": source_url,
                    "source_name": readable_source,
                    "publication_date": pub_date_str,
                    "category": result.get("category", ""),
                    "significance_score": result.get("significance_score", ""),
                    "human_priority": original.get("HumanPriority", 0),
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
            row.get("author", ""),
            row.get("headline", ""),
            row.get("fact_summary", ""),
            row.get("source_url", ""),
            row.get("source_name", ""),
            row.get("publication_date", ""),
            row.get("category", ""),
            row.get("significance_score", ""),
            row.get("human_priority", "")
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