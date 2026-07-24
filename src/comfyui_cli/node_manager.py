"""Node manager — thin wrapper over SQLite-backed ``node_db``."""

from __future__ import annotations

from typing import Any

from .api import ComfyUIApi
from .node_db import add_node as _add_node
from .node_db import clear_nodes as _clear_nodes
from .node_db import list_nodes as _list_nodes
from .node_db import remove_node as _remove_node
from .node_db import NodeNotFoundError

# re-export for callers that still import from here
__all__ = [
    "add_node",
    "clear_nodes",
    "list_nodes",
    "remove_node",
    "select_node",
    "to_api",
    "NodeNotFoundError",
]


def add_node(url: str, user: str = "", password: str = "", name: str = "") -> None:
    _add_node(url, user=user, password=password, name=name)


def list_nodes() -> list[dict[str, Any]]:
    return _list_nodes()


def remove_node(name_or_url: str) -> None:
    _remove_node(name_or_url)


def clear_nodes() -> None:
    _clear_nodes()


def select_node() -> ComfyUIApi:
    """Return an API client for the most idle node."""
    nodes = list_nodes()
    if not nodes:
        raise NodeNotFoundError(
            "No nodes registered.  Use 'multi-comfyui-cli node add --url URL' first."
        )

    best: ComfyUIApi | None = None
    best_size = 9999
    for nd in nodes:
        api = ComfyUIApi(nd["url"], nd.get("user", ""), nd.get("password", ""))
        size = api.queue_size()
        if size < best_size:
            best_size = size
            best = api

    if best is None:
        raise NodeNotFoundError("No reachable ComfyUI node found.")
    return best


def to_api(node: dict[str, Any]) -> ComfyUIApi:
    """Create an API client from a stored node dict."""
    return ComfyUIApi(node["url"], node.get("user", ""), node.get("password", ""))
