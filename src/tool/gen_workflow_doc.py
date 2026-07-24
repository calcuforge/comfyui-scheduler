#!/usr/bin/env python3
"""Thin wrapper — prefer ``multi-comfyui-cli workflow doc``."""

from __future__ import annotations

import json
from pathlib import Path

from comfyui_cli.workflow_db import ensure_db, find_project_root, get_connection


def main() -> None:
    project_root = find_project_root(Path.cwd())
    db_path = ensure_db(project_root)
    conn = get_connection(db_path)

    rows = conn.execute(
        """
        SELECT id, type, purpose, output_type, input_node_mapping
        FROM workflow ORDER BY id
        """
    ).fetchall()
    conn.close()

    lines = [
        "# Workflow List", "",
        "## Summary", "",
        "| ID | Type | Purpose | Output |",
        "|----|------|---------|--------|",
    ]
    for row in rows:
        id_, type_, purpose, output_type, _ = row
        lines.append(f"| {id_} | {type_} | {purpose} | {output_type} |")

    lines.extend(["", "## Input Fields", ""])
    for row in rows:
        id_, _, _, _, mapping_json = row
        lines.append(f"### {id_}")
        lines.append("")
        mapping = json.loads(mapping_json)
        if not mapping:
            lines.append("(no inputs)")
        else:
            items = sorted(
                mapping.items(),
                key=lambda kv: (not kv[1].get("required"), kv[0]),
            )
            lines.append("| Field | Type | Required | Description |")
            lines.append("|-------|------|----------|-------------|")
            for name, info in items:
                vt = info.get("value_type", "?")
                req = "yes" if info.get("required") else "no"
                desc = info.get("description", "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{name}` | {vt} | {req} | {desc} |")
        lines.append("")

    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_path = doc_dir / "workflow.md"
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK — wrote {len(rows)} workflows to {doc_path}")


if __name__ == "__main__":
    main()
