# Workflow List

## Summary

| ID | Type | Purpose | Output |
|----|------|---------|--------|
| index_tts_2 | text_to_speech | text-to-speech requests | audio |
| ltx2.3_flf2v_int8 | first-last-frame-to-video | first-last-frame-to-video requests | video |
| ltx2.3_i2v_int8 | image-to-video | image-to-video requests | video |
| ltx2.3_t2v_int8 | text-to-video | text-to-video requests | video |
| nvidia_rtx_image_upscale | image-upscale | image upscale requests | image |
| nvidia_rtx_video_upscale | video-upscale | video upscale requests | video |
| ominivoice_voice_design | text_to_speech | Character voice design based on text-to-speech | audio |
| qwen_image_edit_2511_int8_step4 | image-to-image | image-to-image requests | image |
| wan2.2_svi2pro_vbvr_int8 | image-to-video | image-to-video requests | video |
| z_image_fp16 | text_to_image | text-to-image requests | image |

## Input Fields

### index_tts_2

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | yes | Audio text content |
| `voice_file` | file | yes | Tone reference audio file |

```bash
comfyui-scheduler run -w index_tts_2 -i '{"content": "hello world this is a test", "voice_file": "C:/Users/anson/Downloads/f8b1504e2799c77536d3fae52be4f3ca.mp3"}'
```

### ltx2.3_flf2v_int8

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `first_frame_image` | file | yes | The reference image for the first frame of the video |
| `fps` | float | yes | frame rate |
| `height` | int | yes | Pixel height of the generated video |
| `last_frame_image` | file | yes | The reference image for the last frame of the video |
| `length` | int | yes | The duration of the generated video, in seconds |
| `prompt` | string | yes | First-Last-Frame-to-Video prompt |
| `width` | int | yes | Pixel width of the generated video |
| `negative_prompt` | string | no | First-Last-Frame-to-Video negative prompt |
| `seed` | int | no | Random seed |

### ltx2.3_i2v_int8

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fps` | float | yes | frame rate |
| `height` | int | yes | Pixel height of the generated video |
| `image_file` | file | yes | The reference image for the first frame of the video |
| `length` | int | yes | The duration of the generated video, in seconds |
| `prompt` | string | yes | Image-to-Video prompt |
| `width` | int | yes | Pixel width of the generated video |
| `negative_prompt` | string | no | Image-to-Video negative prompt |
| `seed` | int | no | Random seed |

### ltx2.3_t2v_int8

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fps` | float | yes | frame rate |
| `height` | int | yes | Pixel height of the generated video |
| `length` | int | yes | The duration of the generated video, in seconds |
| `prompt` | string | yes | Text-to-Video prompt |
| `width` | int | yes | Pixel width of the generated video |
| `negative_prompt` | string | no | Text-to-Video negative prompt |
| `seed` | int | no | Random seed |

### nvidia_rtx_image_upscale

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image_file` | file | yes | Source image that needs to be enlarged |
| `magnification` | float | yes | magnification |

### nvidia_rtx_video_upscale

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `magnification` | float | yes | magnification |
| `video_file` | file | yes | Source video that needs to be enlarged |

```bash
comfyui-scheduler run -w nvidia_rtx_video_upscale -i '{"video_file": "C:/Users/anson/Downloads/wan22_00002.mp4", "magnification": 2.0}'
```

### ominivoice_voice_design

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `voice_instruct` | string | yes | Voice Instruct |
| `content` | string | no | Audio text content |
| `seed` | int | no | Random seed |
| `speed` | float | no | Speed |

```bash
comfyui-scheduler run -w ominivoice_voice_design -i '{"voice_instruct": "男，中年，极低音调", "content": "这不该是兽人的命运"}'
```

### qwen_image_edit_2511_int8_step4

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `height` | int | yes | Pixel height of the generated image |
| `image_file` | file | yes | The reference image |
| `prompt` | string | yes | Image-to-Image prompt |
| `width` | int | yes | Pixel width of the generated image |
| `negative_prompt` | string | no | Image-to-Image negative prompt |
| `seed` | int | no | Random seed |

```bash
comfyui-scheduler run -w qwen_image_edit_2511_int8_step4 -i '{"image_file": "C:/Users/anson/Downloads/desert.png", "prompt": "make it anime style", "width": 1024, "height": 1024}'
```

### wan2.2_svi2pro_vbvr_int8

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fps` | int | yes | frame rate |
| `height` | int | yes | Pixel height of the generated video |
| `image_file` | file | yes | The reference image for the first frame of the video |
| `prompt` | string | yes | Image-to-Video prompt,format:prompt1\|second prompt1\|second ... |
| `width` | int | yes | Pixel width of the generated video |
| `negative_prompt` | string | no | Image-to-Video negative prompt |
| `seed` | int | no | Random seed |

```bash
comfyui-scheduler run -w wan2.2_svi2pro_vbvr_int8 -i '{"image_file": "C:/Users/anson/Downloads/001.jpg", "prompt": "a girl dancing|5\na girl laughing|5", "width": 640, "height": 384, "fps": 16}'
```

### z_image_fp16

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `height` | int | yes | Pixel height of the generated image |
| `prompt` | string | yes | Text-to-Image prompt |
| `width` | int | yes | Pixel width of the generated image |
| `negative_prompt` | string | no | Text-to-Image negative prompt |
| `seed` | int | no | Random seed |

```bash
comfyui-scheduler run -w z_image_fp16 -i '{"prompt": "a cat sitting on a cloud", "width": 1024, "height": 768}'
```


## Run Output

All commands emit JSON to stdout with a unified structure:

```json
{"status": "<ok|error>", "msg": "<human-readable message>", "data": { ... }}
```

Use `--debug` to print progress information to stderr (uploads, scheduler decisions, etc.).

### `comfyui-scheduler run` output

**Success** (`status: "ok"`):

```json
{
  "status": "ok",
  "msg": "Workflow completed — 1 file(s)",
  "data": {
    "workflow_id": "z_image_fp16",
    "prompt_id": "a1b2c3d4-...",
    "output_type": "image",
    "files": [
      {
        "kind": "image",
        "url": "http://127.0.0.1:8188/view?filename=ComfyUI_00001_.png&subfolder=&type=output",
        "filename": "ComfyUI_00001_.png"
      }
    ]
  }
}
```

**Error** (`status: "error"`):

```json
{
  "status": "error",
  "msg": "No ComfyUI node is reachable.",
  "data": {}
}
```

### `comfyui-scheduler status` output

```json
{
  "status": "ok",
  "msg": "ok",
  "data": {
    "nodes": [
      {"name": "node1", "url": "http://127.0.0.1:8188", "running": 0, "pending": 0, "status": "reachable"}
    ]
  }
}
```

### `comfyui-scheduler node list` output

```json
{
  "status": "ok",
  "msg": "ok",
  "data": {
    "nodes": [
      {"id": "node1", "url": "http://127.0.0.1:8188", "name": "node1", "blocking": true}
    ]
  }
}
```

### `comfyui-scheduler workflow import-all` output

```json
{
  "status": "ok",
  "msg": "Imported 6, skipped 1",
  "data": {
    "imported": ["index_tts_2", "z_image_fp16"],
    "skipped": ["ltx2.3_i2v_int8"]
  }
}
```

## ominivoice_voice_design 

### Voice Instruct 
Voice attributes,comma-separated or full-width comma-separated.e.g:male,indian accent And 男，河南话.The generated language depends on the language of the input "Voice Instruct"

| Category | Valid Values |
| :--- | :--- |
| Gender | 男, 女 |
| Age | 儿童, 少年, 青年, 中年, 老年 |
| Dialect | 四川话, 东北话, 陕西话, 河南话, 云南话, 贵州话, 甘肃话, 宁夏话, 石家庄话, 济南话, 青岛话, 桂林话 |
| Pitch | 极低音调, 低音调, 中音调, 高音调, 极高音调 |
| Style | 耳语 |

| Category | Valid Values |
| :--- | :--- |
| Gender | male, female |
| Age | child, young adult, teenager, middle-aged, elderly |
| Accent | american accent, british accent, australian accent, canadian accent, chinese accent, indian accent, japanese accent, korean accent, portuguese accent, russian accent |
| Pitch | very low pitch, low pitch, moderate pitch, high pitch, very high pitch |
| Style | whisper |

### Speed
Speaking speed factor
`>1.0 = faster, <1.0 = slower`
