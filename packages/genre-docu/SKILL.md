---
name: genre-docu
description: "Layer 2 类型导演——伪纪录片/纪实风格。触发关键词：纪录、纪实、探访、采访、documentary、mockumentary。"
type: direction
requires: ["video-core"]
version: "0.1.0"
---

# 类型：伪纪录片 (Pseudo-Documentary)

## 触发条件

当用户请求包含以下任一关键词时激活此类型：

- 中文：纪录、纪录片、纪实、实拍、探访、采访、跟拍
- 英文：documentary、mockumentary、docu-style、cinéma vérité、found footage

## 视听语法（Creative Rules）

以下为所有纪录片风格视频的**强制默认值**。如果当前项目的
`.openclaw/skills/project-guide/SKILL.md` 中存在 Layer 3 项目指南，
则以项目指南为准。

### 1. 画面生成

调用 `video-core generate` 时：

```
--style cinematic
```

**Prompt 后缀**——每条正向提示词末尾必须追加：

```
, handheld shot, natural lighting, grainy 16mm film texture, documentary style, candid moment, shallow depth of field
```

**负向提示词**——除非用户另有指定：

```
--negative "smooth, stabilized, cinematic CGI, studio lighting, polished, over-produced, artificial, 3d render, animation"
```

### 2. 语音 / TTS

推荐 TTS 音色配置：

```
音色： "narrator_deep"  （深沉、权威的男性解说音色）
语速： 0.95             （略慢，营造沉稳感）
```

### 3. Remotion 渲染

通过 Remotion 组装成片时：

```
--template DocStyle
```

**字幕样式**（默认）：
- 字体颜色：**白色**
- 描边/阴影：**黑色**，偏移 2px
- 位置：bottom_center
- 字体：系统无衬线字体（项目指南可指定自定义 .ttf）

### 4. 剪辑节奏

- **平均镜头时长**：3–6 秒
- **转场**：硬切（不用溶接）——纪录片惯例
- **音频**：旁白优先混音；背景音频为旁白音量的 30%
- **B-roll**：每 2–3 段人物讲述之间插入一段

---

## 执行流程

当用户请求伪纪录片风格视频时：

1. **检查 Layer 3 覆盖**：查找当前项目的
   `.openclaw/skills/project-guide/SKILL.md`。如果存在，其规则优先于此文件。

2. **生成画面**：
   ```bash
   video-core generate \
     --style cinematic \
     --prompt "<场景描述>, handheld shot, natural lighting, grainy 16mm film texture, documentary style, candid moment, shallow depth of field" \
     --negative "smooth, stabilized, cinematic CGI, studio lighting, polished, over-produced, artificial, 3d render, animation"
   ```

3. **生成 B-roll**（定场镜头、细节镜头），使用对应场景的 Prompt。

4. **Remotion 组装**：
   ```bash
   video-core render-remotion \
     --template DocStyle \
     --output documentary_final.mp4 \
     --props '<包含场次、字幕和时间轴的 JSON>'
   ```

5. **叠加旁白**：
   ```bash
   video-core audio-overlay \
     --video documentary_final.mp4 \
     --audio narration.mp3 \
     --output documentary_with_voice.mp4
   ```

---

## 冲突解决

如果当前工作区中存在 Layer 3 项目指南（位于
`.openclaw/skills/project-guide/SKILL.md`），其设置**覆盖**此文件的默认值。具体地：

- 字幕颜色、字体、位置 → 以项目指南为准
- TTS 音色 → 以项目指南为准
- Prompt 后缀 → 项目指南的前缀/后缀会追加或替换
- 模板选择 → 以项目指南为准

项目指南不需要重新定义所有内容——只需要写出与默认值不同的部分即可。
