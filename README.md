# SiteGuard

[中文](README.zh-CN.md) | [English](README.md)

SiteGuard is a construction site safety monitoring system that uses computer vision to detect personal protective equipment (PPE) compliance. It provides real-time detection of safety gear (helmets, vests, gloves, boots, goggles) and alerts for non-compliance.

## UI Preview

![Frontend UI Preview](https://cdn.jsdelivr.net/gh/C-Nekopedia/SiteGuard/data/preview/Frontend_preview.png)

*Detection interface: upload an image and the system automatically identifies PPE (helmets, vests, gloves, etc.) and marks risks.*

## Features

- **Real-time PPE detection**: Detects helmets, safety vests, gloves, boots, and goggles using YOLOv26 models
- **Risk evaluation**: Built-in rules for identifying safety violations (e.g., person without helmet, missing vest)
- **Web dashboard**: Vue.js frontend for uploading images and viewing detections with camera stream support
- **REST API + WebSocket**: FastAPI backend for image processing and real-time camera detection
- **Modular monorepo**: Organized into apps (web, server) and package (ai-engine)

## Project Structure

```
site-guard-monorepo/
├── apps/
│   ├── web/                    # Vue.js frontend
│   │   ├── src/
│   │   └── package.json
│   └── server/                 # FastAPI backend
│       └── app/
├── packages/
│   └── ai-engine/              # AI inference engine
│       ├── ai_engine/
│       │   └── model/          # Model manager (load, switch, predict)
│       └── setup.py
├── data/                       # Model and sample data
│   ├── models/                 # Trained model files
│   └── raw/                    # Raw construction site images
└── package.json                # Monorepo root (pnpm + turbo)
```

## Prerequisites

- Node.js 18+ and pnpm 8+
- Python 3.10+

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/C-Nekopedia/SiteGuard.git
cd SiteGuard
```

### 2. Install dependencies

```bash
# Install Node.js dependencies (frontend)
pnpm install

# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -e packages/ai-engine
```

### 3. Set up environment variables

Copy `.env.example` to `.env` in the project root and adjust as needed:

```env
SITEGUARD_BASE_DIR=
HOST=0.0.0.0
PORT=8000
DEBUG=true
CORS_ORIGINS=http://localhost:3000
DEFAULT_MODEL=yolo26n_ppe.pt
CONFIDENCE_THRESHOLD=0.5
```

### 4. Start the development servers

```bash
# Start both frontend and backend in development mode
pnpm dev

# Or start them separately:
# Backend only
cd apps/server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend only
cd apps/web
pnpm dev
```

The web interface will be available at http://localhost:3000 and the API at http://localhost:8000.

## Usage

### Via Web Interface

1. Navigate to http://localhost:3000
2. Upload a construction site image
3. View detection results and risk assessments
4. Configure risk rules in the settings panel

### Via API

```bash
# Health check
curl http://localhost:8000/health

# Detect PPE in an image
curl -X POST -F "file=@image.jpg" http://localhost:8000/api/detect
```

### AI Engine (Standalone)

```python
from ai_engine.model.model_manager import ModelManager
import cv2

# Load model
model_manager = ModelManager("data/models")
model_manager.initialize()
model_manager.load_model("yolo26n_ppe.pt")

# Detect PPE
image = cv2.imread("construction_site.jpg")
results = model_manager.predict(image)
print(results)
```

## Configuration

### Risk Rules

Risk rules are defined in `DetectionService` (`apps/server/app/services/detection_service.py`). The system evaluates detected objects against a set of rules to identify safety violations such as missing helmets or vests. Rules are data-driven -- adding a new rule is done by appending an entry to the `RISK_RULES` list.

### Model

The project includes a YOLOv26 model fine-tuned on a construction PPE dataset. The model file `yolo26n_ppe.pt` is located in `data/models/` and is included in the repository as an example. You can replace it with your own trained model and update `DEFAULT_MODEL` in `.env`.

### Dataset

The model is trained on the [Construction-PPE dataset](https://docs.ultralytics.com/datasets/detect/construction-ppe/) from Ultralytics. If you use this dataset in your research, please cite:

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

### Monorepo Commands

```bash
# Install all dependencies
pnpm install

# Run development servers
pnpm dev

# Build all packages and apps
pnpm build

# Clean build artifacts
pnpm clean
```

### Adding a New Package

1. Create a new directory under `packages/`
2. Add `package.json` (for TypeScript/JavaScript) or `pyproject.toml` (for Python)
3. Update root `package.json` workspaces if needed

## License

MIT License. See [LICENSE](LICENSE) for details.