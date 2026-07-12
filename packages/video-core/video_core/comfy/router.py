"""Workflow router: maps style_tag → workflow JSON + schema.

Layer 2 genre SKILL.md files specify a `style_tag` (e.g. "cinematic",
"anime", "realistic"). This module resolves that tag to a concrete
workflow file, so the caller never needs to know file paths.

Adding a new style is a data change: drop a JSON workflow + schema into
the schemas/ directory and add an entry to STYLE_REGISTRY below.
"""

from __future__ import annotations

from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

# ---------------------------------------------------------------------------
# Style Registry
#
# Each entry maps a short, human-readable tag to:
#   workflow:  relative path (from this file) to the ComfyUI API-format JSON
#   schema:    relative path to the parameter schema JSON
#              (defaults to schemas/<tag>.json if omitted)
# ---------------------------------------------------------------------------

STYLE_REGISTRY: dict[str, dict[str, str]] = {
    "cinematic": {
        "workflow": "workflows/cinematic.json",
        "schema": "schemas/cinematic.json",
    },
    "anime": {
        "workflow": "workflows/anime.json",
        "schema": "schemas/anime.json",
    },
    "realistic": {
        "workflow": "workflows/realistic.json",
        "schema": "schemas/realistic.json",
    },
}


def resolve_style(style_tag: str) -> Path:
    """Return the absolute path to the workflow JSON for the given style tag.

    Args:
        style_tag: Short name like "cinematic", "anime", "realistic".

    Returns:
        Absolute path to the ComfyUI API-format workflow JSON.

    Raises:
        ValueError: If the style_tag is not registered.
    """
    entry = STYLE_REGISTRY.get(style_tag)
    if entry is None:
        available = ", ".join(sorted(STYLE_REGISTRY.keys()))
        raise ValueError(
            f"Unknown style_tag '{style_tag}'. Available: {available}"
        )

    workflow_path = (SCHEMAS_DIR / entry["workflow"]).resolve()
    return workflow_path


def list_styles() -> list[str]:
    """Return all registered style tags."""
    return sorted(STYLE_REGISTRY.keys())


def get_schema_path(style_tag: str) -> Path:
    """Return the absolute path to the parameter schema for a style tag."""
    entry = STYLE_REGISTRY.get(style_tag)
    if entry is None:
        available = ", ".join(sorted(STYLE_REGISTRY.keys()))
        raise ValueError(
            f"Unknown style_tag '{style_tag}'. Available: {available}"
        )

    return (SCHEMAS_DIR / entry["schema"]).resolve()
