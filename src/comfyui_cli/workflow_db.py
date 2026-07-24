"""Shared database helpers for workflow import / doc generation."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml


def find_project_root(start: Path) -> Path:
    """Walk upward from *start* until we find ``pyproject.toml``."""
    candidate = start.resolve()
    while True:
        if (candidate / "pyproject.toml").exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            raise FileNotFoundError("Cannot locate project root (pyproject.toml)")
        candidate = parent


def ensure_db(project_root: Path) -> Path:
    """Create the db directory and return the database file path."""
    db_dir = project_root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "workflows.db"


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a connection and create the workflow table if it does not exist."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow (
            id                  TEXT PRIMARY KEY,
            status              TEXT    NOT NULL DEFAULT 'enabled',
            type                TEXT    NOT NULL,
            purpose             TEXT    NOT NULL DEFAULT '',
            output_type         TEXT    NOT NULL DEFAULT '',
            input_node_mapping  TEXT    NOT NULL DEFAULT '{}',
            workflow_config     TEXT    NOT NULL,
            created_at          TEXT    NOT NULL,
            updated_at          TEXT    NOT NULL
        )
        """
    )
    return conn


def upsert_workflow(conn: sqlite3.Connection, meta: dict, workflow_config: dict) -> None:
    """Insert or update a single workflow row (does NOT commit)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mapping_json = json.dumps(meta.get("input_node_mapping", {}), ensure_ascii=False)
    wf_json = json.dumps(workflow_config, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO workflow (id, status, type, purpose, output_type,
                              input_node_mapping, workflow_config,
                              created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status             = excluded.status,
            type               = excluded.type,
            purpose            = excluded.purpose,
            output_type        = excluded.output_type,
            input_node_mapping = excluded.input_node_mapping,
            workflow_config    = excluded.workflow_config,
            updated_at         = excluded.updated_at
        """,
        (
            meta["id"],
            meta.get("status", "enabled"),
            meta.get("type", ""),
            meta.get("purpose", ""),
            meta.get("output_type", ""),
            mapping_json,
            wf_json,
            now,
            now,
        ),
    )


def load_meta_and_workflow(project_root: Path, meta_rel_path: str) -> tuple[dict, dict]:
    """Parse a meta YAML file and its referenced workflow JSON.

    Returns ``(meta, workflow_config)``.
    """
    meta_path = project_root / meta_rel_path
    if not meta_path.exists():
        raise FileNotFoundError(f"Meta file not found: {meta_path}")

    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = yaml.safe_load(fh)

    api_json_rel = meta.get("api_json_file", "")
    workflow_path = project_root / api_json_rel
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    with open(workflow_path, "r", encoding="utf-8") as fh:
        workflow_config = json.load(fh)

    return meta, workflow_config


def load_workflow_direct(project_root: Path, rel_path: str) -> tuple[dict, dict]:
    """Load a workflow JSON file directly, auto-resolving its meta YAML.

    Looks for a matching meta file in ``data/default_workflows/meta/``
    named ``{stem}_meta.yaml``.  If none is found, a minimal meta dict is
    generated from the JSON filename.

    Returns ``(meta, workflow_config)``.
    """
    wf_path = project_root / rel_path
    if not wf_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {wf_path}")

    with open(wf_path, "r", encoding="utf-8") as fh:
        workflow_config = json.load(fh)

    stem = wf_path.stem
    meta_dir = project_root / "data" / "default_workflows" / "meta"

    candidates = [
        meta_dir / f"{stem}_meta.yaml",
        meta_dir / f"{stem}.yaml",
    ]
    meta_path = next((c for c in candidates if c.exists()), None)

    if meta_path is not None:
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = yaml.safe_load(fh)
    else:
        meta = {
            "id": stem,
            "status": "enabled",
            "type": "",
            "purpose": "",
            "output_type": "",
            "api_json_file": rel_path,
            "input_node_mapping": {},
        }

    return meta, workflow_config


def resolve_import(project_root: Path, rel_path: str) -> tuple[dict, dict]:
    """Dispatch to the correct loader based on file extension.

    ``.yaml`` / ``.yml`` → meta-driven import (``load_meta_and_workflow``).
    ``.json``           → direct import (``load_workflow_direct``).
    """
    ext = Path(rel_path).suffix.lower()
    if ext in (".yaml", ".yml"):
        return load_meta_and_workflow(project_root, rel_path)
    if ext == ".json":
        return load_workflow_direct(project_root, rel_path)
    raise ValueError(f"Unsupported file type: {ext}")
