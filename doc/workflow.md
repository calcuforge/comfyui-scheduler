# Workflow List

| ID | Type | Purpose | Output | Input Fields |
|----|------|---------|--------|--------------|
| index_tts_2 | text_to_speech | text-to-speech requests | audio | content (string, required), voice_file (file, required) |
| nvidia_rtx_video_upscale | video-upscale | video upscale requests | video | magnification (int, required), video_file (file, required) |
| qwen3_tts_voice_design | text_to_speech | Character voice design based on text-to-speech | audio | prompt (string, required), content (string, optional), seed (int, optional) |
| qwen_image_edit_2511_int8_step4 | image-to-image | image-to-image requests | image | seed (int, optional), prompt (string, required), width (int, required), height (int, required), negative_prompt (string, optional), image_file (file, required) |
| wan2.2_svi2pro_vbvr_int8 | image-to-video | image-to-video requests | video | seed (int, optional), prompt (string, required), fps (int, required), width (int, required), height (int, required), negative_prompt (string, optional), image_file (file, required) |
| z_image_fp16 | text_to_image | text-to-image requests | image | prompt (string, required), negative_prompt (string, optional), seed (int, optional), width (int, required), height (int, required) |
