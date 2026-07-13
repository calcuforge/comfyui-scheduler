"""
Node manager — persist registered ComfyUI nodes and select an idle one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .api import ComfyUIApi
from .exceptions import NodeNotFoundError

APP_DIR = Path.home() / ".comfyui-cli"
NODES_FILE = APP_DIR / "nodes.json"


def _ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def _load_nodes() -> list[dict[str, Any]]:
    if not NODES_FILE.exists():
        return []
    return json.loads(NODES_FILE.read_text(encoding="utf-8"))


def _save_nodes(nodes: list[dict[str, Any]]) -> None:
    _ensure_app_dir()
    NODES_FILE.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")


# ── public CRUD ───────────────────────────────────────────────────

def list_nodes() -> list[dict[str, Any]]:
    return _load_nodes()


def add_node(url: str, user: str = "", password: str = "", name: str = "") -> None:
    nodes = _load_nodes()

    for n in nodes:
        if n["url"].rstrip("/") == url.rstrip("/"):
            raise ValueError(f"Node already registered: {url}")

    nodes.append(
        {
            "name": name or url.rstrip("/"),
            "url": url.rstrip("/"),
            "user": user,
            "password": password,
        }
    )
    _save_nodes(nodes)


def remove_node(name_or_url: str) -> None:
    nodes = _load_nodes()
    key = name_or_url.rstrip("/")
    filtered = [n for n in nodes if n["url"] != key and n["name"] != key]
    if len(filtered) == len(nodes):
        raise NodeNotFoundError(f"No node matching '{name_or_url}'.")
    _save_nodes(filtered)


def clear_nodes() -> None:
    _save_nodes([])


# ── selection ─────────────────────────────────────────────────────

def select_node() -> ComfyUIApi:
    """Return an API client for the most idle node.  Raises NodeNotFoundError
    if no nodes are registered (single-node users can still pass ``--url``)."""
    nodes = _load_nodes()
    if not nodes:
        raise NodeNotFoundError(
            "No nodes registered.  Use 'comfyui-cli node add --url URL' first."
        )

    best: ComfyUIApi | None = None
    best_size = 9999
    best_candidate = None

    for nd in nodes:
        api = ComfyUIApi(nd["url"], nd.get("user", ""), nd.get("password", ""))
        size = api.queue_size()
        if size < best_size:
            best_size = size
            best = api
            best_candidate = nd

    if best is None:
        raise NodeNotFoundError("No reachable ComfyUI node found.")
    return best


def to_api(node: dict[str, Any]) -> ComfyUIApi:
    """Create an API client from a stored node dict."""
    return ComfyUIApi(node["url"], node.get("user", ""), node.get("password", ""))
