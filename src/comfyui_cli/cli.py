"""
CLI entry point — ``multi-comfyui-cli`` command.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from .api import ComfyUIApi
from .exceptions import ComfyUICLIError, NodeNotFoundError
from .executor import run as executor_run
from . import node_db
from . import node_manager
from . import workflow_db


@click.group()
@click.version_option(version="1.0.0", prog_name="multi-comfyui-cli")
def main() -> None:
    """ComfyUI CLI — run workflows on remote ComfyUI nodes from the command line."""


# ═══════════════════════════════════════════════════════════════════
#  node  group
# ═══════════════════════════════════════════════════════════════════

@main.group()
def node() -> None:
    """Manage ComfyUI node registrations."""


@node.command("add")
@click.option("--id", "node_id", required=True, help="Unique node identifier")
@click.option("--url", "-u", required=True, help="ComfyUI server URL (e.g. http://192.168.1.10:8188)")
@click.option("--user", default="", help="Basic-auth username")
@click.option("--password", default="", help="Basic-auth password")
@click.option("--name", default="", help="Human-readable label for this node")
def node_add(node_id: str, url: str, user: str, password: str, name: str) -> None:
    """Register or update a ComfyUI node."""
    node_db.add_node(node_id=node_id, url=url, user=user, password=password, name=name)
    click.echo(f"Node added: {name or node_id}")


@node.command("list")
def node_list() -> None:
    """List all registered nodes."""
    nodes = node_manager.list_nodes()
    if not nodes:
        click.echo("(no nodes registered)")
        return
    for i, nd in enumerate(nodes, 1):
        auth = " (auth)" if nd.get("user") else ""
        click.echo(f"  {i}. {nd['name']}  [{nd['url']}]{auth}")


@node.command("remove")
@click.argument("name_or_url")
def node_remove(name_or_url: str) -> None:
    """Remove a registered node by name or URL."""
    try:
        node_manager.remove_node(name_or_url)
        click.echo(f"Node removed: {name_or_url}")
    except NodeNotFoundError as exc:
        raise click.ClickException(str(exc))


@node.command("clear")
def node_clear() -> None:
    """Remove all registered nodes."""
    node_manager.clear_nodes()
    click.echo("All nodes removed.")


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
    ok = skip = 0

    for cf in config_files:
        path = project_root / cf
        if not path.exists():
            click.echo(f"  SKIP {cf} (not found)", err=True)
            skip += 1
            continue

        with open(path, "r", encoding="utf-8") as fh:
            entries = yaml.safe_load(fh)

        if not entries:
            continue

        for entry in entries:
            url = entry.get("url", "").strip()
            node_id = entry.get("id", "").strip()
            if not url or not node_id:
                continue
            node_db.add_node(
                node_id=node_id,
                url=url,
                user=entry.get("user", ""),
                password=entry.get("password", ""),
                name=entry.get("name", ""),
                blocking=entry.get("blocking", True),
            )
            click.echo(f"  OK   {node_id}")
            ok += 1

    click.echo(f"\nDone — {ok} imported, {skip} skipped")


# ═══════════════════════════════════════════════════════════════════
#  run  command
# ═══════════════════════════════════════════════════════════════════

@main.command("run")
@click.option(
    "--workflow-id", "-w",
    default=None,
    help="Workflow id from the database (use 'multi-comfyui-cli workflow doc' to list).",
)
@click.option(
    "--workflow-file", "-f",
    default=None,
    type=click.Path(exists=True),
    help="Path to a workflow JSON file (when not using --workflow-id).",
)
@click.option(
    "--node", "-n", "node_id",
    default=None,
    help="Node id to use (default: auto-select least busy node).",
)
@click.option(
    "--inputs", "-i",
    default="[]",
    help=(
        "JSON array of input objects.  Each object: "
        '{"type":"string|file", "value":"...", "node_title":"...", "node_field":"..."}'
    ),
)
@click.option(
    "--output-node",
    default=None,
    help="_meta.title of the output node (default: last node in workflow).",
)
def run_cmd(
    workflow_id: str | None,
    workflow_file: str | None,
    node_id: str | None,
    inputs: str,
    output_node: str | None,
) -> None:
    """Execute a workflow on a ComfyUI node."""
    if not workflow_id and not workflow_file:
        raise click.UsageError("Either --workflow-id or --workflow-file is required.")

    # -- auto-import workflows if none exist ---------------------------------
    project_root = workflow_db.find_project_root(Path.cwd())
    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM workflow").fetchone()[0]
    conn.close()
    if count == 0:
        click.echo("[auto] No workflows in database — running workflow import-all...")
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
        click.echo(f"[auto] Imported {imported} workflow(s).")

    # -- resolve workflow --------------------------------------------------
    if workflow_id:
        db_path = workflow_db.ensure_db(project_root)
        conn = workflow_db.get_connection(db_path)
        row = conn.execute(
            "SELECT workflow_config, input_node_mapping FROM workflow WHERE id = ?",
            (workflow_id,),
        ).fetchone()
        conn.close()
        if not row:
            raise click.ClickException(f"Workflow not found: {workflow_id}")
        workflow_config = json.loads(row[0])
        mapping = json.loads(row[1])
    else:
        with open(project_root / workflow_file, "r", encoding="utf-8") as fh:
            workflow_config = json.load(fh)
        mapping = {}

    # -- parse inputs (with mapping support) --------------------------------
    try:
        inputs_data: list[dict] = json.loads(inputs)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON for --inputs: {exc}")

    if not isinstance(inputs_data, list):
        raise click.ClickException("--inputs must be a JSON array")

    resolved_inputs: list[dict] = []
    for i, item in enumerate(inputs_data):
        # shortcut: {"field_name": value} → resolve via mapping
        if isinstance(item, dict) and len(item) == 1:
            key = next(iter(item))
            if key in mapping:
                info = mapping[key]
                resolved_inputs.append({
                    "type": "file" if info["value_type"] == "file" else "string",
                    "value": str(item[key]),
                    "node_title": info["node_meta_title"],
                    "node_field": info["node_input_field"],
                })
                continue

        if not isinstance(item, dict):
            raise click.ClickException(f"--inputs[{i}] must be an object")
        for key in ("type", "value", "node_title", "node_field"):
            if key not in item:
                raise click.ClickException(f"--inputs[{i}] missing required field '{key}'")
        if item["type"] not in ("string", "file"):
            raise click.ClickException(f"--inputs[{i}].type must be 'string' or 'file'")
        resolved_inputs.append(item)

    # -- auto-register local node if none exist -----------------------------
    nodes = node_db.list_nodes()
    if not nodes:
        import requests as _requests
        local_url = "http://127.0.0.1:8188"
        try:
            _r = _requests.get(f"{local_url}/system_stats", timeout=3)
            _r.raise_for_status()
        except Exception:
            raise click.ClickException(
                "No nodes registered and no local ComfyUI detected at 127.0.0.1:8188.\n"
                "Register a node first: multi-comfyui-cli node import"
            )

        click.echo(f"[auto] Local ComfyUI detected at {local_url} — running node import...")
        # default first, then user configs — so user overrides take precedence
        config_files = [
            "data/default_nodes.yaml",
            "data/nodes.yaml",
        ]
        for config_path in config_files:
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
        click.echo(f"[auto] {len(nodes)} node(s) registered.")

    # -- resolve node -------------------------------------------------------
    if node_id:
        target = next((n for n in nodes if n["id"] == node_id), None)
        if not target:
            raise click.ClickException(f"Node not found: {node_id}")
        api = node_manager.to_api(target)
    else:
        api = node_manager.select_node()

    # -- execute ------------------------------------------------------------
    try:
        rc = executor_run(
            workflow_source=workflow_config,
            api=api,
            inputs=resolved_inputs,
            output_node_title=output_node,
        )
    except ComfyUICLIError as exc:
        raise click.ClickException(str(exc))

    if rc != 0:
        sys.exit(rc)


# ═══════════════════════════════════════════════════════════════════
#  status  command
# ═══════════════════════════════════════════════════════════════════

@main.command("status")
@click.option(
    "--url", "-u",
    default="",
    help="Check a specific URL instead of all registered nodes.",
)
def status_cmd(url: str) -> None:
    """Show queue status of registered nodes."""
    if url:
        api = ComfyUIApi(url)
        _print_node_status(url, api)
    else:
        nodes = node_manager.list_nodes()
        if not nodes:
            click.echo("(no nodes registered)")
            return
        for nd in nodes:
            name = nd["name"]
            api = ComfyUIApi(nd["url"], nd.get("user", ""), nd.get("password", ""))
            _print_node_status(name, api)


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
    click.echo(f"OK — upserted workflow '{meta['id']}'")


@workflow.command("import-all")
@click.option(
    "--meta-dir", "-d",
    default="data/default_workflows/meta",
    help="Path to the meta YAML directory.",
)
def workflow_import_all(meta_dir: str) -> None:
    """Batch-import meta YAML + workflow JSON files from the data dir.

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

    ok = skip = 0

    def _import_meta_dir(meta_path: Path, wf_dir: Path, label: str) -> None:
        nonlocal ok, skip
        if not meta_path.is_dir():
            return
        for yf in sorted(meta_path.glob("*.yaml")):
            rel_path = str(yf.relative_to(project_root))
            try:
                meta, wf_config = workflow_db.load_meta_and_workflow(project_root, rel_path)
                if meta.get("status") == "disabled":
                    click.echo(f"  SKIP {meta['id']} (status=disabled)")
                    skip += 1
                    continue
                workflow_db.upsert_workflow(conn, meta, wf_config)
                click.echo(f"  OK   {meta['id']} ({label})")
                ok += 1
            except FileNotFoundError as exc:
                click.echo(f"  SKIP {yf.name}: {exc}", err=True)
                skip += 1

        # import orphan JSON files (no matching meta)
        if wf_dir.is_dir():
            for jf in sorted(wf_dir.glob("*.json")):
                stem = jf.stem
                has_meta = (meta_path / f"{stem}_meta.yaml").exists() or (meta_path / f"{stem}.yaml").exists()
                if has_meta:
                    continue
                rel_path = str(jf.relative_to(project_root))
                try:
                    meta, wf_config = workflow_db.load_workflow_direct(project_root, rel_path)
                    if meta.get("status") == "disabled":
                        click.echo(f"  SKIP {meta['id']} (status=disabled)")
                        skip += 1
                        continue
                    workflow_db.upsert_workflow(conn, meta, wf_config)
                    click.echo(f"  OK   {meta['id']} (no meta, {label})")
                    ok += 1
                except FileNotFoundError as exc:
                    click.echo(f"  SKIP {jf.name}: {exc}", err=True)
                    skip += 1

    # phase 1 — default data first
    _import_meta_dir(default_meta, default_wf_dir, "default")

    # phase 2 — non-default data second (can override defaults)
    _import_meta_dir(user_meta, user_wf_dir, "user")

    conn.commit()
    conn.close()
    click.echo(f"\nDone — {ok} upserted, {skip} skipped")


@workflow.command("doc")
def workflow_doc() -> None:
    """Generate doc/workflow.md from the workflow table."""
    project_root = workflow_db.find_project_root(Path.cwd())
    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)

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
        lines.append(f"| {id_} | {type_} | {purpose} | {output_type} |")

    lines.extend(["", "## Input Fields", ""])

    for row in rows:
        id_, type_, purpose, output_type, mapping_json = row
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
    click.echo(f"OK — wrote {len(rows)} workflows to {doc_path}")


def _print_node_status(label: str, api: ComfyUIApi) -> None:
    try:
        q = api.get_queue()
        running = len(q.get("queue_running", []))
        pending = len(q.get("queue_pending", []))
        click.echo(f"  {label}: running={running}  pending={pending}")
    except ComfyUICLIError:
        click.echo(f"  {label}: UNREACHABLE")
