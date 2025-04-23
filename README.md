# 🧠 Kane Pipeline – Daily AI Newsletter Automation

This project powers a daily automated workflow that ingests AI/tech news, prioritizes it using LLMs, formats it, and sends it to Google Docs — ready for newsletter publication.

---

## 🔁 Pipeline Overview

| Step             | Script               | Description |
|------------------|----------------------|-------------|
| 🧹 Clean Sheets   | `k_sheet_clean.py`    | Removes stale or low-priority stories from Sheets |
| 📰 Headscan      | `k_headscanner.py`    | Pulls recent news stories from RSS feeds |
| 📊 Prioritizer   | `k_prioritizer.py`    | Uses LLM to summarize, categorize & score stories |
| 📝 Formatter     | `k_selector.py`       | Appends selected stories to Google Docs |
| 🚀 Master Run    | `k_master.py`         | Runs the full sequence end-to-end |
| 📦 Lambda Entry  | `lambda_function.py`  | AWS Lambda entrypoint (calls `run_kane_pipeline`) |

