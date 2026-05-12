"""
Detection service - handles image, video, and camera stream inference
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
    """Calculate IoU of two bounding boxes [x1, y1, x2, y2]"""
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
    """Inter-frame risk state tracker for camera, prevents per-frame log flooding"""

    def __init__(self, iou_threshold: float = 0.3):
        self.prev_bboxes: Dict[str, list] = {}
        self.iou_threshold = iou_threshold

    def update(self, risks: List[Dict[str, Any]], detections: List[Dict[str, Any]]):
        """
        Compare current frame risk state with previous frame.
        Only writes alert log when state changes.
        """
        # Build current frame risk type -> bbox list
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

            # Count new (current boxes not matching any previous box)
            new_count = 0
            for cb in curr_boxes:
                if not any(_iou(cb, pb) > self.iou_threshold for pb in prev_boxes):
                    new_count += 1

            # Count resolved (previous boxes not matching any current box)
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
    """Detection service"""

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.risk_tracker = CameraRiskTracker()

    async def detect_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Detect a single image
        """
        try:
            detection_logger.info(f"Image detection request received, size: {len(image_data)} bytes")
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("unable to decode image")

            # Record start time
            start_time = time.time()

            # YOLO26 real inference
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

            # Calculate inference time
            inference_time = (time.time() - start_time) * 1000

            # Apply risk rules
            risks = await self._apply_risk_rules(detections)

            # Generate annotated image
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
        Process camera frame
        """
        try:
            start_time = time.time()

            # Detection - real inference, camera mode enables GPU and half precision
            predict_start = time.time()
            detections = self.model_manager.predict(
                frame_data,
                conf=settings.CONFIDENCE_THRESHOLD,
                iou=settings.IOU_THRESHOLD,
                max_det=settings.MAX_DETECTIONS,
                verbose=False,
                camera_mode=True  # Enable camera inference mode (GPU + half precision)
            )
            predict_time = (time.time() - predict_start) * 1000

            risks_start = time.time()
            risks = await self._apply_risk_rules(detections)
            # Inter-frame risk state tracking (camera mode only), writes alert log on change
            self.risk_tracker.update(risks, detections)
            risk_time = (time.time() - risks_start) * 1000

            inference_time = (time.time() - start_time) * 1000

            # Annotate image
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
            logger.error(f"Camera frame processing failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    # Risk rule definitions (data-driven)
    RISK_RULES = [
        {
            "type": "no_helmet",
            "level": "high",
            "message": "No helmet detected",
            "classes": ["no_helmet", "no-helmet"],
        },
        {
            "type": "missing_helmet",
            "level": "high",
            "message": "Person without helmet",
            "classes": ["person", "persons"],
            "absent_classes": ["helmet"],
        },
        {
            "type": "no_vest",
            "level": "medium",
            "message": "No vest detected",
            "classes": ["none"],
        },
    ]

    async def _apply_risk_rules(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply risk rules (data-driven)
        """
        # Build class name -> [(index, detection)] lookup table
        by_class: Dict[str, List[tuple[int, dict]]] = {}
        for i, d in enumerate(detections):
            cls = d.get("class", "").lower()
            by_class.setdefault(cls, []).append((i, d))

        risks = []
        for rule in self.RISK_RULES:
            # Collect detections matching this rule
            matches = []
            for cls in rule["classes"]:
                matches.extend(by_class.get(cls, []))

            # If rule requires certain classes to be absent
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
        Annotate detections on image
        """
        try:
            # Create a copy
            annotated = image.copy()

            # Color mapping (using lowercase keys)
            colors = {
                "person": (128, 128, 128),    # Gray
                "helmet": (0, 255, 0),        # Green
                "no_helmet": (0, 165, 255),   # Orange
                "vest": (255, 0, 0),          # Blue
                "no_vest": (0, 0, 255),       # Red
                "none": (0, 0, 255),          # Red
                "gloves": (255, 255, 0),      # Yellow
                "no_gloves": (255, 165, 0),   # Orange
                "boots": (128, 0, 128),       # Purple
                "no_boots": (128, 0, 255),    # Magenta
                "goggles": (0, 255, 255),     # Cyan
                "no_goggle": (0, 128, 255),   # Teal
            }

            for det in detections:
                bbox = det["bbox"]
                class_name = det["class"]
                confidence = det["confidence"]

                x1, y1, x2, y2 = [int(coord) for coord in bbox]
                # Use lowercase class name for color lookup
                color = colors.get(class_name.lower(), (255, 255, 0))

                # Draw bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                # Draw label background
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

                # Draw label text
                cv2.putText(
                    annotated,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

            # Convert to bytes
            success, encoded_image = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not success:
                raise ValueError("Image encoding failed")

            return encoded_image.tobytes()

        except Exception as e:
            logger.error(f"Annotate image failed: {e}")
            # Return original image
            success, encoded_image = cv2.imencode('.jpg', image)
            return encoded_image.tobytes() if success else b""
