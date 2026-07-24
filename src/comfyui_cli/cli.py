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
@click.option("--url", "-u", required=True, help="ComfyUI server URL (e.g. http://192.168.1.10:8188)")
@click.option("--user", default="", help="Basic-auth username")
@click.option("--password", default="", help="Basic-auth password")
@click.option("--name", default="", help="Human-readable label for this node")
def node_add(url: str, user: str, password: str, name: str) -> None:
    """Register a new ComfyUI node."""
    try:
        node_manager.add_node(url, user=user, password=password, name=name)
        click.echo(f"Node added: {name or url}")
    except ValueError as exc:
        raise click.ClickException(str(exc))


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
            nodes = yaml.safe_load(fh)

        if not nodes:
            continue

        for entry in nodes:
            url = entry.get("url", "").strip()
            if not url:
                continue
            try:
                node_manager.add_node(
                    url=url,
                    user=entry.get("user", ""),
                    password=entry.get("password", ""),
                    name=entry.get("name", ""),
                )
                click.echo(f"  OK   {entry.get('name') or url}")
                ok += 1
            except ValueError:
                click.echo(f"  SKIP {url} (already registered)")
                skip += 1

    click.echo(f"\nDone — {ok} imported, {skip} skipped")


# ═══════════════════════════════════════════════════════════════════
#  run  command
# ═══════════════════════════════════════════════════════════════════

@main.command("run")
@click.option(
    "--workflow", "-w",
    required=True,
    type=click.Path(exists=True),
    help="Path to the ComfyUI API-format workflow JSON file.",
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
    workflow: str,
    inputs: str,
    output_node: str | None,
) -> None:
    """Execute a workflow on a ComfyUI node.

    Uses locally registered nodes with load balancing (least busy node
    is selected automatically).  Credentials are taken from the stored
    node configuration — register nodes first with:

        multi-comfyui-cli node add --url URL [--user USER --password PASS]

    \b
    Examples:
      multi-comfyui-cli run -w workflow.json
      multi-comfyui-cli run -w workflow.json -i '[{"type":"file","value":"./input.png","node_title":"Load Image","node_field":"image"}]'
      multi-comfyui-cli run -w workflow.json -i '[{"type":"string","value":"a cat","node_title":"Prompt","node_field":"text"}]'
      multi-comfyui-cli run -w workflow.json --output-node "Save Image"
    """
    try:
        inputs_data = json.loads(inputs)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON for --inputs: {exc}")

    if not isinstance(inputs_data, list):
        raise click.ClickException("--inputs must be a JSON array")

    for i, item in enumerate(inputs_data):
        if not isinstance(item, dict):
            raise click.ClickException(f"--inputs[{i}] must be an object")
        for key in ("type", "value", "node_title", "node_field"):
            if key not in item:
                raise click.ClickException(f"--inputs[{i}] missing required field '{key}'")
        if item["type"] not in ("string", "file"):
            raise click.ClickException(f"--inputs[{i}].type must be 'string' or 'file', got '{item['type']}'")

    api = node_manager.select_node()

    try:
        rc = executor_run(
            workflow_path=workflow,
            api=api,
            inputs=inputs_data,
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
    """Batch-import meta YAML + workflow JSON files from the data dir."""
    project_root = workflow_db.find_project_root(Path.cwd())
    meta_path = project_root / meta_dir
    workflow_dir = project_root / "data" / "default_workflows" / "workflow"

    if not meta_path.is_dir():
        raise click.ClickException(f"Meta directory not found: {meta_path}")

    yaml_files = sorted(meta_path.glob("*.yaml"))

    db_path = workflow_db.ensure_db(project_root)
    conn = workflow_db.get_connection(db_path)

    ok = skip = 0

    # phase 1 — import all meta YAML files
    for yf in yaml_files:
        rel_path = str(yf.relative_to(project_root))
        try:
            meta, wf_config = workflow_db.load_meta_and_workflow(project_root, rel_path)
            if meta.get("status") == "disabled":
                click.echo(f"  SKIP {meta['id']} (status=disabled)")
                skip += 1
                continue
            workflow_db.upsert_workflow(conn, meta, wf_config)
            click.echo(f"  OK   {meta['id']}")
            ok += 1
        except FileNotFoundError as exc:
            click.echo(f"  SKIP {yf.name}: {exc}", err=True)
            skip += 1

    # phase 2 — import orphan JSON files (no matching meta)
    if workflow_dir.is_dir():
        for jf in sorted(workflow_dir.glob("*.json")):
            stem = jf.stem
            has_meta = (meta_path / f"{stem}_meta.yaml").exists() or (meta_path / f"{stem}.yaml").exists()
            if has_meta:
                continue  # already handled in phase 1
            rel_path = str(jf.relative_to(project_root))
            try:
                meta, wf_config = workflow_db.load_workflow_direct(project_root, rel_path)
                if meta.get("status") == "disabled":
                    click.echo(f"  SKIP {meta['id']} (status=disabled)")
                    skip += 1
                    continue
                workflow_db.upsert_workflow(conn, meta, wf_config)
                click.echo(f"  OK   {meta['id']} (no meta)")
                ok += 1
            except FileNotFoundError as exc:
                click.echo(f"  SKIP {jf.name}: {exc}", err=True)
                skip += 1

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
