"""
Executor — the core run pipeline: validate, upload assets, submit, poll, collect.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from requests.compat import urlencode

from .api import ComfyUIApi
from .exceptions import ExecutionError, WorkflowError
from .workflow import Workflow


class InputItem:
    """Single workflow input — either a string value or a file to upload."""

    def __init__(self, type: str, value: str, node_title: str, node_field: str) -> None:
        if type not in ("string", "file"):
            raise ValueError(f"Invalid input type '{type}', must be 'string' or 'file'")
        self.type = type
        self.value = value
        self.node_title = node_title
        self.node_field = node_field


def run(
    workflow_source: str | Path | dict,
    api: ComfyUIApi,
    *,
    inputs: list[dict] | None = None,
    output_node_title: str | None = None,
    output_type: str = "",
) -> int:
    """Execute a workflow on *api*, blocking until completion.

    Parameters
    ----------
    workflow_source:
        Either a path to a ComfyUI API-format JSON file, or a workflow dict.
    api:
        *ComfyUIApi* client pointing at the target node.
    inputs:
        List of input dicts.
    output_node_title:
        If set, only this node's outputs are reported.
    output_type:
        ``image`` / ``video`` / ``audio`` — filters collected outputs.
        When empty, all outputs are collected from all nodes.

    Returns
    -------
    0 on success, 1 on failure.
    """
    # 1. Load workflow
    if isinstance(workflow_source, dict):
        wf = Workflow(config=workflow_source)
    else:
        wf_path = Path(workflow_source)
        if not wf_path.exists():
            raise WorkflowError(f"Workflow file not found: {wf_path}")
        wf = Workflow(wf_path)

    # 2. Apply inputs
    for item in (inputs or []):
        inp = InputItem(
            type=item["type"],
            value=item["value"],
            node_title=item["node_title"],
            node_field=item["node_field"],
        )
        if inp.type == "file":
            ap = Path(inp.value)
            if not ap.exists():
                raise FileNotFoundError(f"File not found: {ap}")
            print(f"[upload] {ap.name} ...")
            result = api.upload_file(str(ap))
            uploaded_name = result["name"]
            uploaded_subfolder = result.get("subfolder", "")
            composed = f"{uploaded_subfolder}/{uploaded_name}" if uploaded_subfolder else uploaded_name
            wf.set_node_param(inp.node_title, inp.node_field, composed)
            print(f"[upload] {ap.name} -> {composed}")
        else:
            wf.set_node_param(inp.node_title, inp.node_field, inp.value)
            print(f"[input] {inp.node_title}.{inp.node_field} = {inp.value[:80]}{'...' if len(inp.value) > 80 else ''}")

    # 3. Determine output node (if specified)
    output_nid = ""
    if output_node_title:
        output_nid = wf.get_node_id(output_node_title)
        print(f"[run] Output node: '{output_node_title}' ({output_nid})")

    print(f"[run] Submitting workflow to {api.url} ...")

    # 4. Submit & wait
    try:
        prompt_id = api.queue_and_wait(wf)
    except ExecutionError as exc:
        print(f"[error] Workflow execution failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[error] Unexpected error during execution: {exc}", file=sys.stderr)
        return 1

    print(f"[run] Execution completed.  prompt_id={prompt_id}")

    # 5. Collect outputs — scan all nodes, filter by output_type
    try:
        files = api.fetch_outputs(prompt_id, output_nid)
    except Exception as exc:
        print(f"[error] Failed to fetch outputs: {exc}", file=sys.stderr)
        return 1

    if output_type:
        kind_map = {
            "image": {"image"},
            "video": {"video", "gif"},
            "audio": {"audio"},
        }
        allowed = kind_map.get(output_type, set())
        files = [f for f in files if f["kind"] in allowed]

    if not files:
        print(f"[run] No '{output_type}' output files produced.", file=sys.stderr)
        return 1

    print(f"\n[output] {len(files)} file(s) generated:\n")
    for f in files:
        params = urlencode(
            {"filename": f["filename"], "subfolder": f["subfolder"], "type": f["type"]}
        )
        url = f"{api.url}/view?{params}"
        print(f"  {f['kind']:6s}  {url}")

    return 0
