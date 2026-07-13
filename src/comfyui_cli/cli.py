"""
CLI entry point — ``comfyui-cli`` command.
"""

from __future__ import annotations

import json
import sys

import click

from .api import ComfyUIApi
from .exceptions import ComfyUICLIError, NodeNotFoundError
from .executor import run as executor_run
from . import node_manager


@click.group()
@click.version_option(version="1.0.0", prog_name="comfyui-cli")
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

        comfyui-cli node add --url URL [--user USER --password PASS]

    \b
    Examples:
      comfyui-cli run -w workflow.json
      comfyui-cli run -w workflow.json -i '[{"type":"file","value":"./input.png","node_title":"Load Image","node_field":"image"}]'
      comfyui-cli run -w workflow.json -i '[{"type":"string","value":"a cat","node_title":"Prompt","node_field":"text"}]'
      comfyui-cli run -w workflow.json --output-node "Save Image"
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


def _print_node_status(label: str, api: ComfyUIApi) -> None:
    try:
        q = api.get_queue()
        running = len(q.get("queue_running", []))
        pending = len(q.get("queue_pending", []))
        click.echo(f"  {label}: running={running}  pending={pending}")
    except ComfyUICLIError:
        click.echo(f"  {label}: UNREACHABLE")
