"""
Executor — the core run pipeline: validate, upload assets, submit, poll, collect.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import requests
from requests.compat import urlencode, urljoin

from . import output, workflow_db
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

    For non-blocking proxy nodes (``api.blocking == False``), delegates to
    ``run_via_proxy`` which posts a single multipart request to /execute —
    the proxy bundles upload + submit + poll + download in one call, so the
    native ComfyUI endpoints (/prompt, /ws, /history, /view, /upload/*) are
    never touched.
    """
    if not getattr(api, "blocking", True):
        return run_via_proxy(
            workflow_source, api,
            inputs=inputs, output_type=output_type,
        )
    return _run_native(
        workflow_source, api,
        inputs=inputs,
        output_node_title=output_node_title,
        output_type=output_type,
    )


def _run_native(
    workflow_source: str | Path | dict,
    api: ComfyUIApi,
    *,
    inputs: list[dict] | None = None,
    output_node_title: str | None = None,
    output_type: str = "",
) -> dict:
    """Execute a workflow against a native ComfyUI node (blocking path)."""
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

    # 5. Text output — fetch from history and persist to a txt file
    if output_type == "text":
        text = api.fetch_text(prompt_id, output_nid)
        if text:
            path = _output_dir() / f"{prompt_id}.txt"
            path.write_text(text, encoding="utf-8")
            output.debug(f"[run] Text output saved -> {path}")
            return {
                "files": [{
                    "kind": "text",
                    "url": f"file://{path.as_posix()}",
                    "filename": path.name,
                    "path": str(path),
                }],
                "prompt_id": prompt_id,
                "text": text,
            }
        output.debug("[run] No text output found in history")

    # 6. Collect outputs — scan all nodes, filter by output_type
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
        raise ExecutionError("No output files produced.")

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


# ── non-blocking proxy path ────────────────────────────────────────────────

_OUTPUT_EXT = {
    "image": "png",
    "video": "mp4",
    "audio": "wav",
}

_CD_FILENAME_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)


def _parse_content_disposition_filename(value: str | None) -> str | None:
    if not value:
        return None
    m = _CD_FILENAME_RE.search(value)
    return m.group(1) if m else None


def _output_dir() -> Path:
    project_root = workflow_db.find_project_root(Path.cwd())
    out_dir = project_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _build_multipart_body(
    fields: dict[str, tuple[str | None, str | bytes]]
) -> tuple[bytes, str]:
    """Minimal multipart/form-data encoder.

    ``fields`` maps name → (filename_or_None, value).  Text values are UTF-8
    encoded.  Always emits multipart/form-data regardless of whether file
    fields are present — requests falls back to urlencoding when ``files`` is
    empty, which the /execute proxy rejects.
    """
    boundary = f"----comfyui-scheduler-{uuid.uuid4().hex}"
    crlf = b"\r\n"
    parts: list[bytes] = []
    for name, (filename, value) in fields.items():
        parts.append(f"--{boundary}".encode("utf-8") + crlf)
        if filename is None:
            parts.append(
                f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
                + crlf + crlf
            )
        else:
            parts.append(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
                .encode("utf-8")
                + crlf + b"Content-Type: application/octet-stream" + crlf + crlf
            )
        v = value.encode("utf-8") if isinstance(value, str) else value
        parts.append(v + crlf)
    parts.append(f"--{boundary}--".encode("utf-8") + crlf)
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def run_via_proxy(
    workflow_source: str | Path | dict,
    api: ComfyUIApi,
    *,
    inputs: list[dict] | None = None,
    output_type: str = "",
) -> dict:
    """Execute a workflow against a non-blocking proxy node via POST /execute.

    The proxy exposes a single endpoint that bundles: file upload to ComfyUI,
    workflow_api_json submission, blocking poll for completion, and download of
    the produced file.  No native ComfyUI endpoints are used by the scheduler.

    Request (multipart/form-data):
      - file_mapping: JSON string — {form_field_name: {node_input_field, node_meta_title}}
      - workflow_api_json: JSON string — workflow JSON with all non-file fields filled in
      - output_type: string — expected artifact kind (image / video / audio), used by
        the proxy to decide which output node to download
      - <form_field_name>...: file blobs (one per entry in file_mapping)

    Response:
      - 200: raw file bytes of the produced artifact (Content-Disposition may
             carry a filename hint)
      - 500: JSON {"status":"error","msg":"..."}
    """
    # 1. Load workflow
    if isinstance(workflow_source, dict):
        wf = Workflow(config=workflow_source)
    else:
        wf_path = Path(workflow_source)
        if not wf_path.exists():
            raise WorkflowError(f"Workflow file not found: {wf_path}")
        wf = Workflow(wf_path)

    # 2. Partition inputs: string values go straight into the workflow JSON;
    #    file values are stashed for the proxy to upload & splice in.
    file_inputs: list[tuple[str, InputItem]] = []  # (form_field_name, item)
    next_file_idx = 0

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
            next_file_idx += 1
            form_field = f"file{next_file_idx}"
            file_inputs.append((form_field, inp))
            output.debug(f"[proxy] staged {ap.name} as {form_field} -> "
                         f"{inp.node_title}.{inp.node_field}")
        else:
            wf.set_node_param(inp.node_title, inp.node_field, inp.value)
            val_str = str(inp.value)
            output.debug(
                f"[input] {inp.node_title}.{inp.node_field} = "
                f"{val_str[:80]}{'...' if len(val_str) > 80 else ''}"
            )

    # 3. Build multipart payload (always multipart/form-data, even when no
    #    file fields are present — requests would otherwise urlencode).
    file_mapping = {
        field: {
            "node_input_field": inp.node_field,
            "node_meta_title": inp.node_title,
        }
        for field, inp in file_inputs
    }

    form_fields: dict[str, tuple[str | None, str | bytes]] = {
        "file_mapping": (None, json.dumps(file_mapping, ensure_ascii=False)),
        "workflow_api_json": (None, json.dumps(wf, ensure_ascii=False)),
        "output_type": (None, output_type or ""),
    }
    for field, inp in file_inputs:
        local_path = Path(inp.value)
        with open(local_path, "rb") as fh:
            form_fields[field] = (local_path.name, fh.read())

    body, content_type = _build_multipart_body(form_fields)

    execute_url = urljoin(api.url, "/execute")
    output.debug(f"[proxy] POST {execute_url}  "
                 f"files={list(file_mapping)} workflow_nodes={len(wf)}")

    # 4. Single blocking call
    try:
        r = api._session.post(
            execute_url,
            data=body,
            headers={"Content-Type": content_type},
            auth=api.auth,
            stream=True,
        )
    except requests.RequestException as exc:
        raise ExecutionError(f"/execute request failed: {exc}") from exc

    if r.status_code == 500:
        try:
            err = r.json()
            msg = err.get("msg") or err.get("message") or r.text
        except ValueError:
            msg = r.text or "(no error body)"
        raise ExecutionError(f"/execute failed: {msg}")

    if r.status_code != 200:
        raise ExecutionError(
            f"/execute returned {r.status_code} {r.reason}: {r.text[:500]}"
        )

    # 5. Text output — the proxy returns the text directly in the body
    if output_type == "text":
        text = r.content.decode("utf-8", errors="replace")
        output.debug(f"[proxy] text output ({len(text)} chars)")
        return {"files": [], "prompt_id": "", "text": text}

    # 6. Save returned file bytes to a local output dir
    cd = r.headers.get("Content-Disposition")
    filename = _parse_content_disposition_filename(cd)
    expected_ext = _OUTPUT_EXT.get(output_type, "")

    if not filename:
        # No filename hint at all — generate one
        ext = expected_ext or "bin"
        filename = f"{uuid.uuid4().hex}.{ext}"
    else:
        filename = os.path.basename(filename) or f"{uuid.uuid4().hex}.bin"
        # Ensure the extension matches the declared output_type.  The proxy
        # currently returns a bare "comfyui_output" name without an extension.
        _, existing_ext = os.path.splitext(filename)
        if expected_ext and existing_ext.lstrip(".").lower() != expected_ext:
            filename = f"{filename}.{expected_ext}"

    out_dir = _output_dir()
    out_path = out_dir / filename
    size = 0
    with open(out_path, "wb") as fh:
        for chunk in r.iter_content(chunk_size=1 << 20):
            if chunk:
                fh.write(chunk)
                size += len(chunk)

    kind = output_type or r.headers.get("Content-Type", "").split("/")[0] or "file"
    output.debug(f"[proxy] saved {size} bytes -> {out_path}")

    return {
        "files": [{
            "kind": kind,
            "url": f"file://{out_path.as_posix()}",
            "filename": filename,
            "path": str(out_path),
        }],
        "prompt_id": "",
    }
