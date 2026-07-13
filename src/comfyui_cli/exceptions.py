class ComfyUICLIError(Exception):
    """Base exception for ComfyUI CLI."""


class ConnectionError(ComfyUICLIError):
    """Failed to connect to ComfyUI server."""


class ExecutionError(ComfyUICLIError):
    """Workflow execution failed on the server."""


class NodeNotFoundError(ComfyUICLIError):
    """No registered ComfyUI node found."""


class WorkflowError(ComfyUICLIError):
    """Invalid or missing workflow file."""
