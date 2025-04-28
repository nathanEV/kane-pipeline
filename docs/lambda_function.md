# Kane Pipeline AWS Lambda Function Documentation

## Overview
The **Kane Pipeline** Lambda function orchestrates an end-to-end process for collecting, prioritizing, and formatting technology news stories for the Exponential View Special AI Daily Newsletter. It leverages RSS feeds, Google Sheets, Google Docs, and an LLM via OpenRouter to produce a curated, categorized newsletter daily.

## File Structure
```
├── scripts/
│   └── package_lambda.sh      # Build & package script for AWS Lambda deployment
├── kane_lambda/
│   ├── lambda_function.py     # AWS Lambda handler
│   ├── k_master.py            # Orchestrator for all pipeline stages
│   ├── k_headscanner.py       # Stage 1: Fetch & extract raw stories
│   ├── k_prioritizer.py       # Stage 2: Assign categories & significance scores
│   ├── k_selector.py          # Stage 3: Filter, group & format newsletter content
│   └── k_sheet_clean.py       # Stage 4: Clean & normalize Google Sheets
├── service_account.json       # Google service account credentials
└── requirements.txt           # Python dependencies
```  

## Handler Definition
```python
# kane_lambda/lambda_function.py
from kane_lambda.k_master import run_kane_pipeline

def lambda_handler(event, context):
    """
    AWS Lambda entry point. Executes the full Kane pipeline
    and returns an HTTP-style response.
    """
    run_kane_pipeline()
    return {
        "statusCode": 200,
        "body": "Kane pipeline completed successfully."
    }

if __name__ == "__main__":
    run_kane_pipeline()
```

## Pipeline Stages
Each stage is invoked in sequence by `run_kane_pipeline()` (in `k_master.py`).

### 1. Headscanner (`k_headscanner.py`)
- **Purpose**: Fetch up to `max_stories` new articles from predefined RSS feeds.
- **Key Functions**:
  - `discover_articles_from_rss(...)`: Parses feeds, removes duplicates, date filtering.
  - `extract_snippet_author_batch(...)`: Uses OpenRouter LLM to extract context snippets & missing authors.
  - `append_stories_to_sheet(...)`: Writes new stories to the **headscanner** sheet in Google Sheets.
- **Configuration**:
  - `RSS_FEEDS`: List of `(URL, Label)` tuples.
  - `SHEET_ID`, `INPUT_SHEET_NAME` ("headscanner").

### 2. Prioritizer (`k_prioritizer.py`)
- **Purpose**: Categorize stories and assign a significance score using an LLM.
- **Key Functions**:
  - `read_stories_from_sheet(...)`: Loads raw stories from the **headscanner** sheet.
  - `build_prompt(...)`: Constructs a JSON-based prompt for classification.
  - `call_openrouter(...)`: Sends prompt to OpenRouter API for completion.
  - `process_story_batch(...)`: Parses LLM response, normalizes dates, enriches metadata.
  - `write_results_to_sheet(...)`: Appends categorized stories to the **prioritizer** sheet.
- **Configuration**:
  - `OUTPUT_SHEET_NAME` ("prioritizer"), `CATEGORIES`, OpenRouter `MODEL`, `API_KEY`.

### 3. Selector (`k_selector.py`)
- **Purpose**: Filter, group, and format prioritized stories into a newsletter.
- **Key Functions**:
  - `filter_recent_stories(...)`: Keeps articles from the last 24 hours (or future-dated).
  - `group_by_category(...)`: Organizes stories by category order.
  - `insert_formatted_content(...)`: Appends bullet-formatted content to an existing Google Doc.
  - `build_html_email_body(...)`: Generates an HTML email body for downstream emailing.
- **Configuration**:
  - `INPUT_SHEET` ("prioritizer"), `EXISTING_DOC_ID`, `CATEGORY_ORDER`.

### 4. Sheet Cleaner (`k_sheet_clean.py`)
- **Purpose**: Normalize date formats, headers, and remove empty rows for consistency.
- **Key Functions**:
  - Data type normalization for Excel/Google Sheets serial dates.
  - Header enforcement and row trimming.

## Configuration & Environment
| Variable                   | Description                                                      |
| -------------------------- | ---------------------------------------------------------------- |
| OPENROUTER_API_KEY         | API key for OpenRouter LLM calls (used in headscanner & prioritizer) |
| GOOGLE_APPLICATION_CREDENTIALS | Path to `service_account.json` for Sheets & Docs API access     |

## Dependencies
All Python packages are listed in `requirements.txt`. Key libraries include:
- `google-api-python-client`, `google-auth`, `google-auth-httplib2` (Google Sheets & Docs)
- `feedparser` (RSS parsing)
- `requests` (HTTP requests to LLM & feeds)
- `dateutil`, `pytz` (date parsing & timezone handling)
- `openrouter` (via custom HTTP requests)

## Packaging & Deployment
Use the provided Bash script to build and package the Lambda deployment:
```bash
cd scripts
./package_lambda.sh
```
This script:
1. Installs dependencies into `build/`
2. Copies the `kane_lambda/` source and credentials
3. Produces `kane_lambda_package.zip` for AWS Lambda console or CLI upload

## Invocation & Monitoring
- **Trigger**: Typically scheduled via AWS CloudWatch Events (e.g., daily at 06:00 UTC).
- **Logging**: Uses `print()` statements; captured in CloudWatch Logs for each invocation.
- **Error Handling**: Fails fast on exceptions (`set -e` in packaging), LLM errors are caught per batch with warnings.

---
*Last updated: $(date +"%Y-%m-%d")* 