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

## 🛠️ Development

- Source Code: All pipeline logic lives under the `kane_lambda/` directory at the project root. Edit individual steps in their respective files:
  - `kane_lambda/k_master.py` (orchestrator)
  - `kane_lambda/k_headscanner.py`, `kane_lambda/k_prioritizer.py`, `kane_lambda/k_selector.py`, `kane_lambda/k_sheet_clean.py`
  - `kane_lambda/lambda_function.py` (Lambda entry point)

- Local Testing: Run the pipeline locally via:
  ```bash
  python3 -m kane_lambda.lambda_function
  ```

- Dependencies: Update `requirements.txt` (project root) to add or bump libraries, then rebuild the package.

- Packaging & Deployment:
  - The `scripts/package_lambda.sh` script builds the Lambda ZIP in `lambda_package/build/`.
  - To rebuild and deploy:
    ```bash
    bash scripts/package_lambda.sh
    aws lambda update-function-code --function-name kane-pipeline --zip-file fileb://lambda_package/kane_lambda_package.zip
    ```

