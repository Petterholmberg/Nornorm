from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv
import os

load_dotenv()

def get_bq_client() -> bigquery.Client:
    key_path = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
    project = os.getenv("GCP_PROJECT_ID")

    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=project, credentials=credentials)


if __name__ == "__main__":
    client = get_bq_client()
    print("Connected to project:", client.project)
