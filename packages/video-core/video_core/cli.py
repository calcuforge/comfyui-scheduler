"""CLI entry point for video-core.

This module exposes a command-line interface that OpenClaw Agents call via
the `bash` tool. Every command is non-interactive (no stdin prompts) and
prints machine-parseable results to stdout.

Commands::

    video-core generate --style cinematic --prompt "..." [--seed 42]
    video-core concat --clips a.mp4 b.mp4 --output final.mp4
    video-core trim --input raw.mp4 --start 00:00:05 --duration 00:00:10
    video-core audio-overlay --video vid.mp4 --audio voice.mp3 --output out.mp4
    video-core text-overlay --video vid.mp4 --text "Hello" --color yellow
    video-core merge-image-audio --image cover.png --audio podcast.wav
    video-core render-remotion --template DocStyle --props '{"title":"My Video"}'
    video-core list-styles
    video-core check-comfy
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from video_core.comfy.client import ComfyClient
from video_core.comfy.router import list_styles, resolve_style
from video_core.ffmpeg.wrapper import (
    apply_text_overlay,
    concat_videos,
    merge_image_audio,
    overlay_audio,
    trim_video,
)
from video_core.remotion.renderer import render as remotion_render
from video_core.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="video-core",
        description="OpenClaw Video Production Suite — Layer 1 Execution Engine",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- generate -------------------------------------------------------
    gen = sub.add_parser("generate", help="Generate video/images via ComfyUI")
    gen.add_argument(
        "--style", required=True, help="Style tag (cinematic, anime, realistic)"
    )
    gen.add_argument("--prompt", required=True, help="Positive prompt text")
    gen.add_argument("--negative", default=None, help="Negative prompt text")
    gen.add_argument("--seed", type=int, default=-1, help="Random seed")
    gen.add_argument("--steps", type=int, default=None, help="Sampling steps")
    gen.add_argument("--cfg", type=float, default=None, help="CFG scale")
    gen.add_argument("--width", type=int, default=None, help="Output width")
    gen.add_argument("--height", type=int, default=None, help="Output height")
    gen.add_argument(
        "--comfy-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI server base URL",
    )
    gen.add_argument(
        "--output-dir", default="outputs", help="Directory for downloaded outputs"
    )
    gen.add_argument("--timeout", type=float, default=300.0, help="Max wait time (s)")

    # --- concat ---------------------------------------------------------
    conc = sub.add_parser("concat", help="Concatenate video files")
    conc.add_argument("--clips", nargs="+", required=True, help="Video files in order")
    conc.add_argument("--output", required=True, help="Output file path")
    conc.add_argument("--transition", default=None, help="Optional xfade transition")

    # --- trim -----------------------------------------------------------
    trim = sub.add_parser("trim", help="Trim a segment from a video")
    trim.add_argument("--input", required=True, help="Source video")
    trim.add_argument("--output", required=True, help="Output file path")
    trim.add_argument("--start", default="00:00:00", help="Start timecode")
    trim.add_argument("--duration", default=None, help="Duration of segment")
    trim.add_argument("--end", default=None, help="End timecode")

    # --- audio-overlay --------------------------------------------------
    aover = sub.add_parser("audio-overlay", help="Overlay audio onto video")
    aover.add_argument("--video", required=True, help="Source video file")
    aover.add_argument("--audio", required=True, help="Audio file to overlay")
    aover.add_argument("--output", required=True, help="Output file path")
    aover.add_argument("--no-mix", action="store_true", help="Replace original audio")
    aover.add_argument("--volume", type=float, default=1.0, help="Overlay volume (0.0-2.0)")

    # --- text-overlay ---------------------------------------------------
    tover = sub.add_parser("text-overlay", help="Burn subtitles/text into video")
    tover.add_argument("--video", required=True, help="Source video file")
    tover.add_argument("--text", required=True, help="Text to render")
    tover.add_argument("--output", required=True, help="Output file path")
    tover.add_argument("--color", default="white", help="Font color (name or #hex)")
    tover.add_argument("--size", type=int, default=42, help="Font size in pixels")
    tover.add_argument(
        "--position",
        default="bottom",
        choices=["top", "center", "bottom", "bottom_center"],
        help="Text position",
    )
    tover.add_argument("--font", default=None, help="Path to .ttf font file")
    tover.add_argument("--shadow-color", default=None, help="Shadow/outline color")
    tover.add_argument("--shadow-offset", type=int, default=2, help="Shadow offset px")

    # --- merge-image-audio ----------------------------------------------
    mia = sub.add_parser("merge-image-audio", help="Create video from image + audio")
    mia.add_argument("--image", required=True, help="Still image file")
    mia.add_argument("--audio", required=True, help="Audio file")
    mia.add_argument("--output", required=True, help="Output video path")
    mia.add_argument("--duration", default=None, help="Override video length")
    mia.add_argument("--fps", type=int, default=24, help="Frame rate")
    mia.add_argument("--crf", type=int, default=23, help="Quality (lower=better)")

    # --- render-remotion ------------------------------------------------
    rem = sub.add_parser("render-remotion", help="Render a Remotion composition")
    rem.add_argument("--template", required=True, help="Template name (DocStyle, EduStyle, etc.)")
    rem.add_argument("--output", required=True, help="Output video path")
    rem.add_argument("--props", default="{}", help="JSON props for the composition")
    rem.add_argument("--fps", type=int, default=30, help="Frame rate")
    rem.add_argument("--crf", type=int, default=18, help="CRF quality (lower=better)")
    rem.add_argument("--scale", type=float, default=1.0, help="Render scale")

    # --- utility commands -----------------------------------------------
    sub.add_parser("list-styles", help="List all registered ComfyUI style tags")
    check = sub.add_parser("check-comfy", help="Check if ComfyUI server is reachable")
    check.add_argument(
        "--comfy-url", default="http://127.0.0.1:8188", help="ComfyUI server URL"
    )

    args = parser.parse_args()
    asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> None:
    """Route the parsed command to the appropriate handler."""
    cmd = args.command

    if cmd == "generate":
        await _cmd_generate(args)
    elif cmd == "concat":
        _cmd_concat(args)
    elif cmd == "trim":
        _cmd_trim(args)
    elif cmd == "audio-overlay":
        _cmd_audio_overlay(args)
    elif cmd == "text-overlay":
        _cmd_text_overlay(args)
    elif cmd == "merge-image-audio":
        _cmd_merge_image_audio(args)
    elif cmd == "render-remotion":
        _cmd_render_remotion(args)
    elif cmd == "list-styles":
        _cmd_list_styles()
    elif cmd == "check-comfy":
        await _cmd_check_comfy(args)
    else:
        logger.error("Unknown command: %s", cmd)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _cmd_generate(args: argparse.Namespace) -> None:
    """Handle `video-core generate`."""
    workflow_path = resolve_style(args.style)

    params: dict[str, object] = {"prompt": args.prompt, "seed": args.seed}
    if args.negative is not None:
        params["negative_prompt"] = args.negative
    if args.steps is not None:
        params["steps"] = args.steps
    if args.cfg is not None:
        params["cfg"] = args.cfg
    if args.width is not None:
        params["width"] = args.width
    if args.height is not None:
        params["height"] = args.height

    logger.info("Starting generation with style='%s'", args.style)

    async with ComfyClient(
        base_url=args.comfy_url,
        timeout=args.timeout,
        output_dir=args.output_dir,
    ) as client:
        client.load_workflow(workflow_path)
        client.inject_params(params)
        result = await client.queue_and_wait()
        files = await client.download_outputs(result)

    # Print machine-parseable result to stdout for OpenClaw
    output = {
        "status": "completed",
        "style": args.style,
        "files": [str(f) for f in files],
    }
    print(json.dumps(output, ensure_ascii=False))


def _cmd_concat(args: argparse.Namespace) -> None:
    clips = [Path(p) for p in args.clips]
    output = Path(args.output)
    result = concat_videos(clips, output, transition=args.transition)
    print(json.dumps({"status": "completed", "output": str(result)}, ensure_ascii=False))


def _cmd_trim(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output = Path(args.output)
    result = trim_video(input_path, output, start=args.start, duration=args.duration, end=args.end)
    print(json.dumps({"status": "completed", "output": str(result)}, ensure_ascii=False))


def _cmd_audio_overlay(args: argparse.Namespace) -> None:
    video_path = Path(args.video)
    audio_path = Path(args.audio)
    output = Path(args.output)
    result = overlay_audio(
        video_path, audio_path, output,
        mix=not args.no_mix,
        audio_volume=args.volume,
    )
    print(json.dumps({"status": "completed", "output": str(result)}, ensure_ascii=False))


def _cmd_text_overlay(args: argparse.Namespace) -> None:
    video_path = Path(args.video)
    output = Path(args.output)
    result = apply_text_overlay(
        video_path, args.text, output,
        font_color=args.color,
        font_size=args.size,
        position=args.position,
        font_file=args.font,
        shadow_color=args.shadow_color,
        shadow_offset=args.shadow_offset,
    )
    print(json.dumps({"status": "completed", "output": str(result)}, ensure_ascii=False))


def _cmd_merge_image_audio(args: argparse.Namespace) -> None:
    image_path = Path(args.image)
    audio_path = Path(args.audio)
    output = Path(args.output)
    result = merge_image_audio(
        image_path, audio_path, output,
        duration=args.duration,
        framerate=args.fps,
        crf=args.crf,
    )
    print(json.dumps({"status": "completed", "output": str(result)}, ensure_ascii=False))


def _cmd_render_remotion(args: argparse.Namespace) -> None:
    props = json.loads(args.props)
    output = Path(args.output)
    result = remotion_render(
        args.template, output,
        props=props,
        fps=args.fps,
        crf=args.crf,
        scale=args.scale,
    )
    print(json.dumps({"status": "completed", "output": str(result)}, ensure_ascii=False))


def _cmd_list_styles() -> None:
    styles = list_styles()
    print(json.dumps({"styles": styles}, ensure_ascii=False))


async def _cmd_check_comfy(args: argparse.Namespace) -> None:
    async with ComfyClient(base_url=args.comfy_url) as client:
        reachable = await client.ping()
    print(
        json.dumps(
            {"comfy_available": reachable, "url": args.comfy_url},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
