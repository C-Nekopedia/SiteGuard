"""
SiteGuard AI Server - FastAPI 主应用
工地安全风险监测系统后端
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from .core.config import settings, validate_paths
from .utils.logger import setup_logger

# 添加当前app目录到Python路径，解决模块导入问题
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 添加ai-engine包到Python路径
project_root = Path(__file__).parent.parent.parent.parent
ai_engine_path = project_root / "packages" / "ai-engine"
sys.path.insert(0, str(ai_engine_path))

from .routes import detection, models, camera

# 导入AI引擎模块
from ai_engine.model.model_manager import ModelManager
from .services.detection_service import DetectionService

# 设置日志
logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时初始化
    logger.info("SiteGuard AI Server 正在启动...")

    # 验证关键路径
    success, problems = validate_paths()
    if not success:
        logger.warning("⚠️ 路径配置验证发现问题:")
        for problem in problems:
            logger.warning(f"  - {problem}")
        logger.warning("应用将继续启动，但某些功能可能无法正常工作")
    else:
        logger.info("✅ 所有路径配置验证通过")

    # 初始化模型管理器
    app.state.model_manager = ModelManager(settings.MODELS_DIR)
    app.state.model_manager.initialize()
    # 加载默认模型
    try:
        app.state.model_manager.load_model(settings.DEFAULT_MODEL)
        logger.info(f"✅ 默认模型加载成功: {settings.DEFAULT_MODEL}")
    except Exception as e:
        logger.error(f"❌ 默认模型加载失败: {e}")
        # 如果模型不存在，可能使用第一个可用模型
        model_list = app.state.model_manager.get_model_list()
        if model_list:
            first_model = model_list[0]['name']
            app.state.model_manager.load_model(first_model)
            logger.info(f"✅ 备用模型加载成功: {first_model}")
        else:
            logger.warning("⚠️ 没有找到任何模型文件，检测功能将不可用")

    # 初始化检测服务
    app.state.detection_service = DetectionService(app.state.model_manager)

    logger.info(f"模型目录: {settings.MODELS_DIR}")
    logger.info(f"API 文档: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    # 关闭时清理
    logger.info("SiteGuard AI Server 正在关闭...")
    app.state.model_manager.cleanup()
    # DetectionService不需要特殊清理

# 创建FastAPI应用
app = FastAPI(
    title="SiteGuard AI API",
    description="工地安全风险监测系统后端API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 前端开发地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
settings.STATIC_DIR.joinpath("temp").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# 注册路由
app.include_router(detection.router, prefix="/api/v1/detection", tags=["检测"])
app.include_router(models.router, prefix="/api/v1/models", tags=["模型管理"])
app.include_router(camera.router, prefix="/api/v1/camera", tags=["摄像头"])

@app.get("/")
async def root():
    """根端点"""
    return {
        "message": "SiteGuard Server",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/api/v1/detection",
            "/api/v1/models",
            "/api/v1/camera"
        ]
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    # 根据运行方式动态选择模块名
    # 如果在app目录下直接运行python main.py，使用"__main__"
    # 如果在server目录下运行python -m app.main，使用"app.main"
    # 如果在项目根目录运行python -m apps.server.app.main，使用"apps.server.app.main"
    if __package__ is None:
        module_name = "__main__"
    else:
        # 构建完整模块路径
        module_name = __package__ + ".main"
    uvicorn.run(
        f"{module_name}:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )