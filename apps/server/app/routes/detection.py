"""
Detection routes
"""
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Request

from ..core.config import settings
from ..services.detection_service import DetectionService
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

# Dependency: get detection service
def get_detection_service(request: Request) -> DetectionService:
    """Get detection service from app state"""
    return request.app.state.detection_service

@router.post("/image")
async def detect_image(
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    detection_service: DetectionService = Depends(get_detection_service)
):
    """
    Image detection endpoint
    """
    try:
        # Validate file type
        if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type, only: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
            )

        # Read file content
        contents = await file.read()

        # Validate file size
        if len(contents) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB limit"
            )

        logger.info(f"Image detection request received: {file.filename}, size: {len(contents)} bytes")

        # Run detection
        result = await detection_service.detect_image(contents)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Detection failed"))

        # Generate unique filename
        file_id = str(uuid.uuid4())
        annotated_filename = f"{file_id}.jpg"
        annotated_path = settings.STATIC_DIR / "temp" / annotated_filename

        # Save annotated image
        annotated_path.parent.mkdir(parents=True, exist_ok=True)
        with open(annotated_path, "wb") as f:
            f.write(result["annotated_image"])

        # Background task: cleanup temp file
        if background_tasks:
            background_tasks.add_task(cleanup_temp_file, annotated_path)

        return {
            "success": True,
            "detections": result["detections"],
            "risks": result["risks"],
            "inference_time": result["inference_time"],
            "image_info": result["image_size"],
            "annotated_image_url": f"/static/temp/{annotated_filename}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image detection endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/test")
async def test_detection(
    detection_service: DetectionService = Depends(get_detection_service)
):
    """
    Test detection endpoint
    """
    return {
        "message": "Detection endpoint OK",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "POST /image": "Image detection"
        }
    }

async def cleanup_temp_file(file_path: Path):
    """
    Clean up temporary file (background task)
    """
    try:
        await asyncio.sleep(settings.TEMP_FILE_CLEANUP_DELAY)

        # Normal cleanup
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Background cleanup of temp file: {file_path}")
        except Exception as e:
            logger.error(f"Background cleanup failed: {e}")

    except asyncio.CancelledError:
        # When app shuts down task is cancelled, clean up immediately
        logger.debug(f"Background task cancelled, immediate cleanup: {file_path}")
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Shutdown cleanup of temp file: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
        # Silently exit, do not propagate cancellation
