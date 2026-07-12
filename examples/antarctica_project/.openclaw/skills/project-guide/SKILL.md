---
name: project-guide-antarctica
description: "Layer 3 项目指南——《南极日记》伪纪录片系列。覆盖 genre-docu 默认规则，提供项目特有的角色、字幕风格和分集结构。"
type: project-guide
version: "0.1.0"
overrides: ["genre-docu"]
---

# 南极日记 — 项目指南

## 项目简介

《南极日记》是一部 6 集伪纪录片系列，讲述麦克默多站（McMurdo Station）一支
虚构科考队的故事。整体基调：氛围感、忧郁、视觉冷峻。

## 角色档案

### Dr. Elena Vasquez（主角）
- 身份：冰川学家，旁白叙述者
- 年龄：42 岁
- TTS 音色：`narrator_alto`（女声，沉稳、略带疲惫）
- Prompt 用描述："Latina woman, 40s, tired eyes, parka, fur-lined hood"

### Dr. James Chen（配角）
- 身份：海洋生物学家
- 年龄：35 岁
- TTS 音色：`narrator_baritone`（男声，冷静、精准）
- Prompt 用描述："Asian man, 30s, glasses, clean-shaven, orange survival suit"

### 通讯员 Kowalski（配角）
- 身份：通讯官，喜剧担当
- 年龄：55 岁
- TTS 音色：`narrator_gravelly`（男声，沙哑、温暖）
- Prompt 用描述："White man, 50s, beard, weathered face, radio headset, coffee mug always in frame"

---

## 画面覆盖项

### 字幕样式（覆盖 genre-docu 默认值）

genre-docu 默认是"白字黑描边"。本项目改为：

```
--color yellow
--shadow-color "#000000"
--shadow-offset 3
--size 38
```

**为什么用黄色字幕？** 白色在冰雪背景中会丢失可读性。黄色确保在所有南极光照
条件下都清晰可见。

### Prompt 前缀（添加到 genre-docu 后缀之前）

每条 Prompt 开头必须加上：

```
Antarctic research station interior,
```

genre-docu 的后缀（", handheld shot, natural lighting, ..."）仍追加在最后。

### 调色方案

对所有生成的画面应用冷色调：
- 色温：-15（偏冷）
- 饱和度：-10（略微去饱和，营造荒凉感）

---

## 素材路径

| 素材 | 路径 |
|------|------|
| 片头 Logo | `assets/antarctica_logo.png` |
| 转场音效 | `assets/ice_crack.wav` |
| 背景环境音 | `assets/polar_wind_loop.wav` |
| 地图叠加层 | `assets/mcmurdo_map.png` |

---

## 单集结构

每集 5 分钟，按以下模板展开：

1. **冷开场**（30 秒）：极具冲击力的画面 + Dr. Vasquez 旁白，交代场景
2. **标题卡**（5 秒）："ANTARCTICA DIARIES — Episode N: <标题>"
3. **A 故事线**（2 分钟）：主线叙事，人物讲述 + B-roll
4. **通讯室**（1 分钟）：Kowalski 通过无线电提供喜剧调剂
5. **B 故事线**（1 分钟）：支线叙事
6. **悬念结尾**（30 秒）：缓慢推镜至神秘物体/事件，渐黑

---

## 特殊规则

1. **外景画面不使用音乐**：仅保留风雪环境音。内景画面可加入微弱的低频氛围音。

2. **无线电语音滤镜**：Kowalski 的所有对话需加上 EQ 滤波器
   （带通 400Hz–3kHz，轻微失真），模拟无线电传输效果。

3. **时间戳叠加**：每个画面角落显示时间戳：
   "DAY 47 — 03:42 AM"（等宽字体，18px，白色，80% 透明度）。
