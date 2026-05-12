"""
SiteGuard AI Server - FastAPI
Construction site safety monitoring system backend
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

# Add current app directory to Python path for module imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Add ai-engine package to Python path
project_root = Path(__file__).parent.parent.parent.parent
ai_engine_path = project_root / "packages" / "ai-engine"
sys.path.insert(0, str(ai_engine_path))

from .routes import detection, models, camera

# Import AI engine module
from ai_engine.model.model_manager import ModelManager
from .services.detection_service import DetectionService

# Set up logging
logger = setup_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management
    """
    # Initialize on startup
    logger.info("SiteGuard AI Server is starting...")

    # Validate critical paths
    success, problems = validate_paths()
    if not success:
        logger.warning("Path configuration validation issues found:")
        for problem in problems:
            logger.warning(f"  - {problem}")
        logger.warning("Application will continue, but some features may not work")
    else:
        logger.info("All path configuration validated successfully")

    # Initialize model manager
    app.state.model_manager = ModelManager(settings.MODELS_DIR)
    app.state.model_manager.initialize()
    # Load default model
    try:
        app.state.model_manager.load_model(settings.DEFAULT_MODEL)
        logger.info(f"Default model loaded successfully: {settings.DEFAULT_MODEL}")
    except Exception as e:
        logger.error(f"Default model failed to load: {e}")
        # If model doesn't exist, try first available model
        model_list = app.state.model_manager.get_model_list()
        if model_list:
            first_model = model_list[0]['name']
            app.state.model_manager.load_model(first_model)
            logger.info(f"Fallback model loaded successfully: {first_model}")
        else:
            logger.warning("No model files found, detection will be unavailable")

    # Initialize detection service
    app.state.detection_service = DetectionService(app.state.model_manager)

    logger.info(f"Model directory: {settings.MODELS_DIR}")
    logger.info(f"API docs: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    # Clean up on shutdown
    logger.info("SiteGuard AI Server is shutting down...")
    app.state.model_manager.cleanup()
    # DetectionService doesn't need special cleanup

# Create FastAPI application
app = FastAPI(
    title="SiteGuard AI API",
    description="Construction Site Safety Monitoring System Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)
settings.STATIC_DIR.joinpath("temp").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Register routes
app.include_router(detection.router, prefix="/api/v1/detection", tags=["Detection"])
app.include_router(models.router, prefix="/api/v1/models", tags=["Models"])
app.include_router(camera.router, prefix="/api/v1/camera", tags=["Camera"])

@app.get("/")
async def root():
    """Root endpoint"""
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
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    # Dynamically select module name based on run mode
    # Running python main.py directly: use "__main__"
    # Running python -m app.main from server dir: use "app.main"
    # Running python -m apps.server.app.main from root: use "apps.server.app.main"
    if __package__ is None:
        module_name = "__main__"
    else:
        # Build full module path
        module_name = __package__ + ".main"
    uvicorn.run(
        f"{module_name}:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )