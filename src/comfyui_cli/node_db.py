"""SQLite-backed node storage — replaces the old JSON-file persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .workflow_db import ensure_db, find_project_root, get_connection


def _node_table() -> str:
    return """
        CREATE TABLE IF NOT EXISTS node (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url        TEXT    NOT NULL UNIQUE,
            user       TEXT    NOT NULL DEFAULT '',
            password   TEXT    NOT NULL DEFAULT '',
            name       TEXT    NOT NULL DEFAULT '',
            blocking   INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )
    """


def add_node(url: str, user: str = "", password: str = "", name: str = "", blocking: bool = True) -> None:
    """Insert a node.  Raises ValueError if the URL already exists."""
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())

    existing = conn.execute("SELECT id FROM node WHERE url = ?", (url.rstrip("/"),)).fetchone()
    if existing:
        conn.close()
        raise ValueError(f"Node already registered: {url}")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO node (url, user, password, name, blocking, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (url.rstrip("/"), user, password, name or url.rstrip("/"), int(blocking), now, now),
    )
    conn.commit()
    conn.close()


def list_nodes() -> list[dict[str, Any]]:
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())
    rows = conn.execute("SELECT url, user, password, name, blocking FROM node ORDER BY id").fetchall()
    conn.close()
    return [
        {"url": r[0], "user": r[1], "password": r[2], "name": r[3], "blocking": bool(r[4])}
        for r in rows
    ]


def remove_node(name_or_url: str) -> None:
    key = name_or_url.rstrip("/")
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())
    cursor = conn.execute(
        "DELETE FROM node WHERE url = ? OR name = ?", (key, key)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted == 0:
        raise NodeNotFoundError(f"No node matching '{name_or_url}'.")


def clear_nodes() -> None:
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    conn.execute(_node_table())
    conn.execute("DELETE FROM node")
    conn.commit()
    conn.close()


def import_from_yaml(config_path: str, project_root: Path) -> tuple[int, int]:
    """Import nodes from a YAML config file.  Returns ``(ok, skip)``."""
    path = project_root / config_path
    if not path.exists():
        return 0, 0

    with open(path, "r", encoding="utf-8") as fh:
        nodes = yaml.safe_load(fh)

    if not nodes:
        return 0, 0

    ok = skip = 0
    for entry in nodes:
        url = entry.get("url", "").strip()
        if not url:
            continue
        try:
            add_node(
                url=url,
                user=entry.get("user", ""),
                password=entry.get("password", ""),
                name=entry.get("name", ""),
                blocking=entry.get("blocking", True),
            )
            ok += 1
        except ValueError:
            skip += 1

    return ok, skip


class NodeNotFoundError(Exception):
    pass
