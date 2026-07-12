"""Centralized logging for video-core.

Log levels are mapped to audience:
- INFO  → messages intended for the OpenClaw Agent (actionable feedback)
- DEBUG → messages intended for human developers (diagnostics)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".openclaw" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOGGER: logging.Logger | None = None


def get_logger(name: str = "video_core") -> logging.Logger:
    """Return (and memoize) the package-level logger.

    Logs are written to both stderr (for OpenClaw to capture) and a rotating
    file under ~/.openclaw/logs/ for post-mortem debugging.
    """
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    _LOGGER = logging.getLogger(name)
    _LOGGER.setLevel(logging.DEBUG)

    if not _LOGGER.handlers:
        # --- stderr handler: short format for Agent consumption ---
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_fmt = logging.Formatter(
            "[video-core] %(levelname)s: %(message)s"
        )
        stderr_handler.setFormatter(stderr_fmt)
        _LOGGER.addHandler(stderr_handler)

        # --- file handler: verbose format for human debugging ---
        file_handler = logging.FileHandler(
            LOG_DIR / "video_core.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d  %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        _LOGGER.addHandler(file_handler)

    return _LOGGER
