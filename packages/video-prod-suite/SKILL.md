---
name: video-prod-suite
description: "元技能：聚合 video-core（Layer 1）和所有 genre director（Layer 2），提供统一的 AI 视频生成能力。安装这一个技能即可获得全部功能。"
type: meta-skill
version: "0.1.0"
dependencies:
  - video-core
  - genre-docu
  - genre-edu
  - genre-shortdrama
---

# Video Production Suite — 视频生产套件

## 概述

视频生产套件（`video-prod-suite`）是 OpenClaw 视频生成技能库的**统一入口**。
它是一个元技能：安装它即可获得所有子技能（Layer 1 执行引擎 + Layer 2 导演层）。

无需单独安装各个子技能——元技能会自动加载全部。

---

## 架构总览

```
video-prod-suite (元技能，入口)
├── video-core (Layer 1)      ← 原子执行层：ComfyUI、FFmpeg、Remotion
├── genre-docu (Layer 2)      ← 伪纪录片视听语法
├── genre-edu (Layer 2)       ← 科普讲解视听语法
└── genre-shortdrama (Layer 2) ← 短剧/竖屏剧视听语法
```

**Layer 3**（项目指南）不是子技能。它存放在每个项目的
`.openclaw/skills/project-guide/SKILL.md` 中，由 Genre Director 在运行时自动发现。

---

## 决策树：选择哪种类型？

当用户要求创作视频时，请按照以下决策树选择 Genre：

```
用户说："帮我做一个……的视频"

├── 关键词：纪录、纪实、探访、采访、实拍、documentary、mockumentary
│   → 激活：genre-docu
│   → style_tag = "cinematic"
│   → template = "DocStyle"
│
├── 关键词：科普、教育、教学、讲解、知识、explainer、tutorial、science
│   → 激活：genre-edu
│   → style_tag = "anime"
│   → template = "EduStyle"
│
├── 关键词：短剧、霸总、连续剧、网剧、微短剧、short drama、vertical drama、episode
│   → 激活：genre-shortdrama
│   → style_tag = "realistic"
│   → template = "ShortDramaStyle"
│
└── 以上都不匹配
    → 询问用户偏好哪种类型
    → 列出可用类型并简要说明
```

---

## 典型工作流

选定 Genre 后，执行以下流程：

1. **检查 ComfyUI 是否在线**：
   ```bash
   video-core check-comfy
   ```

2. **检查 Layer 3 覆盖**（项目指南）：
   读取当前工作区的 `.openclaw/skills/project-guide/SKILL.md`。
   如果存在，其中的规则会覆盖 Genre Director 的默认值。

3. **生成画面**（一个或多个镜头）：
   ```bash
   video-core generate \
     --style <style_tag> \
     --prompt "<场景描述>, <类型后缀>" \
     --negative "<类型负向提示词>"
   ```

4. **Remotion 组装**：
   ```bash
   video-core render-remotion \
     --template <类型模板> \
     --output final.mp4 \
     --props '<json>'
   ```

5. **后期处理**（音频、字幕、转场）：
   ```bash
   video-core audio-overlay --video final.mp4 --audio voice.mp3 --output done.mp4
   video-core text-overlay --video done.mp4 --text "标题" --output complete.mp4
   ```

---

## Layer 3：项目特化覆盖

每个视频项目可以有一个**项目指南**来定制 Genre 的默认规则。文件位置：

```
<项目根目录>/.openclaw/skills/project-guide/SKILL.md
```

当存在项目指南时，**务必在生成前先读取**。Genre Director 的规则是默认值，
项目指南可以覆盖它们。

项目指南常见的覆盖项：
- 字幕颜色和字体
- 角色姓名和配音档案
- 特定素材路径（Logo、水印、片头片尾）
- 自定义 Prompt 前缀或后缀
- 独特的剪辑规则（如"所有夜景使用蓝色调色"）

---

## 环境准备

一条命令完成全部安装：

```bash
./install_all.sh
```

该脚本会：
1. 安装 `video-core` Python 包
2. 将所有 SKILL.md 注册为 OpenClaw Global Skill
3. 验证 FFmpeg 是否在 PATH 中
4. 检查 Node.js 是否可用于 Remotion

---

## 注意事项

- **video-core 是依赖项**：Genre Director 依赖它。如果 `video-core` CLI 不可用，
  提示用户运行 `install_all.sh`。
- **ComfyUI 是外部服务**：本套件不管理 ComfyUI 服务端，用户需要单独启动。
- **Style tag 稳定**：`cinematic`、`anime`、`realistic`。新增风格只需在
  video-core 的 schemas/ 目录下添加 workflow JSON 即可。
