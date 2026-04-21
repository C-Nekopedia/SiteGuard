# SiteGuard

[中文](README.zh-CN.md) | [English](README.md)

SiteGuard is a construction site safety monitoring system that uses computer vision to detect personal protective equipment (PPE) compliance. It provides real-time detection of safety gear (helmets, vests, gloves, boots, goggles) and alerts for non-compliance.

## Features

- **Real-time PPE detection**: Detects helmets, safety vests, gloves, boots, and goggles using YOLOv8/YOLOv26 models
- **Risk rule engine**: Configurable rules for identifying safety violations (e.g., person without helmet, missing vest)
- **Web dashboard**: Vue.js frontend for uploading images, viewing detections, and managing rules
- **REST API**: FastAPI backend for image processing and detection
- **Modular monorepo**: Separated into apps (web, server) and packages (ai-engine, schema, utils, logger)

## Project Structure

```
site-guard-monorepo/
├── apps/
│   ├── web/                    # Vue.js frontend
│   │   ├── src/
│   │   └── package.json
│   └── server/                 # FastAPI backend
│       ├── app/
│       └── requirements.txt
├── packages/
│   ├── ai-engine/              # AI inference engine
│   │   ├── ai_engine/
│   │   │   ├── inference/      # YOLO26 inference
│   │   │   └── rules/          # Risk rule engine
│   │   └── ai_engine.egg-info/
│   ├── schema/                 # TypeScript schemas
│   ├── logger/                 # Logging utilities
│   └── utils/                  # Shared utilities
├── data/                       # Dataset and sample images
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
# Install Node.js dependencies (frontend and packages)
pnpm install

# Set up Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r apps/server/requirements.txt
pip install -e packages/ai-engine
```

### 3. Set up environment variables

Create `.env` file in the root directory:

```env
# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO

# AI Engine
MODEL_PATH=data/models/yolo26_construction_ppe.pt
RULES_PATH=packages/ai-engine/ai_engine/rules/ppe_rules.yaml
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
from ai_engine.inference.yolo26_inference import YOLO26Inference
from ai_engine.model.model_manager import ModelManager
import cv2

# Load model
model_manager = ModelManager("path/to/model.pt")
inference = YOLO26Inference(model_manager)

# Detect PPE
image = cv2.imread("construction_site.jpg")
results = inference.predict_image(image)
print(results["detections"])
```

## Configuration

### Risk Rules

Risk rules are defined in YAML files (`packages/ai-engine/ai_engine/rules/ppe_rules.yaml`). Example:

```yaml
rules:
  - name: missing_helmet
    condition: "person_detected and (class_id == 7)"
    level: "high"
    message: "未佩戴安全帽"
    description: "检测到人员但未佩戴安全帽"
```

### Model

The default model is YOLOv8/YOLOv26 fine-tuned on a construction PPE dataset. Place your model file at `data/models/yolo26_construction_ppe.pt` or update the `MODEL_PATH` environment variable.

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