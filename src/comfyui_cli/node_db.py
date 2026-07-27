"""SQLite-backed node storage."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workflow_db import ensure_db, find_project_root, get_connection


def _node_table() -> str:
    return """
        CREATE TABLE IF NOT EXISTS node (
            id         TEXT PRIMARY KEY,
            url        TEXT    NOT NULL,
            user       TEXT    NOT NULL DEFAULT '',
            password   TEXT    NOT NULL DEFAULT '',
            name       TEXT    NOT NULL DEFAULT '',
            blocking   INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )
    """


def add_node(node_id: str, url: str, user: str = "", password: str = "",
             name: str = "", blocking: bool = True) -> None:
    """Upsert a node by *node_id*."""
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    expanded_url = os.path.expandvars(url).rstrip("/")
    conn.execute(
        """
        INSERT INTO node (id, url, user, password, name, blocking, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            url        = excluded.url,
            user       = excluded.user,
            password   = excluded.password,
            name       = excluded.name,
            blocking   = excluded.blocking,
            updated_at = excluded.updated_at
        """,
        (node_id, expanded_url, user, password, name or node_id,
         int(blocking), now, now),
    )
    conn.commit()
    conn.close()


def list_nodes() -> list[dict[str, Any]]:
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())
    rows = conn.execute(
        "SELECT id, url, user, password, name, blocking FROM node ORDER BY id"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "url": os.path.expandvars(r[1]), "user": r[2],
         "password": r[3], "name": r[4], "blocking": bool(r[5])}
        for r in rows
    ]


def remove_node(key: str) -> None:
    key = key.rstrip("/")
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())
    cursor = conn.execute(
        "DELETE FROM node WHERE id = ? OR url = ? OR name = ?", (key, key, key)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted == 0:
        raise NodeNotFoundError(f"No node matching '{key}'.")


def clear_nodes() -> None:
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())
    conn.execute("DELETE FROM node")
    conn.commit()
    conn.close()


class NodeNotFoundError(Exception):
    pass
