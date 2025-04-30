from kane_lambda.k_sheet_clean import clean_sheets
from kane_lambda.k_headscanner import run_headscanner
from kane_lambda.k_prioritizer import run_prioritizer
from kane_lambda.k_prioritizer_split import run_split_prioritizer
from kane_lambda.k_selector import run_selector
from kane_lambda.config import ENABLE_K_SHEET_CLEAN, ENABLE_K_SELECTOR, USE_SPLIT_PRIORITIZER

def run_kane_pipeline():
    print("🚀 Starting full Kane pipeline...")
    run_headscanner(300)
    if USE_SPLIT_PRIORITIZER:
        print("🔀 Using split prioritizer...")
        run_split_prioritizer()
    else:
        print("🔀 Using standard prioritizer...")
        run_prioritizer()
    if ENABLE_K_SELECTOR:
        run_selector()
    else:
        print("⚠️ k_selector disabled by config")
    if ENABLE_K_SHEET_CLEAN:
        clean_sheets()
    else:
        print("⚠️ k_sheet_clean disabled by config")
    print("✅ All stages completed.")

if __name__ == "__main__":
    run_kane_pipeline()