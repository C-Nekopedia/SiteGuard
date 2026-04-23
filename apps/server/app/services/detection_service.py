"""
检测服务 - 处理图片、视频和摄像头流的推理
"""
import cv2
import numpy as np
from typing import List, Dict, Any
import time

from ..core.config import settings
from ..utils.logger import setup_logger, setup_detection_logger, setup_risk_logger
from ai_engine.model.model_manager import ModelManager

logger = setup_logger(__name__)
detection_logger = setup_detection_logger()
risk_logger = setup_risk_logger()


def _iou(box1, box2):
    """计算两个检测框 [x1, y1, x2, y2] 的 IoU"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

    return inter / (area1 + area2 - inter + 1e-6)


class CameraRiskTracker:
    """摄像头帧间风险状态追踪，避免逐帧日志刷屏"""

    def __init__(self, iou_threshold: float = 0.3):
        self.prev_bboxes: Dict[str, list] = {}
        self.iou_threshold = iou_threshold

    def update(self, risks: List[Dict[str, Any]], detections: List[Dict[str, Any]]):
        """
        比较当前帧与上一帧的风险状态，仅在有变化时写入告警日志。
        """
        # 构建当前帧风险类型 -> bbox 列表
        current = {}
        for risk in risks:
            rt = risk["type"]
            bboxes = []
            for det_id in risk.get("detection_ids", []):
                if det_id < len(detections):
                    bboxes.append(detections[det_id]["bbox"])
            if bboxes:
                current[rt] = bboxes

        all_types = set(list(self.prev_bboxes.keys()) + list(current.keys()))

        for rt in sorted(all_types):
            prev_boxes = self.prev_bboxes.get(rt, [])
            curr_boxes = current.get(rt, [])

            prev_count = len(prev_boxes)
            curr_count = len(curr_boxes)

            # 统计新增（当前框与所有上一帧框不匹配）
            new_count = 0
            for cb in curr_boxes:
                if not any(_iou(cb, pb) > self.iou_threshold for pb in prev_boxes):
                    new_count += 1

            # 统计解除（上一帧框与所有当前框不匹配）
            resolved_count = 0
            for pb in prev_boxes:
                if not any(_iou(pb, cb) > self.iou_threshold for cb in curr_boxes):
                    resolved_count += 1

            if prev_count == 0 and curr_count > 0:
                risk_logger.warning(
                    f"[{rt}] Risk detected - {curr_count} violation(s)"
                )
            elif prev_count > 0 and curr_count == 0:
                risk_logger.info(
                    f"[{rt}] Risk cleared - all {prev_count} violation(s) resolved"
                )
            elif new_count > 0 and resolved_count == 0 and curr_count > prev_count:
                risk_logger.warning(
                    f"[{rt}] Risk escalated - {new_count} new violation(s) (total: {curr_count})"
                )
            elif resolved_count > 0 and new_count == 0 and curr_count < prev_count:
                risk_logger.info(
                    f"[{rt}] Risk de-escalated - {resolved_count} violation(s) resolved (remaining: {curr_count})"
                )
            elif new_count > 0 and resolved_count > 0:
                risk_logger.warning(
                    f"[{rt}] Risk changed - {new_count} new, {resolved_count} resolved (total: {curr_count})"
                )

        self.prev_bboxes = current

class DetectionService:
    """检测服务"""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.risk_tracker = CameraRiskTracker()

    async def detect_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        检测单张图片
        """
        try:
            detection_logger.info(f"Image detection request received, size: {len(image_data)} bytes")
            # 将bytes转换为numpy数组
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("unable to decode image")

            # 记录开始时间
            start_time = time.time()

            # YOLO26真实推理
            detection_logger.info("Starting YOLO26 inference...")
            detections = self.model_manager.predict(
                image,
                conf=settings.CONFIDENCE_THRESHOLD,
                iou=settings.IOU_THRESHOLD,
                max_det=settings.MAX_DETECTIONS,
                verbose=False
            )
            detection_logger.info(f"Inference complete, {len(detections)} object(s) detected")
            if detections:
                for i, det in enumerate(detections[:3]):
                    detection_logger.info(f"  #{i+1}: {det.get('class')} ({det.get('confidence'):.2f})")

            # 计算推理时间
            inference_time = (time.time() - start_time) * 1000

            # 应用风险规则
            risks = await self._apply_risk_rules(detections)

            # 生成标注图片
            annotated_image = await self._annotate_image(image, detections)

            return {
                "success": True,
                "detections": detections,
                "risks": risks,
                "inference_time": inference_time,
                "image_size": {"width": image.shape[1], "height": image.shape[0]},
                "annotated_image": annotated_image
            }

        except Exception as e:
            detection_logger.error(f"Image detection failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def process_camera_frame(self, frame_data: np.ndarray) -> Dict[str, Any]:
        """
        处理摄像头帧
        """
        try:
            start_time = time.time()

            # 检测 - 使用真实推理，摄像头模式启用GPU和半精度
            predict_start = time.time()
            detections = self.model_manager.predict(
                frame_data,
                conf=settings.CONFIDENCE_THRESHOLD,
                iou=settings.IOU_THRESHOLD,
                max_det=settings.MAX_DETECTIONS,
                verbose=False,
                camera_mode=True  # 启用摄像头推理模式（使用GPU和半精度）
            )
            predict_time = (time.time() - predict_start) * 1000

            risks_start = time.time()
            risks = await self._apply_risk_rules(detections)
            # 帧间风险状态追踪（仅摄像头模式），有变化时写入告警日志
            self.risk_tracker.update(risks, detections)
            risk_time = (time.time() - risks_start) * 1000

            inference_time = (time.time() - start_time) * 1000

            # 标注图像
            annotate_start = time.time()
            annotated_frame = await self._annotate_image(frame_data, detections)
            annotate_time = (time.time() - annotate_start) * 1000

            total_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "detections": detections,
                "risks": risks,
                "inference_time": inference_time,
                "predict_time_ms": predict_time,
                "risk_time_ms": risk_time,
                "annotate_time_ms": annotate_time,
                "total_time_ms": total_time,
                "frame_size": {"width": frame_data.shape[1], "height": frame_data.shape[0]},
                "annotated_frame": annotated_frame
            }

        except Exception as e:
            logger.error(f"摄像头帧处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    # 风险规则定义（数据驱动）
    RISK_RULES = [
        {
            "type": "no_helmet",
            "level": "high",
            "message": "检测到未佩戴安全帽",
            "classes": ["no_helmet", "no-helmet"],
        },
        {
            "type": "missing_helmet",
            "level": "high",
            "message": "人员未佩戴安全帽",
            "classes": ["person", "persons"],
            "absent_classes": ["helmet"],
        },
        {
            "type": "no_vest",
            "level": "medium",
            "message": "检测到未穿防护衣",
            "classes": ["none"],
        },
    ]

    async def _apply_risk_rules(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        应用风险规则（数据驱动）
        """
        # 按类别建立查找表：class_name -> [(index, detection)]
        by_class: Dict[str, List[tuple[int, dict]]] = {}
        for i, d in enumerate(detections):
            cls = d.get("class", "").lower()
            by_class.setdefault(cls, []).append((i, d))

        risks = []
        for rule in self.RISK_RULES:
            # 收集匹配该规则的检测结果
            matches = []
            for cls in rule["classes"]:
                matches.extend(by_class.get(cls, []))

            # 如果规则要求某些类别必须缺失
            absent = rule.get("absent_classes", [])
            has_absent = any(by_class.get(c, []) for c in absent)

            if not matches or (absent and has_absent):
                continue

            risks.append({
                "type": rule["type"],
                "level": rule["level"],
                "message": rule["message"],
                "count": len(matches),
                "detection_ids": [i for i, _ in matches],
            })

        return risks

    async def _annotate_image(self, image: np.ndarray, detections: List[Dict[str, Any]]) -> bytes:
        """
        在图片上标注检测结果
        """
        try:
            # 创建副本
            annotated = image.copy()

            # 颜色映射（使用小写键名）
            colors = {
                "person": (128, 128, 128),    # 灰色
                "helmet": (0, 255, 0),        # 绿色
                "no_helmet": (0, 165, 255),   # 橙色
                "vest": (255, 0, 0),          # 蓝色
                "no_vest": (0, 0, 255),       # 红色
                "none": (0, 0, 255),          # 红色
                "gloves": (255, 255, 0),      # 黄色
                "no_gloves": (255, 165, 0),   # 橙色
                "boots": (128, 0, 128),       # 紫色
                "no_boots": (128, 0, 255),    # 紫红色
                "goggles": (0, 255, 255),     # 青色
                "no_goggle": (0, 128, 255),   # 深青色
            }

            for det in detections:
                bbox = det["bbox"]
                class_name = det["class"]
                confidence = det["confidence"]

                x1, y1, x2, y2 = [int(coord) for coord in bbox]
                # 使用小写类名获取颜色
                color = colors.get(class_name.lower(), (255, 255, 0))

                # 绘制边界框
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                # 绘制标签背景
                label = f"{class_name} {confidence:.2f}"
                (label_width, label_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )

                cv2.rectangle(
                    annotated,
                    (x1, y1 - label_height - 10),
                    (x1 + label_width, y1),
                    color,
                    -1
                )

                # 绘制标签文字
                cv2.putText(
                    annotated,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

            # 转换为bytes
            success, encoded_image = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not success:
                raise ValueError("图片编码失败")

            return encoded_image.tobytes()

        except Exception as e:
            logger.error(f"Annotate image failed: {e}")
            # 返回原始图片
            success, encoded_image = cv2.imencode('.jpg', image)
            return encoded_image.tobytes() if success else b""