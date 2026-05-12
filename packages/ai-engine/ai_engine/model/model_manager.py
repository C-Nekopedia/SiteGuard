"""
Model manager - manages YOLO26 model loading and switching
"""
import logging
import time
import threading
import torch
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from ultralytics import YOLO

logger = logging.getLogger(__name__)

class ModelType(Enum):
    """Model type"""
    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"

class ModelManager:
    """YOLO26 model manager"""

    def __init__(self, models_dir: Path):
        self.models_dir = Path(models_dir)
        self.models: Dict[str, Dict[str, Any]] = {}
        self.current_model: Optional[str] = None
        self.model_instance: Optional[YOLO] = None
        self.model_lock = threading.Lock()
        self._initialized = False
        self.use_end2end = True  # Enable end-to-end inference by default
        # Device configuration
        self.default_device = self._detect_default_device()
        self.default_half = False  # Disable half precision by default (single image inference)
        self.camera_device = self.default_device  # Camera inference device
        self.camera_half = True  # Use half precision for camera inference

    def _detect_default_device(self) -> str:
        """Detect default device"""
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            logger.info(f"Detected {device_count} CUDA device(s):")
            for i in range(device_count):
                logger.info(f"  - GPU {i}: {torch.cuda.get_device_name(i)}")
            return "cuda:0"
        else:
            logger.info("No CUDA device detected, using CPU")
            return "cpu"

    def initialize(self):
        """Initialize model manager"""
        if self._initialized:
            return

        # Create models directory
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Scan models
        self.scan_models()

        self._initialized = True

    def scan_models(self):
        """Scan model directory"""
        self.models.clear()

        # Scan PyTorch models
        for model_file in self.models_dir.glob("*.pt"):
            self._add_model(model_file, ModelType.PYTORCH)

        # Scan ONNX models
        for model_file in self.models_dir.glob("*.onnx"):
            self._add_model(model_file, ModelType.ONNX)

        # Scan TensorRT models
        for model_file in self.models_dir.glob("*.engine"):
            self._add_model(model_file, ModelType.TENSORRT)

    def _add_model(self, model_path: Path, model_type: ModelType):
        """Add model to the management list"""
        stat = model_path.stat()
        self.models[model_path.name] = {
            "path": str(model_path),
            "name": model_path.stem,
            "type": model_type.value,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime
        }

    def load_model(self, model_name: str, use_end2end: bool = True, device: Optional[str] = None, half: Optional[bool] = None) -> bool:
        """
        Load model

        Args:
            model_name: Model filename
            use_end2end: Whether to use end-to-end inference (one-to-one head)
            device: Device ('cuda:0', 'cpu'), uses default when None
            half: Whether to use half precision, uses default when None

        Returns:
            Whether loading succeeded
        """
        if model_name not in self.models:
            raise ValueError(f"Model not found: {model_name}")

        with self.model_lock:
            try:
                model_info = self.models[model_name]
                model_path = model_info["path"]

                # Determine device
                target_device = device if device is not None else self.default_device
                target_half = half if half is not None else self.default_half

                logger.info(f"Loading model: {model_name} ({model_info['type']})")
                logger.info(f"  Device: {target_device}, Half precision: {target_half}, End-to-end inference: {use_end2end}")

                # Load YOLO26 model
                # YOLO26 supports end2end parameter to control one-to-one head
                # Note: YOLO's device parameter can be string or torch.device object
                self.model_instance = YOLO(model_path)

                # Configure model
                if model_info["type"] == ModelType.PYTORCH.value:
                    # PyTorch model can set device and half
                    # Note: YOLO model can be moved to device via to() after loading
                    if target_device.startswith('cuda'):
                        self.model_instance.to(target_device)
                        if target_half:
                            self.model_instance.half()
                    elif target_device == 'cpu':
                        self.model_instance.to('cpu')
                        if target_half:
                            logger.warning("CPU does not support half precision, using full precision")
                elif model_info["type"] == ModelType.ONNX.value:
                    raise NotImplementedError("ONNX model loading not yet implemented")

                self.current_model = model_name
                self.use_end2end = use_end2end  # Store end-to-end setting
                logger.info(f"Model loaded successfully: {model_name}, Device: {target_device}, Half precision: {target_half}, End-to-end inference: {use_end2end}")

                return True

            except Exception as e:
                logger.error(f"Model loading failed: {model_name}, Error: {e}")
                raise

    def switch_model(self, model_name: str, use_end2end: Optional[bool] = None) -> bool:
        """Switch to the specified model"""
        if model_name == self.current_model:
            logger.info(f"Model already active: {model_name}")
            return True

        try:
            # If use_end2end not specified, use current setting (if exists), otherwise default to True
            if use_end2end is None:
                use_end2end = getattr(self, 'use_end2end', True)

            success = self.load_model(model_name, use_end2end=use_end2end)
            if success:
                logger.info(f"Model switch successful: {self.current_model} -> {model_name}, End-to-end inference: {use_end2end}")
            return success
        except Exception as e:
            logger.error(f"Model switch failed: {e}")
            return False

    def unload_model(self):
        """Unload current model"""
        with self.model_lock:
            self.model_instance = None
            self.current_model = None
            logger.info("Model unloaded")

    def get_model_list(self) -> List[Dict[str, Any]]:
        """Get model list"""
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
        """Get current model info"""
        if not self.current_model:
            return None

        info = self.models[self.current_model].copy()
        info["loaded_at"] = time.time()
        return info

    def predict(self, image, device: Optional[str] = None, half: Optional[bool] = None, **kwargs):
        """
        Run prediction using current model

        Args:
            image: Input image
            device: Device ('cuda:0', 'cpu'), uses default when None
            half: Whether to use half precision, uses default when None
            **kwargs: Additional parameters passed to YOLO

        Returns:
            Prediction results
        """
        if not self.model_instance:
            raise RuntimeError("No model loaded")

        with self.model_lock:
            # YOLO26 inference
            # Use end2end parameter to enable one-to-one head (NMS-free)
            # Prefer end2end from kwargs, otherwise use model loading setting
            inference_kwargs = kwargs.copy()
            end2end = inference_kwargs.pop('end2end', self.use_end2end)

            # Determine inference device
            target_device = device if device is not None else self.default_device
            target_half = half if half is not None else self.default_half

            # If camera inference, use camera-specific configuration
            is_camera_inference = inference_kwargs.pop('camera_mode', False)
            if is_camera_inference:
                target_device = self.camera_device
                target_half = self.camera_half

            # Prepare YOLO inference parameters
            yolo_kwargs = inference_kwargs.copy()
            yolo_kwargs['end2end'] = end2end
            yolo_kwargs['device'] = target_device
            if target_half:
                yolo_kwargs['half'] = target_half

            results = self.model_instance(image, **yolo_kwargs)

            # Process results
            processed_results = []
            for result in results:
                # Extract detection info
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
        """Clean up resources"""
        self.unload_model()
        logger.info("Model manager cleanup complete")
