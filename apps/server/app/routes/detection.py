"""
检测相关路由
"""
import io
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..core.config import settings
from ..services.detection_service import DetectionService
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

# 依赖函数：获取检测服务
def get_detection_service(request: Request) -> DetectionService:
    """从应用状态获取检测服务"""
    return request.app.state.detection_service

@router.post("/image")
async def detect_image(
    request: Request,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    detection_service: DetectionService = Depends(get_detection_service)
):
    """
    图片检测接口
    """
    try:
        # 验证文件类型
        if file.content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型，仅支持: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
            )

        # 读取文件内容
        contents = await file.read()

        # 验证文件大小
        if len(contents) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB"
            )

        logger.info(f"收到图片检测请求: {file.filename}, 大小: {len(contents)} bytes")

        # 执行检测
        result = await detection_service.detect_image(contents)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "检测失败"))

        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        annotated_filename = f"{file_id}.jpg"
        annotated_path = settings.STATIC_DIR / "temp" / annotated_filename

        # 保存标注图片
        annotated_path.parent.mkdir(parents=True, exist_ok=True)
        with open(annotated_path, "wb") as f:
            f.write(result["annotated_image"])

        # 添加后台任务：清理临时文件
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
        logger.error(f"图片检测接口异常: {e}")
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")

@router.post("/video")
async def detect_video(
    request: Request,
    file: UploadFile = File(...),
    detection_service: DetectionService = Depends(get_detection_service)
):
    """
    视频检测接口（返回SSE流）
    """
    try:
        # 验证文件类型
        if file.content_type not in settings.ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型，仅支持: {', '.join(settings.ALLOWED_VIDEO_TYPES)}"
            )

        # 保存临时文件
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)

        temp_file_path = temp_dir / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)

        logger.info(f"收到视频检测请求: {file.filename}, 大小: {len(contents)} bytes")

        # 定义SSE流生成器
        async def generate_sse():
            try:
                async for frame_result in detection_service.detect_video(temp_file_path):
                    yield f"data: {frame_result}\n\n"
            finally:
                # 清理临时文件
                try:
                    temp_file_path.unlink()
                    logger.info(f"清理临时视频文件: {temp_file_path}")
                except Exception as e:
                    logger.error(f"清理临时文件失败: {e}")

        return StreamingResponse(
            generate_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"视频检测接口异常: {e}")
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")

@router.get("/test")
async def test_detection(
    detection_service: DetectionService = Depends(get_detection_service)
):
    """
    测试检测接口
    """
    return {
        "message": "检测接口正常",
        "timestamp": "2024-01-15T10:00:00Z",
        "endpoints": {
            "POST /image": "图片检测",
            "POST /video": "视频检测（SSE流）"
        }
    }

async def cleanup_temp_file(file_path: Path):
    """
    清理临时文件（后台任务）
    """
    import asyncio
    try:
        await asyncio.sleep(3600)  # 1小时后清理

        # 正常执行清理
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"后台清理临时文件: {file_path}")
        except Exception as e:
            logger.error(f"后台清理文件失败: {e}")

    except asyncio.CancelledError:
        # 当应用关闭时任务被取消，立即清理文件
        logger.debug(f"后台任务被取消，立即清理临时文件: {file_path}")
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"应用关闭时清理临时文件: {file_path}")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
        # 安静地退出，不传播取消异常