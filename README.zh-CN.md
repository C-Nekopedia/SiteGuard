# SiteGuard

[English](README.md) | [中文](README.zh-CN.md)

SiteGuard 是一个建筑工地安全监测系统，使用计算机视觉检测个人防护装备（PPE）合规性。该系统提供安全装备（安全帽、反光衣、手套、安全鞋、护目镜）的实时检测和不合规警报。

## 功能特性

- **实时PPE检测**：使用YOLOv8/YOLOv26模型检测安全帽、反光衣、手套、安全鞋和护目镜
- **风险规则引擎**：可配置的规则用于识别安全违规（例如：未戴安全帽的人员、缺少反光衣）
- **Web仪表板**：Vue.js前端用于上传图像、查看检测结果和管理规则
- **REST API**：FastAPI后端用于图像处理和检测
- **模块化单体仓库**：分离为应用（web、server）和包（ai-engine、schema、utils、logger）
- **Docker支持**：使用Docker Compose进行容器化部署

## 项目结构

```
site-guard-monorepo/
├── apps/
│   ├── web/                    # Vue.js前端
│   │   ├── src/
│   │   └── package.json
│   └── server/                 # FastAPI后端
│       ├── app/
│       └── requirements.txt
├── packages/
│   ├── ai-engine/              # AI推理引擎
│   │   ├── ai_engine/
│   │   │   ├── inference/      # YOLO26推理
│   │   │   └── rules/          # 风险规则引擎
│   │   └── ai_engine.egg-info/
│   ├── schema/                 # TypeScript模式定义
│   ├── logger/                 # 日志工具
│   └── utils/                  # 共享工具
├── data/                       # 数据集和示例图像
│   └── raw/                    # 原始建筑工地图像
├── docker/                     # Docker配置
├── docker-compose.yml          # Docker Compose设置
└── package.json                # 单体仓库根目录（pnpm + turbo）
```

## 环境要求

- Node.js 18+ 和 pnpm 8+
- Python 3.10+
- Docker 和 Docker Compose（可选）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/C-Nekopedia/SiteGuard.git
cd SiteGuard
```

### 2. 安装依赖

```bash
# 安装Node.js依赖（前端和包）
pnpm install

# 设置Python虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装Python依赖
pip install -r apps/server/requirements.txt
pip install -e packages/ai-engine
```

### 3. 设置环境变量

在根目录创建 `.env` 文件：

```env
# 服务器
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO

# AI引擎
MODEL_PATH=data/models/yolo26_construction_ppe.pt
RULES_PATH=packages/ai-engine/ai_engine/rules/ppe_rules.yaml
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

Web界面将在 http://localhost:5173 可用，API在 http://localhost:8000。

## Docker部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

通过 http://localhost:80 访问Web界面。

## 使用方法

### 通过Web界面

1. 访问 http://localhost:5173
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
from ai_engine.inference.yolo26_inference import YOLO26Inference
from ai_engine.model.model_manager import ModelManager
import cv2

# 加载模型
model_manager = ModelManager("path/to/model.pt")
inference = YOLO26Inference(model_manager)

# 检测PPE
image = cv2.imread("construction_site.jpg")
results = inference.predict_image(image)
print(results["detections"])
```

## 配置

### 风险规则

风险规则定义在YAML文件中（`packages/ai-engine/ai_engine/rules/ppe_rules.yaml`）。示例：

```yaml
rules:
  - name: missing_helmet
    condition: "person_detected and (class_id == 7)"
    level: "high"
    message: "未佩戴安全帽"
    description: "检测到人员但未佩戴安全帽"
```

### 模型

默认模型是基于建筑PPE数据集微调的YOLOv8/YOLOv26模型。将模型文件放在 `data/models/yolo26_construction_ppe.pt` 或更新 `MODEL_PATH` 环境变量。

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