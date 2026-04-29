"""
memory.py — Memória persistente do SwitchBot via SQLite

Duas camadas de memória:
  1. Sessões: cada conversa tem um ID, timestamp e resumo
  2. Mensagens: histórico completo por sessão
  3. Fatos: memórias semânticas permanentes (preferências, contexto do usuário)

O JarvisCore usa isso para:
  - Retomar contexto entre sessões
  - Lembrar preferências do usuário
  - Carregar últimas N mensagens como contexto
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
DB_PATH = os.path.join(BASE_DIR, 'memory.db')

def _connect():
    """Retorna conexão SQLite com row_factory para dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Melhor performance concorrente
    return conn

def init_db():
    """Cria as tabelas se não existirem."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                summary     TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS facts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT UNIQUE NOT NULL,
                value       TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id);
        """)

def create_session() -> int:
    """Cria nova sessão e retorna seu ID."""
    now = datetime.now().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (created_at, updated_at) VALUES (?, ?)",
            (now, now)
        )
        return cur.lastrowid

def save_message(session_id: int, role: str, content: str):
    """Persiste uma mensagem na sessão."""
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )

def load_session_messages(session_id: int, limit: int = 20) -> list[dict]:
    """Carrega as últimas N mensagens de uma sessão (sem o system prompt)."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT role, content FROM messages
               WHERE session_id = ? AND role != 'system'
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit)
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def get_last_session() -> dict | None:
    """Retorna dados da sessão mais recente."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None

def get_session_count() -> int:
    """Total de sessões salvas."""
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

def update_session_summary(session_id: int, summary: str):
    """Salva um resumo da sessão (gerado pela IA)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET summary = ?, updated_at = ? WHERE id = ?",
            (summary, datetime.now().isoformat(), session_id)
        )

def set_fact(key: str, value: str):
    """Salva ou atualiza um fato/preferência do usuário."""
    now = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO facts (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, now)
        )

def get_fact(key: str) -> str | None:
    """Recupera um fato pelo key."""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM facts WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None

def get_all_facts() -> dict:
    """Retorna todos os fatos salvos como dict."""
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM facts").fetchall()
    return {r["key"]: r["value"] for r in rows}

def get_recent_sessions(limit: int = 5) -> list[dict]:
    """Retorna as últimas N sessões com resumo e timestamps."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, created_at, updated_at, summary,
               (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) as msg_count
               FROM sessions ORDER BY updated_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

def get_context_summary(max_messages: int = 10) -> str:
    """
    Gera um bloco de contexto compacto para inserir no system prompt.
    Inclui fatos do usuário + resumo da última sessão.
    """
    parts = []
    
    # Fatos persistentes
    facts = get_all_facts()
    if facts:
        facts_str = "\n".join(f"  • {k}: {v}" for k, v in facts.items())
        parts.append(f"MEMÓRIA PERMANENTE (preferências do usuário):\n{facts_str}")
    
    # Resumo da última sessão
    last = get_last_session()
    if last and last.get("summary"):
        dt = last["updated_at"][:10]
        parts.append(f"ÚLTIMA SESSÃO ({dt}): {last['summary']}")
    
    if not parts:
        return ""
    
    return "\n\n".join(parts)

# Inicializa o DB ao importar
init_db()
