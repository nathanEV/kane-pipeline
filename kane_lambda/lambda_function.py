from kane_lambda.k_master import run_kane_pipeline

def lambda_handler(event, context):
    run_kane_pipeline()
    return {
        "statusCode": 200,
        "body": "Kane pipeline completed successfully."
    }

if __name__ == "__main__":
    run_kane_pipeline()