#!/usr/bin/env python3
"""Thin wrapper — prefer ``multi-comfyui-cli workflow import <meta_file>``."""

from __future__ import annotations

import sys
from pathlib import Path

from comfyui_cli.workflow_db import (
    ensure_db,
    find_project_root,
    get_connection,
    load_meta_and_workflow,
    upsert_workflow,
)


def main(meta_rel_path: str) -> None:
    project_root = find_project_root(Path.cwd())
    meta, workflow_config = load_meta_and_workflow(project_root, meta_rel_path)
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)
    upsert_workflow(conn, meta, workflow_config)
    conn.commit()
    conn.close()
    print(f"OK — upserted workflow '{meta['id']}' into {db_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <meta_yaml_path>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
