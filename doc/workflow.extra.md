
## Run Output

All commands emit JSON to stdout with a unified structure:

```json
{"status": "<ok|error>", "msg": "<human-readable message>", "data": { ... }}
```

Use `--debug` to print progress information to stderr (uploads, scheduler decisions, etc.).

### `multi-comfyui-cli run` output

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

### `multi-comfyui-cli status` output

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

### `multi-comfyui-cli node list` output

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

### `multi-comfyui-cli workflow import-all` output

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

