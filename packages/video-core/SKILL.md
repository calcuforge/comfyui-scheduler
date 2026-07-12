---
name: video-core
description: "Layer 1 原子执行层——封装 ComfyUI、FFmpeg、Remotion。需要生成画面、编辑视频或渲染合成时使用。"
type: execution
version: "0.1.0"
---

# Video Core — Layer 1 原子执行层

## 技能概述

Video Core 是视频生产流水线的"施工队"。它将底层工具（ComfyUI、FFmpeg、Remotion）
封装为简洁的 CLI 命令，供 Agent 通过 `bash` 工具调用。它只知道**如何**执行，
但不知道**要创作什么**。

**核心原则**：video-core 不做任何创意决策。它接收参数，返回文件路径。
Layer 2（Genre Director）和 Layer 3（Project Guide）负责提供创意方向。

---

## 前置条件

- Python 3.10+，已安装 `video-core` 包
- ComfyUI 服务端运行中（使用 `generate` 命令时需要）
- FFmpeg 在 PATH 中（使用 `concat`、`trim`、`audio-overlay`、`text-overlay`、`merge-image-audio` 时需要）
- Node.js + Remotion 项目（使用 `render-remotion` 时需要）

---

## 可用命令

### `video-core generate` — AI 视频/图像生成

向 ComfyUI 提交 Prompt 并下载结果。

```bash
video-core generate \
  --style cinematic \
  --prompt "一只猫走过夜晚霓虹灯照亮的巷子" \
  --seed 42 \
  --comfy-url http://127.0.0.1:8188 \
  --output-dir ./outputs
```

**参数说明：**

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--style` | **是** | — | 风格标签：`cinematic`、`anime`、`realistic` |
| `--prompt` | **是** | — | 正向提示词 |
| `--negative` | 否 | — | 负向提示词（覆盖 schema 默认值） |
| `--seed` | 否 | `-1` | 随机种子（`-1` = 随机） |
| `--steps` | 否 | schema 值 | 采样步数 |
| `--cfg` | 否 | schema 值 | CFG 引导系数 |
| `--width` | 否 | schema 值 | 输出宽度（像素） |
| `--height` | 否 | schema 值 | 输出高度（像素） |
| `--comfy-url` | 否 | `http://127.0.0.1:8188` | ComfyUI 服务地址 |
| `--output-dir` | 否 | `outputs` | 结果保存目录 |
| `--timeout` | 否 | `300` | 最大等待时间（秒） |

**输出**（JSON 输出到 stdout）：
```json
{"status": "completed", "style": "cinematic", "files": ["outputs/final_00001.mp4"]}
```

如果提供了 `--negative` 参数，会覆盖 schema 中默认的负向提示词。不提供则使用默认值。

---

### `video-core concat` — 拼接视频片段

将多个视频文件首尾拼接（编码相同时可无损拼接）。

```bash
video-core concat \
  --clips scene1.mp4 scene2.mp4 scene3.mp4 \
  --output final_cut.mp4
```

### `video-core trim` — 裁剪视频片段

从视频中截取一段。

```bash
video-core trim \
  --input raw_footage.mp4 \
  --start 00:01:30 \
  --duration 00:00:15 \
  --output clip.mp4
```

使用 `--end` 替代 `--duration` 可指定绝对结束时间码。

### `video-core audio-overlay` — 叠加音频

为视频添加旁白或背景音乐。

```bash
video-core audio-overlay \
  --video scene.mp4 \
  --audio narration.mp3 \
  --output scene_with_audio.mp4 \
  --volume 0.8
```

使用 `--no-mix` 可完全替换原始音频轨道。

### `video-core text-overlay` — 烧录字幕/文字

```bash
video-core text-overlay \
  --video scene.mp4 \
  --text "第一章：开端" \
  --output scene_titled.mp4 \
  --color yellow \
  --shadow-color black \
  --shadow-offset 2
```

### `video-core merge-image-audio` — 图片 + 音频 → 视频

将静态图片与音频合成为视频（适合播客风格）。

```bash
video-core merge-image-audio \
  --image cover_art.png \
  --audio episode.mp3 \
  --output podcast_video.mp4 \
  --fps 24
```

### `video-core render-remotion` — Remotion 渲染

```bash
video-core render-remotion \
  --template DocStyle \
  --output documentary_final.mp4 \
  --props '{"title":"我的影片","subtitles":[{"text":"你好","start":0,"end":3}]}'
```

### `video-core list-styles` — 列出可用的 ComfyUI 风格

```bash
video-core list-styles
# {"styles": ["anime", "cinematic", "realistic"]}
```

### `video-core check-comfy` — 健康检查

```bash
video-core check-comfy --comfy-url http://127.0.0.1:8188
# {"comfy_available": true, "url": "http://127.0.0.1:8188"}
```

---

## 给 OpenClaw Agent 的注意事项

1. **先检查 ComfyUI**：在尝试生成前务必执行 `video-core check-comfy`。
   如果返回 `false`，告知用户先启动 ComfyUI 服务端。

2. **Style tag 来自 Genre Director**：当 Layer 2 技能指定
   "使用 style_tag='cinematic'"时，将该值直接传给 `--style`。

3. **Prompt 拼接**：Genre Director（或 Project Guide）负责组装完整的 Prompt。
   video-core 只负责转发。在调用 `generate` 之前，应先拼接好类型特定的后缀
   （如", handheld shot, documentary style"）。

4. **输出路径**：所有命令输出 JSON 格式。解析 `files` 字段获取生成文件的列表。
   这些路径是相对于工作目录的。

5. **错误处理**：如果命令以非零状态退出，读取 stderr 获取错误信息。常见问题：
   - ComfyUI 未启动
   - 工作流中存在重复的节点名称（会列出所有重复项）
   - 引用的节点名称不存在（会列出所有可用名称）
   - FFmpeg 不在 PATH 中
