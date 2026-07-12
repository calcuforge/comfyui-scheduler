"""ComfyUI HTTP client with name-based node resolution.

The core design decision: we do NOT use ComfyUI's raw node IDs (integers).
Instead, users reference nodes by their *title* (set in ComfyUI's UI via
the _meta.title property). This module resolves those names to integer IDs
at prompt-submission time.

This makes workflows human-readable and resistant to ID drift when nodes
are added / removed in the ComfyUI editor.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from video_core.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ComfyError(Exception):
    """Base exception for all ComfyUI-related failures."""


class DuplicateNodeNameError(ComfyError):
    """Raised when a workflow JSON contains duplicate node titles."""


class NodeNotFoundError(ComfyError):
    """Raised when a referenced node_name is not found in the workflow."""


class WorkflowNotLoadedError(ComfyError):
    """Raised when the ComfyUI server has no workflow loaded."""


class PromptExecutionError(ComfyError):
    """Raised when a queued prompt fails during execution."""


# ---------------------------------------------------------------------------
# Name → ID Resolver
# ---------------------------------------------------------------------------

class NameToIDResolver:
    """Resolve human-readable node names to ComfyUI integer node IDs.

    ComfyUI workflows are JSON objects where keys are node IDs (strings of
    integers) and values describe each node. The `_meta.title` field is the
    human-readable name set in ComfyUI's UI.

    Usage::

        resolver = NameToIDResolver(workflow_json)
        node_id = resolver.resolve("KSampler")
    """

    def __init__(self, workflow: dict[str, Any]) -> None:
        self._workflow = workflow
        self._name_to_id: dict[str, str] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Walk every node in the workflow and build the name→id map.

        Raises DuplicateNodeNameError if two nodes share the same title,
        because ambiguity would silently corrupt the prompt.
        """
        duplicates: dict[str, list[str]] = {}

        for node_id, node_data in self._workflow.items():
            if not isinstance(node_data, dict):
                continue

            meta = node_data.get("_meta", {})
            title = meta.get("title", "").strip()

            if not title:
                continue  # nodes without titles are ignored

            if title in self._name_to_id:
                duplicates.setdefault(title, [self._name_to_id[title]]).append(
                    node_id
                )
                continue

            self._name_to_id[title] = node_id

        if duplicates:
            detail = "\n".join(
                f"  '{name}' → IDs: {ids}" for name, ids in duplicates.items()
            )
            raise DuplicateNodeNameError(
                f"Duplicate node titles found in workflow. "
                f"Please rename them in ComfyUI to be unique:\n{detail}"
            )

    def resolve(self, node_name: str) -> str:
        """Return the integer node ID (as a string) for the given name.

        Raises NodeNotFoundError if the name is not found.
        """
        node_id = self._name_to_id.get(node_name)
        if node_id is None:
            available = sorted(self._name_to_id.keys())
            raise NodeNotFoundError(
                f"Node '{node_name}' not found in workflow. "
                f"Available nodes: {available}"
            )
        return node_id

    @property
    def node_count(self) -> int:
        """Total number of named nodes in the workflow."""
        return len(self._name_to_id)

    @property
    def available_names(self) -> list[str]:
        """Sorted list of all resolvable node names."""
        return sorted(self._name_to_id.keys())


# ---------------------------------------------------------------------------
# ComfyUI Client
# ---------------------------------------------------------------------------

class ComfyClient:
    """HTTP client for a ComfyUI server.

    Covers the full lifecycle: load workflow → inject params → queue →
    poll history → download outputs.

    Usage::

        async with ComfyClient("http://localhost:8188") as client:
            client.load_workflow("schemas/cinematic.json")
            client.inject_params({"prompt": "a cat", "seed": 42})
            result = await client.queue_and_wait()
            files = await client.download_outputs(result)
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        *,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
        output_dir: Path | str = "outputs",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._client: httpx.AsyncClient | None = None
        self._workflow: dict[str, Any] | None = None
        self._resolver: NameToIDResolver | None = None
        self._schema: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "ComfyClient":
        self._client = await httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        ).__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.__aexit__(*args)
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ComfyClient must be used as an async context manager")
        return self._client

    # ------------------------------------------------------------------
    # Workflow Loading
    # ------------------------------------------------------------------

    def load_workflow(self, schema_path: Path | str) -> None:
        """Load a workflow JSON (API format) and its parameter schema.

        The workflow JSON is the file you get from ComfyUI's "Save (API
        Format)" button. It must contain node `_meta.title` fields for
        the Name-to-ID resolver to work.

        The schema JSON is a separate file that maps human-readable
        parameter names to (node_name, field) pairs.
        """
        workflow_path = Path(schema_path)

        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

        with open(workflow_path, "r", encoding="utf-8") as f:
            self._workflow = json.load(f)

        self._resolver = NameToIDResolver(self._workflow)

        # Load corresponding parameter schema if it exists
        schema_file = (
            workflow_path.parent / "schemas" / f"{workflow_path.stem}.json"
        )
        if schema_file.exists():
            with open(schema_file, "r", encoding="utf-8") as f:
                self._schema = json.load(f)
        else:
            logger.warning(
                "No parameter schema found at %s; using raw node IDs only",
                schema_file,
            )
            self._schema = None

        logger.info(
            "Loaded workflow '%s' (%d named nodes)",
            workflow_path.stem,
            self._resolver.node_count,
        )

    # ------------------------------------------------------------------
    # Parameter Injection
    # ------------------------------------------------------------------

    def inject_params(self, params: dict[str, Any]) -> None:
        """Inject parameter values into the workflow using node names.

        This uses the schema (if loaded) to map parameter names to
        (node_name, field) pairs. If no schema is loaded, params are
        treated as direct node_name→value mappings.

        Example with schema::

            client.inject_params({"prompt": "a beautiful sunset", "seed": 42})
            # schema maps "prompt" → ("PositivePrompt", "text")
            # resolver finds node ID for "PositivePrompt" → writes to .inputs.text

        Example without schema::

            client.inject_params({"PositivePrompt": {"text": "a beautiful sunset"}})
            # direct injection — node name is the key
        """
        if self._workflow is None:
            raise WorkflowNotLoadedError(
                "No workflow loaded. Call load_workflow() first."
            )
        assert self._resolver is not None  # set by load_workflow

        if self._schema is not None:
            self._inject_via_schema(params)
        else:
            self._inject_direct(params)

    def _inject_via_schema(self, params: dict[str, Any]) -> None:
        """Use the parameter schema to map param_name → (node_name, field)."""
        assert self._workflow is not None
        assert self._resolver is not None
        assert self._schema is not None

        schema_params: dict[str, dict[str, Any]] = self._schema.get(
            "parameters", {}
        )

        for param_name, value in params.items():
            if param_name not in schema_params:
                logger.debug(
                    "Skipping '%s': not defined in schema", param_name
                )
                continue

            spec = schema_params[param_name]
            node_name = spec["node_name"]
            field = spec.get("field", "text")

            node_id = self._resolver.resolve(node_name)

            # Navigate to the field — ComfyUI stores values in .inputs.<field>
            node = self._workflow[node_id]
            if "inputs" not in node:
                node["inputs"] = {}
            node["inputs"][field] = value

            logger.info(
                "Injected %s='%s' → node '%s' (ID %s).%s",
                param_name,
                str(value)[:80],
                node_name,
                node_id,
                field,
            )

    def _inject_direct(self, params: dict[str, Any]) -> None:
        """Direct node-name keyed injection (no schema)."""
        assert self._workflow is not None
        assert self._resolver is not None

        for node_name, node_inputs in params.items():
            node_id = self._resolver.resolve(node_name)
            node = self._workflow[node_id]

            if isinstance(node_inputs, dict):
                node.setdefault("inputs", {}).update(node_inputs)
            else:
                # Scalar: write to "text" field by convention
                node.setdefault("inputs", {})["text"] = node_inputs

            logger.info(
                "Injected node '%s' (ID %s) with %s",
                node_name,
                node_id,
                str(node_inputs)[:80],
            )

    # ------------------------------------------------------------------
    # Prompt Submission & Polling
    # ------------------------------------------------------------------

    async def queue_prompt(self) -> str:
        """Submit the current workflow to ComfyUI's /prompt endpoint.

        Returns the prompt_id for tracking.
        """
        if self._workflow is None:
            raise WorkflowNotLoadedError(
                "No workflow loaded. Call load_workflow() first."
            )

        # ComfyUI expects the "prompt" key wrapping the workflow
        payload = {"prompt": self._workflow}

        logger.info("Queueing prompt to ComfyUI (%d nodes)", len(self._workflow))

        response = await self.client.post("/prompt", json=payload)
        response.raise_for_status()

        data = response.json()
        prompt_id = data.get("prompt_id")

        if prompt_id is None:
            # ComfyUI sometimes returns an error object instead
            error_msg = data.get("error", {})
            raise PromptExecutionError(
                f"ComfyUI rejected the prompt: {error_msg}"
            )

        logger.info("Prompt queued: %s", prompt_id)
        return prompt_id

    async def wait_for_result(
        self, prompt_id: str
    ) -> dict[str, Any]:
        """Poll /history/{prompt_id} until execution completes or fails.

        Returns the history entry for the prompt.
        """
        url = f"/history/{prompt_id}"

        start_time = time.monotonic()
        attempt = 0

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed > self.timeout:
                raise TimeoutError(
                    f"Prompt {prompt_id} did not complete within {self.timeout}s"
                )

            attempt += 1
            response = await self.client.get(url)
            response.raise_for_status()

            # The history API returns a dict keyed by prompt_id
            data = response.json()
            entry = data.get(prompt_id)

            if entry is not None:
                status = entry.get("status", {})

                if status.get("completed") is True:
                    logger.info(
                        "Prompt %s completed (attempt %d, %.1fs)",
                        prompt_id,
                        attempt,
                        elapsed,
                    )
                    return entry

                if status.get("status_str") == "error":
                    error_detail = status.get("messages", [[None, "Unknown error"]])
                    raise PromptExecutionError(
                        f"Prompt {prompt_id} failed: {error_detail}"
                    )

            logger.debug(
                "Waiting for %s… (attempt %d, %.1fs elapsed)",
                prompt_id,
                attempt,
                elapsed,
            )
            await _async_sleep(self.poll_interval)

    async def queue_and_wait(self) -> dict[str, Any]:
        """Convenience: queue the prompt and block until done."""
        prompt_id = await self.queue_prompt()
        return await self.wait_for_result(prompt_id)

    # ------------------------------------------------------------------
    # Output Download
    # ------------------------------------------------------------------

    async def download_outputs(
        self, history_entry: dict[str, Any]
    ) -> list[Path]:
        """Download all output files (images/videos) from a completed prompt.

        Parses the history entry, extracts output file metadata, and
        downloads each file via ComfyUI's /view endpoint.

        Returns a list of saved file paths.
        """
        outputs = history_entry.get("outputs", {})
        saved: list[Path] = []

        for node_id, node_output in outputs.items():
            # Each node can produce multiple output types (images, gifs, etc.)
            for media_type in ("images", "gifs", "videos", "audio"):
                items = node_output.get(media_type, [])
                for item in items:
                    filename = item.get("filename", "")
                    subfolder = item.get("subfolder", "")
                    media_type_path = item.get("type", media_type)

                    if not filename:
                        continue

                    saved_path = await self._download_file(
                        filename=filename,
                        subfolder=subfolder,
                        media_type=media_type_path,
                    )
                    saved.append(saved_path)

        logger.info("Downloaded %d output files to %s", len(saved), self.output_dir)
        return saved

    async def _download_file(
        self,
        filename: str,
        subfolder: str,
        media_type: str,
    ) -> Path:
        """Download a single file from ComfyUI's /view endpoint."""
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": media_type,
        }

        response = await self.client.get("/view", params=params)
        response.raise_for_status()

        dest = self.output_dir / filename
        dest.write_bytes(response.content)

        logger.info("Downloaded: %s (%.1f KB)", filename, len(response.content) / 1024)
        return dest

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Check if the ComfyUI server is reachable."""
        try:
            response = await self.client.get("/system_stats")
            return response.is_success
        except httpx.RequestError:
            return False


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

async def _async_sleep(seconds: float) -> None:
    """Async sleep wrapper (keeps the import footprint minimal)."""
    import asyncio

    await asyncio.sleep(seconds)
