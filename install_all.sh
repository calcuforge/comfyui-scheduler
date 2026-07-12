#!/usr/bin/env bash
# =============================================================================
# Video Production Suite — One-Click Installer
# =============================================================================
# Installs the video-core Python package and registers all SKILL.md files
# as OpenClaw Global Skills.
#
# Usage:
#   chmod +x install_all.sh
#   ./install_all.sh
#
# Prerequisites:
#   - Python 3.10+ with pip
#   - OpenClaw CLI (`openclaw`) on PATH
#   - FFmpeg (optional but recommended)
#   - Node.js + npm (optional, for Remotion rendering)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGES_DIR="$SCRIPT_DIR/packages"

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Video Production Suite — Installer${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ---------------------------------------------------------------------------
# 1. Check pre-requisites
# ---------------------------------------------------------------------------

echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

# Python
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo -e "${RED}ERROR: Python 3.10+ is required but not found on PATH.${NC}"
    exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "  Python: ${GREEN}$PY_VERSION${NC}"

# OpenClaw
if command -v openclaw &>/dev/null; then
    echo -e "  OpenClaw: ${GREEN}found${NC}"
else
    echo -e "  OpenClaw: ${YELLOW}not found — will install skills manually${NC}"
fi

# FFmpeg (optional)
if command -v ffmpeg &>/dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)
    echo -e "  FFmpeg: ${GREEN}$FFMPEG_VERSION${NC}"
else
    echo -e "  FFmpeg: ${YELLOW}not found — install it for video editing features${NC}"
fi

# Node.js (optional, for Remotion)
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "  Node.js: ${GREEN}$NODE_VERSION${NC}"
else
    echo -e "  Node.js: ${YELLOW}not found — install it for Remotion features${NC}"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. Install video-core Python package
# ---------------------------------------------------------------------------

echo -e "${YELLOW}[2/5] Installing video-core Python package...${NC}"

cd "$PACKAGES_DIR/video-core"
$PYTHON -m pip install -e . --quiet 2>&1 | tail -1

if $PYTHON -c "import video_core" 2>/dev/null; then
    echo -e "  video-core: ${GREEN}installed successfully${NC}"
else
    echo -e "${RED}ERROR: video-core installation failed.${NC}"
    exit 1
fi

echo ""

# ---------------------------------------------------------------------------
# 3. Register SKILL.md files as OpenClaw Global Skills
# ---------------------------------------------------------------------------

echo -e "${YELLOW}[3/5] Registering skills with OpenClaw...${NC}"

declare -A SKILLS=(
    ["video-core"]="$PACKAGES_DIR/video-core/SKILL.md"
    ["genre-docu"]="$PACKAGES_DIR/genre-docu/SKILL.md"
    ["genre-edu"]="$PACKAGES_DIR/genre-edu/SKILL.md"
    ["genre-shortdrama"]="$PACKAGES_DIR/genre-shortdrama/SKILL.md"
    ["video-prod-suite"]="$PACKAGES_DIR/video-prod-suite/SKILL.md"
)

SKILLS_DIR="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/skills}"

if command -v openclaw &>/dev/null; then
    for SKILL_NAME in "${!SKILLS[@]}"; do
        SKILL_PATH="${SKILLS[$SKILL_NAME]}"
        openclaw skill install "$SKILL_NAME" --path "$SKILL_PATH" 2>/dev/null && \
            echo -e "  $SKILL_NAME: ${GREEN}registered${NC}" || \
            echo -e "  $SKILL_NAME: ${YELLOW}skipped (may already exist)${NC}"
    done
else
    # Fallback: copy SKILL.md files into ~/.openclaw/skills/<name>/
    echo -e "  ${YELLOW}OpenClaw CLI not found. Copying skills to $SKILLS_DIR...${NC}"
    mkdir -p "$SKILLS_DIR"
    for SKILL_NAME in "${!SKILLS[@]}"; do
        SKILL_PATH="${SKILLS[$SKILL_NAME]}"
        mkdir -p "$SKILLS_DIR/$SKILL_NAME"
        cp "$SKILL_PATH" "$SKILLS_DIR/$SKILL_NAME/SKILL.md"
        echo -e "  $SKILL_NAME: ${GREEN}copied to $SKILLS_DIR/$SKILL_NAME/${NC}"
    done
fi

echo ""

# ---------------------------------------------------------------------------
# 4. Verify CLI accessibility
# ---------------------------------------------------------------------------

echo -e "${YELLOW}[4/5] Verifying CLI...${NC}"

if $PYTHON -m video_core.cli --help &>/dev/null; then
    echo -e "  video-core CLI: ${GREEN}working${NC}"
else
    echo -e "  video-core CLI: ${RED}failed — check your Python PATH${NC}"
fi

if command -v video-core &>/dev/null; then
    echo -e "  video-core (global): ${GREEN}available${NC}"
else
    echo -e "  video-core (global): ${YELLOW}run 'pip install -e packages/video-core' manually${NC}"
fi

echo ""

# ---------------------------------------------------------------------------
# 5. Done
# ---------------------------------------------------------------------------

echo -e "${YELLOW}[5/5] Done!${NC}"
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Available skills:"
echo "    - video-prod-suite  (meta — load this one)"
echo "    - video-core        (Layer 1 execution)"
echo "    - genre-docu        (Layer 2 documentary)"
echo "    - genre-edu         (Layer 2 educational)"
echo "    - genre-shortdrama  (Layer 2 short drama)"
echo ""
echo "  Example project:"
echo "    examples/antarctica_project/  (Layer 3 project guide)"
echo ""
echo "  Get started:"
echo "    Open your OpenClaw session and try:"
echo "    'Create a documentary about coffee making using genre-docu'"
echo ""
