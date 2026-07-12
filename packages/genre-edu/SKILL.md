---
name: genre-edu
description: "Layer 2 类型导演——科普/教育讲解视频。触发关键词：科普、教育、讲解、教学、explainer、educational、science。"
type: direction
requires: ["video-core"]
version: "0.1.0"
---

# 类型：科普讲解 (Educational / Science Explainer)

## 触发条件

当用户请求包含以下任一关键词时激活此类型：

- 中文：科普、教育、教学、讲解、知识、学习、科学、百科
- 英文：educational、explainer、tutorial、science、how-to、learn、knowledge

## 视听语法（Creative Rules）

### 1. 画面生成

调用 `video-core generate` 时：

```
--style anime
```

**Prompt 后缀**——每条正向提示词末尾必须追加：

```
, clean vector illustration, educational diagram, vibrant colors, simple shapes, isometric view, white background, infographic style
```

**负向提示词**：

```
--negative "dark, gritty, horror, scary, photorealistic, complex background, cluttered, messy, handwritten text"
```

### 2. 语音 / TTS

推荐 TTS 音色配置：

```
音色： "teacher_friendly"  （温和、亲切、略带热情的讲解音色）
语速： 1.0                 （自然语速）
```

### 3. Remotion 渲染

通过 Remotion 组装成片时：

```
--template EduStyle
```

**文字样式**（默认）：
- 字体颜色：**白色**，置于**深蓝** (#1a365d) 背景卡片上
- 标题字号：56px
- 正文字号：32px
- 要点揭示动画：从左侧滑入

### 4. 剪辑节奏

- **平均镜头时长**：4–8 秒（留出阅读文字的时间）
- **转场**：幻灯片之间的轻柔左推动画
- **音频**：清晰的旁白优先混音
- **视觉层次**：核心概念 → 图解 → 示例 → 小结

---

## 执行流程

1. **检查 Layer 3 覆盖**：查找当前项目的
   `.openclaw/skills/project-guide/SKILL.md`。

2. **生成画面**：
   ```bash
   video-core generate \
     --style anime \
     --prompt "<主题画面>, clean vector illustration, educational diagram, vibrant colors, simple shapes, infographic style" \
     --negative "dark, gritty, horror, scary, photorealistic, complex background, cluttered"
   ```

3. **Remotion 组装**：
   ```bash
   video-core render-remotion \
     --template EduStyle \
     --output explainer_final.mp4 \
     --props '<包含幻灯片和动画的 JSON>'
   ```

4. **叠加旁白**：
   ```bash
   video-core audio-overlay \
     --video explainer_final.mp4 \
     --audio narration.mp3 \
     --output explainer_with_voice.mp4
   ```

---

## 冲突解决

Layer 3 项目指南（`.openclaw/skills/project-guide/SKILL.md`）覆盖以上所有默认值。
