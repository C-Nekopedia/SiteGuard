# SiteGuard

[English](README.md) | [中文](README.zh-CN.md)

SiteGuard 是一个建筑工地安全监测系统，使用计算机视觉检测个人防护装备（PPE）合规性。提供安全装备（安全帽、反光衣、手套、安全鞋、护目镜）的实时检测与不合规告警。

## 界面预览

![前端界面预览](https://cdn.jsdelivr.net/gh/C-Nekopedia/SiteGuard/data/preview/Frontend_preview.png)

*检测界面：上传图像后系统自动识别 PPE（安全帽、反光衣、手套等）并标记风险。*

## 功能特性

- **实时 PPE 检测**：基于 YOLO26n 检测安全帽、反光衣、手套、安全鞋和护目镜
- **风险评估**：内置规则识别安全违规 — no_helmet（高）、missing_helmet（高）、no_vest（中）
- **摄像头实时流**：基于 WebSocket 的实时摄像头检测与标注帧渲染
- **模型热切换**：运行时切换检测模型，无需重启服务（约 2–3 秒加载）
- **Web 仪表板**：Vue 3 + TypeScript 前端，支持图片上传、摄像头取景和检测结果展示
- **REST API + WebSocket**：FastAPI 后端，提供图像处理和实时摄像头检测

## 项目结构

```
site-guard-monorepo/
├── apps/
│   ├── web/                         # Vue 3 前端
│   │   ├── src/
│   │   │   ├── views/               # 页面组件
│   │   │   ├── components/          # 可复用 UI 组件
│   │   │   ├── stores/              # Pinia 状态管理
│   │   │   └── utils/               # Axios、WebSocket 工具
│   │   ├── vite.config.ts
│   │   └── package.json
│   └── server/                      # FastAPI 后端
│       └── app/
│           ├── main.py              # 应用入口
│           ├── core/config.py       # pydantic-settings 配置
│           ├── routes/              # API 路由模块
│           │   ├── detection.py     # POST /api/v1/detection/image
│           │   ├── camera.py        # WebSocket /api/v1/camera/stream
│           │   └── models.py        # 模型列表、切换、统计
│           └── services/
│               └── detection_service.py  # 风险规则引擎
├── packages/
│   └── ai-engine/                   # AI 推理引擎
│       ├── ai_engine/
│       │   └── model/
│       │       └── model_manager.py # YOLO 模型加载 / 切换 / 推理
│       └── setup.py
├── scripts/                         # 辅助脚本
│   ├── start.sh                     # 一键启动（Linux / macOS / Git Bash）
│   ├── start.bat                    # 一键启动（Windows CMD）
│   └── train.py                     # YOLO 训练与导出脚本
├── data/
│   ├── models/                      # 训练好的模型文件（.pt / .onnx / .engine）
│   └── raw/                         # 原始工地图像
├── logs/                            # 运行时日志（system / detection / alerts）
├── .env.example                     # 环境变量模板
├── requirements.txt                 # Python 依赖
├── package.json                     # Monorepo 根（pnpm + Turborepo）
├── pnpm-workspace.yaml
└── turbo.json
```

## 环境要求

- Python 3.10+
- Node.js 18+ 和 pnpm 8+

## 快速开始

### 一键启动（推荐）

**Windows（Git Bash）：**
```bash
bash scripts/start.sh
```

**Linux / macOS：**
```bash
bash scripts/start.sh
```

脚本会自动完成：环境检查 → 虚拟环境 → 依赖安装 → `.env` 创建 → 启动前后端。

**按 `Ctrl+C` 停止所有服务。**

### 手动安装

<details>
<summary>点击展开手动安装步骤</summary>

#### 1. 克隆仓库

```bash
git clone https://github.com/C-Nekopedia/SiteGuard.git
cd SiteGuard
```

#### 2. 安装依赖

```bash
# 安装 Node.js 依赖（monorepo）
pnpm install

# 创建并激活 Python 虚拟环境
python -m venv venv
source venv/bin/activate      # Windows (Git Bash): source venv/Scripts/activate
                              # Windows (CMD): venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt
pip install -e packages/ai-engine
```

#### 3. 配置环境变量

```bash
cp .env.example .env
```

按需编辑 `.env`，详见[配置说明](#配置)。

#### 4. 启动开发服务器

```bash
# 启动后端（终端 1）
cd apps/server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端（终端 2）
cd apps/web
pnpm dev
```

</details>

前端界面访问 **http://localhost:3000**，API 访问 **http://localhost:8000**。

## API 参考

| 方法 | 端点 | 说明 |
|--------|----------|-------------|
| `GET` | `/` | 根信息 |
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/v1/detection/image` | 上传图片进行 PPE 检测 |
| `GET` | `/api/v1/models/list` | 列出可用模型文件 |
| `POST` | `/api/v1/models/switch` | 运行时切换模型 |
| `GET` | `/api/v1/models/current` | 获取当前加载的模型信息 |
| `GET` | `/api/v1/models/stats` | 获取模型统计信息 |
| `WS` | `/api/v1/camera/stream` | 实时摄像头检测流 |
| `GET` | `/api/v1/camera/status` | 摄像头状态 |
| `POST` | `/api/v1/camera/start` | 启动摄像头捕获 |
| `POST` | `/api/v1/camera/stop` | 停止摄像头捕获 |

**交互式文档**：访问 **http://localhost:8000/docs** 查看自动生成的 Swagger UI。

### 示例：图像检测

```bash
# 检测图像中的 PPE
curl -X POST -F "image=@construction_site.jpg" http://localhost:8000/api/v1/detection/image

# 图像需包含至少一位人员才能触发风险规则评估
```

### AI 引擎（独立使用）

```python
from ai_engine.model.model_manager import ModelManager
import cv2

# 初始化模型管理器
manager = ModelManager("data/models")
manager.initialize()
manager.load_model("yolo26n_ppe.pt")

# 运行推理
image = cv2.imread("construction_site.jpg")
results = manager.predict(image)
print(results)  # JSON 可序列化的字典，含检测结果和告警
```

## 配置

所有配置通过环境变量（`.env`）管理：

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | 服务器监听地址 |
| `PORT` | `8000` | 服务器监听端口 |
| `DEBUG` | `true` | 调试模式（启用热重载） |
| `CORS_ORIGINS` | `http://localhost:3000` | 允许的 CORS 来源 |
| `MODELS_DIR` | `data/models` | 模型文件目录 |
| `DATA_DIR` | `data/raw` | 原始数据目录 |
| `STATIC_DIR` | `apps/server/static` | 静态文件目录 |
| `EXPORTS_DIR` | `apps/server/exports` | 标注图片导出目录 |
| `DEFAULT_MODEL` | `yolo26n_ppe.pt` | 启动时默认加载的模型 |
| `CONFIDENCE_THRESHOLD` | `0.5` | 检测置信度阈值 |
| `IOU_THRESHOLD` | `0.5` | NMS IoU 阈值 |
| `MAX_DETECTIONS` | `300` | 单张图片最大检测数 |

## 风险规则

三条约则定义在 `DetectionService`（[detection_service.py](apps/server/app/services/detection_service.py)）中：

| 规则 | 等级 | 逻辑 |
|------|-------|-------|
| `no_helmet` | HIGH | 检测到 `no_helmet` / `no-helmet` 类别 |
| `missing_helmet` | HIGH | 检测到 `Person` 但不存在 `helmet` |
| `no_vest` | MEDIUM | 检测到 `none` 类别（人员未穿反光衣） |

规则是数据驱动的——在 `RISK_RULES` 列表中添加或修改条目即可自定义规则引擎。类别名称匹配不区分大小写。

## 模型

本项目使用 **YOLO26n**（nano 版本，2.4M 参数，5.1 MB），是一种端到端检测架构，通过一对一标签分配消除了 NMS 后处理步骤。

| 指标 | 值 |
|--------|-------|
| 架构 | YOLO26n（端到端，无 NMS） |
| 参数量 | 2.4 M |
| 模型大小 | 5.1 MB |
| 训练轮次 | 50 |
| 图像尺寸 | 640×640 |
| 批次大小 | 8 |
| mAP50 | 0.523 |
| mAP50-95 | 0.270 |

模型文件 `yolo26n_ppe.pt` 位于 `data/models/` 目录。可替换为自己的模型并修改 `.env` 中的 `DEFAULT_MODEL`。系统支持 PyTorch（`.pt`）、ONNX（`.onnx`）和 TensorRT（`.engine`）格式。

### 数据集

基于 [Construction-PPE 数据集](https://docs.ultralytics.com/datasets/detect/construction-ppe/) 训练（11 个类别：helmet、gloves、vest、boots、goggles、none、Person、no_helmet、no_goggle、no_gloves、no_boots）。

如果在您的研究中使用此数据集，请引用：

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

```bash
# 安装所有依赖
pnpm install

# 同时运行前端和后端（通过 Turborepo）
pnpm dev

# 构建所有包和应用
pnpm build

# 清理构建产物
pnpm clean
```

### 技术栈

| 层级 | 技术 |
|-------|-----------|
| 前端 | Vue 3, TypeScript, Element Plus, Pinia, Vite |
| 后端 | FastAPI, uvicorn, pydantic-settings, WebSocket |
| AI 引擎 | Ultralytics YOLO26, PyTorch, OpenCV, NumPy |
| 项目管理 | pnpm workspaces, Turborepo |

## 许可证

MIT 许可证。详见 [LICENSE](LICENSE)。
