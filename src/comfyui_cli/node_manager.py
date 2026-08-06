"""Node manager — thin wrapper over SQLite-backed ``node_db``."""

from __future__ import annotations

import os
import time
from typing import Any

from . import output
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


def add_node(url: str, user: str = "", password: str = "", name: str = "", blocking: bool = True) -> None:
    _add_node(node_id=name or url.rstrip("/"), url=url, user=user, password=password, name=name, blocking=blocking)


def list_nodes() -> list[dict[str, Any]]:
    return _list_nodes()


def remove_node(name_or_url: str) -> None:
    _remove_node(name_or_url)


def clear_nodes() -> None:
    _clear_nodes()


def select_node(task_id: str = "") -> ComfyUIApi:
    """Select a node with scheduling logic.

    Rules (in priority order):
    1. If any blocking node is idle (queue_running == 0), pick it.
    2. Otherwise, if any non-blocking proxy node exists, pick it (it exposes
       only POST /execute and handles concurrency internally, so it is always
       eligible).
    3. Otherwise (all nodes are blocking and busy), wait for one to become idle.
    """
    nodes = list_nodes()
    if not nodes:
        raise NodeNotFoundError(
            "No nodes registered.  Use 'comfyui-scheduler node add --url URL' first."
        )

    while True:
        idle: list[tuple[ComfyUIApi, dict]] = []
        nonblocking: list[tuple[ComfyUIApi, dict]] = []
        reachable = 0

        for nd in nodes:
            url = os.path.expandvars(nd["url"])
            blocking = bool(nd.get("blocking", True))
            api = ComfyUIApi(url, nd.get("user", ""), nd.get("password", ""),
                              task_id=task_id, blocking=blocking)

            # Non-blocking proxy nodes don't speak the ComfyUI REST protocol —
            # only POST /execute.  Treat them as always-eligible and skip the
            # /queue probe (it would 404 and mark the node unreachable).
            if not blocking:
                nonblocking.append((api, nd))
                reachable += 1
                continue

            try:
                q = api.get_queue()
                running = len(q.get("queue_running", []))
                reachable += 1
            except Exception:
                output.debug(f"[scheduler] node '{nd['name']}' ({url}) is unreachable")
                continue

            if running == 0:
                idle.append((api, nd))

        if reachable == 0:
            raise NodeNotFoundError(
                "No ComfyUI node is reachable. Check the server URLs and try again."
            )

        if idle:
            best = min(idle, key=lambda x: len(x[0].get_queue().get("queue_pending", [])))
            output.debug(f"[scheduler] selected idle node '{best[1]['name']}' ({best[1]['url']})")
            return best[0]

        if nonblocking:
            best = nonblocking[0]
            output.debug(
                f"[scheduler] selected non-blocking proxy '{best[1]['name']}' "
                f"({best[1]['url']})"
            )
            return best[0]

        output.debug("[scheduler] all nodes busy (blocking=true), waiting for an idle node...")
        time.sleep(5)


def to_api(node: dict[str, Any], task_id: str = "") -> ComfyUIApi:
    """Create an API client from a stored node dict."""
    url = os.path.expandvars(node["url"])
    return ComfyUIApi(url, node.get("user", ""), node.get("password", ""), task_id=task_id)
