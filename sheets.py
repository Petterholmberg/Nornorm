import os
import sqlite3

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

SPREADSHEET_ID = "1DqJYoXG4iA-L0CHQR3cLvKtekIBBEiwU9or6F823rkI"
SA_PATH = os.getenv("GCP_SERVICE_ACCOUNT_KEY", "service-account.json")

SCOPES = [
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _get_service():
    creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _read_sheet(service, tab: str) -> tuple[list[str], list[list]]:
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=tab
    ).execute()
    rows = result.get("values", [])
    if not rows:
        return [], []
    headers = rows[0]
    data = [row + [""] * (len(headers) - len(row)) for row in rows[1:]]
    return headers, data


def sync_to_sqlite(db_path: str = "insights.db"):
    service = _get_service()
    conn = sqlite3.connect(db_path)

    tabs = ["curated_columns", "join_definitions", "kpi_documentation", "concepts"]
    for tab in tabs:
        headers, rows = _read_sheet(service, tab)
        if not headers:
            print(f"  {tab}: tomt blad, hoppar över")
            continue

        cols = ", ".join(f'"{h}" TEXT' for h in headers)
        conn.execute(f"DROP TABLE IF EXISTS {tab}")
        conn.execute(f"CREATE TABLE {tab} ({cols})")

        placeholders = ", ".join("?" for _ in headers)
        conn.executemany(f"INSERT INTO {tab} VALUES ({placeholders})", rows)
        print(f"  {tab}: {len(rows)} rader laddade från Sheets")

    conn.commit()
    conn.close()
