from kane_lambda.k_sheet_clean import clean_sheets
from kane_lambda.k_headscanner import run_headscanner
from kane_lambda.k_prioritizer import run_prioritizer
from kane_lambda.k_selector import run_selector

def run_kane_pipeline():
    print("🚀 Starting full Kane pipeline...")
    run_headscanner(300)
    run_prioritizer()
    run_selector()
    clean_sheets()
    print("✅ All stages completed.")

if __name__ == "__main__":
    run_kane_pipeline()