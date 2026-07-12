"""Thin wrappers around FFmpeg CLI.

Every function follows the same contract:
    receive: paths + options → return: pathlib.Path of the output file

No business logic, no creative decisions — just pure execution.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from video_core.utils.logger import get_logger

logger = get_logger(__name__)


def _run_ffmpeg(args: list[str], description: str) -> Path:
    """Execute ffmpeg with the given arguments and return the output path.

    Args:
        args: Full argument list *including* the output path as the last element.
        description: Human-readable label for logging.

    Returns:
        Path to the output file.
    """
    # Ensure ffmpeg is on PATH
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it via your system package manager "
            "or download from https://ffmpeg.org"
        )

    cmd = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", *args]
    output_path = Path(args[-1])  # convention: output is always last

    logger.info("FFmpeg: %s → %s", description, output_path.name)
    logger.debug("FFmpeg command: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("FFmpeg failed: %s", result.stderr.strip())
        raise subprocess.CalledProcessError(
            result.returncode, " ".join(cmd), result.stdout, result.stderr
        )

    if not output_path.exists():
        raise FileNotFoundError(
            f"FFmpeg reported success but output file {output_path} was not created"
        )

    logger.info("FFmpeg: %s completed successfully", description)
    return output_path


def concat_videos(
    clip_paths: list[Path],
    output: Path,
    *,
    transition: str | None = None,
) -> Path:
    """Concatenate multiple video clips into one file.

    Args:
        clip_paths: Ordered list of video files to join.
        output: Destination path (must end in .mp4 or .mkv).
        transition: Optional xfade transition name (e.g. "fade", "dissolve").

    Returns:
        Path to the concatenated output file.
    """
    if len(clip_paths) < 1:
        raise ValueError("Need at least one clip to concatenate")

    if len(clip_paths) == 1:
        # Single clip: just copy it
        logger.info("Only one clip provided; copying without re-encode")
        shutil.copy2(clip_paths[0], output)
        return output

    # Build concat demuxer file
    concat_list = output.with_suffix(".txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in clip_paths:
            # ffmpeg concat demuxer needs forward-slashes and single-quoted paths
            f.write(f"file '{p.as_posix()}'\n")

    args = ["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy"]
    args.append(str(output))

    result = _run_ffmpeg(args, f"concat {len(clip_paths)} clips")
    concat_list.unlink(missing_ok=True)
    return result


def trim_video(
    input_path: Path,
    output: Path,
    start: str = "00:00:00",
    duration: str | None = None,
    end: str | None = None,
) -> Path:
    """Trim a segment from a video.

    Args:
        input_path: Source video.
        output: Destination path.
        start: Start timecode (HH:MM:SS or seconds).
        duration: Length of the segment.
        end: End timecode. Mutually exclusive with duration.

    Returns:
        Path to the trimmed output.
    """
    args = ["-i", str(input_path), "-ss", start]

    if duration is not None:
        args.extend(["-t", duration])
    elif end is not None:
        args.extend(["-to", end])
    else:
        raise ValueError("Either duration or end must be specified for trim")

    args.extend(["-c", "copy", str(output)])
    return _run_ffmpeg(args, f"trim {input_path.name}")


def overlay_audio(
    video_path: Path,
    audio_path: Path,
    output: Path,
    *,
    mix: bool = True,
    audio_volume: float = 1.0,
) -> Path:
    """Overlay an audio track onto a video.

    If mix=True, the original audio is preserved and mixed with the overlay.
    If mix=False, the original audio is dropped.

    Args:
        video_path: Source video.
        audio_path: Audio file to overlay.
        output: Destination path.
        mix: Whether to keep the original audio stream.
        audio_volume: Volume multiplier for the overlay track (0.0–2.0).

    Returns:
        Path to the output video.
    """
    args = ["-i", str(video_path), "-i", str(audio_path)]

    if mix:
        # Mix both audio streams: original [0:a] + overlay [1:a] with volume adjustment
        filter_expr = (
            f"[1:a]volume={audio_volume}[ov];"
            f"[0:a][ov]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        args.extend([
            "-filter_complex", filter_expr,
            "-map", "0:v",
            "-map", "[aout]",
        ])
    else:
        # Replace audio entirely
        filter_expr = f"[1:a]volume={audio_volume}[aout]"
        args.extend([
            "-filter_complex", filter_expr,
            "-map", "0:v",
            "-map", "[aout]",
        ])

    args.append(str(output))
    return _run_ffmpeg(args, f"overlay audio onto {video_path.name}")


def apply_text_overlay(
    video_path: Path,
    text: str,
    output: Path,
    *,
    font_color: str = "white",
    font_size: int = 42,
    position: str = "bottom",
    font_file: str | None = None,
    shadow_color: str | None = None,
    shadow_offset: int = 2,
) -> Path:
    """Burn subtitles / text overlay into a video using the drawtext filter.

    Args:
        video_path: Source video.
        text: Text to render.
        output: Destination path.
        font_color: Hex color or named color (e.g. "yellow", "#FFFF00").
        font_size: Font size in pixels.
        position: "top", "center", "bottom", or "bottom_center".
        font_file: Path to a .ttf font file (uses default sans-serif if omitted).
        shadow_color: Optional shadow/outline color.

    Returns:
        Path to the output video.
    """
    # Resolve vertical position
    y_positions = {
        "top": "h/10",
        "center": "h/2",
        "bottom": "h-th-80",
        "bottom_center": "h-th-60",
    }
    y_expr = y_positions.get(position, "h-th-80")

    # Build drawtext filter
    font_clause = f"fontfile='{font_file}'" if font_file else ""
    drawtext = (
        f"drawtext=text='{text}':fontcolor={font_color}:fontsize={font_size}"
        f":x=(w-text_w)/2:y={y_expr}:box=0"
    )

    if shadow_color:
        shadow_args = (
            f":shadowcolor={shadow_color}:shadowx={shadow_offset}:shadowy={shadow_offset}"
        )
        drawtext += shadow_args

    if font_clause:
        drawtext += f":{font_clause}"

    args = ["-i", str(video_path), "-vf", drawtext, "-c:a", "copy", str(output)]
    return _run_ffmpeg(args, f"overlay text on {video_path.name}")


def merge_image_audio(
    image_path: Path,
    audio_path: Path,
    output: Path,
    *,
    duration: str | None = None,
    framerate: int = 24,
    codec: str = "libx264",
    preset: str = "medium",
    crf: int = 23,
) -> Path:
    """Create a video from a still image + audio track (podcast-style output).

    If duration is not provided, the video length matches the full audio duration.

    Args:
        image_path: Still image to use as visual.
        audio_path: Audio file.
        output: Destination path.
        duration: Optional override for video length (HH:MM:SS).
        framerate: Frames per second for the video stream.
        codec: Video codec.
        preset: x264 preset (ultrafast … veryslow).
        crf: Quality (lower = better, 18–28 is a good range).

    Returns:
        Path to the output video.
    """
    args = [
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", codec,
        "-preset", preset,
        "-crf", str(crf),
        "-r", str(framerate),
        "-pix_fmt", "yuv420p",
    ]

    if duration:
        args.extend(["-t", duration])
    else:
        args.extend(["-shortest"])

    args.append(str(output))
    return _run_ffmpeg(args, f"image+audio merge: {image_path.name}")
