"""
AI Engine package - YOLO26 wrapper
"""
from setuptools import setup, find_packages

setup(
    name="ai-engine",
    version="1.0.0",
    description="SiteGuard AI Engine - YOLO26 wrapper and inference engine",
    author="SiteGuard Team",
    packages=find_packages(),
    install_requires=[
        "ultralytics>=8.4.0",
        "numpy>=1.24.3,<2",
        "opencv-python>=4.8.0",
        "PyYAML>=6.0",
        "watchdog>=3.0.0",
        "onnxruntime>=1.15.0",
    ],
    python_requires=">=3.8",
)