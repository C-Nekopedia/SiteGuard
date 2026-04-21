"""
检测服务 - 处理图片、视频和摄像头流的推理
"""
import asyncio
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
import tempfile
import time

from ..core.config import settings
from ..utils.logger import setup_logger
from ai_engine.model.model_manager import ModelManager

logger = setup_logger(__name__)

class DetectionService:
    """检测服务"""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager

    async def detect_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        检测单张图片
        """
        try:
            logger.info(f"📥 检测图片请求到达，数据大小: {len(image_data)} bytes")
            # 将bytes转换为numpy数组
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("无法解码图片")

            # 记录开始时间
            start_time = time.time()

            # YOLO26真实推理
            logger.info("🎯 开始YOLO26真实推理...")
            print(f"📞 调用 ModelManager.predict，模型实例: {self.model_manager}")
            detections = self.model_manager.predict(
                image,
                conf=settings.CONFIDENCE_THRESHOLD,
                iou=settings.IOU_THRESHOLD,
                max_det=settings.MAX_DETECTIONS,
                verbose=False
            )
            logger.info(f"✅ YOLO26真实推理完成，检测到 {len(detections)} 个目标")
            print(f"📊 检测结果数量: {len(detections)}")
            if detections:
                for i, det in enumerate(detections[:3]):  # 显示前3个检测
                    logger.info(f"  检测{i+1}: {det.get('class')} ({det.get('confidence'):.2f}) at {det.get('bbox')}")

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
            logger.error(f"图片检测失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def detect_video(self, video_path: Path) -> Generator[Dict[str, Any], None, None]:
        """
        检测视频文件（逐帧）
        """
        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"无法打开视频文件: {video_path}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            logger.info(f"🎬 开始处理视频: {video_path.name}, FPS: {fps}, 总帧数: {total_frames}")

            frame_count = 0
            processed_frames = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # 抽帧处理
                if frame_count % int(fps / settings.VIDEO_FRAME_RATE) == 0:
                    try:
                        # 检测当前帧 - 使用真实推理
                        detections = self.model_manager.predict(
                            frame,
                            conf=settings.CONFIDENCE_THRESHOLD,
                            iou=settings.IOU_THRESHOLD,
                            max_det=settings.MAX_DETECTIONS,
                            verbose=False
                        )
                        risks = await self._apply_risk_rules(detections)

                        yield {
                            "frame_index": frame_count,
                            "detections": detections,
                            "risks": risks,
                            "progress": frame_count / total_frames
                        }

                        processed_frames += 1

                    except Exception as e:
                        logger.error(f"视频帧检测失败: {e}")

                # 避免处理过快
                await asyncio.sleep(0.01)

            logger.info(f"✅ 视频处理完成，处理了 {processed_frames} 帧")

        finally:
            if cap:
                cap.release()
                logger.debug("📹 视频资源已释放")

    async def process_camera_frame(self, frame_data: np.ndarray) -> Dict[str, Any]:
        """
        处理摄像头帧
        """
        try:
            start_time = time.time()

            # 检测 - 使用真实推理
            detections = self.model_manager.predict(
                frame_data,
                conf=settings.CONFIDENCE_THRESHOLD,
                iou=settings.IOU_THRESHOLD,
                max_det=settings.MAX_DETECTIONS,
                verbose=False
            )
            risks = await self._apply_risk_rules(detections)

            inference_time = (time.time() - start_time) * 1000

            # 标注图像
            annotated_frame = await self._annotate_image(frame_data, detections)

            return {
                "success": True,
                "detections": detections,
                "risks": risks,
                "inference_time": inference_time,
                "frame_size": {"width": frame_data.shape[1], "height": frame_data.shape[0]},
                "annotated_frame": annotated_frame
            }

        except Exception as e:
            logger.error(f"摄像头帧处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    async def _apply_risk_rules(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        应用风险规则
        """
        risks = []

        # 检查是否有未戴安全帽
        no_helmet_detections = [d for d in detections if d.get("class", "").lower() in ["no_helmet", "no-helmet"]]
        if no_helmet_detections:
            risks.append({
                "type": "no_helmet",
                "level": "high",
                "message": "检测到未佩戴安全帽",
                "count": len(no_helmet_detections)
            })

        # 检查是否有人员但无安全帽
        person_detections = [d for d in detections if d.get("class", "").lower() in ["person", "persons"]]
        helmet_detections = [d for d in detections if d.get("class", "").lower() == "helmet"]

        if person_detections and not helmet_detections:
            risks.append({
                "type": "missing_helmet",
                "level": "high",
                "message": "人员未佩戴安全帽",
                "count": len(person_detections)
            })

        # 检查是否有完全无防护
        none_detections = [d for d in detections if d.get("class", "").lower() == "none"]
        if none_detections:
            risks.append({
                "type": "no_ppe",
                "level": "critical",
                "message": "检测到完全无防护人员",
                "count": len(none_detections)
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
            logger.error(f"图片标注失败: {e}")
            # 返回原始图片
            success, encoded_image = cv2.imencode('.jpg', image)
            return encoded_image.tobytes() if success else b""