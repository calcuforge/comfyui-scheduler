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


def run(
    workflow_path: str | Path,
    api: ComfyUIApi,
    *,
    assets: list[str | Path] | None = None,
    asset_node_title: str = "Load Image",
    asset_param: str = "image",
    output_node_title: str | None = None,
) -> int:
    """Execute *workflow_path* on *api*, blocking until completion.

    Parameters
    ----------
    workflow_path:
        Path to a ComfyUI API-format JSON workflow file.
    api:
        *ComfyUIApi* client pointing at the target node.
    assets:
        Local file paths to upload and bind into the workflow (images, videos, masks).
    asset_node_title:
        *_meta.title* of the node to receive uploaded assets (default ``"Load Image"``).
    asset_param:
        Input parameter name on the asset node (default ``"image"``).
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

    # 2. Upload assets
    assets = assets or []
    for asset_path in assets:
        ap = Path(asset_path)
        if not ap.exists():
            raise FileNotFoundError(f"Asset not found: {ap}")

        ext = ap.suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".mask"}:
            print(f"[upload] {ap.name} ...")
            result = api.upload_file(str(ap))
            uploaded_name = result["name"]
            uploaded_subfolder = result.get("subfolder", "")
            # ComfyUI expects "subfolder/filename" or just "filename"
            if uploaded_subfolder:
                wf.set_node_param(asset_node_title, asset_param, f"{uploaded_subfolder}/{uploaded_name}")
            else:
                wf.set_node_param(asset_node_title, asset_param, uploaded_name)
            print(f"[upload] {ap.name} -> {uploaded_subfolder}/{uploaded_name}")
        else:
            print(f"[upload] {ap.name} (video/other) ...")
            result = api.upload_file(str(ap))
            uploaded_name = result["name"]
            uploaded_subfolder = result.get("subfolder", "")
            if uploaded_subfolder:
                wf.set_node_param(asset_node_title, asset_param, f"{uploaded_subfolder}/{uploaded_name}")
            else:
                wf.set_node_param(asset_node_title, asset_param, uploaded_name)
            print(f"[upload] {ap.name} -> {uploaded_subfolder}/{uploaded_name}")

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
