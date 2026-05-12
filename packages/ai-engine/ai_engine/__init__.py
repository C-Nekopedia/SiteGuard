"""
SiteGuard AI Engine
YOLO26 wrapper and inference engine
"""

__version__ = "1.0.0"
__author__ = "SiteGuard Team"

from .model.model_manager import ModelManager

__all__ = ["ModelManager"]
