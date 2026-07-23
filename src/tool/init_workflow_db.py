#!/usr/bin/env python3
"""
Write workflow meta + workflow JSON config into the SQLite database.

Usage::

    python src/tool/init_workflow_db.py data/default_workflows/meta/index_tts_2_meta.yaml

The script resolves the meta file's ``api_json_file`` path relative to the
project root (detected automatically), reads both files, and upserts a row
into ``db/workflows.db`` → ``workflow`` table.
"""

from __future__ import annotations

import json
import sqlite3
import sys
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


def main(meta_rel_path: str) -> None:
    # -- resolve paths -------------------------------------------------------
    cwd = Path.cwd()
    project_root = find_project_root(cwd)

    meta_path = project_root / meta_rel_path
    if not meta_path.exists():
        print(f"ERROR: meta file not found: {meta_path}", file=sys.stderr)
        sys.exit(1)

    # -- parse meta YAML ----------------------------------------------------
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = yaml.safe_load(fh)

    # -- resolve & read workflow JSON ---------------------------------------
    api_json_rel = meta.get("api_json_file", "")
    workflow_path = project_root / api_json_rel
    if not workflow_path.exists():
        print(f"ERROR: workflow file not found: {workflow_path}", file=sys.stderr)
        sys.exit(1)

    with open(workflow_path, "r", encoding="utf-8") as fh:
        workflow_config = json.load(fh)

    # -- ensure db directory exists ------------------------------------------
    db_dir = project_root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    db_path = db_dir / "workflows.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    # -- create table if not exists -----------------------------------------
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow (
            id              TEXT PRIMARY KEY,
            status          TEXT    NOT NULL DEFAULT 'enabled',
            api_json_file   TEXT    NOT NULL,
            type            TEXT    NOT NULL,
            purpose         TEXT    NOT NULL DEFAULT '',
            output_type     TEXT    NOT NULL DEFAULT '',
            meta_config     TEXT    NOT NULL,
            workflow_config TEXT    NOT NULL,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        )
        """
    )

    # -- upsert -------------------------------------------------------------
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta_json = json.dumps(meta, ensure_ascii=False, indent=2)
    wf_json = json.dumps(workflow_config, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO workflow (id, status, api_json_file, type, purpose,
                              output_type, meta_config, workflow_config,
                              created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status          = excluded.status,
            api_json_file   = excluded.api_json_file,
            type            = excluded.type,
            purpose         = excluded.purpose,
            output_type     = excluded.output_type,
            meta_config     = excluded.meta_config,
            workflow_config = excluded.workflow_config,
            updated_at      = excluded.updated_at
        """,
        (
            meta["id"],
            meta.get("status", "enabled"),
            meta.get("api_json_file", ""),
            meta.get("type", ""),
            meta.get("purpose", ""),
            meta.get("output_type", ""),
            meta_json,
            wf_json,
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()

    print(f"OK — upserted workflow '{meta['id']}' into {db_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <meta_yaml_path>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
