"""
CLI entry point — ``comfyui-scheduler`` command.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import click
import yaml

from . import node_db
from . import node_manager
from . import output
from . import workflow_db
from .api import ComfyUIApi
from .exceptions import ComfyUICLIError
from .executor import run as executor_run


@click.group()
@click.version_option(version="1.0.0", prog_name="comfyui-scheduler")
@click.option("--debug", is_flag=True, default=False, help="Enable verbose progress output.")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """ComfyUI CLI — run workflows on remote ComfyUI nodes from the command line."""
    output.set_debug(debug)
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


# ═══════════════════════════════════════════════════════════════════
#  node  group
# ═══════════════════════════════════════════════════════════════════

@main.group()
def node() -> None:
    """Manage ComfyUI node registrations."""


@node.command("add")
@click.option("--id", "node_id", required=True, help="Unique node identifier")
@click.option("--url", "-u", required=True, help="ComfyUI server URL")
@click.option("--user", default="", help="Basic-auth username")
@click.option("--password", default="", help="Basic-auth password")
@click.option("--name", default="", help="Human-readable label")
def node_add(node_id: str, url: str, user: str, password: str, name: str) -> None:
    """Register or update a ComfyUI node."""
    node_db.add_node(node_id=node_id, url=url, user=user, password=password, name=name)
    output.ok(f"Node added: {name or node_id}", {"id": node_id, "url": url})


@node.command("list")
def node_list() -> None:
    """List all registered nodes."""
    nodes = node_db.list_nodes()
    output.ok("ok", {"nodes": nodes})


@node.command("remove")
@click.argument("key")
def node_remove(key: str) -> None:
    """Remove a registered node by id, name, or url."""
    try:
        node_db.remove_node(key)
        output.ok(f"Node removed: {key}")
    except node_db.NodeNotFoundError:
        output.error(f"No node matching '{key}'.")


@node.command("clear")
def node_clear() -> None:
    """Remove all registered nodes."""
    node_db.clear_nodes()
    output.ok("All nodes removed.")


@node.command("import")
@click.argument("config_files", nargs=-1, type=click.Path(exists=True))
def node_import(config_files: tuple[str, ...]) -> None:
    """Import nodes from YAML config files.

    If no files are given, defaults to data/default_nodes.yaml and data/nodes.yaml.
    """
    if not config_files:
        config_files = (
            "data/default_nodes.yaml",
            "data/nodes.yaml",
        )

    project_root = workflow_db.find_project_root(Path.cwd())
    imported: list[str] = []
    skipped: list[str] = []

    for cf in config_files:
        path = project_root / cf
        if not path.exists():
            output.debug(f"  SKIP {cf} (not found)")
            skipped.append(cf)
            continue

        with open(path, "r", encoding="utf-8") as fh:
            entries = yaml.safe_load(fh)
        if not entries:
            continue

        for entry in entries:
            url = entry.get("url", "").strip()
            nid = entry.get("id", "").strip()
            if not url or not nid:
                continue
            node_db.add_node(
                node_id=nid, url=url,
                user=entry.get("user", ""),
                password=entry.get("password", ""),
                name=entry.get("name", ""),
                blocking=entry.get("blocking", True),
            )
            output.debug(f"  OK   {nid}")
            imported.append(nid)

    output.ok(
        f"Imported {len(imported)} node(s)",
        {"imported": imported, "skipped": skipped},
    )


# ═══════════════════════════════════════════════════════════════════
#  run  command
# ═══════════════════════════════════════════════════════════════════

@main.command("run")
@click.option("--workflow-id", "-w", default=None, help="Workflow id from the database.")
@click.option("--workflow-file", "-f", default=None, type=click.Path(exists=True),
              help="Path to a workflow JSON file.")
@click.option("--inputs", "-i", default="[]", help="JSON array of input objects.")
@click.option("--output-node", default=None, help="_meta.title of the output node.")
def run_cmd(
    workflow_id: str | None,
    workflow_file: str | None,
    inputs: str,
    output_node: str | None,
) -> None:
    """Execute a workflow, auto-selecting the least-busy ComfyUI node."""
    if not workflow_id and not workflow_file:
        raise click.UsageError("Either --workflow-id or --workflow-file is required.")

    # -- auto-import workflows if none exist ---------------------------------
    project_root = workflow_db.find_project_root(Path.cwd())
    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM workflow").fetchone()[0]
    conn.close()
    if count == 0:
        output.debug("[auto] No workflows in database — importing...")
        meta_dirs = [
            project_root / "data" / "default_workflows" / "meta",
            project_root / "data" / "workflows" / "meta",
        ]
        db_path = workflow_db.ensure_db(project_root)
        conn = workflow_db.get_connection(db_path)
        imported = 0
        for meta_path in meta_dirs:
            if not meta_path.is_dir():
                continue
            for yf in sorted(meta_path.glob("*.yaml")):
                rel_path = str(yf.relative_to(project_root))
                try:
                    meta, wf_config = workflow_db.load_meta_and_workflow(project_root, rel_path)
                    if meta.get("status") == "disabled":
                        continue
                    workflow_db.upsert_workflow(conn, meta, wf_config)
                    imported += 1
                except FileNotFoundError:
                    pass
        conn.commit()
        conn.close()
        output.debug(f"[auto] Imported {imported} workflow(s).")

    # -- resolve workflow --------------------------------------------------
    output_type = ""
    if workflow_id:
        db_path = workflow_db.ensure_db(project_root)
        conn = workflow_db.get_connection(db_path)
        row = conn.execute(
            "SELECT workflow_config, input_node_mapping, output_type FROM workflow WHERE id = ?",
            (workflow_id,),
        ).fetchone()
        conn.close()
        if not row:
            output.error(f"Workflow not found: {workflow_id}")
        workflow_config = json.loads(row[0])
        mapping = json.loads(row[1])
        output_type = row[2]
    else:
        with open(project_root / workflow_file, "r", encoding="utf-8") as fh:
            workflow_config = json.load(fh)
        mapping = {}

    # -- parse inputs -------------------------------------------------------
    try:
        raw = json.loads(inputs)
    except json.JSONDecodeError as exc:
        output.error(f"Invalid JSON for --inputs: {exc}")

    resolved_inputs: list[dict] = []

    # JSON object → resolve each key via input_node_mapping
    if isinstance(raw, dict):
        if not mapping:
            output.error("No input mapping available — use --workflow-file with explicit format or import the workflow first.")
        for key, val in raw.items():
            if key not in mapping:
                available = list(mapping.keys())
                output.error(f"Unknown input field '{key}'. Available: {available}")
            info = mapping[key]
            vt = info.get("value_type", "string")
            if vt == "file":
                resolved_inputs.append({
                    "type": "file", "value": str(val),
                    "node_title": info["node_meta_title"],
                    "node_field": info["node_input_field"],
                })
            else:
                # string / int / float — cast to proper type for ComfyUI
                if vt == "int":
                    val = int(val)
                elif vt == "float":
                    val = float(val)
                resolved_inputs.append({
                    "type": "string", "value": val,
                    "node_title": info["node_meta_title"],
                    "node_field": info["node_input_field"],
                })
    # JSON array (backward compat) → explicit format
    elif isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                output.error(f"--inputs[{i}] must be an object")
            for k in ("type", "value", "node_title", "node_field"):
                if k not in item:
                    output.error(f"--inputs[{i}] missing required field '{k}'")
            if item["type"] not in ("string", "file"):
                output.error(f"--inputs[{i}].type must be 'string' or 'file'")
            resolved_inputs.append(item)
    else:
        output.error("--inputs must be a JSON object or array")

    # -- auto-register local node if none exist -----------------------------
    nodes = node_db.list_nodes()
    if not nodes:
        import requests as _requests
        local_url = "http://127.0.0.1:8188"
        try:
            _r = _requests.get(f"{local_url}/system_stats", timeout=3)
            _r.raise_for_status()
        except Exception:
            output.error(
                "No nodes registered and no local ComfyUI detected at 127.0.0.1:8188."
            )

        output.debug(f"[auto] Local ComfyUI detected at {local_url} — running node import...")
        for config_path in ("data/default_nodes.yaml", "data/nodes.yaml"):
            path = project_root / config_path
            if not path.exists():
                continue
            with open(path, "r", encoding="utf-8") as fh:
                entries = yaml.safe_load(fh)
            if not entries:
                continue
            for entry in entries:
                nid = entry.get("id", "").strip()
                if not nid:
                    continue
                node_db.add_node(
                    node_id=nid,
                    url=entry.get("url", local_url).strip() or local_url,
                    user=entry.get("user", ""),
                    password=entry.get("password", ""),
                    name=entry.get("name", ""),
                    blocking=entry.get("blocking", True),
                )
        nodes = node_db.list_nodes()
        output.debug(f"[auto] {len(nodes)} node(s) registered.")

    # -- auto-select node --------------------------------------------------
    task_id = str(uuid.uuid4())
    try:
        api = node_manager.select_node(task_id=task_id)
    except node_db.NodeNotFoundError as exc:
        output.error(str(exc))

    # -- execute ------------------------------------------------------------
    try:
        result = executor_run(
            workflow_source=workflow_config,
            api=api,
            inputs=resolved_inputs,
            output_node_title=output_node,
            output_type=output_type,
        )
    except (ComfyUICLIError, node_db.NodeNotFoundError) as exc:
        output.error(str(exc))

    output.ok(
        f"Workflow completed — {len(result['files'])} file(s)",
        {
            "workflow_id": workflow_id,
            "task_id": task_id,
            "prompt_id": result["prompt_id"],
            "output_type": output_type,
            "files": result["files"],
        },
    )


# ═══════════════════════════════════════════════════════════════════
#  status  command
# ═══════════════════════════════════════════════════════════════════

@main.command("status")
@click.option("--url", "-u", default="", help="Check a specific URL.")
def status_cmd(url: str) -> None:
    """Show queue status of registered nodes."""
    nodes_status: list[dict] = []
    if url:
        url = os.path.expandvars(url)
        api = ComfyUIApi(url)
        nodes_status.append(_get_node_status(url, api))
    else:
        nodes = node_db.list_nodes()
        if not nodes:
            output.ok("ok", {"nodes": [], "msg": "(no nodes registered)"})
            return
        for nd in nodes:
            api = ComfyUIApi(nd["url"], nd.get("user", ""), nd.get("password", ""))
            nodes_status.append(_get_node_status(nd["name"], api))
    output.ok("ok", {"nodes": nodes_status})


def _get_node_status(label: str, api: ComfyUIApi) -> dict:
    try:
        q = api.get_queue()
        running = len(q.get("queue_running", []))
        pending = len(q.get("queue_pending", []))
        output.debug(f"  {label}: running={running}  pending={pending}")
        return {"name": label, "url": api.url, "running": running, "pending": pending,
                "status": "reachable"}
    except ComfyUICLIError:
        output.debug(f"  {label}: UNREACHABLE")
        return {"name": label, "url": api.url, "status": "unreachable"}


# ═══════════════════════════════════════════════════════════════════
#  workflow  group
# ═══════════════════════════════════════════════════════════════════

@main.group()
def workflow() -> None:
    """Manage workflow configurations in the local database."""


@workflow.command("import")
@click.argument("workflow_file", type=click.Path(exists=True))
def workflow_import(workflow_file: str) -> None:
    """Import a workflow from a meta YAML or workflow JSON file."""
    project_root = workflow_db.find_project_root(Path.cwd())
    meta, wf_config = workflow_db.resolve_import(project_root, workflow_file)
    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)
    workflow_db.upsert_workflow(conn, meta, wf_config)
    conn.commit()
    conn.close()
    output.ok(
        f"Upserted workflow '{meta['id']}'",
        {"id": meta["id"], "type": meta.get("type", "")},
    )


@workflow.command("import-all")
def workflow_import_all() -> None:
    """Batch-import meta YAML + workflow JSON files.

    Default data is imported first, then non-default data so that
    user overrides take precedence over defaults with the same id.
    """
    project_root = workflow_db.find_project_root(Path.cwd())
    default_meta = project_root / "data" / "default_workflows" / "meta"
    user_meta = project_root / "data" / "workflows" / "meta"
    default_wf_dir = project_root / "data" / "default_workflows" / "workflow"
    user_wf_dir = project_root / "data" / "workflows" / "workflow"

    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)

    imported: list[str] = []
    skipped: list[str] = []

    def _import_dir(meta_path: Path, wf_dir: Path, label: str) -> None:
        if not meta_path.is_dir():
            return
        for yf in sorted(meta_path.glob("*.yaml")):
            rel_path = str(yf.relative_to(project_root))
            try:
                meta, wf_config = workflow_db.load_meta_and_workflow(project_root, rel_path)
                if meta.get("status") == "disabled":
                    output.debug(f"  SKIP {meta['id']} (status=disabled)")
                    skipped.append(meta["id"])
                    continue
                workflow_db.upsert_workflow(conn, meta, wf_config)
                output.debug(f"  OK   {meta['id']} ({label})")
                imported.append(meta["id"])
            except FileNotFoundError as exc:
                output.debug(f"  SKIP {yf.name}: {exc}")
                skipped.append(yf.name)

        if wf_dir.is_dir():
            for jf in sorted(wf_dir.glob("*.json")):
                stem = jf.stem
                has_meta = (
                    (meta_path / f"{stem}_meta.yaml").exists()
                    or (meta_path / f"{stem}.yaml").exists()
                )
                if has_meta:
                    continue
                rel_path = str(jf.relative_to(project_root))
                try:
                    meta, wf_config = workflow_db.load_workflow_direct(project_root, rel_path)
                    if meta.get("status") == "disabled":
                        output.debug(f"  SKIP {meta['id']} (status=disabled)")
                        skipped.append(meta["id"])
                        continue
                    workflow_db.upsert_workflow(conn, meta, wf_config)
                    output.debug(f"  OK   {meta['id']} (no meta, {label})")
                    imported.append(meta["id"])
                except FileNotFoundError as exc:
                    output.debug(f"  SKIP {jf.name}: {exc}")
                    skipped.append(jf.name)

    _import_dir(default_meta, default_wf_dir, "default")
    _import_dir(user_meta, user_wf_dir, "user")

    conn.commit()
    conn.close()
    output.ok(
        f"Imported {len(imported)}, skipped {len(skipped)}",
        {"imported": imported, "skipped": skipped},
    )


@workflow.command("doc")
def workflow_doc() -> None:
    """Generate doc/workflow.md from the workflow table."""
    project_root = workflow_db.find_project_root(Path.cwd())
    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)

    rows = conn.execute(
        "SELECT id, type, purpose, output_type, input_node_mapping, command_example FROM workflow ORDER BY id"
    ).fetchall()
    conn.close()

    lines = [
        "# Workflow List", "",
        "## Summary", "",
        "| ID | Type | Purpose | Output |",
        "|----|------|---------|--------|",
    ]
    workflows = []
    for row in rows:
        id_, type_, purpose, output_type, mapping_json, _ = row
        mapping = json.loads(mapping_json)
        lines.append(f"| {id_} | {type_} | {purpose} | {output_type} |")
        workflows.append({
            "id": id_, "type": type_, "purpose": purpose,
            "output_type": output_type,
            "input_fields": list(mapping.keys()),
        })

    lines.extend(["", "## Input Fields", ""])
    for row in rows:
        id_, type_, purpose, output_type, mapping_json, cmd_example = row
        lines.append(f"### {id_}")
        lines.append("")
        mapping = json.loads(mapping_json)
        if not mapping:
            lines.append("(no inputs)")
        else:
            items = sorted(mapping.items(),
                           key=lambda kv: (not kv[1].get("required"), kv[0]))
            lines.append("| Field | Type | Required | Description |")
            lines.append("|-------|------|----------|-------------|")
            for name, info in items:
                vt = info.get("value_type", "?")
                req = "yes" if info.get("required") else "no"
                desc = info.get("description", "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{name}` | {vt} | {req} | {desc} |")
        if cmd_example:
            lines.append("")
            lines.append("```bash")
            lines.append(cmd_example.strip())
            lines.append("```")
        lines.append("")

    # Append static extra content if present
    extra_path = project_root / "doc" / "workflow.extra.md.tpl"
    if extra_path.exists():
        lines.append(extra_path.read_text(encoding="utf-8").rstrip("\n"))

    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_path = doc_dir / "workflow.md"
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output.ok(
        f"Generated doc with {len(rows)} workflows",
        {"path": str(doc_path), "workflows": workflows},
    )
