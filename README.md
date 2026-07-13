# comfyui-cli

Command-line tool for executing ComfyUI workflows on remote ComfyUI servers.  Supports multi-node load balancing, file upload, blocking execution with progress, and basic-auth credentials.

## Installation

```bash
cd multi-comfyui-cli
pip install -e .
```

This registers the `comfyui-cli` command globally.

> **Requirements:** Python ≥ 3.10.  Dependencies: `requests`, `websockets`, `click`.

---

## Quick Start

```bash
# 1. Register a ComfyUI node
comfyui-cli node add --url http://192.168.1.100:8188

# 2. Run a workflow
comfyui-cli run --workflow ./my_workflow.json

# 3. Run with input images
comfyui-cli run -w ./img2img.json --asset ./photo.png
```

---

## Commands

### `node` — Manage ComfyUI node registrations

Nodes are persisted to `~/.comfyui-cli/nodes.json`.

#### `node add`

Register a new ComfyUI node.

```bash
comfyui-cli node add --url http://10.0.0.5:8188
comfyui-cli node add --url http://10.0.0.5:8188 --name "gpu-server-1"
comfyui-cli node add --url https://comfy.example.com --user admin --password s3cret
```

| Option | Required | Description |
|--------|----------|-------------|
| `--url`, `-u` | yes | ComfyUI server URL (e.g. `http://192.168.1.10:8188`) |
| `--user` | no | Basic-auth username |
| `--password` | no | Basic-auth password |
| `--name` | no | Human-readable label (defaults to URL) |

#### `node list`

List all registered nodes.

```bash
$ comfyui-cli node list
  1. gpu-server-1  [http://10.0.0.5:8188]
  2. gpu-server-2  [http://10.0.0.6:8188] (auth)
```

#### `node remove`

Remove a node by name or URL.

```bash
comfyui-cli node remove gpu-server-1
comfyui-cli node remove http://10.0.0.5:8188
```

#### `node clear`

Remove all registered nodes.

```bash
comfyui-cli node clear
```

---

### `run` — Execute a workflow

This is the main command.  It:

1. Loads the workflow JSON
2. Uploads any asset files (images, videos, masks) to the node
3. Binds uploaded files to the specified nodes in the workflow
4. Submits the workflow for execution
5. Opens a WebSocket and blocks until execution completes or errors
6. Prints download URLs for every generated output file

```bash
comfyui-cli run --workflow ./workflow.json
```

#### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--workflow`, `-w` | yes | — | Path to the ComfyUI API-format workflow JSON file |
| `--asset`, `-a` | no | — | Asset file to upload. Repeat `-a` for multiple files |
| `--asset-node` | no | `Load Image` | `_meta.title` of the node receiving uploaded assets |
| `--asset-param` | no | `image` | Input parameter name on the asset node |
| `--output-node` | no | (last node) | `_meta.title` of the output node to collect results from |
| `--url`, `-u` | no | — | Direct server URL (bypasses registered nodes and load balancing) |
| `--user` | no | — | Basic-auth username (only with `--url`) |
| `--password` | no | — | Basic-auth password (only with `--url`) |

#### Examples

```bash
# Simplest invocation: run on auto-selected idle node
comfyui-cli run -w workflow.json

# Direct-to-node (bypasses load balancing)
comfyui-cli run -w workflow.json --url http://10.0.0.5:8188

# Direct-to-node with auth
comfyui-cli run -w workflow.json --url https://comfy.example.com --user admin --password s3cret

# Upload input images into a "Load Image" node
comfyui-cli run -w img2img.json -a photo.png -a mask.png

# Upload a video into a "Load Video" node
comfyui-cli run -w vid2vid.json -a input.mp4 --asset-node "Load Video"

# Specify the output node
comfyui-cli run -w workflow.json --output-node "Save Image"
```

#### Output

On success the tool prints download URLs:

```
[upload] photo.png -> default_upload_folder/photo.png
[run] Submitting workflow to http://10.0.0.5:8188 ...
[run] Output node: 'Save Image' (42)
[run] Execution completed.  prompt_id=a1b2c3d4-...

[output] 3 file(s) generated:

  image   http://10.0.0.5:8188/view?filename=result_00001.png&subfolder=&type=output
  image   http://10.0.0.5:8188/view?filename=result_00002.png&subfolder=&type=output
  video   http://10.0.0.5:8188/view?filename=result.mp4&subfolder=&type=output
```

On failure the tool prints a readable error:

```
[error] Workflow execution failed: Execution error on server: CUDA out of memory.
```

---

### `status` — Check node availability

```bash
# All registered nodes
$ comfyui-cli status
  gpu-server-1: running=1  pending=3
  gpu-server-2: running=0  pending=0

# Specific node
$ comfyui-cli status --url http://10.0.0.5:8188
  http://10.0.0.5:8188: running=0  pending=2
```

---

## Multi-Node Load Balancing

When you run a workflow without `--url`, the tool automatically picks the node with the smallest queue (running + pending jobs).  This is how load balancing works:

1. All registered nodes are queried via `GET /queue`
2. The node with the fewest `queue_running` + `queue_pending` entries wins
3. The workflow is submitted to that node

If a node is unreachable it is assigned a sentinel queue size of 9999, effectively disqualifying it from selection.

```bash
# Register multiple nodes
comfyui-cli node add --url http://10.0.0.5:8188 --name "node-a"
comfyui-cli node add --url http://10.0.0.6:8188 --name "node-b"
comfyui-cli node add --url http://10.0.0.7:8188 --name "node-c"

# This will pick the least busy node
comfyui-cli run -w heavy_workflow.json
```

---

## Basic Auth

If your ComfyUI server is behind a reverse proxy with HTTP Basic Auth, provide credentials when adding the node:

```bash
comfyui-cli node add --url https://comfy.example.com --user admin --password s3cret
```

The credentials are stored in `~/.comfyui-cli/nodes.json` and automatically included in every HTTP and WebSocket request to that node.  Credentials are embedded in the WebSocket URL (`ws://user:password@host/ws?...`).

---

## Workflow JSON Format

The tool expects the standard **ComfyUI API-format JSON** — the JSON produced by ComfyUI's "Export (API)" button in the web UI.  Each node should have a `_meta.title` field for addressing:

```json
{
  "1": {
    "inputs": {"text": "a cat", "seed": 42},
    "class_type": "CLIPTextEncode",
    "_meta": {"title": "Prompt"}
  },
  "2": {
    "inputs": {"image": "input.png"},
    "class_type": "LoadImage",
    "_meta": {"title": "Load Image"}
  },
  "3": {
    "inputs": {"images": ["1", 0], ...},
    "class_type": "SaveImage",
    "_meta": {"title": "Save Image"}
  }
}
```

- **Node addressing:** Nodes are looked up by `_meta.title`, not numeric ID.  If multiple nodes share the same title, all are updated.
- **Asset binding:** Uploaded files are written into the `inputs` of the node specified by `--asset-node` / `--asset-param`.
- **Output node:** Defaults to the *last* node in the JSON dictionary.  Override with `--output-node`.

---

## Storage

All local state lives under `~/.comfyui-cli/`:

```
~/.comfyui-cli/
  nodes.json    # registered ComfyUI nodes (URL, credentials, label)
```

---

## Error Codes

| Exit code | Meaning |
|-----------|---------|
| 0 | Workflow completed successfully, outputs printed |
| 1 | Workflow execution failed (server-side error, e.g. CUDA OOM, missing model) |
| 2 | Usage error (missing required option, etc.) |

---

## Programmatic Usage

The package can also be imported directly:

```python
from comfyui_cli.api import ComfyUIApi
from comfyui_cli.workflow import Workflow
from comfyui_cli import node_manager

# Direct API usage
api = ComfyUIApi("http://10.0.0.5:8188", user="admin", password="s3cret")
wf = Workflow("path/to/workflow.json")
api.upload_file("input.png")
prompt_id = api.queue_and_wait(wf)
urls = api.build_output_urls(prompt_id, wf.get_node_id("Save Image"))

# Node management
node_manager.add_node("http://10.0.0.5:8188", name="server1")
api = node_manager.select_node()  # picks the least busy node
```
