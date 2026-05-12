# SiteGuard

[中文](README.zh-CN.md) | [English](README.md)

SiteGuard is a construction site safety monitoring system that uses computer vision to detect personal protective equipment (PPE) compliance. It provides real-time detection of safety gear (helmets, vests, gloves, boots, goggles) and alerts for non-compliance.

## UI Preview

![Frontend UI Preview](https://cdn.jsdelivr.net/gh/C-Nekopedia/SiteGuard/data/preview/Frontend_preview.png)

*Detection interface: upload an image and the system automatically identifies PPE (helmets, vests, gloves, etc.) and flags risks.*

## Features

- **Real-time PPE detection**: Detects helmets, vests, gloves, boots, and goggles using YOLO26n
- **Risk evaluation**: Hardcoded rules identify safety violations — no_helmet (HIGH), missing_helmet (HIGH), no_vest (MEDIUM)
- **Camera streaming**: Real-time WebSocket-based camera detection with annotated frame rendering
- **Model hot-swap**: Switch detection models at runtime without restarting the server (~2–3 s reload)
- **Web dashboard**: Vue 3 + TypeScript frontend for image upload, camera view, and detection results
- **REST API + WebSocket**: FastAPI backend for image processing and real-time camera detection

## Project Structure

```
site-guard-monorepo/
├── apps/
│   ├── web/                         # Vue 3 frontend
│   │   ├── src/
│   │   │   ├── views/               # Page components
│   │   │   ├── components/          # Reusable UI components
│   │   │   ├── stores/              # Pinia state management
│   │   │   └── utils/               # Axios, WebSocket helpers
│   │   ├── vite.config.ts
│   │   └── package.json
│   └── server/                      # FastAPI backend
│       └── app/
│           ├── main.py              # Application entry point
│           ├── core/config.py       # pydantic-settings configuration
│           ├── routes/              # API route modules
│           │   ├── detection.py     # POST /api/v1/detection/image
│           │   ├── camera.py        # WebSocket /api/v1/camera/stream
│           │   └── models.py        # Model list, switch, stats
│           └── services/
│               └── detection_service.py  # Risk rule engine
├── packages/
│   └── ai-engine/                   # AI inference engine
│       ├── ai_engine/
│       │   └── model/
│       │       └── model_manager.py # YOLO model load / switch / predict
│       └── setup.py
├── scripts/                         # Utility scripts
│   ├── start.sh                     # One-click start (Linux / macOS / Git Bash)
│   ├── start.bat                    # One-click start (Windows)
│   └── train.py                     # YOLO training & export script
├── data/
│   ├── models/                      # Trained model files (.pt / .onnx / .engine)
│   └── raw/                         # Raw construction site images
├── logs/                            # Runtime logs (system / detection / alerts)
├── .env.example                     # Environment variable template
├── requirements.txt                 # Python dependencies
├── package.json                     # Monorepo root (pnpm + Turborepo)
├── pnpm-workspace.yaml
└── turbo.json
```

## Prerequisites

- Python 3.10+
- Node.js 18+ and pnpm 8+

## Quick Start

### One-Click Start (Recommended)

**Windows:**
```bash
bash scripts/start.sh
```

**Linux / macOS:**
```bash
bash scripts/start.sh
```

The script handles everything: environment check → virtual environment → dependency install → `.env` creation → start frontend & backend.

**Press `Ctrl+C` to stop all services.**

### Manual Setup

<details>
<summary>Click to expand manual setup steps</summary>

#### 1. Clone the repository

```bash
git clone https://github.com/C-Nekopedia/SiteGuard.git
cd SiteGuard
```

#### 2. Install dependencies

```bash
# Install Node.js dependencies (monorepo)
pnpm install

# Set up Python virtual environment
python -m venv venv
source venv/bin/activate      # Windows (Git Bash): source venv/Scripts/activate
                              # Windows (CMD): venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -e packages/ai-engine
```

#### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` as needed. See [Configuration](#configuration) for details.

#### 4. Start the development servers

```bash
# Start backend (terminal 1)
cd apps/server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend (terminal 2)
cd apps/web
pnpm dev
```

</details>

The web interface is available at **http://localhost:3000** and the API at **http://localhost:8000**.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root info |
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/detection/image` | Upload an image for PPE detection |
| `GET` | `/api/v1/models/list` | List available model files |
| `POST` | `/api/v1/models/switch` | Switch to a different model at runtime |
| `GET` | `/api/v1/models/current` | Get currently loaded model info |
| `GET` | `/api/v1/models/stats` | Get model statistics |
| `WS` | `/api/v1/camera/stream` | Real-time camera detection stream |
| `GET` | `/api/v1/camera/status` | Camera status |
| `POST` | `/api/v1/camera/start` | Start camera capture |
| `POST` | `/api/v1/camera/stop` | Stop camera capture |

**Interactive docs**: visit **http://localhost:8000/docs** for the auto-generated Swagger UI.

### Example: Image Detection

```bash
# Detect PPE in an image
curl -X POST -F "image=@construction_site.jpg" http://localhost:8000/api/v1/detection/image

# Image must include at least one person for risk evaluation
```

### AI Engine (Standalone Usage)

```python
from ai_engine.model.model_manager import ModelManager
import cv2

# Initialize model manager
manager = ModelManager("data/models")
manager.initialize()
manager.load_model("yolo26n_ppe.pt")

# Run inference
image = cv2.imread("construction_site.jpg")
results = manager.predict(image)
print(results)  # JSON-serializable dict with detections and alerts
```

## Configuration

All configuration is managed through environment variables (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server listen address |
| `PORT` | `8000` | Server listen port |
| `DEBUG` | `true` | Debug mode (enables hot-reload) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |
| `MODELS_DIR` | `data/models` | Model files directory |
| `DATA_DIR` | `data/raw` | Raw data directory |
| `STATIC_DIR` | `apps/server/static` | Static file serving directory |
| `EXPORTS_DIR` | `apps/server/exports` | Annotated image export directory |
| `DEFAULT_MODEL` | `yolo26n_ppe.pt` | Default model to load on startup |
| `CONFIDENCE_THRESHOLD` | `0.5` | Detection confidence threshold |
| `IOU_THRESHOLD` | `0.5` | NMS IoU threshold |
| `MAX_DETECTIONS` | `300` | Maximum detections per image |

## Risk Rules

Three rules are defined in `DetectionService` ([detection_service.py](apps/server/app/services/detection_service.py)):

| Rule | Level | Logic |
|------|-------|-------|
| `no_helmet` | HIGH | A `no_helmet` / `no-helmet` class is detected |
| `missing_helmet` | HIGH | A `Person` is detected but no `helmet` is present |
| `no_vest` | MEDIUM | A `none` class is detected (person without vest) |

Rules are data-driven — add or modify entries in the `RISK_RULES` list to customize the rule engine. Class names are matched case-insensitively.

## Model

The project uses **YOLO26n** (nano variant, 2.4M parameters, 5.1 MB), an end-to-end detection architecture that eliminates the need for NMS post-processing via one-to-one label assignment.

| Metric | Value |
|--------|-------|
| Architecture | YOLO26n (end-to-end, NMS-free) |
| Parameters | 2.4 M |
| Model size | 5.1 MB |
| Training epochs | 50 |
| Image size | 640×640 |
| Batch size | 8 |
| mAP50 | 0.523 |
| mAP50-95 | 0.270 |

The model file `yolo26n_ppe.pt` is located in `data/models/`. You can replace it with your own trained model and update `DEFAULT_MODEL` in `.env`. The system supports PyTorch (`.pt`), ONNX (`.onnx`), and TensorRT (`.engine`) formats.

### Dataset

Trained on the [Construction-PPE dataset](https://docs.ultralytics.com/datasets/detect/construction-ppe/) (11 classes: helmet, gloves, vest, boots, goggles, none, Person, no_helmet, no_goggle, no_gloves, no_boots).

If you use this dataset in your research, please cite:

```bibtex
@dataset{Dalvi_Construction_PPE_Dataset_2025,
    author = {Mrunmayee Dalvi and Niyati Singh and Sahil Bhingarde and Ketaki Chalke},
    title = {Construction-PPE: Personal Protective Equipment Detection Dataset},
    month = {January},
    year = {2025},
    version = {1.0.0},
    license = {AGPL-3.0},
    url = {https://docs.ultralytics.com/datasets/detect/construction-ppe/},
    publisher = {Ultralytics}
}
```

## Development

```bash
# Install all dependencies
pnpm install

# Run both frontend and backend (via Turborepo)
pnpm dev

# Build all packages and apps
pnpm build

# Clean build artifacts
pnpm clean
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, TypeScript, Element Plus, Pinia, Vite |
| Backend | FastAPI, uvicorn, pydantic-settings, WebSocket |
| AI Engine | Ultralytics YOLO26, PyTorch, OpenCV, NumPy |
| Monorepo | pnpm workspaces, Turborepo |

## License

MIT License. See [LICENSE](LICENSE) for details.
