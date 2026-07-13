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
comfyui-cli run --workflow FILE [-a ASSET...] [--output-node TITLE] [--url URL] [--user U --password P]
```

## `run` Options

| Option | Purpose |
|--------|---------|
| `-w, --workflow PATH` | **(required)** ComfyUI API-format JSON workflow file |
| `-a, --asset PATH` | Upload a file before execution (repeatable) |
| `--asset-node TITLE` | Node that receives uploaded files (default: `Load Image`) |
| `--asset-param NAME` | Input parameter name on the asset node (default: `image`) |
| `--output-node TITLE` | Node to collect outputs from (default: last node) |
| `--url URL` | Direct server URL; skips registered nodes & load balancing |
| `--user USER` | Basic-auth user (only with `--url`) |
| `--password PASS` | Basic-auth password (only with `--url`) |

## Behavior

- **Without `--url`:** Auto-selects the least-busy registered node (smallest queue_running + queue_pending).
- **Blocks until completion:** Opens a WebSocket, waits for execution to finish or error.
- **Output:** Prints one download URL per generated file to stdout.
- **Errors:** Printed to stderr; exit code 0 on success, 1 on failure, 2 on usage error.

## Expected Workflow JSON Format

Standard ComfyUI API format exported from the web UI.  Nodes must have `_meta.title`:

```json
{"1": {"inputs": {...}, "class_type": "...", "_meta": {"title": "Load Image"}}, ...}
```

## Multi-Node Load Balancing

Register multiple nodes, then run without `--url` — the tool picks the least loaded:

```bash
comfyui-cli node add --url http://10.0.0.5:8188 --name node-a
comfyui-cli node add --url http://10.0.0.6:8188 --name node-b
comfyui-cli run -w workflow.json   # auto-picks idle node
```

## Typical Patterns

```
# Text-to-image
comfyui-cli run -w t2i.json

# Image-to-image with multiple inputs
comfyui-cli run -w img2img.json -a input.png -a mask.png

# Video processing
comfyui-cli run -w vid.json -a clip.mp4 --asset-node "Load Video"

# Direct node (no registration needed)
comfyui-cli run -w wf.json --url http://127.0.0.1:8188

# Authenticated node
comfyui-cli run -w wf.json --url https://comfy.example.com --user admin --password s3cret
```

## Storage

Nodes are stored in `~/.comfyui-cli/nodes.json`.
