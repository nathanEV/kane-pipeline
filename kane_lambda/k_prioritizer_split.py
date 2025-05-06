import requests
import json
import re
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from urllib.parse import urlparse
from dateutil import parser as date_parser
import pytz
import google.genai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

from kane_lambda.config import (
    CATEGORY_MODEL,
    SIGNIFICANCE_MODEL,
    RELEVANCE_MODEL,
    CATEGORY_PROMPT_TEMPLATE,
    SIGNIFICANCE_PROMPT_TEMPLATE,
    RELEVANCE_PROMPT_TEMPLATE,
    LLM_BACKEND,
    GEMINI_API_KEY
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
    for idx, row in enumerate(rows, start=2):
        try:
            story = dict(zip(headers, row))
            # Normalize input_type from possible header variants
            raw_input_type = (story.get("input_type") or story.get("input type") or story.get("Input Type") or story.get("inputType") or "")
            human_priority_str = story.get("human_priority", "0") or "0"
            human_priority = int(human_priority_str)
            story_batch.append({
                "story_id": story.get("story_id", ""),
                "author": story.get("author", ""),
                "headline": story.get("headline", ""),
                "context_snippet": story.get("context_snippet", ""),
                "source_url": story.get("source_url", ""),
                "publication_date": story.get("publication_date", ""),
                "human_priority": human_priority,
                "input_type": raw_input_type
            })
        except Exception as e:
            print(f"⚠️ Skipping invalid row {idx} in sheet '{sheet_name}': {row}. Error: {e}")
            continue
    return story_batch

def get_processed_story_ids(spreadsheet_id, sheet_name, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    range_str = f"{sheet_name}!A2:A"
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_str).execute()
    values = result.get('values', [])
    processed_ids = set()
    for idx, row in enumerate(values, start=2):
        try:
            if row:
                processed_ids.add(row[0])
        except Exception as e:
            print(f"⚠️ Skipping invalid ID row {idx} in sheet '{sheet_name}': {row}. Error: {e}")
            continue
    return processed_ids

def call_llm(prompt, model):
    if LLM_BACKEND == "openrouter":
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
    elif LLM_BACKEND == "gemini":
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {LLM_BACKEND}")

def parse_source_from_url(url):
    try:
        netloc = urlparse(url).netloc
        domain = netloc.replace("www.", "").split(".")[0]
        return domain.upper()
    except Exception:
        return ""

def _process_one_batch(batch, batch_number):
    print(f"\n🔄 Processing batch {batch_number} ({len(batch)} stories)...")
    results = []
    # First prompt: category & reason
    cat_prompt = CATEGORY_PROMPT_TEMPLATE.replace("{story_batch}", json.dumps(batch, indent=2))
    raw_cat = call_llm(cat_prompt, CATEGORY_MODEL)
    try:
        cleaned_cat = re.sub(r"^```(?:json)?\n|\n```$", "", raw_cat.strip())
        parsed_cat = json.loads(cleaned_cat)
    except json.JSONDecodeError as e:
        print("❌ Failed to parse category response:", e)
        print("🔍 Raw category response:", raw_cat)
        return []

    # Enrich with category fields
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
    raw_sig = call_llm(sig_prompt, SIGNIFICANCE_MODEL)
    try:
        cleaned_sig = re.sub(r"^```(?:json)?\n|\n```$", "", raw_sig.strip())
        parsed_sig = json.loads(cleaned_sig)
    except json.JSONDecodeError as e:
        print("❌ Failed to parse significance response:", e)
        print("🔍 Raw significance response:", raw_sig)
        return []

    # Third prompt: relevance
    rel_prompt = RELEVANCE_PROMPT_TEMPLATE.replace("{story_batch}", json.dumps(enriched, indent=2))
    raw_rel = call_llm(rel_prompt, RELEVANCE_MODEL)
    try:
        cleaned_rel = re.sub(r"^```(?:json)?\n|\n```$", "", raw_rel.strip())
        parsed_rel = json.loads(cleaned_rel)
    except json.JSONDecodeError as e:
        print("❌ Failed to parse relevance response:", e)
        print("🔍 Raw relevance response:", raw_rel)
        return []

    # Merge relevance and build final list
    for item, rel_item in zip(enriched, parsed_rel):
        item["relevant"] = rel_item.get("relevant", "")

    batch_results = []
    for item, sig_item in zip(enriched, parsed_sig):
        sid = item["story_id"]
        readable_source = parse_source_from_url(item.get("source_url", ""))
        raw_pub = item.get("publication_date", "")
        try:
            dt = date_parser.parse(raw_pub)
            dt_utc = dt.astimezone(pytz.UTC) if dt.tzinfo else dt.replace(tzinfo=pytz.UTC)
            pub_date_str = dt_utc.strftime("%Y-%m-%d")
        except Exception:
            pub_date_str = raw_pub

        batch_results.append({
            "story_id": sid,
            "author": item.get("author", ""),
            "headline": item.get("headline", ""),
            "fact_summary": item.get("fact_summary", ""),
            "source_url": item.get("source_url", ""),
            "source_name": readable_source,
            "publication_date": pub_date_str,
            "category": item.get("category", ""),
            "category_reason": item.get("category_reason", ""),
            "significance_score": sig_item.get("significance_score", ""),
            "relevant": item.get("relevant", ""),
            "human_priority": item.get("human_priority", 0),
            "input_type": item.get("input_type", "")
        })
    return batch_results

def process_story_batch_split(story_batch, batch_size=5):
    batches = [story_batch[i:i+batch_size] for i in range(0, len(story_batch), batch_size)]
    results = []
    # Cap concurrency to avoid overwhelming Lambda
    max_workers = min(len(batches), batch_size)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {executor.submit(_process_one_batch, batch, idx+1): idx+1 for idx, batch in enumerate(batches)}
        for future in as_completed(future_to_batch):
            batch_number = future_to_batch[future]
            try:
                batch_results = future.result()
                if batch_results:
                    results.extend(batch_results)
            except Exception as e:
                print(f"❌ Batch {batch_number} failed:", e)
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
            row.get("human_priority", ""),
            row.get("input_type", "")
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
        return

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