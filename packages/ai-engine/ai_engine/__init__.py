"""
SiteGuard AI Engine
YOLO26封装和推理引擎
"""

__version__ = "1.0.0"
__author__ = "SiteGuard Team"

from .model.model_manager import ModelManager

__all__ = ["ModelManager"]