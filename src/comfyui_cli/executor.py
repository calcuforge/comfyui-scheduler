"""
Executor — the core run pipeline: validate, upload assets, submit, poll, collect.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from requests.compat import urlencode

from . import output
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
) -> dict:
    """Execute a workflow on *api*, blocking until completion.

    Returns a dict with keys ``files`` and ``prompt_id``.
    Raises ``WorkflowError`` / ``ExecutionError`` on failure.
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
            output.debug(f"[upload] {ap.name} ...")
            result = api.upload_file(str(ap))
            uploaded_name = result["name"]
            uploaded_subfolder = result.get("subfolder", "")
            composed = f"{uploaded_subfolder}/{uploaded_name}" if uploaded_subfolder else uploaded_name
            wf.set_node_param(inp.node_title, inp.node_field, composed)
            output.debug(f"[upload] {ap.name} -> {composed}")
        else:
            wf.set_node_param(inp.node_title, inp.node_field, inp.value)
            val_str = str(inp.value)
            output.debug(
                f"[input] {inp.node_title}.{inp.node_field} = "
                f"{val_str[:80]}{'...' if len(val_str) > 80 else ''}"
            )

    # 3. Determine output node (if specified)
    output_nid = ""
    if output_node_title:
        output_nid = wf.get_node_id(output_node_title)
        output.debug(f"[run] Output node: '{output_node_title}' ({output_nid})")

    output.debug(f"[run] Submitting workflow to {api.url} ...")

    # 4. Submit & wait
    try:
        prompt_id = api.queue_and_wait(wf)
    except ExecutionError as exc:
        raise ExecutionError(f"Workflow execution failed: {exc}")
    except Exception as exc:
        raise ExecutionError(f"Unexpected error during execution: {exc}")

    output.debug(f"[run] Execution completed.  prompt_id={prompt_id}")

    # 5. Collect outputs — scan all nodes, filter by output_type
    files = api.fetch_outputs(prompt_id, output_nid)
    kinds_seen = {f["kind"] for f in files}
    output.debug(f"[run] Raw output kinds found: {kinds_seen or '(none)'}")

    if output_type:
        kind_map = {
            "image": {"image"},
            "video": {"video", "gif"},
            "audio": {"audio"},
        }
        allowed = kind_map.get(output_type, set())
        matched = [f for f in files if f["kind"] in allowed]
        if matched:
            files = matched
        else:
            output.debug(f"[run] No files matched output_type='{output_type}', falling back to all files")
        output.debug(f"[run] Final file count: {len(files)}")

    if not files:
        raise ExecutionError(f"No output files produced.")

    # Build full URLs
    result_files = []
    for f in files:
        params = urlencode(
            {"filename": f["filename"], "subfolder": f["subfolder"], "type": f["type"]}
        )
        url = f"{api.url}/view?{params}"
        result_files.append({
            "kind": f["kind"],
            "url": url,
            "filename": f["filename"],
        })
        output.debug(f"  {f['kind']:6s}  {url}")

    return {"files": result_files, "prompt_id": prompt_id}
