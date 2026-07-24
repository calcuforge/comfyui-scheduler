"""Unified JSON output — all CLI commands emit ``{status, msg, data}``.

With ``--debug``, verbose progress is printed to stderr alongside the
final JSON result.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import click

_debug: bool = False


def set_debug(enabled: bool) -> None:
    global _debug
    _debug = enabled


def debug(msg: str) -> None:
    """Print a progress message — only shown when --debug is set."""
    if _debug:
        click.echo(msg, err=True)


def ok(msg: str = "ok", data: Any = None) -> None:
    """Emit success JSON to stdout and exit 0."""
    _emit("ok", msg, data if data is not None else {})
    sys.exit(0)


def error(msg: str, data: Any = None) -> None:
    """Emit error JSON to stderr and exit 1."""
    _emit("error", msg, data if data is not None else {}, err=True)
    sys.exit(1)


def _emit(status: str, msg: str, data: Any, *, err: bool = False) -> None:
    payload = json.dumps(
        {"status": status, "msg": msg, "data": data},
        ensure_ascii=False,
        indent=2,
    )
    if err:
        click.echo(payload, err=True)
    else:
        click.echo(payload)
