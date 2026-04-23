"""
模型管理路由
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request

from ..core.config import settings
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

@router.get("/list")
async def list_models(request: Request):
    """
    获取可用模型列表
    """
    try:
        model_manager = request.app.state.model_manager
        models = []
        for model_name, model_info in model_manager.models.items():
            models.append({
                "name": model_name,
                "display_name": model_name.replace("_", " ").title(),
                "type": model_info.get("type", "pytorch"),
                "size": model_info.get("size", 0),
                "path": model_info.get("path", "")
            })

        current_model = settings.DEFAULT_MODEL
        if not any(m["name"] == current_model for m in models) and models:
            current_model = models[0]["name"]

        return {
            "success": True,
            "models": models,
            "current_model": current_model,
            "models_dir": str(settings.MODELS_DIR.relative_to(settings.BASE_DIR))
        }
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@router.post("/switch")
async def switch_model(request: Request, model_name: str, use_end2end: bool = None):
    """
    切换当前模型
    """
    try:
        # 验证模型文件是否存在
        model_path = settings.MODELS_DIR / model_name
        if not model_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"模型文件不存在: {model_name}"
            )

        # 获取模型管理器并切换模型
        model_manager = request.app.state.model_manager
        if not model_manager:
            raise HTTPException(
                status_code=500,
                detail="模型管理器未初始化"
            )

        # 调用ModelManager切换模型
        logger.info(f"请求切换模型: {model_name}, 端到端推理: {use_end2end}")
        success = model_manager.switch_model(model_name, use_end2end=use_end2end)

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"模型切换失败: {model_name}"
            )

        return {
            "success": True,
            "message": f"已切换模型到 {model_name}",
            "model_name": model_name,
            "use_end2end": model_manager.use_end2end if hasattr(model_manager, 'use_end2end') else True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换模型失败: {str(e)}")

@router.get("/current")
async def get_current_model():
    """
    获取当前模型信息
    """
    try:
        # 模拟当前模型信息
        model_name = settings.DEFAULT_MODEL
        model_path = settings.MODELS_DIR / model_name

        if model_path.exists():
            model_info = {
                "name": model_name,
                "display_name": model_path.stem.replace("_", " ").title(),
                "type": "pytorch" if model_name.endswith(".pt") else "onnx",
                "size": model_path.stat().st_size,
                "loaded_at": datetime.now(timezone.utc).isoformat()
            }
        else:
            # 如果默认模型不存在，返回第一个找到的模型
            models = list(settings.MODELS_DIR.glob("*.pt"))
            if not models:
                models = list(settings.MODELS_DIR.glob("*.onnx"))

            if models:
                model_path = models[0]
                model_info = {
                    "name": model_path.name,
                    "display_name": model_path.stem.replace("_", " ").title(),
                    "type": "pytorch" if model_path.suffix == ".pt" else "onnx",
                    "size": model_path.stat().st_size,
                    "loaded_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                model_info = None

        return {
            "success": True,
            "model": model_info,
            "message": "获取当前模型成功" if model_info else "没有加载任何模型"
        }

    except Exception as e:
        logger.error(f"获取当前模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取当前模型失败: {str(e)}")

@router.get("/stats")
async def get_model_stats():
    """
    获取模型统计信息
    """
    try:
        models_dir = settings.MODELS_DIR
        if not models_dir.exists():
            return {
                "success": True,
                "stats": {
                    "total_models": 0,
                    "pytorch_models": 0,
                    "onnx_models": 0,
                    "total_size_mb": 0
                }
            }

        pytorch_models = list(models_dir.glob("*.pt"))
        onnx_models = list(models_dir.glob("*.onnx"))
        total_size = sum(f.stat().st_size for f in pytorch_models + onnx_models)

        return {
            "success": True,
            "stats": {
                "total_models": len(pytorch_models) + len(onnx_models),
                "pytorch_models": len(pytorch_models),
                "onnx_models": len(onnx_models),
                "total_size_mb": round(total_size / 1024 / 1024, 2)
            }
        }

    except Exception as e:
        logger.error(f"获取模型统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型统计失败: {str(e)}")