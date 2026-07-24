"""
ComfyUI API client — HTTP + WebSocket communication with a ComfyUI server.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

import requests
import websockets
from requests.auth import HTTPBasicAuth
from requests.compat import urljoin, urlencode

from .exceptions import ComfyUICLIError, ConnectionError, ExecutionError


class ComfyUIApi:
    """Thin wrapper around ComfyUI's HTTP and WebSocket endpoints."""

    def __init__(
        self,
        url: str = "http://127.0.0.1:8188",
        user: str = "",
        password: str = "",
        task_id: str = "",
    ) -> None:
        self.url = url.rstrip("/")
        self.auth = HTTPBasicAuth(user, password) if user else None
        self.task_id = task_id

        self._session = requests.Session()
        if task_id:
            self._session.headers["Host-Task-ID"] = task_id
        if self.auth:
            self._session.auth = self.auth

        host = self.url.split("//", 1)[-1]
        ws_protocol = "wss" if self.url.startswith("https") else "ws"
        if user:
            self.ws_url = f"{ws_protocol}://{user}:{password}@{host}/ws?clientId={{}}"
        else:
            self.ws_url = f"{ws_protocol}://{host}/ws?clientId={{}}"

    # ── HTTP helpers ──────────────────────────────────────────────

    def queue_prompt(self, prompt: dict, client_id: str | None = None) -> dict:
        payload = {"prompt": prompt}
        if client_id:
            payload["client_id"] = client_id
        r = self._session.post(
            urljoin(self.url, "/prompt"),
            data=json.dumps(payload).encode("utf-8"),
            auth=self.auth,
        )
        if r.status_code != 200:
            raise ComfyUICLIError(f"POST /prompt failed ({r.status_code}): {r.reason}")
        return r.json()

    def get_history(self, prompt_id: str) -> dict:
        r = self._session.get(urljoin(self.url, f"/history/{prompt_id}"))
        if r.status_code != 200:
            raise ComfyUICLIError(f"GET /history failed ({r.status_code}): {r.reason}")
        return r.json()

    def get_queue(self) -> dict:
        r = self._session.get(urljoin(self.url, "/queue"))
        if r.status_code != 200:
            raise ComfyUICLIError(f"GET /queue failed ({r.status_code}): {r.reason}")
        return r.json()

    def get_system_stats(self) -> dict:
        r = self._session.get(urljoin(self.url, "/system_stats"))
        if r.status_code != 200:
            raise ComfyUICLIError(f"GET /system_stats failed ({r.status_code}): {r.reason}")
        return r.json()

    def upload_file(
        self, filepath: str, subfolder: str = "default_upload_folder"
    ) -> dict:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        basename = os.path.basename(filepath)
        ext = os.path.splitext(basename)[1].lower()

        # ComfyUI uses different endpoints for image vs mask uploads
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            endpoint = "/upload/image"
        elif ext == ".mask":
            endpoint = "/upload/mask"
        else:
            # Other file types go through /upload/image as well
            endpoint = "/upload/image"

        url = urljoin(self.url, endpoint)
        with open(filepath, "rb") as f:
            r = self._session.post(
                url,
                files={"image": (basename, f)},
                data={"subfolder": subfolder},
                )
        if r.status_code != 200:
            raise ComfyUICLIError(
                f"Upload failed ({r.status_code}): {r.reason} — {r.text}"
            )
        return r.json()

    def download_file(
        self, filename: str, subfolder: str, folder_type: str
    ) -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url = urljoin(self.url, f"/view?{urlencode(params)}")
        r = self._session.get(url)
        if r.status_code != 200:
            raise ComfyUICLIError(f"Download failed ({r.status_code}): {r.reason}")
        return r.content

    # ── WebSocket helpers ─────────────────────────────────────────

    async def _ws_wait(self, prompt_id: str, client_id: str) -> str:
        """Connect to WS and wait until *prompt_id* finishes or errors."""
        ws_url = self.ws_url.format(client_id)
        try:
            async with websockets.connect(ws_url) as ws:
                while True:
                    raw = await ws.recv()
                    if not isinstance(raw, str):
                        continue
                    msg = json.loads(raw)
                    msg_type = msg.get("type")

                    if msg_type == "crystools.monitor":
                        continue

                    if msg_type == "execution_error":
                        data = msg.get("data", {})
                        if data.get("prompt_id") == prompt_id:
                            err_detail = data.get("exception_message", "")
                            raise ExecutionError(
                                f"Execution error on server: {err_detail}"
                                if err_detail
                                else "Execution error on server (no detail provided)."
                            )

                    if msg_type == "executing":
                        data = msg.get("data", {})
                        if data.get("node") is None and data.get("prompt_id") == prompt_id:
                            return prompt_id

                    if msg_type == "status":
                        data = msg.get("data", {})
                        exec_info = data.get("status", {}).get("exec_info", {})
                        if exec_info.get("queue_remaining") == 0:
                            return prompt_id
        except (ExecutionError, ConnectionError):
            raise
        except Exception as exc:
            raise ConnectionError(f"WebSocket error: {exc}") from exc

    # ── High-level convenience ────────────────────────────────────

    def queue_and_wait(self, prompt: dict) -> str:
        """Submit *prompt*, then block until execution completes.  Returns prompt_id."""
        client_id = str(uuid.uuid4())
        resp = self.queue_prompt(prompt, client_id)
        prompt_id = resp["prompt_id"]

        try:
            return asyncio.run(self._ws_wait(prompt_id, client_id))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._ws_wait(prompt_id, client_id))
            finally:
                loop.close()

    def fetch_outputs(
        self, prompt_id: str, output_node_id: str = ""
    ) -> list[dict[str, str]]:
        """Return metadata dicts for each output file.

        If *output_node_id* is given, only that node's outputs are returned.
        Otherwise scans all nodes.
        """
        history = self.get_history(prompt_id)
        nodes_outputs = history.get(prompt_id, {}).get("outputs", {})
        targets = (
            {output_node_id: nodes_outputs.get(output_node_id, {})}
            if output_node_id
            else nodes_outputs
        )

        files: list[dict[str, str]] = []
        for outputs in targets.values():
            for kind in ("images", "gifs", "videos", "audio"):
                for item in outputs.get(kind, []):
                    files.append(
                        {
                            "filename": item["filename"],
                            "subfolder": item.get("subfolder", ""),
                            "type": item.get("type", "output"),
                            "kind": kind.rstrip("s"),
                        }
                    )
        return files

    def build_output_urls(
        self, prompt_id: str, output_node_id: str
    ) -> list[str]:
        """Return full download URLs for every output of *output_node_id*."""
        files = self.fetch_outputs(prompt_id, output_node_id)
        urls = []
        for f in files:
            params = urlencode(
                {"filename": f["filename"], "subfolder": f["subfolder"], "type": f["type"]}
            )
            urls.append(urljoin(self.url, f"/view?{params}"))
        return urls

    # ── Node availability helpers ─────────────────────────────────

    def is_idle(self) -> bool:
        """Return True when the node has no running or pending jobs."""
        try:
            q = self.get_queue()
            return len(q.get("queue_running", [])) == 0 and len(q.get("queue_pending", [])) == 0
        except ComfyUICLIError:
            return False

    def queue_size(self) -> int:
        """Return total number of running + pending jobs."""
        try:
            q = self.get_queue()
            return len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
        except ComfyUICLIError:
            return 9999  # effectively disqualifies an unreachable node
