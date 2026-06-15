from __future__ import annotations

from bq import execute_query

import json
import os
import sqlite3

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

BQ_TOOLS = [
    {
        "name": "run_sql",
        "description": "Run a SQL query against BigQuery and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL query to run"}
            },
            "required": ["sql"],
        },
    },
    {
        "name": "run_sqlite_sql",
        "description": "Run a SQL query against the local insights.db database containing Excel data about KPIs and metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL query to run"}
            },
            "required": ["sql"],
        },
    },
]

load_dotenv()

app = FastAPI()
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Claude Chat</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #0a1628; height: 100vh; display: flex; flex-direction: column; }
    #messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
    .msg { max-width: 72%; padding: 10px 14px; border-radius: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; max-height: 400px; overflow-y: auto; }
    .user { align-self: flex-end; background: #0071e3; color: #fff; }
    .assistant { align-self: flex-start; background: #fff; color: #1d1d1f; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
    #form { display: flex; gap: 8px; padding: 12px 16px; background: #fff; border-top: 1px solid #e0e0e0; }
    #input { flex: 1; padding: 10px 14px; border: 1px solid #d0d0d0; border-radius: 8px; font-size: 14px; resize: none; height: 44px; font-family: inherit; }
    #input:focus { outline: none; border-color: #0071e3; }
    #send { padding: 6px 30px; background: #0071e3; color: #fff; border: none; border-radius: 8px; font-size: 10px; cursor: pointer; height: 44px;}
    #send:disabled { opacity: .5; cursor: not-allowed; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
    th { background: #f0f0f0; font-weight: bold; }
    tr:nth-child(even) { background: #f9f9f9; }

    
    #table-panel { background: #fff; border-top: 2px solid #0071e3; max-height: 300px; overflow-y: auto; min-height: 300px; flex: 1; }


    #table-panel table { border-collapse: collapse; width: 100%; }
    #table-panel th, #table-panel td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 13px; }
    #table-panel th { background: #e8f0fe; font-weight: bold; position: sticky; top: 0; }
    #table-panel tr:nth-child(even) { background: #f9f9f9; }

    #bottom { display: flex; }
    #sql-box { width: 180px; min-width: 180px; background: #1e1e1e; color: #9cdcfe; font-family: monospace; font-size: 11px; padding: 8px; overflow-y: auto; white-space: pre-wrap; }


  </style>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
    <div id="messages"></div>
    <div id="form">
      <textarea id="input" placeholder="Write a message... (Enter to send, Shift+Enter for newline)"></textarea>
      <button id="send">Send</button>
    </div>
    <div id="bottom">
      <div id="sql-box">SQL visas här...</div>
      <div id="table-panel">...</div>
    </div>



  <script>
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('send');
    const history = [];

    function addMessage(role, text) {
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      div.textContent = text;
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return div;
    }

    let currentRaw = null;
    let currentSort = null;

    const currencyKeywords = /mrr|arr|revenue|amount|eur|price|gmv|acv|tcv/i;

    function formatCell(col, val) {
      if (val === null || val === undefined || val === '') return '';
      const num = typeof val === 'number' ? val : (String(val).trim() !== '' ? Number(val) : NaN);
      if (!isNaN(num) && String(val).trim() !== '') {
        const formatted = Math.round(num).toLocaleString('sv-SE');
        return currencyKeywords.test(col) ? '€' + formatted : formatted;
      }
      return val;
    }

    function renderTable(raw) {
      const cols = raw.columns.map(c => c.name);
      const rows = currentSort ? [...raw.rows].sort((a, b) => (parseFloat(b[currentSort]) || 0) - (parseFloat(a[currentSort]) || 0)) : raw.rows;
      const header = '<tr>' + cols.map(c => `<th>${c.replace(/_/g, ' ')} <button onclick="currentSort='${c}'; renderTable(currentRaw)" style="font-size:10px;padding:2px 6px;cursor:pointer;border:none;background:#0071e3;color:#fff;border-radius:4px;">↕</button></th>`).join('') + '</tr>';
      const body = rows.map(r => '<tr>' + cols.map(c => `<td>${formatCell(c, r[c])}</td>`).join('') + '</tr>').join('');
      document.getElementById('table-panel').innerHTML = `<table><thead>${header}</thead><tbody>${body}</tbody></table>`;
    }


    async function send() {
      const text = inputEl.value.trim();
      if (!text) return;
      inputEl.value = '';
      sendBtn.disabled = true;

      addMessage('user', text);
      const assistantDiv = addMessage('assistant', '');
      document.getElementById('sql-box').textContent = '';

      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let reply = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') break;
          const parsed = JSON.parse(data);
          if (typeof parsed === 'object' && parsed.type === 'table') {
              currentRaw = parsed.data;
              currentSort = null;
              renderTable(currentRaw);
              continue;
          }
          if (typeof parsed === 'object' && parsed.type === 'sql') {
              document.getElementById('sql-box').textContent = parsed.data;
              continue;
          }
          reply += parsed;
          assistantDiv.innerHTML = marked.parse(reply);
          messagesEl.scrollTop = messagesEl.scrollHeight;
          

          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
      }

      history.push({ role: 'user', content: text });
      history.push({ role: 'assistant', content: reply });
      sendBtn.disabled = false;
      inputEl.focus();
    }
    function sortTable(col, cols, rows) {
      const sorted = [...rows].sort((a, b) => {
       const av = parseFloat(a[col]) || 0;
        const bv = parseFloat(b[col]) || 0;
        return bv - av;
      });
    return sorted;
}

    sendBtn.addEventListener('click', send);
    inputEl.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
  </script>
</body>
</html>"""


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(_HTML)


def execute_sqlite_query(sql: str) -> dict:
    conn = sqlite3.connect("insights.db")
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [{"name": desc[0]} for desc in cursor.description]
    rows = [dict(zip([c["name"] for c in columns], row)) for row in cursor.fetchall()]
    conn.close()
    return {"columns": columns, "rows": rows}


def apply_aliases(result: dict) -> dict:
    conn = sqlite3.connect("insights.db")
    cursor = conn.cursor()
    cursor.execute("SELECT source_column, alias FROM curated_columns")
    alias_map = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    result["columns"] = [
        {"name": alias_map.get(col["name"], col["name"])} for col in result["columns"]
    ]
    return result


def load_schema():
    conn = sqlite3.connect("insights.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT source_table, source_column, alias, data_type FROM curated_columns WHERE is_groupable = 1 OR is_aggregatable = 1"
    )
    columns = cursor.fetchall()

    cursor.execute(
        "SELECT left_table, left_column, right_table, right_column, join_type FROM join_definitions"
    )
    joins = cursor.fetchall()

    conn.close()

    tables = {}
    for table_name, column_name, alias, col_type in columns:
        if table_name not in tables:
            tables[table_name] = []
        tables[table_name].append(f"{column_name} (alias: {alias}, type: {col_type})")

    text = "Available tables in BigQuery:\n"
    for table, cols in tables.items():
        text += f"\n{table}:\n"
        for col in cols:
            text += f"  - {col}\n"

    text += "\nHow tables are joined:\n"
    for left_table, left_col, right_table, right_col, join_type in joins:
        text += (
            f"  - {left_table}.{left_col} → {right_table}.{right_col} ({join_type})\n"
        )

    conn2 = sqlite3.connect("insights.db")
    cursor2 = conn2.cursor()
    cursor2.execute(
        "SELECT metric_kpi, calculation FROM kpi_documentation WHERE calculation IS NOT NULL"
    )
    kpis = cursor2.fetchall()
    conn2.close()

    text += "\nKPI calculation rules (follow these exactly when writing SQL):\n"
    for metric, calculation in kpis:
        text += f"\n{metric}:\n  {calculation}\n"

    conn3 = sqlite3.connect("insights.db")
    cursor3 = conn3.cursor()
    cursor3.execute("SELECT name, description FROM concepts")
    concepts = cursor3.fetchall()
    conn3.close()

    if concepts:
        text += "\nBusiness concept definitions:\n"
        for name, description in concepts:
            text += f"\n{name}: {description}\n"

    return text


SYSTEM_PROMPT = (
    """CRITICAL: Always respond in the exact same language the user writes in. If the user writes in Swedish, your entire response must be in Swedish. If the user writes in English, your entire response must be in English. Never mix languages. Always translate any database content to match the user's language.

You are a data analyst for Nornorm helping users retrieve data from BigQuery.
When the user asks for data, generate a SQL query and run it using the run_sql tool.
Respond very briefly in the chat, just one sentence. Do NOT show the table in the chat — data is automatically shown in the table panel below.

When the user asks about KPIs, metrics or explanations, use the run_sqlite_sql tool against the table kpi_documentation.
The table has columns: metric_kpi, short_explanation, data_explanation, columns_used, filters_used, calculation, note, category.
Category values: Sales Clean Version, Design Clean Version, Marketing Clean Version, Supply Chain Clean Version, Customer & Delivery Performance, Circularity&Quality (WIP).
The calculation column will roughly explain how you can calculate the KPI:s.
Always use alias names in SQL queries, e.g. SELECT subscription_id AS "Subscription ID.
Always round numerical values to the nearest integer in SQL queries using ROUND().
Always run a fresh SQL query for every data request. Never assume data exists or doesn't exist based on previous queries in the conversation.
Never guess or estimate answers. Only state facts that come directly from a query result.
If you are unsure how to answer a question or which data to use, be honest and ask the user a follow up question instead of guessing.
".
"""
    + load_schema()
)


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    messages = req.history + [{"role": "user", "content": req.message}]

    def generate():
        while True:
            response = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=BQ_TOOLS,
                messages=messages,
            )

            for block in response.content:
                if block.type == "text":
                    yield f"data: {json.dumps(block.text)}\n\n"

            if response.stop_reason != "tool_use":
                break

            tool_use_block = next(b for b in response.content if b.type == "tool_use")
            sql = tool_use_block.input["sql"]

            if tool_use_block.name == "run_sqlite_sql":
                try:
                    result = execute_sqlite_query(sql)
                    tool_result_content = json.dumps(result)
                except Exception as exc:
                    tool_result_content = json.dumps({"error": str(exc)})
            else:
                yield f"data: {json.dumps({'type': 'sql', 'data': sql})}\n\n"
                yield f"data: {json.dumps(chr(10) + chr(10))}\n\n"
                try:
                    result = apply_aliases(execute_query(sql))
                    tool_result_content = json.dumps(result)
                    yield f"data: {json.dumps({'type': 'table', 'data': result})}\n\n"
                except Exception as exc:
                    tool_result_content = json.dumps({"error": str(exc)})

            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "content": tool_result_content,
                        }
                    ],
                }
            )

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
