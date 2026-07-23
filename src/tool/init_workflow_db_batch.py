#!/usr/bin/env python3
"""
Batch-import all meta YAML files from the meta directory into the workflow table.

Usage::

    python src/tool/init_workflow_db_batch.py [meta_dir]

If *meta_dir* is omitted, ``data/default_workflows/meta`` is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

from init_workflow_db import (
    ensure_db,
    find_project_root,
    get_connection,
    load_meta_and_workflow,
    upsert_workflow,
)


def main(meta_dir_rel: str) -> None:
    project_root = find_project_root(Path.cwd())
    meta_dir = project_root / meta_dir_rel

    if not meta_dir.is_dir():
        print(f"ERROR: meta directory not found: {meta_dir}", file=sys.stderr)
        sys.exit(1)

    yaml_files = sorted(meta_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"No .yaml files found in {meta_dir}")
        return

    db_path = ensure_db(project_root)
    conn = get_connection(db_path)

    ok = skip = 0
    for yf in yaml_files:
        rel_path = str(yf.relative_to(project_root))
        try:
            meta, workflow_config = load_meta_and_workflow(project_root, rel_path)
            upsert_workflow(conn, meta, workflow_config)
            print(f"  OK   {meta['id']}")
            ok += 1
        except FileNotFoundError as exc:
            print(f"  SKIP {yf.name}: {exc}", file=sys.stderr)
            skip += 1

    conn.commit()
    conn.close()

    print(f"\nDone — {ok} upserted, {skip} skipped → {db_path}")


if __name__ == "__main__":
    meta_dir = sys.argv[1] if len(sys.argv) > 1 else "data/default_workflows/meta"
    main(meta_dir)
