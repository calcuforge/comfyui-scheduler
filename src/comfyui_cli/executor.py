"""
Executor — the core run pipeline: validate, upload assets, submit, poll, collect.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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
    workflow_path: str | Path,
    api: ComfyUIApi,
    *,
    inputs: list[dict] | None = None,
    output_node_title: str | None = None,
) -> int:
    """Execute *workflow_path* on *api*, blocking until completion.

    Parameters
    ----------
    workflow_path:
        Path to a ComfyUI API-format JSON workflow file.
    api:
        *ComfyUIApi* client pointing at the target node.
    inputs:
        List of input dicts, each with:
        - type: ``"string"`` | ``"file"``
        - value: the string content or file path
        - node_title: *_meta.title* of the target node
        - node_field: input parameter name on that node
    output_node_title:
        If set, only this node's outputs are reported.  Otherwise the *last* node
        in the workflow is treated as the output node.

    Returns
    -------
    0 on success, 1 on failure.
    """
    # 1. Load workflow
    wf_path = Path(workflow_path)
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

    # 3. Determine output node
    if output_node_title:
        output_nid = wf.get_node_id(output_node_title)
    else:
        # Last node in the dict is the output node (convention)
        output_nid = list(wf.keys())[-1]
        output_node_title = wf._title(wf[output_nid]) or output_nid

    print(f"[run] Submitting workflow to {api.url} ...")
    print(f"[run] Output node: '{output_node_title}' ({output_nid})")

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

    # 5. Collect outputs
    try:
        files = api.fetch_outputs(prompt_id, output_nid)
    except Exception as exc:
        print(f"[error] Failed to fetch outputs: {exc}", file=sys.stderr)
        return 1

    if not files:
        print("[run] No output files produced.", file=sys.stderr)
        return 1

    print(f"\n[output] {len(files)} file(s) generated:\n")
    for f in files:
        from requests.compat import urlencode
        params = urlencode(
            {"filename": f["filename"], "subfolder": f["subfolder"], "type": f["type"]}
        )
        url = f"{api.url}/view?{params}"
        print(f"  {f['kind']:6s}  {url}")

    return 0
