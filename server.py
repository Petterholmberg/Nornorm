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
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NORNORM-BI · Data Chat</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    /* ---- NORNORM-BI design tokens (mirrors the React app's Tailwind theme) ---- */
    :root {
      --sand-1: #FFFFFF; --sand-2: #F1F5F9; --sand-3: #E2E8F0;
      --shade-1: #1E3A8A; --shade-2: #2563EB; --shade-3: #475569; --shade-4: #94A3B8;
      --primary: #1E3A8A; --primary-hover: #1E40AF;
      --green: #16A34A; --blue: #0EA5E9; --yellow: #EAB308; --red: #DC2626;
      --shadow-card: 0 1px 2px rgba(30, 58, 138, .05);
      --shadow-card-hover: 0 4px 16px rgba(30, 58, 138, .10);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; }
    body {
      font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
      color: var(--shade-1); background: var(--sand-1);
      -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
      font-feature-settings: 'cv11', 'ss01';
      display: flex; height: 100vh; overflow: hidden;
    }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: var(--sand-1); }
    ::-webkit-scrollbar-thumb { background: var(--sand-3); border-radius: 4px; border: 2px solid var(--sand-1); }
    ::-webkit-scrollbar-thumb:hover { background: var(--shade-4); }

    /* ---- Sidebar (the NORNORM-BI app shell) ---- */
    .sidebar { width: 240px; flex-shrink: 0; background: var(--sand-2); border-right: 1px solid var(--sand-3); display: flex; flex-direction: column; }
    .brand { display: flex; align-items: center; gap: 8px; padding: 32px 24px 24px; }
    .brand-logo { width: 28px; height: 28px; border-radius: 4px; background: var(--shade-1); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
    .brand-logo svg { width: 16px; height: 16px; }
    .brand-name { font-size: 18px; font-weight: 500; letter-spacing: -0.01em; color: var(--shade-1); }
    .nav-label { padding: 0 24px 12px; font-size: 11px; line-height: 14px; letter-spacing: .14em; text-transform: uppercase; color: var(--shade-4); font-weight: 500; }
    .nav { padding: 0 12px; display: flex; flex-direction: column; gap: 4px; }
    .nav-item { display: flex; align-items: center; gap: 12px; padding: 8px 16px; border-radius: 4px; font-size: 14px; font-weight: 500; letter-spacing: -0.01em; color: var(--shade-3); text-decoration: none; transition: background .15s, color .15s; }
    .nav-item svg { width: 20px; height: 20px; flex-shrink: 0; }
    .nav-item:hover { background: var(--sand-3); color: var(--shade-1); }
    .nav-item.active { background: var(--shade-1); color: #fff; }
    .status { margin-top: auto; padding: 18px 24px; display: flex; align-items: center; gap: 10px; border-top: 1px solid var(--sand-3); }
    .status-dot { width: 8px; height: 8px; border-radius: 9999px; background: var(--green); box-shadow: 0 0 0 3px rgba(22, 163, 74, .15); flex-shrink: 0; }
    .status-text { font-size: 12px; color: var(--shade-3); }

    /* ---- Main column ---- */
    .main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--sand-1); }
    .page-header { padding: 22px 32px; border-bottom: 1px solid var(--sand-3); display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-shrink: 0; }
    .page-eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--shade-4); font-weight: 500; margin-bottom: 2px; }
    .page-title { font-size: 28px; line-height: 34px; letter-spacing: -0.015em; font-weight: 500; color: var(--shade-1); }
    .pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; background: var(--sand-2); color: var(--shade-2); border: 1px solid var(--sand-3); border-radius: 4px; font-size: 12px; font-weight: 500; }
    .pill-dot { width: 6px; height: 6px; border-radius: 9999px; background: var(--shade-2); }

    /* ---- Split: chat on the left, data on the right ---- */
    .content { flex: 1; display: flex; min-height: 0; }
    .chat-pane { flex: 1 1 56%; min-width: 380px; display: flex; flex-direction: column; min-height: 0; border-right: 1px solid var(--sand-3); }
    .data-pane { flex: 1 1 44%; min-width: 340px; max-width: 720px; display: flex; flex-direction: column; min-height: 0; background: var(--sand-1); }

    /* ---- Messages ---- */
    .messages { flex: 1; overflow-y: auto; padding: 24px 32px; display: flex; flex-direction: column; gap: 16px; }
    .msg { max-width: 80%; padding: 12px 16px; border-radius: 16px; line-height: 1.6; font-size: 14px; word-break: break-word; }
    .msg.user { align-self: flex-end; background: var(--shade-1); color: #fff; border-bottom-right-radius: 4px; }
    .msg.assistant { align-self: flex-start; background: #fff; color: var(--shade-1); border: 1px solid var(--sand-3); box-shadow: var(--shadow-card); border-bottom-left-radius: 4px; }
    .msg.assistant p { margin: 0 0 8px; } .msg.assistant p:last-child { margin-bottom: 0; }
    .msg.assistant strong { font-weight: 600; }
    .msg.assistant ul, .msg.assistant ol { margin: 4px 0 8px 20px; }
    .msg.assistant code { font-family: 'JetBrains Mono', monospace; font-size: 12px; background: var(--sand-2); padding: 1px 5px; border-radius: 4px; }
    .msg.assistant pre { background: var(--sand-2); padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
    .msg.assistant pre code { background: none; padding: 0; }
    .msg.assistant a { color: var(--shade-2); }

    .thinking .dots { display: inline-flex; gap: 4px; align-items: center; height: 20px; }
    .thinking .dots span { width: 6px; height: 6px; border-radius: 9999px; background: var(--shade-4); animation: blink 1.2s infinite both; }
    .thinking .dots span:nth-child(2) { animation-delay: .2s; }
    .thinking .dots span:nth-child(3) { animation-delay: .4s; }
    @keyframes blink { 0%, 80%, 100% { opacity: .2; } 40% { opacity: 1; } }

    /* ---- Empty welcome state ---- */
    .empty { margin: auto; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 24px; }
    .empty svg { width: 40px; height: 40px; color: var(--sand-3); }
    .empty-title { font-size: 16px; color: var(--shade-3); font-weight: 500; }
    .empty-sub { font-size: 14px; color: var(--shade-4); max-width: 340px; line-height: 1.5; }

    /* ---- Composer ---- */
    .composer { flex-shrink: 0; padding: 16px 32px 24px; border-top: 1px solid var(--sand-3); display: flex; gap: 8px; align-items: flex-end; }
    .composer textarea { flex: 1; resize: none; height: 48px; max-height: 160px; padding: 13px 16px; background: #fff; border: 1px solid var(--sand-3); border-radius: 8px; font-family: inherit; font-size: 14px; line-height: 20px; color: var(--shade-1); transition: border-color .15s, box-shadow .15s; }
    .composer textarea::placeholder { color: var(--shade-4); }
    .composer textarea:focus { outline: none; border-color: var(--shade-2); box-shadow: 0 0 0 2px rgba(37, 99, 235, .15); }
    .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 48px; padding: 0 26px; border-radius: 4px; font-size: 14px; font-weight: 500; letter-spacing: -0.01em; background: var(--primary); color: #fff; border: 1px solid var(--primary); cursor: pointer; transition: background .15s, border-color .15s; }
    .btn:hover { background: var(--primary-hover); border-color: var(--primary-hover); }
    .btn:disabled { opacity: .4; cursor: not-allowed; }

    /* ---- Data pane (SQL + results), styled as nn-surface cards ---- */
    .data-header { padding: 20px 24px 4px; flex-shrink: 0; }
    .data-header .page-eyebrow { margin: 0; }
    .data-body { flex: 1; overflow-y: auto; padding: 16px 24px 24px; display: flex; flex-direction: column; gap: 16px; min-height: 0; }
    .card { background: #fff; border: 1px solid var(--sand-3); border-radius: 16px; box-shadow: var(--shadow-card); overflow: hidden; }
    .card-grow { flex: 1; display: flex; flex-direction: column; min-height: 0; }
    .card-label { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--shade-3); font-weight: 500; padding: 12px 14px; border-bottom: 1px solid var(--sand-3); display: flex; align-items: center; gap: 8px; }
    .card-label svg { width: 14px; height: 14px; color: var(--shade-4); }
    .row-count { margin-left: auto; text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--shade-4); }
    .sql-code { font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace; font-size: 12px; line-height: 1.6; color: var(--shade-1); background: var(--sand-2); padding: 14px; white-space: pre-wrap; word-break: break-word; overflow-x: auto; max-height: 220px; overflow-y: auto; }
    .sql-code.sql-empty { font-family: 'Inter', sans-serif; color: var(--shade-4); }
    .table-wrap { overflow: auto; }
    .card-grow .table-wrap { flex: 1; min-height: 0; }
    .table-empty { padding: 14px; font-size: 13px; color: var(--shade-4); }

    table.nn { border-collapse: collapse; width: 100%; font-size: 13px; }
    table.nn thead th { position: sticky; top: 0; background: var(--sand-2); color: var(--shade-3); font-size: 11px; font-weight: 500; letter-spacing: .06em; text-transform: uppercase; text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--sand-3); white-space: nowrap; }
    table.nn tbody td { padding: 7px 12px; border-bottom: 1px solid var(--sand-3); color: var(--shade-1); white-space: nowrap; }
    table.nn tbody tr:last-child td { border-bottom: none; }
    table.nn tbody tr:hover { background: var(--sand-2); }
    .sort-btn { margin-left: 6px; border: none; background: transparent; color: var(--shade-4); cursor: pointer; font-size: 11px; padding: 2px 5px; border-radius: 4px; vertical-align: middle; }
    .sort-btn:hover { background: var(--sand-3); color: var(--shade-1); }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-logo">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <span class="brand-name">NORNORM-BI</span>
    </div>

    <div class="nav-label">Workspace</div>
    <nav class="nav">
      <a class="nav-item active">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        Data Chat
      </a>
    </nav>

    <div class="status">
      <span class="status-dot"></span>
      <span class="status-text">Connected to BigQuery</span>
    </div>
  </aside>

  <main class="main">
    <div class="page-header">
      <div>
        <div class="page-eyebrow">Workspace</div>
        <h1 class="page-title">Data Chat</h1>
      </div>
      <span class="pill"><span class="pill-dot"></span>Powered by Claude</span>
    </div>

    <div class="content">
      <section class="chat-pane">
        <div id="messages" class="messages">
          <div class="empty" id="empty-state">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <div class="empty-title">Ask anything about your data</div>
            <div class="empty-sub">Query BigQuery in natural language or explore KPI and metric definitions. The generated SQL and results appear in the panel on the right.</div>
          </div>
        </div>
        <div class="composer">
          <textarea id="input" placeholder="Ask about your data…  (Enter to send, Shift+Enter for newline)"></textarea>
          <button id="send" class="btn">Send</button>
        </div>
      </section>

      <aside class="data-pane">
        <div class="data-header">
          <div class="page-eyebrow">Results</div>
        </div>
        <div class="data-body">
          <div class="card">
            <div class="card-label">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
              SQL Query
            </div>
            <pre id="sql-code" class="sql-code sql-empty">Run a query to see the generated SQL here.</pre>
          </div>
          <div class="card card-grow">
            <div class="card-label">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 10h18M3 14h18M12 4v16M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z" /></svg>
              Data
              <span id="row-count" class="row-count"></span>
            </div>
            <div id="table-panel" class="table-wrap"><div class="table-empty">Query results will appear here.</div></div>
          </div>
        </div>
      </aside>
    </div>
  </main>

  <script>
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('send');
    const sqlEl = document.getElementById('sql-code');
    const history = [];

    function clearEmptyState() {
      const e = document.getElementById('empty-state');
      if (e) e.remove();
    }

    function resetSql() {
      sqlEl.classList.add('sql-empty');
      sqlEl.textContent = 'Run a query to see the generated SQL here.';
    }

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
      const header = '<tr>' + cols.map(c => `<th>${c.replace(/_/g, ' ')}<button class="sort-btn" title="Sort descending" onclick="currentSort='${c}'; renderTable(currentRaw)">↕</button></th>`).join('') + '</tr>';
      const body = rows.map(r => '<tr>' + cols.map(c => `<td>${formatCell(c, r[c])}</td>`).join('') + '</tr>').join('');
      document.getElementById('table-panel').innerHTML = `<table class="nn"><thead>${header}</thead><tbody>${body}</tbody></table>`;
      const rc = document.getElementById('row-count');
      if (rc) rc.textContent = rows.length + (rows.length === 1 ? ' row' : ' rows');
    }

    async function send() {
      const text = inputEl.value.trim();
      if (!text) return;
      inputEl.value = '';
      inputEl.style.height = '48px';
      sendBtn.disabled = true;
      clearEmptyState();

      addMessage('user', text);
      const assistantDiv = addMessage('assistant', '');
      assistantDiv.classList.add('thinking');
      assistantDiv.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
      resetSql();

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
            sqlEl.classList.remove('sql-empty');
            sqlEl.textContent = parsed.data;
            continue;
          }
          reply += parsed;
          assistantDiv.classList.remove('thinking');
          assistantDiv.innerHTML = marked.parse(reply);
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
      }

      if (assistantDiv.classList.contains('thinking')) {
        assistantDiv.classList.remove('thinking');
        assistantDiv.innerHTML = marked.parse(reply);
      }

      history.push({ role: 'user', content: text });
      history.push({ role: 'assistant', content: reply });
      sendBtn.disabled = false;
      inputEl.focus();
    }

    sendBtn.addEventListener('click', send);
    inputEl.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
    inputEl.addEventListener('input', () => {
      inputEl.style.height = '48px';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
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
