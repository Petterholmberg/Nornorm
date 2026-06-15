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
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def read_table(table: str) -> tuple[list[str], list[list]]:
    conn = sqlite3.connect("insights.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    headers = [desc[0] for desc in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]
    conn.close()
    return headers, rows


def ensure_sheet(service, title: str, existing: dict[str, int]) -> int:
    if title in existing:
        return existing[title]
    body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    resp = service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
    return resp["replies"][0]["addSheet"]["properties"]["sheetId"]


def clear_and_write(service, sheet_id: int, title: str, headers: list, rows: list):
    values = [headers] + [[str(v) if v is not None else "" for v in row] for row in rows]
    service.spreadsheets().values().clear(
        spreadsheetId=SPREADSHEET_ID, range=title
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def main():
    service = get_sheets_service()

    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    conn = sqlite3.connect("insights.db")
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()

    for table in tables:
        headers, rows = read_table(table)
        sheet_id = ensure_sheet(service, table, existing)
        clear_and_write(service, sheet_id, table, headers, rows)
        print(f"  {table}: {len(rows)} rader skrivna")

    print(f"\nKlart! https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


if __name__ == "__main__":
    main()
