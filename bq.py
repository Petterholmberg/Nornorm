from __future__ import annotations

import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException
from google.api_core import exceptions as gax_exceptions
from google.cloud import bigquery
from google.oauth2 import service_account

load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES_BILLED = 50 * 1000 * 1000 * 1000  # 50 GB
_DEFAULT_TIMEOUT_SECONDS = 60
# Result-row cap: anything beyond this is dropped before returning the response,
# and a ``truncated`` flag is set so the frontend can warn. Rendering hundreds
# of thousands of rows in a pivot table freezes the browser, and dashboards
# rarely need that many — TML imports of detail-level pivots can otherwise
# return 60k+ rows. 35k is the largest cap we've found that still produces
# a usable CSV export (which the cap also gates) without making the in-page
# pivot table unresponsive. Tunable via ``BQ_MAX_RESULT_ROWS``.
_DEFAULT_MAX_RESULT_ROWS = 35_000


def get_client() -> bigquery.Client:
    """Return an authenticated BigQuery client.

    Uses a service-account JSON file when GCP_SERVICE_ACCOUNT_KEY is set (local dev).
    Falls back to Application Default Credentials when running on Cloud Run.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    sa_path = os.getenv("GCP_SERVICE_ACCOUNT_KEY")

    if sa_path and os.path.exists(sa_path):
        credentials = service_account.Credentials.from_service_account_file(
            sa_path,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        return bigquery.Client(credentials=credentials, project=project_id)

    return bigquery.Client(project=project_id)


def _build_job_config() -> bigquery.QueryJobConfig:
    max_bytes = int(os.getenv("BQ_MAX_BYTES_BILLED", str(_DEFAULT_MAX_BYTES_BILLED)))
    return bigquery.QueryJobConfig(
        maximum_bytes_billed=max_bytes,
        use_query_cache=True,
    )


def dry_run_query(sql: str) -> None:
    """Submit SQL as a BigQuery dry-run.

    Validates parsing, type-checking, and reference resolution without
    executing the query (zero bytes billed). Raises ``HTTPException(400)``
    with the BigQuery error message if the SQL doesn't validate; returns
    ``None`` on success.
    """
    client = get_client()
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        client.query(sql, job_config=job_config)
    except gax_exceptions.BadRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except gax_exceptions.GoogleAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def execute_query(sql: str) -> dict[str, Any]:
    """Execute SQL against BigQuery with a Postgres-backed result cache.

    Returns a payload shaped like:
        columns      - list of {"name": str, "type": str}
        rows         - list of row dicts
        duration_ms  - query wall-clock time in milliseconds (0 on cache hit)
        total_rows   - number of rows returned
        cache_hit    - True when served from the Postgres cache
    """

    client = get_client()
    timeout_s = int(
        os.getenv("BQ_QUERY_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS))
    )

    try:
        start = time.time()
        query_job = client.query(sql, job_config=_build_job_config())
        results = query_job.result(timeout=timeout_s)
        duration_ms = int((time.time() - start) * 1000)

        columns = [
            {"name": field.name, "type": field.field_type} for field in results.schema
        ]
        max_rows = int(os.getenv("BQ_MAX_RESULT_ROWS", str(_DEFAULT_MAX_RESULT_ROWS)))
        rows: list[dict[str, Any]] = []
        truncated = False
        for row in results:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append(dict(row.items()))
        # When truncated, the row iterator knows the un-truncated count.
        total_rows = (results.total_rows or len(rows)) if truncated else len(rows)

        payload: dict[str, Any] = {
            "columns": columns,
            "rows": rows,
            "duration_ms": duration_ms,
            "total_rows": total_rows,
            "cache_hit": False,
            "truncated": truncated,
        }

        return payload
    except gax_exceptions.BadRequest as exc:
        msg = str(exc)
        if "bytes billed" in msg.lower() or "would exceed limit" in msg.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Query exceeds BigQuery byte cap. Narrow the date range "
                    f"or add filters and retry. ({msg})"
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"Query timed out after {timeout_s}s. "
                "Narrow the query or add aggregation."
            ),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
