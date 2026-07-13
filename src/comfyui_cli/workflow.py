"""
Workflow wrapper — load ComfyUI API-format JSON and manipulate node parameters.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Workflow(dict):
    """Wraps a ComfyUI API-format workflow JSON file.

    Workflow JSON structure::

        {
          "1": {"inputs": {"text": "..."}, "class_type": "CLIPTextEncode", "_meta": {"title": "Prompt"}},
          "2": {"inputs": {"image": "..."}, "class_type": "LoadImage", "_meta": {"title": "Load Image"}},
          ...
        }

    Parameters are addressed by node *_meta.title* (the friendly name shown in
    the ComfyUI UI) rather than by numeric node ID.
    """

    def __init__(self, path: str | Path) -> None:
        raw = Path(path).read_text(encoding="utf-8")
        super().__init__(json.loads(raw))
        self._source = Path(path)

    # ── node look-up ──────────────────────────────────────────────

    def _nodes_by_title(self, title: str) -> list[tuple[str, dict]]:
        return [(nid, n) for nid, n in self.items() if self._title(n) == title]

    @staticmethod
    def _title(node: dict) -> str:
        return node.get("_meta", {}).get("title", "")

    # ── public API ────────────────────────────────────────────────

    def get_node_id(self, title: str) -> str:
        for nid, node in self.items():
            if self._title(node) == title:
                return nid
        raise KeyError(f"No node with title '{title}'")

    def set_node_param(self, title: str, param: str, value: Any) -> None:
        updated = 0
        for _nid, node in self._nodes_by_title(title):
            if param in node.get("inputs", {}):
                node["inputs"][param] = value
                updated += 1
        if updated == 0:
            raise KeyError(f"No node with title='{title}' has input param '{param}'")

    def get_node_param(self, title: str, param: str) -> Any:
        for _nid, node in self._nodes_by_title(title):
            if param in node.get("inputs", {}):
                return node["inputs"][param]
        raise KeyError(f"No node with title='{title}' has input param '{param}'")

    def list_node_titles(self) -> list[str]:
        seen: list[str] = []
        for node in self.values():
            t = self._title(node)
            if t and t not in seen:
                seen.append(t)
        return seen

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self, indent=2, ensure_ascii=False), encoding="utf-8")
