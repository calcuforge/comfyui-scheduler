"""Remotion renderer wrapper.

Launches `npx remotion render` in a subprocess. All creative decisions
(template choice, composition props) are supplied by the caller (Layer 2/3).
This module *only* deals with execution.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from video_core.utils.logger import get_logger

logger = get_logger(__name__)

# Map genre-level template names to Remotion composition IDs.
# Layer 2 SKILL.md references the short name; this module resolves it.
TEMPLATE_MAP: dict[str, str] = {
    "DocStyle": "DocumentaryComposition",
    "EduStyle": "EducationalComposition",
    "ShortDramaStyle": "ShortDramaComposition",
    "SocialClip": "SocialClipComposition",
}


def render(
    template_name: str,
    output: Path,
    *,
    props: dict | None = None,
    remotion_project: Path | None = None,
    fps: int = 30,
    codec: str = "h264",
    crf: int = 18,
    scale: float = 1.0,
) -> Path:
    """Render a Remotion composition to video.

    Args:
        template_name: Short name from TEMPLATE_MAP (e.g. "DocStyle").
        output: Destination path (.mp4).
        props: Props to pass into the Remotion composition (React props).
        remotion_project: Path to the Remotion project root (directory
            containing package.json with remotion dependency).
            Defaults to the bundled templates shipped with video-core.
        fps: Frame rate.
        codec: Video codec (h264, h265, vp8, vp9, prores, gif).
        crf: Constant Rate Factor (lower = higher quality, 0–51).
        scale: Scale factor (0.5 = half resolution).

    Returns:
        Path to the rendered output file.

    Raises:
        RuntimeError: If npx / remotion is not available or the render fails.
    """
    if remotion_project is None:
        remotion_project = Path(__file__).resolve().parent / "templates"

    if not (remotion_project / "package.json").exists():
        raise FileNotFoundError(
            f"No Remotion project found at {remotion_project}. "
            "Set remotion_project to the directory containing the Remotion app."
        )

    composition_id = TEMPLATE_MAP.get(template_name)
    if composition_id is None:
        available = ", ".join(TEMPLATE_MAP.keys())
        raise ValueError(
            f"Unknown template '{template_name}'. Available: {available}"
        )

    props_json = json.dumps(props or {})

    cmd = [
        "npx",
        "remotion",
        "render",
        str(composition_id),
        str(output),
        f"--props={props_json}",
        f"--fps={fps}",
        f"--codec={codec}",
        f"--crf={crf}",
        f"--scale={scale}",
    ]

    logger.info("Remotion: rendering %s → %s", template_name, output.name)
    logger.debug("Remotion command: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        cwd=str(remotion_project),
        capture_output=True,
        text=True,
        timeout=600,  # 10-minute timeout for renders
    )

    if result.returncode != 0:
        logger.error("Remotion render failed:\n%s", result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode, " ".join(cmd), result.stdout, result.stderr
        )

    if not output.exists():
        raise FileNotFoundError(
            f"Remotion reported success but {output} was not created"
        )

    logger.info("Remotion: render completed → %s", output)
    return output
