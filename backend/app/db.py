from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import List

from .config import DB_PATH
from .models import HistoryItem, ScoreHistoryItem



def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                job_id     TEXT PRIMARY KEY,
                cnpj       TEXT NOT NULL,
                email      TEXT NOT NULL,
                empresa    TEXT,
                status     TEXT NOT NULL,
                num_docs   INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS credenciais (
                id         TEXT PRIMARY KEY,
                email_enc  BLOB NOT NULL,
                senha_enc  BLOB NOT NULL,
                senha2_enc BLOB,
                updated_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS historico_score (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                email            TEXT NOT NULL,
                status           TEXT NOT NULL,
                ultimo_passo     TEXT NOT NULL,
                error            TEXT,
                diagnostics_base TEXT,
                created_at       TEXT NOT NULL
            )
            """
        )



def registrar(
    job_id: str, cnpj: str, email: str, empresa: str | None, status: str, num_docs: int
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO history
                (job_id, cnpj, email, empresa, status, num_docs, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                cnpj,
                email,
                empresa,
                status,
                num_docs,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def listar(email: str, limit: int = 50) -> List[HistoryItem]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM history WHERE email = ? ORDER BY created_at DESC LIMIT ?",
            (email, limit),
        ).fetchall()
    return [
        HistoryItem(
            job_id=r["job_id"],
            cnpj=r["cnpj"],
            email=r["email"],
            empresa=r["empresa"],
            status=r["status"],
            num_docs=r["num_docs"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def registrar_navegacao_score(
    email: str, status: str, ultimo_passo: str, error: str | None = None, diagnostics_base: str | None = None
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO historico_score
                (email, status, ultimo_passo, error, diagnostics_base, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                email,
                status,
                ultimo_passo,
                error,
                diagnostics_base,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def listar_historico_score(email: str, limit: int = 50) -> List[ScoreHistoryItem]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM historico_score WHERE email = ? ORDER BY created_at DESC LIMIT ?",
            (email, limit),
        ).fetchall()
    return [
        ScoreHistoryItem(
            id=r["id"],
            email=r["email"],
            status=r["status"],
            ultimo_passo=r["ultimo_passo"],
            error=r["error"],
            diagnostics_base=r["diagnostics_base"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

