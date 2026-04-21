"""
应用配置
"""
import os
from pathlib import Path
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    """应用设置"""

    # 基础配置
    APP_NAME: str = "SiteGuard AI"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # 文件上传配置
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/jpg"]
    ALLOWED_VIDEO_TYPES: List[str] = ["video/mp4", "video/avi"]

    # 路径配置
    # 可以通过环境变量 SITEGUARD_BASE_DIR 覆盖
    BASE_DIR: Path = Path(__file__).parent.parent.parent.parent.parent
    # 模型目录，环境变量：MODELS_DIR
    MODELS_DIR: Path = BASE_DIR / "data" / "models"
    # 数据目录，环境变量：DATA_DIR
    DATA_DIR: Path = BASE_DIR / "data" / "raw"
    # 静态文件目录，环境变量：STATIC_DIR
    STATIC_DIR: Path = Path(__file__).parent.parent.parent / "static"
    # 导出目录，环境变量：EXPORTS_DIR
    EXPORTS_DIR: Path = Path(__file__).parent.parent.parent / "exports"

    # AI配置
    DEFAULT_MODEL: str = "yolo26n_ppe.pt"
    CONFIDENCE_THRESHOLD: float = 0.5
    IOU_THRESHOLD: float = 0.5
    MAX_DETECTIONS: int = 300  # YOLO26一对一头部最大检测数

    # 视频处理配置
    VIDEO_FRAME_RATE: int = 2  # 每秒抽帧数
    MAX_FRAME_QUEUE_SIZE: int = 2

    # 风险规则配置
    RULES_DIR: Path = BASE_DIR / "packages" / "ai-engine" / "ai_engine" / "rules"

    @field_validator(
        "MODELS_DIR", "DATA_DIR", "STATIC_DIR", "EXPORTS_DIR", "RULES_DIR",
        mode="after"
    )
    @classmethod
    def resolve_relative_paths(cls, v: Path, info: ValidationInfo) -> Path:
        """
        解析相对路径：如果路径是相对的，则相对于BASE_DIR解析。
        环境变量可以设置绝对路径或相对于BASE_DIR的相对路径。
        """
        # 如果路径已经是绝对路径，直接返回
        if v.is_absolute():
            return v

        # 获取BASE_DIR值
        # 注意：由于验证顺序，BASE_DIR可能尚未验证
        # 这里我们直接从数据中获取
        data = info.data
        if data and "BASE_DIR" in data:
            base_dir = data["BASE_DIR"]
            if isinstance(base_dir, Path):
                return base_dir / v
        # 如果无法获取BASE_DIR，返回相对路径（相对于当前工作目录）
        return v

    @field_validator("BASE_DIR", mode="after")
    @classmethod
    def ensure_absolute_path(cls, v: Path) -> Path:
        """确保BASE_DIR是绝对路径"""
        if not v.is_absolute():
            # 如果提供的是相对路径，转换为绝对路径（相对于当前工作目录）
            return v.resolve()
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# 创建必要的目录
for directory in [settings.MODELS_DIR, settings.DATA_DIR, settings.STATIC_DIR, settings.EXPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

def validate_paths() -> tuple[bool, list[str]]:
    """
    验证关键路径配置。
    返回：(是否成功, 问题消息列表)
    """
    import os
    from pathlib import Path

    problems = []

    # 需要验证的目录
    critical_dirs = [
        ("MODELS_DIR", settings.MODELS_DIR, True, "模型目录"),
        ("DATA_DIR", settings.DATA_DIR, False, "数据目录"),  # 不一定需要存在
        ("STATIC_DIR", settings.STATIC_DIR, True, "静态文件目录"),
        ("EXPORTS_DIR", settings.EXPORTS_DIR, True, "导出目录"),
        ("RULES_DIR", settings.RULES_DIR, False, "规则目录"),  # 不一定需要存在
    ]

    for name, path, must_exist, desc in critical_dirs:
        try:
            path = Path(path)
            if must_exist and not path.exists():
                problems.append(f"{desc}不存在: {path}")
            elif path.exists():
                # 检查是否可读（对于目录）
                if not os.access(path, os.R_OK):
                    problems.append(f"{desc}不可读: {path}")
                # 检查是否可写（对于需要写入的目录）
                if name in ["STATIC_DIR", "EXPORTS_DIR"] and not os.access(path, os.W_OK):
                    problems.append(f"{desc}不可写: {path}")
        except Exception as e:
            problems.append(f"检查{desc}时出错: {e}")

    return len(problems) == 0, problems