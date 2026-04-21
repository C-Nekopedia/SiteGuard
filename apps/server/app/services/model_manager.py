"""
模型管理器 - 负责YOLO26模型的加载、切换和热更新
"""
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from core.config import settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ModelWatcher(FileSystemEventHandler):
    """模型文件变化监视器"""

    def __init__(self, manager: "ModelManager"):
        self.manager = manager

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(('.pt', '.onnx')):
            logger.info(f"检测到新模型文件: {Path(event.src_path).name}")
            self.manager.scan_models()

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(('.pt', '.onnx')):
            logger.info(f"模型文件被删除: {Path(event.src_path).name}")
            self.manager.scan_models()

class ModelManager:
    """模型管理器"""

    def __init__(self):
        self.models: Dict[str, Dict[str, Any]] = {}
        self.current_model: Optional[str] = None
        self.model_instance: Optional[Any] = None
        self.model_lock = threading.Lock()
        self.observer: Optional[Observer] = None
        self.watcher: Optional[ModelWatcher] = None

    async def initialize(self):
        """初始化模型管理器"""
        logger.info("🔄 初始化模型管理器...")

        # 扫描模型目录
        self.scan_models()

        # 加载默认模型
        if self.models:
            default_model = settings.DEFAULT_MODEL
            if default_model in self.models:
                await self.load_model(default_model)
            else:
                first_model = list(self.models.keys())[0]
                await self.load_model(first_model)

        # 启动文件监视器
        await self.start_watcher()

    def scan_models(self):
        """扫描模型目录"""
        with self.model_lock:
            self.models.clear()
            model_dir = settings.MODELS_DIR

            if not model_dir.exists():
                logger.warning(f"模型目录不存在: {model_dir}")
                return

            for model_file in model_dir.glob("*.pt"):
                model_info = {
                    "path": str(model_file),
                    "name": model_file.stem,
                    "size": model_file.stat().st_size,
                    "modified": model_file.stat().st_mtime,
                    "type": "pytorch"
                }
                self.models[model_file.name] = model_info
                logger.info(f"发现模型: {model_file.name} ({model_info['size'] / 1024 / 1024:.1f} MB)")

            for model_file in model_dir.glob("*.onnx"):
                model_info = {
                    "path": str(model_file),
                    "name": model_file.stem,
                    "size": model_file.stat().st_size,
                    "modified": model_file.stat().st_mtime,
                    "type": "onnx"
                }
                self.models[model_file.name] = model_info
                logger.info(f"发现ONNX模型: {model_file.name}")

    async def load_model(self, model_name: str):
        """加载指定模型"""
        if model_name not in self.models:
            logger.error(f"模型不存在: {model_name}")
            raise ValueError(f"模型不存在: {model_name}")

        with self.model_lock:
            try:
                logger.info(f"正在加载模型: {model_name}")

                # 这里实际应该加载YOLO26模型
                # 暂时用模拟加载
                await asyncio.sleep(1)  # 模拟加载时间

                model_info = self.models[model_name]
                self.current_model = model_name
                self.model_instance = {
                    "name": model_name,
                    "type": model_info["type"],
                    "loaded_at": time.time()
                }

                logger.info(f"模型加载成功: {model_name}")
                return True

            except Exception as e:
                logger.error(f"模型加载失败: {model_name}, 错误: {e}")
                raise

    async def switch_model(self, model_name: str):
        """切换模型"""
        if model_name == self.current_model:
            logger.info(f"模型已是当前模型: {model_name}")
            return True

        old_model = self.current_model
        try:
            await self.load_model(model_name)
            logger.info(f"模型切换成功: {old_model} -> {model_name}")
            return True
        except Exception as e:
            logger.error(f"模型切换失败: {e}")
            return False

    async def start_watcher(self):
        """启动文件监视器"""
        self.watcher = ModelWatcher(self)
        self.observer = Observer()
        self.observer.schedule(self.watcher, str(settings.MODELS_DIR), recursive=False)
        self.observer.start()
        logger.info("模型文件监视器已启动")

    async def stop_watcher(self):
        """停止文件监视器"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("模型文件监视器已停止")

    async def cleanup(self):
        """清理资源"""
        await self.stop_watcher()
        logger.info("模型管理器清理完成")

    def get_model_list(self) -> List[Dict[str, Any]]:
        """获取模型列表"""
        return [
            {
                "name": model_name,
                "display_name": info["name"],
                "size": info["size"],
                "type": info["type"],
                "is_current": model_name == self.current_model
            }
            for model_name, info in self.models.items()
        ]

    def get_current_model(self) -> Optional[Dict[str, Any]]:
        """获取当前模型信息"""
        if not self.current_model or self.current_model not in self.models:
            return None

        info = self.models[self.current_model]
        return {
            "name": self.current_model,
            "display_name": info["name"],
            "type": info["type"],
            "loaded_at": self.model_instance.get("loaded_at") if self.model_instance else None
        }