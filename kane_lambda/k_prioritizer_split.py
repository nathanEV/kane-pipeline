import requests
import json
import re
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from urllib.parse import urlparse
from dateutil import parser as date_parser
import pytz

from kane_lambda.config import (
    CATEGORY_MODEL,
    SIGNIFICANCE_MODEL,
    RELEVANCE_MODEL,
    CATEGORY_PROMPT_TEMPLATE,
    SIGNIFICANCE_PROMPT_TEMPLATE,
    RELEVANCE_PROMPT_TEMPLATE
)
from kane_lambda.k_prioritizer import (
    SHEET_ID,
    INPUT_SHEET_NAME,
    OUTPUT_SHEET_NAME,
    CREDS_FILE
)

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

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

    story_batch = []
    for row in rows:
        story = dict(zip(headers, row))
        story_batch.append({
            "story_id": story.get("story_id", ""),
            "author": story.get("author", ""),
            "headline": story.get("headline", ""),
            "context_snippet": story.get("context_snippet", ""),
            "source_url": story.get("source_url", ""),
            "publication_date": story.get("publication_date", ""),
            "human_priority": int(story.get("human_priority", "0") or 0)
        })
    return story_batch

def get_processed_story_ids(spreadsheet_id, sheet_name, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    range_str = f"{sheet_name}!A2:A"
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_str).execute()
    values = result.get('values', [])
    return {row[0] for row in values if row}

def call_model(prompt, model):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("❌ Model request HTTPError:", e)
        print("🔍 Model:", model)
        print("🔍 Request payload:", json.dumps(payload))
        print("🔍 Response status:", response.status_code)
        print("🔍 Response body:", response.text)
        raise
    return response.json()["choices"][0]["message"]["content"]

def parse_source_from_url(url):
    try:
        netloc = urlparse(url).netloc
        domain = netloc.replace("www.", "").split(".")[0]
        return domain.upper()
    except Exception:
        return ""

def process_story_batch_split(story_batch, batch_size=5):
    results = []
    for i in range(0, len(story_batch), batch_size):
        batch = story_batch[i:i+batch_size]
        print(f"\n🔄 Processing batch {i//batch_size + 1} ({len(batch)} stories)...")

        # First prompt: category & reason
        cat_prompt = CATEGORY_PROMPT_TEMPLATE.replace("{story_batch}", json.dumps(batch, indent=2))
        raw_cat = call_model(cat_prompt, CATEGORY_MODEL)
        try:
            cleaned_cat = re.sub(r"^```(?:json)?\n|\n```$", "", raw_cat.strip())
            parsed_cat = json.loads(cleaned_cat)
        except json.JSONDecodeError as e:
            print("❌ Failed to parse category response:", e)
            print("🔍 Raw category response:", raw_cat)
            continue

        # Merge category info by list position; use sheet's story_id and context_snippet
        enriched = []
        for original, item in zip(batch, parsed_cat):
            enriched.append({
                **original,
                "fact_summary": original.get("context_snippet", ""),
                "category": item.get("category", ""),
                "category_reason": item.get("category_reason", "")
            })

        # Second prompt: significance score
        sig_prompt = SIGNIFICANCE_PROMPT_TEMPLATE.replace("{story_batch}", json.dumps(enriched, indent=2))
        raw_sig = call_model(sig_prompt, SIGNIFICANCE_MODEL)
        try:
            cleaned_sig = re.sub(r"^```(?:json)?\n|\n```$", "", raw_sig.strip())
            parsed_sig = json.loads(cleaned_sig)
        except json.JSONDecodeError as e:
            print("❌ Failed to parse significance response:", e)
            print("🔍 Raw significance response:", raw_sig)
            continue

        # Third prompt: relevance
        rel_prompt = RELEVANCE_PROMPT_TEMPLATE.replace("{story_batch}", json.dumps(enriched, indent=2))
        raw_rel = call_model(rel_prompt, RELEVANCE_MODEL)
        try:
            cleaned_rel = re.sub(r"^```(?:json)?\n|\n```$", "", raw_rel.strip())
            parsed_rel = json.loads(cleaned_rel)
        except json.JSONDecodeError as e:
            print("❌ Failed to parse relevance response:", e)
            print("🔍 Raw relevance response:", raw_rel)
            continue

        # Merge relevance info by list position
        for item, rel_item in zip(enriched, parsed_rel):
            item["relevant"] = rel_item.get("relevant", "")

        # Build final results by list position; ignore story_id from LLM output
        for item, sig_item in zip(enriched, parsed_sig):
            sid = item["story_id"]
            source_url = item.get("source_url", "")
            readable_source = parse_source_from_url(source_url)
            raw_pub = item.get("publication_date", "")
            try:
                dt = date_parser.parse(raw_pub)
                dt_utc = dt.astimezone(pytz.UTC) if dt.tzinfo else dt.replace(tzinfo=pytz.UTC)
                pub_date_str = dt_utc.strftime("%Y-%m-%d")
            except Exception:
                pub_date_str = raw_pub

            results.append({
                "story_id": sid,
                "author": item.get("author", ""),
                "headline": item.get("headline", ""),
                "fact_summary": item.get("fact_summary", ""),
                "source_url": source_url,
                "source_name": readable_source,
                "publication_date": pub_date_str,
                "category": item.get("category", ""),
                "category_reason": item.get("category_reason", ""),
                "significance_score": sig_item.get("significance_score", ""),
                "relevant": item.get("relevant", ""),
                "human_priority": item.get("human_priority", 0)
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
            row.get("publication_date", ""),
            row.get("headline", ""),
            row.get("source_name", ""),
            row.get("fact_summary", ""),
            row.get("source_url", ""),
            row.get("category", ""),
            row.get("category_reason", ""),
            row.get("significance_score", ""),
            row.get("relevant", ""),
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

def run_split_prioritizer():
    print("📥 Reading stories from input sheet...")
    story_batch = read_stories_from_sheet(SHEET_ID, INPUT_SHEET_NAME, CREDS_FILE)

    if not story_batch:
        print("🚫 No input stories found.")
        exit()

    print("📤 Checking processed stories in output sheet...")
    processed_ids = get_processed_story_ids(SHEET_ID, OUTPUT_SHEET_NAME, CREDS_FILE)

    unprocessed = [s for s in story_batch if s["story_id"] not in processed_ids]
    if not unprocessed:
        print("✅ All stories already processed. Exiting split prioritizer...")
        return

    print(f"⚙️ Processing {len(unprocessed)} unprocessed stories...")
    results = process_story_batch_split(unprocessed, batch_size=5)

    if results:
        print(f"\n✍️ Writing {len(results)} new results to output sheet...")
        write_results_to_sheet(SHEET_ID, OUTPUT_SHEET_NAME, results, CREDS_FILE)
    else:
        print("✅ No new results to write.")

if __name__ == "__main__":
    run_split_prioritizer() 