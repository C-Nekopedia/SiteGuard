"""
YOLO26推理引擎
"""
import time
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from ..model.model_manager import ModelManager

@dataclass
class DetectionResult:
    """检测结果"""
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float
    class_id: int
    class_name: str

@dataclass
class InferenceStats:
    """推理统计"""
    inference_time: float  # 毫秒
    preprocess_time: float  # 毫秒
    postprocess_time: float  # 毫秒
    total_time: float  # 毫秒
    num_detections: int

class YOLO26Inference:
    """YOLO26推理引擎"""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.class_names = self._load_class_names()
        self.stats_history = []

    def _load_class_names(self) -> Dict[int, str]:
        """加载类别名称映射"""
        # Construction-PPE数据集类别映射
        # 根据construction-ppe.yaml定义
        return {
            0: "helmet",
            1: "gloves",
            2: "vest",
            3: "boots",
            4: "goggles",
            5: "none",
            6: "Person",
            7: "no_helmet",
            8: "no_goggle",
            9: "no_gloves",
            10: "no_boots"
        }

    def predict_image(self, image: np.ndarray,
                     confidence_threshold: float = 0.5,
                     iou_threshold: float = 0.5,
                     max_detections: int = 300) -> Dict[str, Any]:
        """
        预测单张图片

        Args:
            image: 输入图像 (H, W, C) BGR格式
            confidence_threshold: 置信度阈值
            iou_threshold: IOU阈值（如果使用一对多头部）
            max_detections: 最大检测数

        Returns:
            包含检测结果和统计信息的字典
        """
        start_time = time.time()

        # 预处理
        preprocess_start = time.time()
        processed_image = self._preprocess_image(image)
        preprocess_time = (time.time() - preprocess_start) * 1000

        # 推理
        inference_start = time.time()
        try:
            # 使用模型管理器进行推理
            detections = self.model_manager.predict(
                processed_image,
                conf=confidence_threshold,
                iou=iou_threshold,
                max_det=max_detections,
                verbose=False
            )
        except Exception as e:
            raise RuntimeError(f"推理失败: {e}")

        inference_time = (time.time() - inference_start) * 1000

        # 后处理
        postprocess_start = time.time()
        processed_detections = self._postprocess_detections(detections)
        postprocess_time = (time.time() - postprocess_start) * 1000

        total_time = (time.time() - start_time) * 1000

        # 更新统计
        stats = InferenceStats(
            inference_time=inference_time,
            preprocess_time=preprocess_time,
            postprocess_time=postprocess_time,
            total_time=total_time,
            num_detections=len(processed_detections)
        )
        self.stats_history.append(stats)

        # 限制历史记录大小
        if len(self.stats_history) > 100:
            self.stats_history = self.stats_history[-100:]

        return {
            "detections": processed_detections,
            "stats": {
                "inference_time_ms": inference_time,
                "total_time_ms": total_time,
                "fps": 1000 / total_time if total_time > 0 else 0,
                "num_detections": len(processed_detections)
            },
            "image_info": {
                "height": image.shape[0],
                "width": image.shape[1],
                "channels": image.shape[2] if len(image.shape) > 2 else 1
            }
        }

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        预处理图像

        Args:
            image: 输入图像

        Returns:
            预处理后的图像
        """
        # YOLO模型通常需要RGB格式
        if len(image.shape) == 2:
            # 灰度图转RGB
            image = np.stack([image] * 3, axis=-1)
        elif image.shape[2] == 1:
            # 单通道转RGB
            image = np.repeat(image, 3, axis=2)
        elif image.shape[2] == 4:
            # RGBA转RGB
            image = image[:, :, :3]
        elif image.shape[2] == 3:
            # BGR转RGB（如果输入是BGR）
            image = image[:, :, ::-1]

        return image

    def _postprocess_detections(self, raw_detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        后处理检测结果

        Args:
            raw_detections: 原始检测结果

        Returns:
            处理后的检测结果
        """
        processed = []
        for det in raw_detections:
            # 确保bbox是列表
            bbox = det.get("bbox", [])
            if not isinstance(bbox, list):
                bbox = bbox.tolist() if hasattr(bbox, "tolist") else list(bbox)

            # 获取类别名称
            class_id = det.get("class_id", -1)
            class_name = self.class_names.get(class_id, f"class_{class_id}")

            processed.append({
                "bbox": bbox,
                "confidence": float(det.get("confidence", 0)),
                "class_id": class_id,
                "class": class_name
            })

        return processed

    def batch_predict(self, images: List[np.ndarray], **kwargs) -> List[Dict[str, Any]]:
        """
        批量预测

        Args:
            images: 图像列表
            **kwargs: 额外参数

        Returns:
            预测结果列表
        """
        results = []
        for image in images:
            result = self.predict_image(image, **kwargs)
            results.append(result)

        return results

    def get_stats_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        if not self.stats_history:
            return {}

        recent_stats = self.stats_history[-50:] if len(self.stats_history) >= 50 else self.stats_history

        inference_times = [s.inference_time for s in recent_stats]
        total_times = [s.total_time for s in recent_stats]
        num_detections = [s.num_detections for s in recent_stats]

        return {
            "avg_inference_time": np.mean(inference_times) if inference_times else 0,
            "avg_total_time": np.mean(total_times) if total_times else 0,
            "avg_fps": 1000 / np.mean(total_times) if total_times and np.mean(total_times) > 0 else 0,
            "avg_detections": np.mean(num_detections) if num_detections else 0,
            "total_predictions": len(self.stats_history),
            "recent_sample_size": len(recent_stats)
        }

    def warmup(self, warmup_iters: int = 10):
        """
        预热模型

        Args:
            warmup_iters: 预热迭代次数
        """
        print(f"🔥 预热模型 ({warmup_iters}次迭代)...")

        # 创建测试图像
        test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        for i in range(warmup_iters):
            try:
                self.predict_image(test_image)
                print(f"  迭代 {i+1}/{warmup_iters} 完成")
            except Exception as e:
                print(f"  迭代 {i+1} 失败: {e}")

        print("✅ 模型预热完成")