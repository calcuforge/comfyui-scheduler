# comfyui-cli Usage (AI Agent Reference)

## Overview

`comfyui-cli` is a CLI tool to run ComfyUI workflows on remote servers.  It handles file upload, submission, blocking wait, and output collection.

## Essential Commands

### Add a node
```bash
comfyui-cli node add --url URL [--name NAME] [--user USER --password PASS]
```

### List nodes
```bash
comfyui-cli node list
```

### Remove a node
```bash
comfyui-cli node remove NAME_OR_URL
```

### Check node status
```bash
comfyui-cli status [--url URL]
```

### Run a workflow
```bash
comfyui-cli run --workflow FILE [-i INPUTS_JSON] [--output-node TITLE]
```

## `run` Options

| Option | Purpose |
|--------|---------|
| `-w, --workflow PATH` | **(required)** ComfyUI API-format JSON workflow file |
| `-i, --inputs JSON` | JSON array of input objects (default: `[]`) |
| `--output-node TITLE` | Node to collect outputs from (default: last node) |

## `--inputs` Format

JSON array where each object has:
- `type`: `"string"` for text, `"file"` for upload
- `value`: the string content or local file path
- `node_title`: `_meta.title` of target workflow node
- `node_field`: input parameter name on that node

Example:
```json
[
  {"type":"string","value":"a cat","node_title":"Prompt","node_field":"text"},
  {"type":"file","value":"./input.png","node_title":"Load Image","node_field":"image"}
]
```

## Behavior

- **Load balancing:** Auto-selects the least-busy registered node (smallest queue_running + queue_pending).
- **Blocks until completion:** Opens a WebSocket, waits for execution to finish or error.
- **Credentials:** Always taken from locally stored node config — register nodes before running.
- **Output:** Prints one download URL per generated file to stdout.
- **Errors:** Printed to stderr; exit code 0 on success, 1 on failure, 2 on usage error.

## Expected Workflow JSON Format

Standard ComfyUI API format exported from the web UI.  Nodes must have `_meta.title`:

```json
{"1": {"inputs": {...}, "class_type": "...", "_meta": {"title": "Load Image"}}, ...}
```

## Multi-Node Load Balancing

Register multiple nodes — the tool picks the least loaded:

```bash
comfyui-cli node add --url http://10.0.0.5:8188 --name node-a
comfyui-cli node add --url http://10.0.0.6:8188 --name node-b
comfyui-cli run -w workflow.json   # auto-picks idle node
```

## Typical Patterns

```
# Text-to-image
comfyui-cli run -w t2i.json -i '[{"type":"string","value":"a cat","node_title":"Prompt","node_field":"text"}]'

# Image-to-image with multiple inputs
comfyui-cli run -w img2img.json -i '[{"type":"file","value":"./input.png","node_title":"Load Image","node_field":"image"},{"type":"file","value":"./mask.png","node_title":"Load Mask","node_field":"image"}]'

# Video processing
comfyui-cli run -w vid.json -i '[{"type":"file","value":"./clip.mp4","node_title":"Load Video","node_field":"video"}]'
```
```

## Storage

Nodes are stored in `~/.comfyui-cli/nodes.json`.
