import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import feedparser
import sys
import re
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests
import json
from urllib.parse import urlparse
from html import unescape
import math
import os
from kane_lambda.config import HEADSCANNER_MODEL, HEADSCANNER_PROMPT_TEMPLATE, LLM_BACKEND, GEMINI_API_KEY
import google.genai as genai

# === CONFIG ===
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

SHEET_ID = "11hRH6mnlTGO1qIQUsqkSZawigy1LQlzBPYnJNbpb_RQ"
INPUT_SHEET_NAME = "headscanner"
CREDS_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "service_account.json"))

HEADERS = [
    "story_id",
    "author",
    "headline",
    "context_snippet",
    "source_url",
    "publication_date",
    "human_priority",
    "input_type",
]

RSS_FEEDS = [
    ("https://www.techmeme.com/feed.xml", "Techmeme River"),
    ("https://rss.app/feeds/4uZTg1jssusYbBdz.xml", "Techmeme Semiconductor"),
    ("https://rss.app/feeds/unnX4o3PFEpblbx4.xml", "Techmeme AI"),
    ("https://rss.app/feeds/HLekB8mvrvIxQ4pS.xml", "Techmeme DataCent"),
    ("https://rss.app/feeds/H4qnuCkcvceXwJBE.xml", "Techmeme OpenAI/Lambda/Google"),
    ("https://rss.app/feeds/e3y2n9NIz8By1H4h.xml", "Techmeme Apple/Amazon/Anthropic"),
    ("https://rss.app/feeds/tWJEPf9NQjIJXENk.xml", "Techmeme Alibaba/Deepseek/Tencent/China"),
    ("https://www.techinasia.com/feed", "Tech in Asia"),
    ("https://www.scmp.com/rss/91/feed", "SCMP Technology"),
    ("https://www.datacenterdynamics.com/en/rss/", "DatacenterDynamics"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "NYT Technology"),
    ("https://digital-strategy.ec.europa.eu/en/rss.xml", "EU Digital Strategy"),
    ("https://www.artificialintelligence-news.com/feed/", "Artificial Intelligence News"),
    ("https://epochai.org/atom.xml", "Epoch AI Blog"),
    ("https://deepmind.google/blog/rss.xml", "Google DeepMind Blog"),
    ("https://www.techdirt.com/feed/", "Techdirt"),
    ("https://about.bnef.com/blog/feed/", "BloombergNEF Blog"),
    ("https://feeds.bloomberg.com/technology/news.rss", "Bloomberg Technology"),
    ("https://www.politico.eu/section/competition/feed/", "POLITICO Competition"),
    ("https://www.politico.eu/section/technology/feed/", "POLITICO Technology"),
    ("https://www.politico.eu/section/cybersecurity/feed/", "POLITICO Cybersecurity"),
    ("https://tech.eu/feed/", "Tech.eu"),
    ("https://www.politico.eu/section/energy/feed/", "POLITICO Energy"),
    ("https://www.aei.org/feed/", "American Enterprise Institute"),
    ("https://www.bruegel.org/rss.xml", "Bruegel"),
    ("https://cepr.net/feed/", "Center for Economic & Policy Research"),
    ("https://www.hpcwire.com/feed/", "HPCwire"),
]
# === HELPERS ===


def clean_headline(title: str) -> str:
    title = title.strip()
    title = re.sub(r"^Sources:\s*", "", title, flags=re.IGNORECASE)  # remove "Sources:" prefix
    title = re.sub(r"\s*[\(\[].*?[\)\]]\s*$", "", title)  # remove trailing (Bloomberg), [TechCrunch], etc.
    return title.strip()

def format_date(published_struct):
    try:
        parsed = datetime(*published_struct[:6], tzinfo=timezone.utc)
    except Exception:
        parsed = datetime.now(timezone.utc)
    
    # Format as MM/DD/YYYY, not as Excel serial number
    # This ensures consistency with the clean_sheets function
    return parsed.strftime("%Y-%m-%d")

def extract_real_url(summary: str) -> str:
    summary = unescape(summary)
    match = re.search(r'href="(https?://[^"]+)"', summary)
    return match.group(1) if match else ""

def extract_snippet_author_batch(summaries, headlines, known_authors=None, batch_size=5):
    # initialize content for error handling across all batches
    content = ""
    if known_authors is None:
        known_authors = [""] * len(summaries)

    def call_llm(prompt, model):
        if LLM_BACKEND == "openrouter":
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise
            return resp.json()["choices"][0]["message"]["content"].strip()
        elif LLM_BACKEND == "gemini":
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {LLM_BACKEND}")

    results = []
    for i in range(0, len(summaries), batch_size):
        batch = [
            {
                "title": headlines[i + j],
                "summary": summaries[i + j],
                "has_author": bool(known_authors[i + j]),
            }
            for j in range(min(batch_size, len(summaries) - i))
        ]

        prompt = HEADSCANNER_PROMPT_TEMPLATE.replace("{batch}", json.dumps(batch, indent=2))

        try:
            content = call_llm(prompt, HEADSCANNER_MODEL)

            # 🧹 Strip markdown/code blocks and noise
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            content = re.sub(r'^[^{\[]+', '', content).strip()  # Remove leading junk
            content = content.replace('"', '"').replace("'", "'").replace("'", "'")

            # 🔍 Attempt JSON parse
            parsed = json.loads(content)

            for item in parsed:
                if not isinstance(item, dict):
                    continue
                author = item.get("author", "").strip()
                snippet = item.get("context_snippet", "").strip()
                results.append({
                    "context_snippet": snippet,
                    "author": author
                })

        except Exception as e:
            print("⚠️ LLM batch extraction failed:", e)
            # Log model, prompt, request and response details
            try:
                print("🔍 Model:", HEADSCANNER_MODEL)
                print("🔍 Prompt to model:\n", prompt)
            except Exception:
                pass
            print("🔎 Raw response snippet:\n", content[:300])
            for _ in batch:
                results.append({"context_snippet": "", "author": ""})

    return results


def get_existing_sources_and_last_id(spreadsheet_id, sheet_name, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A2:E"
    ).execute()

    values = result.get('values', [])
    sources = set()
    last_id = 0

    for row in values:
        if len(row) >= 5:
            sources.add(row[4])
        if row and row[0].isdigit():
            last_id = max(last_id, int(row[0]))

    return sources, last_id

def append_stories_to_sheet(spreadsheet_id, sheet_name, stories, creds_file):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    values = []
    for s in stories:
        values.append([
            str(s["story_id"]),
            s["author"],
            s["headline"],
            s["context_snippet"],
            s.get("source_url", ""),
            s.get("publication_date", ""),
            s.get("human_priority", 0),
            s.get("input_type", "")
        ])

    if not values:
        print("⚠️ No new stories to write.")
        return

    body = {"values": values}
    sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

    print(f"✅ Appended {len(values)} new stories to '{sheet_name}'.")

def discover_articles_from_rss(feeds, existing_sources, cutoff, max_stories):
    candidates = []

    for url,label in feeds:
        print(f"📡 Fetching feed: {label}")
        feed = feedparser.parse(url)

        for entry in feed.entries:
            if len(candidates) >= max_stories:
                break

            raw_link = entry.get("link", "").strip()
            summary = entry.get("summary", "").strip()
            real_url = extract_real_url(summary) or raw_link

            if not real_url:
                print(f"⏭️ Skipping entry with no valid link: {entry.get('title', 'No Title')}")
                continue

            if real_url in existing_sources:
                print(f"🧾 Already processed: {real_url}")
                continue

            pub_time = entry.get("published_parsed")
            pub_dt = datetime(*pub_time[:6], tzinfo=timezone.utc) if pub_time else datetime.now(timezone.utc)

            if pub_dt < cutoff:
                print(f"⏱️ Skipping old article: {entry.get('title', 'No Title')} ({pub_dt})")
                continue

            author = entry.get("dc:creator") or entry.get("author", "")
            author = author.strip()

            candidates.append({
                "headline": clean_headline(entry.get("title", "Untitled").strip()),
                "summary": summary,
                "source": real_url,
                "publication_date": format_date(pub_time),
                "author": author
            })

    print(f"✅ Found {len(candidates)} new articles within cutoff.")
    return candidates

def run_headscanner(max_stories):

    # 📌 Step 1: Load existing sources and last used story ID
    existing_sources, last_id = get_existing_sources_and_last_id(SHEET_ID, INPUT_SHEET_NAME, CREDS_FILE)

    # 📌 Step 2: Define time cutoff (last 24h, timezone-aware)
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    next_id = last_id + 1

    # 📌 Step 3: Discover articles via RSS feeds
    candidates = discover_articles_from_rss(RSS_FEEDS, existing_sources, cutoff, max_stories)

    if not candidates:
        print("✅ No new recent stories found.")
        return

    # 📌 Step 4: Prepare inputs for LLM
    summaries = [c["summary"] for c in candidates]
    headlines = [c["headline"] for c in candidates]
    rss_authors = [c.get("author", "") for c in candidates]  # FIX: previously used wrong field

    print(f"🧠 Sending {len(summaries)} summaries to LLM for snippet/author extraction...")
    snippet_results = extract_snippet_author_batch(summaries, headlines, known_authors=rss_authors)

    # 📌 Step 5: Finalize stories
    fresh_stories = []
    for i, meta in enumerate(snippet_results):
        final_author = rss_authors[i] or meta["author"]
        snippet = meta["context_snippet"]

        if not snippet:
            print(f"⏭️ Skipping due to missing snippet: {headlines[i][:50]}")
            continue

        fresh_stories.append({
            "story_id": str(next_id),
            "author": final_author,
            "headline": headlines[i],
            "context_snippet": snippet,
            "source_url": candidates[i]["source"],
            "publication_date": candidates[i]["publication_date"],
            "human_priority": 0,
            "input_type": "RSS"
        })
        print(f"✅ Added: {headlines[i][:60]}...")
        next_id += 1

    # 📌 Step 6: Upload to Google Sheets
    if fresh_stories:
        append_stories_to_sheet(SHEET_ID, INPUT_SHEET_NAME, fresh_stories, CREDS_FILE)
    else:
        print("✅ No new stories to add.")