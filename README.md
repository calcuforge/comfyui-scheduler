# comfyui-scheduler

Command-line tool for executing ComfyUI workflows on remote ComfyUI servers.  Supports multi-node load balancing, file upload, blocking execution with progress, and basic-auth credentials.

## Installation

```bash
cd comfyui-scheduler
pip install -e .
```

This registers the `comfyui-scheduler` command globally.

> **Requirements:** Python ≥ 3.10.  Dependencies: `requests`, `websockets`, `click`, `pyyaml`.

---

## Quick Start

```bash
# 1. Register a ComfyUI node
comfyui-scheduler node add --id node1 --url http://127.0.0.1:8188

# 2. Import workflows into the local database
comfyui-scheduler workflow import-all

# 3. Run a workflow by ID with simplified inputs
comfyui-scheduler run -w qwen_image_edit_2511_int8_step4 -i '{"image_file": "./photo.png", "prompt": "make it anime style", "width": 1024, "height": 1024}'

# 4. Run a workflow from a JSON file with explicit inputs
comfyui-scheduler run -f ./my_workflow.json -i '[{"type":"file","value":"./photo.png","node_title":"Load Image","node_field":"image"}]'
```

> See [doc/workflow.md](doc/workflow.md) for the full workflow list, input fields, and command examples.

---

## Pipeline Execution (`run`)

The `run` command is the core of the tool. It loads a workflow, uploads input files, submits the job, blocks until completion, and returns output file URLs.

### Using a Workflow ID (recommended)

Workflows imported into the local database can be referenced by ID. Inputs are specified as a JSON object where keys map to workflow input fields:

```bash
comfyui-scheduler run -w <workflow-id> -i '{"<field>": <value>, ...}'
```

**Examples:**

```bash
# Text-to-speech
comfyui-scheduler run -w index_tts_2 -i '{"content": "hello world", "voice_file": "./reference.mp3"}'

# Image-to-image
comfyui-scheduler run -w qwen_image_edit_2511_int8_step4 -i '{"image_file": "./input.png", "prompt": "make it anime style", "width": 1024, "height": 1024}'

# Image-to-video with multi-scene prompt
comfyui-scheduler run -w wan2.2_svi2pro_vbvr_int8 -i '{"image_file": "./001.jpg", "prompt": "a girl dancing|5\na girl laughing|5", "width": 640, "height": 384, "fps": 16}'
```

Input values are automatically typed based on the workflow's `input_node_mapping`: strings and numbers are set directly on workflow nodes, while `file`-typed fields are uploaded to the server first.

### Using a Workflow File

You can also run a workflow directly from a JSON file. In this mode, inputs use the explicit array format:

```bash
comfyui-scheduler run -f ./workflow.json -i '[{"type":"string","value":"a cat","node_title":"Prompt","node_field":"text"}]'
```

### Options

| Option | Description |
|--------|-------------|
| `-w, --workflow-id ID` | Workflow ID from the database (preferred). Mutually required with `-f`. |
| `-f, --workflow-file PATH` | Path to a ComfyUI API-format workflow JSON file. |
| `-i, --inputs JSON` | Input values — a JSON object (with `-w`) or JSON array (with `-f`). |
| `--output-node TITLE` | `_meta.title` of the node to collect outputs from. Defaults to the last node. |

### Input Format: JSON Object (with `-w`)

When using `--workflow-id`, inputs are a JSON object. Each key corresponds to a field defined in the workflow's `input_node_mapping`:

```json
{"prompt": "a cat", "image_file": "./input.png", "width": 1024}
```

- `string` / `int` / `float` fields — the value is set directly on the target workflow node.
- `file` fields — the file is uploaded to the server and the resulting path is bound to the node.

### Input Format: JSON Array (with `-f`)

When using `--workflow-file`, inputs are an explicit JSON array:

```json
[
  {"type": "string", "value": "a cat", "node_title": "Prompt", "node_field": "text"},
  {"type": "file",   "value": "./input.png", "node_title": "Load Image", "node_field": "image"}
]
```

| Field | Description |
|-------|-------------|
| `type` | `"string"` for a text/number value, `"file"` for a file path to upload |
| `value` | The string content (for `"string"`) or local file path (for `"file"`) |
| `node_title` | `_meta.title` of the target workflow node |
| `node_field` | Input parameter name on that node |

### Output

On success the tool prints a JSON result with output file URLs:

```json
{
  "status": "ok",
  "data": {
    "workflow_id": "qwen_image_edit_2511_int8_step4",
    "task_id": "a1b2c3d4-...",
    "prompt_id": "e5f6g7h8-...",
    "output_type": "image",
    "files": [
      {"kind": "image", "url": "http://127.0.0.1:8188/view?filename=result_00001.png&subfolder=&type=output", "filename": "result_00001.png"}
    ]
  }
}
```

On failure the tool prints an error to stderr and exits with code 1:

```
error: Workflow execution failed: CUDA out of memory.
```

---

## Node Management

### `node add`

Register a ComfyUI node.

```bash
comfyui-scheduler node add --id node1 --url http://127.0.0.1:8188
comfyui-scheduler node add --id node2 --url http://10.0.0.5:8188 --name "gpu-server" --user admin --password s3cret
```

| Option | Required | Description |
|--------|----------|-------------|
| `--id` | yes | Unique node identifier |
| `--url`, `-u` | yes | ComfyUI server URL |
| `--name` | no | Human-readable label |
| `--user` | no | Basic-auth username |
| `--password` | no | Basic-auth password |

### `node list`

List all registered nodes.

```bash
comfyui-scheduler node list
```

### `node remove`

Remove a node by ID, name, or URL.

```bash
comfyui-scheduler node remove node1
comfyui-scheduler node remove http://127.0.0.1:8188
```

### `node import`

Batch-import nodes from YAML config files. If no files are specified, defaults to `data/default_nodes.yaml` and `data/nodes.yaml`.

```bash
comfyui-scheduler node import
comfyui-scheduler node import data/my_nodes.yaml
```

YAML format:

```yaml
- id: node1
  url: "http://127.0.0.1:8188"
  user: ""
  password: ""
  blocking: true
```

---

## Workflow Import

Workflows are stored in a local SQLite database (`db/workflows.db`) and referenced by ID at runtime.

### `workflow import`

Import a single workflow from a meta YAML file or workflow JSON file.

```bash
comfyui-scheduler workflow import data/default_workflows/meta/qwen_image_edit_2511_int8_step4.yaml
comfyui-scheduler workflow import data/default_workflows/workflow/index_tts_2.json
```

### `workflow import-all`

Batch-import all workflows from `data/default_workflows/` and `data/workflows/`. Default workflows are imported first; user workflows in `data/workflows/` override defaults with the same ID.

```bash
comfyui-scheduler workflow import-all
```

### Meta YAML Format

Each workflow can have a meta YAML file that defines its ID, input mapping, and command examples:

```yaml
id: qwen_image_edit_2511_int8_step4
status: enabled
api_json_file: data/default_workflows/workflow/qwen_image_edit_2511_int8_step4.json
type: image-to-image
purpose: image-to-image requests
output_type: image
command_example: |
  comfyui-scheduler run -w qwen_image_edit_2511_int8_step4 -i '{"image_file": "./input.png", "prompt": "make it anime style", "width": 1024, "height": 1024}'
input_node_mapping:
  image_file:
    description: The reference image
    node_input_field: "image"
    node_meta_title: "LoadImage"
    value_type: file
    required: true
  prompt:
    description: Image-to-Image prompt
    node_input_field: "prompt"
    node_meta_title: "TextEncodeQwenImageEditPlus (Positive)"
    value_type: string
    required: true
  width:
    description: Pixel width of the generated image
    node_input_field: "width"
    node_meta_title: "Empty Latent"
    value_type: int
    required: true
  height:
    description: Pixel height of the generated image
    node_input_field: "height"
    node_meta_title: "Empty Latent"
    value_type: int
    required: true
```

---

## Multi-Node Load Balancing

When multiple nodes are registered, `run` automatically picks the one with the smallest queue (running + pending jobs).

```bash
comfyui-scheduler node add --id node-a --url http://10.0.0.5:8188
comfyui-scheduler node add --id node-b --url http://10.0.0.6:8188
comfyui-scheduler node add --id node-c --url http://10.0.0.7:8188

# Auto-selects the least busy node
comfyui-scheduler run -w my_workflow -i '{...}'
```

All workflow execution uses automatic least-busy node selection.

### `status` — Check node availability

```bash
comfyui-scheduler status
comfyui-scheduler status --url http://10.0.0.5:8188
```

---

## Workflow JSON Format

The tool expects the standard **ComfyUI API-format JSON** — the JSON produced by ComfyUI's "Export (API)" button. Each node should have a `_meta.title` field for addressing:

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
    "inputs": {"images": ["1", 0]},
    "class_type": "SaveImage",
    "_meta": {"title": "Save Image"}
  }
}
```

---

## Storage

| Location | Content |
|----------|---------|
| `~/.comfyui-cli/nodes.json` | Registered ComfyUI nodes (URL, credentials, label) |
| `./db/workflows.db` | Imported workflow configurations (SQLite) |

---

## Error Codes

| Exit code | Meaning |
|-----------|---------|
| 0 | Workflow completed successfully |
| 1 | Workflow execution failed (server-side error, e.g. CUDA OOM, missing model) |
| 2 | Usage error (missing required option, etc.) |

---

## Programmatic Usage

```python
from comfyui_cli.executor import run as executor_run
from comfyui_cli import node_manager, node_db, workflow_db

# Node management
node_db.add_node(node_id="node1", url="http://127.0.0.1:8188")
api = node_manager.select_node()  # picks the least busy node

# Execute a workflow
result = executor_run(
    workflow_source={"1": {"inputs": {...}, "class_type": "...", "_meta": {"title": "..."}}},
    api=api,
    inputs=[{"type": "string", "value": "hello", "node_title": "Prompt", "node_field": "text"}],
)
print(result["files"])  # list of {"kind", "url", "filename"}
```
