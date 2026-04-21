"""
模型管理器 - 管理YOLO26模型加载和切换
"""
import os
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from ultralytics import YOLO

class ModelType(Enum):
    """模型类型"""
    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"

class ModelManager:
    """YOLO26模型管理器"""

    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)
        self.models: Dict[str, Dict[str, Any]] = {}
        self.current_model: Optional[str] = None
        self.model_instance: Optional[YOLO] = None
        self.model_lock = threading.Lock()
        self._initialized = False
        self.use_end2end = True  # 默认启用端到端推理

    def initialize(self):
        """初始化模型管理器"""
        if self._initialized:
            return

        # 创建模型目录
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # 扫描模型
        self.scan_models()

        self._initialized = True

    def scan_models(self):
        """扫描模型目录"""
        self.models.clear()

        # 扫描PyTorch模型
        for model_file in self.models_dir.glob("*.pt"):
            self._add_model(model_file, ModelType.PYTORCH)

        # 扫描ONNX模型
        for model_file in self.models_dir.glob("*.onnx"):
            self._add_model(model_file, ModelType.ONNX)

        # 扫描TensorRT模型
        for model_file in self.models_dir.glob("*.engine"):
            self._add_model(model_file, ModelType.TENSORRT)

    def _add_model(self, model_path: Path, model_type: ModelType):
        """添加模型到管理列表"""
        stat = model_path.stat()
        self.models[model_path.name] = {
            "path": str(model_path),
            "name": model_path.stem,
            "type": model_type.value,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime
        }

    def load_model(self, model_name: str, use_end2end: bool = True) -> bool:
        """
        加载模型

        Args:
            model_name: 模型文件名
            use_end2end: 是否使用端到端推理（一对一头部）

        Returns:
            是否加载成功
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        with self.model_lock:
            try:
                model_info = self.models[model_name]
                model_path = model_info["path"]

                print(f"🔄 加载模型: {model_name} ({model_info['type']})")

                # 加载YOLO26模型
                # YOLO26支持end2end参数控制是否使用一对一头部
                self.model_instance = YOLO(model_path)

                # 设置模型配置
                if model_info["type"] == ModelType.PYTORCH.value:
                    # PyTorch模型可以设置end2end参数
                    # 注意：YOLO26的具体API可能需要调整
                    pass
                elif model_info["type"] == ModelType.ONNX.value:
                    # ONNX模型需要不同的加载方式
                    pass

                self.current_model = model_name
                self.use_end2end = use_end2end  # 存储端到端设置
                print(f"✅ 模型加载成功: {model_name}, 端到端推理: {use_end2end}")

                return True

            except Exception as e:
                print(f"❌ 模型加载失败: {model_name}, 错误: {e}")
                raise

    def switch_model(self, model_name: str, use_end2end: Optional[bool] = None) -> bool:
        """切换到指定模型"""
        if model_name == self.current_model:
            print(f"ℹ️ 模型已是当前模型: {model_name}")
            return True

        try:
            # 如果没有指定use_end2end，则使用当前设置（如果存在），否则使用默认值True
            if use_end2end is None:
                use_end2end = getattr(self, 'use_end2end', True)

            success = self.load_model(model_name, use_end2end=use_end2end)
            if success:
                print(f"🔄 模型切换成功: {self.current_model} -> {model_name}, 端到端推理: {use_end2end}")
            return success
        except Exception as e:
            print(f"❌ 模型切换失败: {e}")
            return False

    def unload_model(self):
        """卸载当前模型"""
        with self.model_lock:
            self.model_instance = None
            self.current_model = None
            print("🗑️ 模型已卸载")

    def get_model_list(self) -> List[Dict[str, Any]]:
        """获取模型列表"""
        return [
            {
                "name": model_name,
                "display_name": info["name"],
                "type": info["type"],
                "size": info["size"],
                "is_current": model_name == self.current_model
            }
            for model_name, info in self.models.items()
        ]

    def get_current_model_info(self) -> Optional[Dict[str, Any]]:
        """获取当前模型信息"""
        if not self.current_model:
            return None

        info = self.models[self.current_model].copy()
        info["loaded_at"] = time.time()
        return info

    def predict(self, image, **kwargs):
        """
        使用当前模型进行预测

        Args:
            image: 输入图像
            **kwargs: 传递给YOLO的额外参数

        Returns:
            预测结果
        """
        if not self.model_instance:
            raise RuntimeError("没有加载模型")

        print(f"🔍 ModelManager.predict 被调用，图像形状: {image.shape}")
        with self.model_lock:
            # YOLO26推理
            # 使用end2end参数启用一对一头部（免NMS）
            # 优先使用kwargs中的end2end参数，否则使用模型加载时的设置
            inference_kwargs = kwargs.copy()
            end2end = inference_kwargs.pop('end2end', self.use_end2end)

            print(f"🎯 开始YOLO推理，端到端模式: {end2end}, 参数: {inference_kwargs}")
            results = self.model_instance(image, end2end=end2end, **inference_kwargs)
            print(f"✅ YOLO推理完成，原始结果类型: {type(results)}")

            # 处理结果
            processed_results = []
            for result in results:
                # 提取检测信息
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        detection = {
                            "bbox": box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                            "confidence": box.conf.item(),
                            "class_id": int(box.cls.item()),
                            "class": result.names[int(box.cls.item())]
                        }
                        processed_results.append(detection)

            return processed_results

    def cleanup(self):
        """清理资源"""
        self.unload_model()
        print("🧹 模型管理器清理完成")