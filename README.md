# OpenClaw 视频生产套件

基于三层洋葱架构的 AI 视频生成技能库：**执行层 → 导演层 → 项目定制层**。

## 架构设计

```
video-prod-suite (元技能：安装这一个即可)
├── Layer 1: video-core        ← ComfyUI + FFmpeg + Remotion 封装
├── Layer 2: genre-docu        ← 伪纪录片视听语法
├── Layer 2: genre-edu         ← 科普讲解视听语法
└── Layer 2: genre-shortdrama  ← 短剧/竖屏剧视听语法

Layer 3: .openclaw/skills/project-guide/SKILL.md  ← 单个项目的定制覆盖
```

## 快速开始

```bash
# 1. 克隆并安装
git clone <repo-url> video-stack
cd video-stack/video-stack-skill
chmod +x install_all.sh
./install_all.sh

# 2. 启动 ComfyUI（另开终端）
# （你的 ComfyUI 启动命令）

# 3. 在 OpenClaw 中尝试：
# "用 genre-docu 生成一个关于咖啡制作的伪纪录短片"
```

## 工作原理

**Layer 1 (video-core)** 是执行引擎。它知道*如何*调用 ComfyUI、FFmpeg 和
Remotion，但不知道*要创作什么*内容。

**Layer 2 (Genre Director)** 定义每种视频类型的"视听语法"——Prompt 后缀、
TTS 音色、字幕样式、剪辑节奏。

**Layer 3 (Project Guide)** 存放在项目目录的 `.openclaw/skills/` 中，
用于覆盖 Layer 2 的默认规则（角色设定、自定义字体、特殊调色方案等）。

## 示例项目

参考 `examples/antarctica_project/`，这是一个完整的 Layer 3 示例。它覆盖了
genre-docu 的默认设置：将白字黑描边字幕改为**黄色字幕**，定义了三位南极科考
站角色的档案，并规定了每集 5 分钟的结构模板。

## 环境要求

- Python 3.10+
- FFmpeg（视频编辑）
- ComfyUI 服务端（AI 画面生成）
- Node.js（可选，Remotion 渲染需要）
- OpenClaw（技能集成）
