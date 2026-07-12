---
name: genre-shortdrama
description: "Layer 2 类型导演——短剧/竖屏连续剧。触发关键词：短剧、霸总、连续剧、short drama、vertical drama、series。"
type: direction
requires: ["video-core"]
version: "0.1.0"
---

# 类型：短剧 (Short Drama)

## 触发条件

当用户请求包含以下任一关键词时激活此类型：

- 中文：短剧、霸总、连续剧、网剧、微短剧、甜宠、虐恋
- 英文：short drama、vertical drama、soap、melodrama、series、episode、cliffhanger

## 视听语法（Creative Rules）

### 1. 画面生成

调用 `video-core generate` 时：

```
--style realistic
```

**Prompt 后缀**——每条正向提示词末尾必须追加：

```
, cinematic lighting, dramatic shadows, close-up shot, 9:16 vertical aspect ratio, high contrast, film grain, intense emotion, professional color grading
```

**负向提示词**：

```
--negative "cartoon, anime, illustration, flat lighting, wide shot, landscape orientation, low contrast, blurry"
```

### 2. 语音 / TTS

按角色原型的推荐 TTS 音色配置：

```
男主角：     "drama_hero"       （深沉、有磁性、略带气声）
女主角：     "drama_heroine"    （清晰、有情感层次、年轻）
反派：       "drama_villain"    （冷酷、沉稳、有威胁感）
旁白：       "drama_narrator"   （戏剧性停顿、有分量）
```

### 3. Remotion 渲染

通过 Remotion 组装成片时：

```
--template ShortDramaStyle
```

**字幕样式**（默认）：
- 字体颜色：**白色** + **黑色描边**（竖屏短剧标准）
- 位置：**bottom_center**（下三分之一，避开人脸）
- 字号：28px（适配手机观看）
- 动画：逐字卡拉 OK 高亮效果跟随当前对话

### 4. 剪辑节奏

- **单集时长**：1–3 分钟
- **平均镜头时长**：1.5–3 秒（快节奏）
- **转场**：硬切为主，关键揭示时刻使用闪白
- **悬念结尾**：最后 5 秒使用慢推镜 + 渐黑
- **竖屏格式**：1080×1920 (9:16) 原生分辨率
- **音频**：对话优先，关键节点加入戏剧性音效

---

## 执行流程

1. **检查 Layer 3 覆盖**：查找当前项目的
   `.openclaw/skills/project-guide/SKILL.md`。

2. **生成画面**：
   ```bash
   video-core generate \
     --style realistic \
     --prompt "<场景描述>, cinematic lighting, dramatic shadows, close-up shot, 9:16 vertical aspect ratio, high contrast" \
     --width 1080 --height 1920 \
     --negative "cartoon, anime, illustration, flat lighting, wide shot, landscape orientation"
   ```

3. **Remotion 组装**：
   ```bash
   video-core render-remotion \
     --template ShortDramaStyle \
     --output episode_01.mp4 \
     --props '<包含场次、角色和字幕的 JSON>'
   ```

4. **叠加角色对白音频**：
   ```bash
   video-core audio-overlay \
     --video episode_01.mp4 \
     --audio dialogue_mix.mp3 \
     --output episode_01_final.mp4
   ```

---

## 特殊注意事项

### 角色一致性

如果项目指南定义了角色档案（姓名、外貌、音色），请对同一角色在不同集之间
使用相同的 seed 值，以保持视觉一致性。

### 集数命名规范

输出文件应遵循格式：`S01E01_标题.mp4`、`S01E02_标题.mp4`，以此类推。

---

## 冲突解决

Layer 3 项目指南（`.openclaw/skills/project-guide/SKILL.md`）覆盖以上所有默认值。
对于短剧类型尤其重要——项目指南通常会定义角色姓名、具体情节走向和独特的风格要求
（如"所有闪回镜头均为黑白"）。
