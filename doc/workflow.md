# Workflow List

## Summary

| ID | Type | Purpose | Output |
|----|------|---------|--------|
| index_tts_2 | text_to_speech | text-to-speech requests | audio |
| nvidia_rtx_video_upscale | video-upscale | video upscale requests | video |
| qwen3_tts_voice_design | text_to_speech | Character voice design based on text-to-speech | audio |
| qwen_image_edit_2511_int8_step4 | image-to-image | image-to-image requests | image |
| wan2.2_svi2pro_vbvr_int8 | image-to-video | image-to-video requests | video |
| z_image_fp16 | text_to_image | text-to-image requests | image |

## Input Fields

### index_tts_2

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | yes | Audio text content |
| `voice_file` | file | yes | Tone reference audio file |

### nvidia_rtx_video_upscale

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `magnification` | int | yes | magnification |
| `video_file` | file | yes | Source video that needs to be enlarged |

### qwen3_tts_voice_design

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | yes | Timbre Prompt |
| `content` | string | no | Audio text content |
| `seed` | int | no | Random seed |

### qwen_image_edit_2511_int8_step4

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `height` | int | yes | Pixel height of the generated image |
| `image_file` | file | yes | The reference image |
| `prompt` | string | yes | Image-to-Image prompt |
| `width` | int | yes | Pixel width of the generated image |
| `negative_prompt` | string | no | Image-to-Image negative prompt |
| `seed` | int | no | Random seed |

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

### z_image_fp16

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `height` | int | yes | Pixel height of the generated image |
| `prompt` | string | yes | Text-to-Image prompt |
| `width` | int | yes | Pixel width of the generated image |
| `negative_prompt` | string | no | Text-to-Image negative prompt |
| `seed` | int | no | Random seed |

