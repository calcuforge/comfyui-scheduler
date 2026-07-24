
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
