#!/usr/bin/env python3
"""
Generate ``doc/workflow.md`` from the workflow table in the SQLite database.

Usage::

    python src/tool/gen_workflow_doc.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from init_workflow_db import ensure_db, find_project_root, get_connection


def build_input_field_list(mapping_json: str) -> str:
    """Convert input_node_mapping JSON to a compact field list string."""
    mapping = json.loads(mapping_json)
    if not mapping:
        return "-"
    return ", ".join(
        f"{name} ({info.get('value_type', '?')}, {'required' if info.get('required') else 'optional'})" for name, info in mapping.items()
    )


def main() -> None:
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)

    rows = conn.execute(
        """
        SELECT id, type, purpose, output_type, input_node_mapping
        FROM workflow
        ORDER BY id
        """
    ).fetchall()
    conn.close()

    lines: list[str] = [
        "# Workflow List",
        "",
        "| ID | Type | Purpose | Output | Input Fields |",
        "|----|------|---------|--------|--------------|",
    ]

    for row in rows:
        id_, type_, purpose, output_type, mapping_json = row
        inputs = build_input_field_list(mapping_json)
        lines.append(
            f"| {id_} | {type_} | {purpose} | {output_type} | {inputs} |"
        )

    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_path = doc_dir / "workflow.md"
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK — wrote {len(rows)} workflows to {doc_path}")


if __name__ == "__main__":
    main()
