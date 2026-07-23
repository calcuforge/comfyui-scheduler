#!/usr/bin/env python3
"""
Generate ``doc/workflow.md`` from the workflow table in the SQLite database.

Usage::

    python src/tool/gen_workflow_doc.py
"""

from __future__ import annotations

import json
from pathlib import Path

from init_workflow_db import ensure_db, find_project_root, get_connection


def build_input_table(mapping_json: str) -> list[str]:
    """Build a standalone markdown table for the input node mapping."""
    mapping = json.loads(mapping_json)
    if not mapping:
        return []

    items = sorted(
        mapping.items(),
        key=lambda kv: (not kv[1].get("required"), kv[0]),
    )

    lines = [
        "| Field | Type | Required | Description |",
        "|-------|------|----------|-------------|",
    ]
    for name, info in items:
        vt = info.get("value_type", "?")
        req = "yes" if info.get("required") else "no"
        desc = (
            info.get("description", "")
            .replace("|", "\\|")
            .replace("\n", " ")
        )
        lines.append(f"| `{name}` | {vt} | {req} | {desc} |")

    return lines


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
        "## Summary",
        "",
        "| ID | Type | Purpose | Output |",
        "|----|------|---------|--------|",
    ]

    for row in rows:
        id_, type_, purpose, output_type, mapping_json = row
        mapping = json.loads(mapping_json)
        field_count = len(mapping)
        lines.append(f"| {id_} | {type_} | {purpose} | {output_type} |")

    lines.append("")
    lines.append("## Input Fields")
    lines.append("")

    for row in rows:
        id_, type_, purpose, output_type, mapping_json = row
        lines.append(f"### {id_}")
        lines.append("")
        input_lines = build_input_table(mapping_json)
        if input_lines:
            lines.extend(input_lines)
        else:
            lines.append("(no inputs)")
        lines.append("")

    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_path = doc_dir / "workflow.md"
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK — wrote {len(rows)} workflows to {doc_path}")


if __name__ == "__main__":
    main()
