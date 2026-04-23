# SiteGuard

[English](README.md) | [中文](README.zh-CN.md)

SiteGuard 是一个建筑工地安全监测系统，使用计算机视觉检测个人防护装备（PPE）合规性。该系统提供安全装备（安全帽、反光衣、手套、安全鞋、护目镜）的实时检测和不合规警报。

## 界面预览

![前端界面预览](https://cdn.jsdelivr.net/gh/C-Nekopedia/SiteGuard/data/preview/Frontend_preview.png)

*检测界面：上传图像后系统自动识别 PPE（安全帽、反光衣、手套等）并标记风险。*

## 功能特性

- **实时PPE检测**：使用YOLOv26模型检测安全帽、反光衣、手套、安全鞋和护目镜
- **风险评估**：内置规则用于识别安全违规（例如：未戴安全帽的人员、缺少反光衣）
- **Web仪表板**：Vue.js前端用于上传图像、查看检测结果，支持摄像头实时流
- **REST API + WebSocket**：FastAPI后端用于图像处理和实时摄像头检测
- **模块化单体仓库**：组织为应用（web、server）和包（ai-engine）

## 项目结构

```
site-guard-monorepo/
├── apps/
│   ├── web/                    # Vue.js前端
│   │   ├── src/
│   │   └── package.json
│   └── server/                 # FastAPI后端
│       └── app/
├── packages/
│   └── ai-engine/              # AI推理引擎
│       ├── ai_engine/
│       │   └── model/          # 模型管理器（加载、切换、预测）
│       └── setup.py
├── data/                       # 模型和示例数据
│   ├── models/                 # 训练好的模型文件
│   └── raw/                    # 原始建筑工地图像
└── package.json                # 单体仓库根目录（pnpm + turbo）
```

## 环境要求

- Node.js 18+ 和 pnpm 8+
- Python 3.10+

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/C-Nekopedia/SiteGuard.git
cd SiteGuard
```

### 2. 安装依赖

```bash
# 安装Node.js依赖（前端）
pnpm install

# 设置Python虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装Python依赖
pip install -r requirements.txt
pip install -e packages/ai-engine
```

### 3. 设置环境变量

复制 `.env.example` 到 `.env` 并根据需要调整：

```env
SITEGUARD_BASE_DIR=
HOST=0.0.0.0
PORT=8000
DEBUG=true
CORS_ORIGINS=http://localhost:3000
DEFAULT_MODEL=yolo26n_ppe.pt
CONFIDENCE_THRESHOLD=0.5
```

### 4. 启动开发服务器

```bash
# 以开发模式同时启动前端和后端
pnpm dev

# 或分别启动：
# 仅后端
cd apps/server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 仅前端
cd apps/web
pnpm dev
```

Web界面将在 http://localhost:3000 可用，API在 http://localhost:8000。

## 使用方法

### 通过Web界面

1. 访问 http://localhost:3000
2. 上传建筑工地图像
3. 查看检测结果和风险评估
4. 在设置面板中配置风险规则

### 通过API

```bash
# 健康检查
curl http://localhost:8000/health

# 检测图像中的PPE
curl -X POST -F "file=@image.jpg" http://localhost:8000/api/detect
```

### AI引擎（独立使用）

```python
from ai_engine.model.model_manager import ModelManager
import cv2

# 加载模型
model_manager = ModelManager("data/models")
model_manager.initialize()
model_manager.load_model("yolo26n_ppe.pt")

# 检测PPE
image = cv2.imread("construction_site.jpg")
results = model_manager.predict(image)
print(results)
```

## 配置

### 风险规则

风险规则定义在 `DetectionService`（`apps/server/app/services/detection_service.py`）中。系统根据一组规则评估检测到的对象，识别安全违规行为（如未戴安全帽、未穿反光衣）。规则是数据驱动的 -- 添加新规则只需在 `RISK_RULES` 列表中追加一个条目。

### 模型

本项目包含一个基于建筑PPE数据集微调的YOLOv26模型。模型文件 `yolo26n_ppe.pt` 位于 `data/models/` 目录，已作为示例包含在仓库中。您可以替换为自己的模型，并在 `.env` 中修改 `DEFAULT_MODEL`。

### 数据集

模型使用Ultralytics的[Construction-PPE数据集](https://docs.ultralytics.com/datasets/detect/construction-ppe/)进行训练。如果在您的研究中使用此数据集，请引用：

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

## 开发

### 单体仓库命令

```bash
# 安装所有依赖
pnpm install

# 运行开发服务器
pnpm dev

# 构建所有包和应用
pnpm build

# 清理构建产物
pnpm clean
```

### 添加新包

1. 在 `packages/` 下创建新目录
2. 添加 `package.json`（用于TypeScript/JavaScript）或 `pyproject.toml`（用于Python）
3. 如果需要，更新根目录 `package.json` 的workspaces配置

## 许可证

MIT许可证。详见 [LICENSE](LICENSE)。