# AI Lip Sync Studio

A local Flask web application for turning still portraits into talking videos and preparing images for AI animation.

It brings three tools together under one web interface:

| Tool | What it does | Powered by |
|---|---|---|
| **Lip Sync** | Animates a face photo so it speaks a supplied voice recording | [SadTalker](https://github.com/OpenTalker/SadTalker), run locally |
| **Animation Studio** | Audio-driven portrait animation with facial expressions and upper-body movement, using pluggable engines | [EchoMimicV3](https://github.com/antgroup/echomimic_v3), run on a **remote GPU worker** |
| **Image Studio** | Runs images through processing modules such as resizing, format conversion and background removal | Pillow, [rembg](https://github.com/danielgatis/rembg) + ONNX Runtime |

All jobs run in the background. The browser polls for progress and shows the finished video or image with a download link.

---

## Table of contents

1. [Features](#features)
2. [Technology stack](#technology-stack)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Running the application](#running-the-application)
7. [How to use](#how-to-use)
8. [Project structure](#project-structure)
9. [HTTP API reference](#http-api-reference)
10. [Troubleshooting](#troubleshooting)
11. [Known limitations](#known-limitations)
12. [Development](#development)

---

## Features

### Lip Sync (SadTalker)
- Upload a face image (`.jpg`, `.jpeg`, `.png`) and a voice recording (`.wav`, `.mp3`, `.m4a`).
- Generates an MP4 talking-head video with SadTalker in a background thread.
- Uses fixed generation settings from [`app/services/sadtalker.py`](app/services/sadtalker.py) and [`config.py`](config.py): 256 px model, `full` preprocessing, expression scale `1.3`, and the GFPGAN face enhancer.
- Shows live status messages, an in-browser video preview and an MP4 download.
- Writes a full SadTalker log for every job to `logs/<job_id>.log`.

### Animation Studio (pluggable engines)
- Lists the available animation engines from the engine registry, with each engine's description and availability.
- Accepts a source image (`png`, `jpg`, `jpeg`, `webp`) and audio (`wav`, `mp3`, `m4a`, `aac`, `ogg`, `flac`), with drag-and-drop.
- Builds each engine's settings form automatically from the options the engine declares.
- **EchoMimic V3** engine settings: *Animation prompt* (default `A person speaking naturally.`), *Random seed* (default `43`) and *Inference steps* (default `25`, range 1–100).
- Shows a progress bar with percentage, an in-browser preview and a download link.
- New engines are discovered automatically. See [Adding an animation engine](#adding-an-animation-engine).

### Image Studio (processing modules)
- Upload a PNG, JPG/JPEG or WEBP image, by drag-and-drop or file picker.
- Select one or more processing modules. They run in sequence as a pipeline.
- Implemented modules:
  - **Image Preprocessor** (`image_preprocessor`): corrects EXIF orientation, optionally resizes (`width`, `height`, fit `contain`/`cover`/`stretch`), converts the format (`original`, `JPEG`, `PNG`, `WEBP`) and sets `quality` (1–100). It keeps DPI, ICC profile and EXIF metadata, and copies the original unchanged when no change is needed.
  - **Background Remover** (`background_remover`): removes the background with rembg (`u2net` or `u2netp` model, CPU) and outputs a transparent PNG. It appears as *Unavailable* until `rembg` and `onnxruntime` are installed.
- Shows an output preview and a download of the processed image.
- Images are limited to 10,000 px per side and 40 megapixels.

### Application shell
- Persistent sidebar navigation that can be collapsed on desktop and opens as a slide-out drawer on mobile.
- One shared dark design system across all pages.
- Rotating application log at `logs/application.log` (5 MB × 5 files), plus a log line for every request and response.

---

## Technology stack

| Layer | Technology |
|---|---|
| Language | Python **3.8** (required by SadTalker's pinned dependencies) |
| Environment | Conda (Miniconda or Anaconda) |
| Web framework | Flask 3.0 (blueprints, Jinja2 templates), Werkzeug |
| Lip-sync model | SadTalker (PyTorch 1.12.1, face-alignment, GFPGAN, basicsr, facexlib, librosa, kornia, safetensors, imageio-ffmpeg) |
| Animation model | EchoMimicV3, run by a separate GPU worker over HTTP (`requests`) |
| Image processing | Pillow, rembg, ONNX Runtime |
| Media tooling | FFmpeg |
| Frontend | Server-rendered HTML, one shared stylesheet, plain JavaScript (no frontend framework or build step) |
| Tests | Python `unittest` |

**Known working environment** (the `sadtalker` Conda environment used during development):

```
python 3.8.20       flask 3.0.3        werkzeug 3.0.6     requests 2.32.4
pillow 10.4.0       rembg 2.0.57       onnxruntime 1.18.1
torch 1.12.1+cpu    torchvision 0.13.1+cpu   torchaudio 0.12.1+cpu
numpy 1.23.4        face-alignment 1.3.5     gfpgan 1.3.8   basicsr 1.4.2
facexlib 0.3.0      librosa 0.9.2      kornia 0.6.8       safetensors 0.5.3
```

> There is no `requirements.txt` at the project root. Install dependencies with the steps in [Installation](#installation).

---

## Requirements

### Software
- **Git**
- **Miniconda or Anaconda**
- **FFmpeg** on your `PATH`. SadTalker needs it to encode videos.
- A modern browser (Chrome, Edge, Firefox or Safari).

### Hardware
- **Lip Sync runs on the CPU.** The SadTalker command in [`app/services/sadtalker.py`](app/services/sadtalker.py) always passes `--cpu`, so you don't need a GPU on the Flask machine. CPU generation is slow: expect minutes to hours depending on audio length and CPU. The timeout is 8 hours (`GENERATION_TIMEOUT = 28800`).
- **RAM:** at least 8 GB is recommended for SadTalker with GFPGAN enhancement.
- **Disk:** a few GB for the Conda environment and model checkpoints, plus space for uploads and generated videos.
- **EchoMimic V3 needs a separate GPU worker.** Inference doesn't run on the Flask machine. See [EchoMimic V3 remote worker](#echomimic-v3-remote-worker).

### Model files

#### SadTalker checkpoints, in `SadTalker/checkpoints/`
| File | Purpose |
|---|---|
| `SadTalker_V0.0.2_256.safetensors` | Main SadTalker model (256 px, matches `VIDEO_SIZE = 256`) |
| `mapping_00109-model.pth.tar` | Mapping network |
| `mapping_00229-model.pth.tar` | Mapping network |

#### GFPGAN / facexlib weights, in `SadTalker/gfpgan/weights/`
| File | Purpose |
|---|---|
| `GFPGANv1.4.pth` | Face enhancer used by `--enhancer gfpgan` |
| `alignment_WFLW_4HG.pth` | Face alignment |
| `detection_Resnet50_Final.pth` | Face detection |
| `parsing_parsenet.pth` | Face parsing |

> If `GFPGANv1.4.pth` is missing from both `gfpgan/weights/` and `checkpoints/`, SadTalker downloads it during the first job, so that job needs internet access.

#### Background removal models
rembg downloads the `u2net` / `u2netp` ONNX model the first time Background Remover runs (by default into `~/.u2net`). That first run needs internet access.

---

## Installation

The commands below use Windows paths, but the same steps work on Linux and macOS.

### 1. Clone the project

```bash
git clone https://github.com/gdesiganax/ai_lipsync.git
cd ai_lipsync
```

### 2. Clone SadTalker into `SadTalker/`

`SadTalker/` is listed in `.gitignore` and must be cloned separately. The app expects it at exactly this path (`SADTALKER_DIR = BASE_DIR / "SadTalker"`).

```bash
git clone https://github.com/OpenTalker/SadTalker.git SadTalker
```

### 3. Create and activate the Conda environment

```bash
conda create -n sadtalker python=3.8 -y
conda activate sadtalker
```

> **Important:** run Flask from this same environment. The app starts SadTalker with the same Python interpreter that runs Flask (`sys.executable`), so Flask, SadTalker and all their dependencies must live in one environment.

### 4. Install PyTorch (CPU build)

```bash
pip install torch==1.12.1+cpu torchvision==0.13.1+cpu torchaudio==0.12.1 --extra-index-url https://download.pytorch.org/whl/cpu
```

### 5. Install SadTalker's dependencies

```bash
pip install -r SadTalker/requirements.txt
```

### 6. Install the web application's dependencies

```bash
pip install flask==3.0.3 requests rembg==2.0.57 onnxruntime==1.18.1
```

`rembg` and `onnxruntime` are only needed for the Background Remover module. Without them, the rest of the app still works and the module shows as *Unavailable*.

### 7. Install FFmpeg

Either install it inside the Conda environment:

```bash
conda install -c conda-forge ffmpeg -y
```

Or install it system-wide and add its `bin` folder to `PATH`. Then check it works:

```bash
ffmpeg -version
```

### 8. Download the model files

**Linux / macOS / Git Bash** (needs `wget`):

```bash
cd SadTalker
bash scripts/download_models.sh
cd ..
```

**Windows without `wget`:** download the files listed in [Model files](#model-files) manually from the URLs in [`SadTalker/scripts/download_models.sh`](SadTalker/scripts/download_models.sh), and place them in `SadTalker/checkpoints/` and `SadTalker/gfpgan/weights/`.

> The script also downloads `SadTalker_V0.0.2_512.safetensors`. The app uses the 256 px model, so that file is optional.

### 9. (Optional) Verify the installation

```bash
python -m unittest discover -s tests
```

See [Running the tests](#running-the-tests) for the expected result.

---

## Configuration

All settings live in the `Config` class in [`config.py`](config.py). Paths are relative to the project root (`BASE_DIR`).

### Environment variables

Only the EchoMimic remote-worker settings are read from the environment. **The app doesn't load `.env` files**, so set these variables in your shell before starting it.

| Variable | Default | Description |
|---|---|---|
| `ECHOMIMIC_WORKER_URL` | *(unset)* | Base URL of the EchoMimic V3 worker, e.g. `https://my-gpu-worker.example.com`. |
| `ECHOMIMIC_WORKER_TOKEN` | *(unset)* | Bearer token sent as `Authorization: Bearer <token>`. |
| `ECHOMIMIC_WORKER_TIMEOUT` | `14400` | Seconds to wait for a worker job to finish (4 hours). |
| `ECHOMIMIC_WORKER_POLL_INTERVAL` | `3` | Seconds between job-status checks. |
| `ECHOMIMIC_WORKER_CONNECT_TIMEOUT` | `30` | Connection timeout in seconds for worker requests. |
| `ECHOMIMIC_WORKER_UPLOAD_TIMEOUT` | `300` | Read timeout in seconds while uploading media to the worker. |

The EchoMimic V3 engine counts as **available** only when both `ECHOMIMIC_WORKER_URL` and `ECHOMIMIC_WORKER_TOKEN` are set. No network check happens at startup.

**Windows (PowerShell):**

```powershell
$env:ECHOMIMIC_WORKER_URL = "https://my-gpu-worker.example.com"
$env:ECHOMIMIC_WORKER_TOKEN = "your-token"
```

**Linux / macOS / Git Bash:**

```bash
export ECHOMIMIC_WORKER_URL="https://my-gpu-worker.example.com"
export ECHOMIMIC_WORKER_TOKEN="your-token"
```

### Settings in `config.py`

| Setting | Value | Description |
|---|---|---|
| `SECRET_KEY` | `"change-this-local-development-key"` | Flask secret key. Change it before exposing the app beyond your machine. |
| `MAX_CONTENT_LENGTH` | `100 MB` | Maximum upload size per request. |
| `UPLOAD_FOLDER` | `uploads/` | Uploaded source files. |
| `OUTPUT_FOLDER` | `outputs/` | Generated videos and processed images. |
| `LOG_FOLDER` | `logs/` | Application log and per-job SadTalker logs. |
| `SADTALKER_DIR` | `SadTalker/` | SadTalker repository location. |
| `SADTALKER_CHECKPOINTS` | `SadTalker/checkpoints/` | Passed to SadTalker as `--checkpoint_dir`. |
| `VIDEO_SIZE` | `256` | SadTalker model resolution (`--size`). |
| `VIDEO_PREPROCESS` | `"full"` | SadTalker preprocessing mode (`--preprocess`). |
| `GENERATION_TIMEOUT` | `28800` | SadTalker job timeout in seconds (8 hours). |
| `ANIMATION_MODELS_DIR` | `models/` | Created at startup. Holds the EchoMimicV3 source checkout. |

`config.py` also defines `ECHOMIMIC_V3_DIR`, `ECHOMIMIC_V3_VARIANT`, `ECHOMIMIC_V3_PYTHON` and `ECHOMIMIC_V3_TIMEOUT`. These are left over from earlier local-inference work. **No current application code reads them.**

`uploads/`, `outputs/`, `logs/` and `models/` are created automatically when the app starts.

### EchoMimic V3 remote worker

The worker service **isn't part of this repository**. `models/EchoMimicV3/` holds a checkout of the upstream [EchoMimicV3](https://github.com/antgroup/echomimic_v3) source, but the Flask app never runs it. Any worker you use must provide the HTTP contract that [`app/services/animation/engines/echomimic_v3.py`](app/services/animation/engines/echomimic_v3.py) expects. Every request includes `Authorization: Bearer <ECHOMIMIC_WORKER_TOKEN>`.

| Method & path | Request | Expected response |
|---|---|---|
| `POST /jobs` | multipart form: `image` file, `audio` file, `prompt` (str), `seed` (int), `steps` (int, 1–100) | JSON `{"job_id": "..."}` |
| `GET /jobs/<job_id>` | — | JSON `{"status": "queued" \| "processing" \| "completed" \| "failed", "progress": 0-100, "message": "..."}` |
| `GET /jobs/<job_id>/result` | — | The MP4 file (streamed) |

Error responses may include a JSON `detail` field, which is shown in the job error.

---

## Running the application

From the project root, with the Conda environment active:

```bash
conda activate sadtalker
python run.py
```

Then open **http://127.0.0.1:5000** in your browser.

[`run.py`](run.py) starts Flask's development server with these settings:

```python
app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False, threaded=True)
```

- It listens on **localhost only**.
- `debug=True` turns on detailed error pages, but `use_reloader=False` means **code changes need a manual restart**.
- `threaded=True` lets status polling continue while jobs run.

> This is a development server for local use. It isn't hardened for public deployment.

Stop the server with `Ctrl+C`. This also stops any running jobs and clears their status, because job state is kept in memory.

---

## How to use

Use the sidebar on the left to switch tools. On narrow screens, open it with the ☰ button. On desktop, the **Collapse** button at the bottom shrinks it to icons.

| Sidebar item | URL |
|---|---|
| Video generation → **Lip Sync** | `/` |
| Video generation → **Animation Studio** | `/animation/` |
| Image tools → **Image Studio** | `/image-studio/` |

### Generate a talking video (Lip Sync)
1. Open **Lip Sync**.
2. Click or drop a **face image** (JPG/PNG). A clear, front-facing, well-lit portrait works best.
3. Click or drop a **voice recording** (WAV/MP3/M4A).
4. Click **Generate Talking Video**. Status messages appear below the button.
5. When it finishes, the video plays on the page. Use **Download Talking Video** to save the MP4.

Keep the tab open while it runs, because the page polls the server every 3 seconds. Generation runs on the CPU and can take a long time.

### Animate with an AI engine (Animation Studio)
1. Open **Animation Studio**.
2. Pick an engine in **Choose your engine**. The badge shows **Engine ready** or **Model installation required**. For EchoMimic V3, *ready* means the worker environment variables are set.
3. Add a **source image** and an **audio file** in **Add your media**.
4. Adjust the engine's **Generation settings** if any are shown.
5. Click **Generate animation**. This button stays disabled until an available engine, an image and an audio file are selected.
6. Watch the progress bar. When it completes, preview the video and click **Download your animation**.

### Process an image (Image Studio)
1. Open **Image Studio**.
2. Click or drop an image (PNG/JPG/JPEG/WEBP).
3. Tick one or more **Processing modules**. Each module's options appear when you select it. Leave *width* or *height* empty to keep the original size.
4. Click **Process Image**.
5. The result appears under **Output preview**. Transparent areas show as a checkerboard. Click **Download Processed Image**.

Modules run in the order they're listed. For example, selecting both modules resizes and converts the image first, then removes the background from the result.

---

## Project structure

```
ai_lipsync/
├── run.py                      # Entry point: creates the app and starts the dev server
├── config.py                   # Config class: paths, SadTalker settings, EchoMimic worker env vars
├── app/
│   ├── __init__.py             # create_app(): folders, logging, module registry, blueprints
│   ├── routes/                 # Flask blueprints (HTTP layer)
│   │   ├── main.py             #   main         → "/" (Lip Sync page)
│   │   ├── generation.py       #   generation   → "/api/*" (SadTalker jobs)
│   │   ├── animation.py        #   animation    → "/animation/*" (engines + jobs)
│   │   └── image_studio.py     #   image_studio → "/image-studio/*" (modules + jobs)
│   ├── services/
│   │   ├── sadtalker.py        # Runs SadTalker inference.py as a subprocess; in-memory job store
│   │   ├── animation/
│   │   │   ├── base.py         # AnimationEngine abstract base class
│   │   │   ├── registry.py     # EngineRegistry
│   │   │   ├── loader.py       # Auto-discovers engines in engines/
│   │   │   ├── job_manager.py  # Thread-pool job runner (1 worker) with progress tracking
│   │   │   └── engines/
│   │   │       └── echomimic_v3.py   # EchoMimic V3 remote-worker client
│   │   ├── modules/
│   │   │   ├── base.py         # ProcessingModule abstract base class
│   │   │   ├── registry.py     # ModuleRegistry
│   │   │   ├── loader.py       # Auto-discovers modules in processors/
│   │   │   ├── context.py      # ProcessingContext passed between modules
│   │   │   ├── pipeline.py     # Runs modules in sequence, records history
│   │   │   └── processors/
│   │   │       ├── image_preprocessor.py   # Orientation, resize, format conversion
│   │   │       ├── background_remover.py   # rembg background removal
│   │   │       └── *.py (empty)            # Placeholders: audio_cleanup, background_removal,
│   │   │                                   #   face_enhancement, image_upscaling
│   │   └── image_processing/
│   │       └── job_manager.py  # Thread-pool job runner (2 workers) for Image Studio
│   ├── templates/
│   │   ├── base.html           # App shell: sidebar, mobile top bar, content area
│   │   ├── partials/
│   │   │   ├── _sidebar.html   # Navigation groups and links
│   │   │   ├── _components.html# Macros: page_header, card, alert, dropzone, steps
│   │   │   └── _icons.html     # Inline SVG icon macro
│   │   ├── index.html          # Lip Sync page
│   │   ├── animation/index.html     # Animation Studio page (+ its page script)
│   │   └── image_studio/index.html  # Image Studio page (+ its page script)
│   └── static/
│       ├── css/studio.css      # Shared design system
│       └── js/
│           ├── app.js          # Lip Sync form submission and status polling
│           └── ui.js           # Sidebar collapse, mobile drawer, upload-zone feedback
├── tests/                      # unittest suite (API, jobs, registry, pipeline, preprocessor)
├── SadTalker/                  # SadTalker repo (cloned separately, git-ignored) + checkpoints
├── models/EchoMimicV3/         # Upstream EchoMimicV3 source checkout (not executed by the app)
├── uploads/                    # Runtime: uploaded files (git-ignored)
├── outputs/                    # Runtime: generated videos/images (git-ignored)
└── logs/                       # Runtime: application.log and <job_id>.log (git-ignored)
```

Notes:
- The root-level `static/` and `templates/` folders are empty and unused. Flask serves `app/static/` and `app/templates/`.

### Where files are written

| Tool | Uploads | Outputs |
|---|---|---|
| Lip Sync | `uploads/<job_id>/source.<ext>`, `audio.<ext>` | `outputs/<job_id>/…/*.mp4` |
| Animation Studio | `uploads/animation/<job_id>/` | `outputs/animation/<job_id>/echomimic_<id>.mp4` |
| Image Studio | `uploads/image_processing/<job_id>/` | `outputs/image_processing/<job_id>/<module>/<id>/…` |

The app never deletes these files automatically. Clean them up yourself when you need the disk space.

---

## HTTP API reference

The pages call these JSON endpoints. They're also useful for scripting and testing.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/generate` | Start a SadTalker job (multipart: `image`, `audio`) → `202 {job_id}` |
| `GET` | `/api/status/<job_id>` | SadTalker job status. Includes `video_url` when completed. |
| `GET` | `/api/video/<job_id>` | Stream the generated MP4 |
| `GET` | `/animation/api/engines` | List registered engines with their options and availability |
| `POST` | `/animation/api/generate` | Start an animation job (multipart: `engine`, `image`, `audio`, `options` as a JSON string) → `202 {job_id}` |
| `GET` | `/animation/api/jobs/<job_id>` | Animation job status, progress and error |
| `GET` | `/animation/api/jobs/<job_id>/video` | Stream the generated animation |
| `GET` | `/image-studio/api/modules` | List processing modules with their options and availability |
| `POST` | `/image-studio/api/process` | Start an image job (multipart: `image`, `module_ids` JSON list, `module_options` JSON object) → `202 {job_id}` |
| `GET` | `/image-studio/api/jobs/<job_id>` | Image job status and progress |
| `GET` | `/image-studio/api/jobs/<job_id>/preview` | View the processed image inline |
| `GET` | `/image-studio/api/jobs/<job_id>/download` | Download the processed image |

---

## Troubleshooting

### Installation

| Symptom | Cause / fix |
|---|---|
| `pip` fails building `numpy==1.23.4`, `scikit-image`, `numba`, etc. | You're probably not on Python 3.8. Recreate the environment with `conda create -n sadtalker python=3.8`. |
| `ModuleNotFoundError: No module named 'flask'` (or `requests`) | Flask was installed in a different environment. Run `conda activate sadtalker` and repeat [step 6](#6-install-the-web-applications-dependencies). |
| `ModuleNotFoundError` for `face_alignment`, `gfpgan`, `basicsr`, etc. in `logs/<job_id>.log` | SadTalker's dependencies aren't in the environment that runs Flask. Install `SadTalker/requirements.txt` into that environment. |
| `ImportError` from `basicsr` mentioning `torchvision.transforms.functional_tensor` | A newer torchvision is installed. Use the pinned `torchvision==0.13.1` from [step 4](#4-install-pytorch-cpu-build). |
| Background Remover shows *(Unavailable)* | `rembg` or `onnxruntime` isn't installed: `pip install rembg==2.0.57 onnxruntime==1.18.1`. |

### Model loading

| Symptom | Cause / fix |
|---|---|
| Lip Sync fails with *"SadTalker encountered an error."* | Open `logs/<job_id>.log` for the full SadTalker traceback. Missing checkpoints are the most common cause. Check the files listed in [Model files](#model-files). |
| Log shows a missing `SadTalker_V0.0.2_256.safetensors` or `mapping_*.pth.tar` | Download them into `SadTalker/checkpoints/`. |
| First job hangs or fails while downloading `GFPGANv1.4.pth` | The machine is offline or GitHub is blocked. Download the file manually into `SadTalker/gfpgan/weights/`. |
| `FileNotFoundError` for `inference.py` | SadTalker isn't cloned at `<project root>/SadTalker/`. See [step 2](#2-clone-sadtalker-into-sadtalker). |
| Background Remover's first run fails with a network error | rembg couldn't download the `u2net` model. Connect to the internet for the first run, or pre-download the model into `~/.u2net`. |

### GPU

| Symptom | Cause / fix |
|---|---|
| Lip Sync doesn't use my NVIDIA GPU | Expected. The SadTalker command always includes `--cpu` (see `app/services/sadtalker.py`). GPU use would require a code change. |
| EchoMimic V3 shows **Model installation required** | Set **both** `ECHOMIMIC_WORKER_URL` and `ECHOMIMIC_WORKER_TOKEN` in the shell that runs `python run.py`, then restart. The app doesn't read `.env` files. |
| EchoMimic job fails with `HTTP 401/403` | The worker rejected the token. Check `ECHOMIMIC_WORKER_TOKEN`. |
| EchoMimic job fails with a connection error or timeout | The worker is unreachable. Check the URL and that the worker is running. Increase `ECHOMIMIC_WORKER_CONNECT_TIMEOUT` / `ECHOMIMIC_WORKER_UPLOAD_TIMEOUT` for slow networks. |
| *"EchoMimic generation exceeded the 14400-second timeout."* | Raise `ECHOMIMIC_WORKER_TIMEOUT`. |

### Generation

| Symptom | Cause / fix |
|---|---|
| *"Unsupported image format."* / *"Unsupported audio format."* | Lip Sync accepts `.jpg/.jpeg/.png` and `.wav/.mp3/.m4a` only. Animation Studio and Image Studio accept more formats (see [Features](#features)). |
| *"No MP4 video was produced."* | SadTalker exited without writing a video. Check the job log. Common causes are no face detected in the image or FFmpeg missing from `PATH`. |
| *"Video generation timed out."* | The job ran longer than `GENERATION_TIMEOUT` (8 h). Use shorter audio or increase the value in `config.py`. |
| `413 Request Entity Too Large` | The upload is over `MAX_CONTENT_LENGTH` (100 MB). |
| *"Generation job not found."* after restarting the server | Job state is stored in memory and lost on restart. Output files are still in `outputs/`. |
| Animation Studio: *"Generation is taking longer than expected…"* | The page stops polling after about 12 minutes (360 × 2 s). The job keeps running on the server. Check `/animation/api/jobs/<job_id>`. |
| Image Studio: *"Image dimensions exceed the supported processing limit."* | The image is larger than 10,000 px per side or 40 MP. Downscale it first. |

### Logs
- `logs/application.log`: startup, every request and response, and job errors.
- `logs/<job_id>.log`: complete SadTalker output for one Lip Sync job.
- The terminal running `python run.py` shows the same application log output.

---

## Known limitations

These come from the current code and are documented here rather than changed:

- **In-memory jobs.** Job status for all three tools lives in process memory. Restarting the server loses it. There is no database.
- **Lip Sync is CPU-only.** `--cpu` is hard-coded in the SadTalker command. Lip Sync settings (size, preprocess, expression scale, enhancer) can't be changed from the UI.
- **Single animation worker.** Animation jobs run one at a time (`AnimationJobManager(max_workers=1)`). Image jobs run two at a time.
- **EchoMimic video endpoint result shape.** `EchoMimicV3Engine.generate()` returns a file path, but `GET /animation/api/jobs/<job_id>/video` expects the job result to be a dictionary with a `video_path` key. That's the shape the test engines return. After a successful EchoMimic job, the preview or download request will most likely fail with a server error until the two are aligned. The video file itself is still saved under `outputs/animation/<job_id>/`.
- **Placeholder modules.** `audio_cleanup.py`, `background_removal.py`, `face_enhancement.py` and `image_upscaling.py` in `processors/` are empty files and add no features.
- **No authentication.** The app is meant for local use on `127.0.0.1`.

---

## Development

### Architecture in brief

```
Browser ──► Flask blueprint (app/routes) ──► service / job manager (app/services) ──► model
   ▲                                                   │
   └────────── polls /…/jobs/<id> for progress ◄───────┘ (background thread)
```

- **Routes** validate input, save uploads, submit a background job and return `202` with a `job_id`.
- **Job managers** run work on threads and keep `status`, `progress`, `message`, `result` and `error` in memory.
- **Animation engines** and **processing modules** are plugins. Loaders find them automatically by scanning their package folders for concrete subclasses.
- `create_app()` builds the processing-module registry and pipeline once at startup (`app.extensions["processing_module_registry"]` and `app.extensions["processing_pipeline"]`). The animation engine registry is built lazily on the first `/animation/api/*` request.

### Running the tests

```bash
conda activate sadtalker
python -m unittest discover -s tests
```

Current state: **35 tests, 34 pass, 1 error.** `test_successful_processing` in `tests/test_image_studio_api.py` raises `UnboundLocalError` because the test refers to a `download` variable it never assigns. This is a bug in the test, not in the application.

### Adding an animation engine

1. Create `app/services/animation/engines/my_engine.py`.
2. Subclass `AnimationEngine` and implement `is_available()` and `generate()`:

   ```python
   from app.services.animation.base import AnimationEngine

   class MyEngine(AnimationEngine):
       engine_id = "my_engine"            # unique
       name = "My Engine"
       description = "What this engine does."
       options = [
           {"name": "strength", "label": "Strength", "type": "number",
            "default": 1.0, "min": 0, "max": 2, "step": 0.1},
       ]

       def __init__(self, config):        # the loader passes app.config
           self.config = config

       def is_available(self):
           return True                    # e.g. check model files / env vars

       def generate(self, image_path, audio_path, output_dir,
                    options=None, progress_callback=None):
           # ...produce an MP4 inside output_dir...
           if progress_callback:
               progress_callback(50, "Halfway there.")
           return {"video_path": str(output_dir / "result.mp4")}
   ```

3. Restart the server. The engine then appears in Animation Studio automatically.

Notes:
- The constructor must accept `config`. The loader calls `engine_class(config)`.
- Return a dict with `video_path` inside `OUTPUT_FOLDER`. The video endpoint reads `result["video_path"]` and refuses paths outside `outputs/`.
- Supported option `type` values in the UI: `text`, `number`, `range`, `password`, `select` (with `options`), `textarea`, `checkbox`/`boolean`. Optional keys: `label`, `default`, `min`, `max`, `step`, `placeholder`, `required`, `readonly`, `description`/`help`, `full_width`. The key is taken from `key`, `name` or `id`.

### Adding a processing module

1. Create `app/services/modules/processors/my_module.py`.
2. Subclass `ProcessingModule`:

   ```python
   from pathlib import Path
   from app.services.modules.base import ProcessingModule

   class MyModule(ProcessingModule):
       module_id = "my_module"
       name = "My Module"
       description = "What this module does."
       category = "image"
       options = [
           {"name": "level", "type": "integer", "default": 5},
           {"name": "mode", "type": "select", "default": "a", "choices": ["a", "b"]},
       ]

       def __init__(self, config):
           self.config = config

       def is_available(self):
           return True

       def process(self, input_data, options=None, progress_callback=None):
           source = Path(input_data.get("image_path"))
           output_root = Path(input_data.get("output_dir")) / "my_module"
           output_root.mkdir(parents=True, exist_ok=True)
           output_path = output_root / source.name
           # ...write the processed image to output_path...
           input_data.set("image_path", str(output_path))   # hand off to the next module
           return {"image_path": str(output_path)}
   ```

3. Restart the server. The module then appears in Image Studio.

Notes:
- `input_data` is a `ProcessingContext`. Read with `get()`, and update `image_path` with `set()` so later modules and the job manager use your output.
- Write outputs under `input_data.get("output_dir")`. Image Studio only serves files inside `outputs/image_processing/<job_id>/`.
- Image Studio renders option `type` values `select` (with `choices`) and `integer`. Any other type renders as a text input.

### Adding a route or page

1. Add a view to an existing blueprint in `app/routes/`, or create a new blueprint and register it in `create_app()` in [`app/__init__.py`](app/__init__.py).
2. For a page, create a template that extends the shell:

   ```jinja
   {% extends "base.html" %}
   {% from "partials/_components.html" import page_header, card %}

   {% block title %}My Page · AI Lip Sync Studio{% endblock %}

   {% block content %}
     {{ page_header("My Page", "Short description.", eyebrow="Section") }}
     {% call card(title="Card title", step="01") %}
       ...
     {% endcall %}
   {% endblock %}

   {% block scripts %}<script>/* page script */</script>{% endblock %}
   ```

3. Add the page to the sidebar by adding an entry to `nav_groups` in [`app/templates/partials/_sidebar.html`](app/templates/partials/_sidebar.html), using its endpoint name (e.g. `"my_bp.index"`). The active state is set automatically from `request.endpoint`.

### Frontend conventions
- All styling lives in [`app/static/css/studio.css`](app/static/css/studio.css), built on CSS custom properties (`--accent`, `--surface`, …).
- Reusable Jinja macros live in `partials/_components.html`: `page_header`, `card`, `alert`, `dropzone`, `steps`. Icons come from `partials/_icons.html`.
- `ui.js` handles shell behaviour only. Keep generation and API logic in each page's own script.
- Page scripts find elements by `id`. Keep those IDs when you change templates.

### Contribution checklist
- [ ] New engines and modules declare a unique `engine_id` / `module_id` and accept `config` in `__init__`.
- [ ] Outputs are written inside `OUTPUT_FOLDER`.
- [ ] Tests are added under `tests/` and `python -m unittest discover -s tests` passes.
- [ ] No model weights, uploads, outputs or secrets are committed (see `.gitignore`).

---

## Acknowledgements

- [SadTalker](https://github.com/OpenTalker/SadTalker) by OpenTalker (see `SadTalker/LICENSE`)
- [EchoMimicV3](https://github.com/antgroup/echomimic_v3) by Ant Group (see `models/EchoMimicV3/LICENSE.txt`)
- [GFPGAN](https://github.com/TencentARC/GFPGAN), [facexlib](https://github.com/xinntao/facexlib), [rembg](https://github.com/danielgatis/rembg)

Each third-party model and repository has its own license. Check them before any non-personal or commercial use.
