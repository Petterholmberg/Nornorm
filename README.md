# Nornorm Data Chat

A chat interface powered by Claude that lets you query BigQuery and explore KPI/metric definitions in natural language. Results are streamed back and rendered in a live table panel alongside the chat.

## How it works

- The frontend sends messages to `/chat` (FastAPI + SSE)
- Claude uses two tools: `run_sql` (BigQuery) and `run_sqlite_sql` (local `insights.db`)
- BigQuery schema, join definitions, KPI calculations, and business concepts are loaded from `insights.db` at startup and injected into Claude's system prompt
- Query results are streamed token-by-token and rendered in the table panel below the chat

## Setup

### 1. Install dependencies

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
GCP_PROJECT_ID=your_gcp_project_id
GCP_SERVICE_ACCOUNT_KEY=service-account.json   # path to your GCP service account file
```

`GCP_SERVICE_ACCOUNT_KEY` is only needed for local development. On Cloud Run, Application Default Credentials are used automatically.

### 3. Initialize the local database

```bash
python init_db.py
```

This creates `insights.db` from `seed.sql`. The seed contains mock data — replace it with your own schema and curated column/KPI definitions.

### 4. Run the server

```bash
uvicorn server:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Project structure

```
server.py         # FastAPI app, Claude chat loop, SSE streaming
bq.py             # BigQuery client and query execution
init_db.py        # Creates insights.db from seed.sql
seed.sql          # Schema + seed data for insights.db
requirements.txt  # Python dependencies
.env              # Local env vars (not committed)
service-account.json  # GCP credentials (not committed)
```

## insights.db tables

| Table | Purpose |
|---|---|
| `curated_columns` | Curated BigQuery columns with aliases, types, and aggregation rules |
| `join_definitions` | How BigQuery tables relate to each other |
| `kpi_documentation` | KPI definitions, calculations, and explanations |
| `concepts` | Business concept definitions injected into the system prompt |
