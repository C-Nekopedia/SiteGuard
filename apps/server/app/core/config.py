"""
Application configuration
"""
import os
from pathlib import Path
from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""

    # Basic configuration
    APP_NAME: str = "SiteGuard AI"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # File upload configuration
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/jpg"]

    # Path configuration
    # Override via SITEGUARD_BASE_DIR env var; defaults to 5 levels up from config.py to project root
    _BASE_DIR_FALLBACK: Path = Path(__file__).resolve().parent.parent.parent.parent.parent
    BASE_DIR: Path = Path(os.environ.get("SITEGUARD_BASE_DIR", str(_BASE_DIR_FALLBACK)))
    # Model directory, env var: MODELS_DIR
    MODELS_DIR: Path = BASE_DIR / "data" / "models"
    # Data directory, env var: DATA_DIR
    DATA_DIR: Path = BASE_DIR / "data" / "raw"
    # Static files directory, env var: STATIC_DIR
    STATIC_DIR: Path = BASE_DIR / "apps" / "server" / "static"
    # Export directory, env var: EXPORTS_DIR
    EXPORTS_DIR: Path = BASE_DIR / "apps" / "server" / "exports"

    # AI configuration
    DEFAULT_MODEL: str = "yolo26n_ppe.pt"
    CONFIDENCE_THRESHOLD: float = 0.5
    IOU_THRESHOLD: float = 0.5
    MAX_DETECTIONS: int = 300  # YOLO26 one-to-one head max detections

    # CORS configuration
    CORS_ORIGINS: str = "http://localhost:3000"

    # Camera configuration
    CAMERA_FRAME_WIDTH: int = 480
    CAMERA_FRAME_HEIGHT: int = 360
    CAMERA_JPEG_QUALITY: int = 50

    # Temp file cleanup delay (seconds)
    TEMP_FILE_CLEANUP_DELAY: int = 3600

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @field_validator(
        "MODELS_DIR", "DATA_DIR", "STATIC_DIR", "EXPORTS_DIR",
        mode="after"
    )
    @classmethod
    def resolve_relative_paths(cls, v: Path, info: ValidationInfo) -> Path:
        """
        Resolve relative paths: if a path is relative, resolve it against BASE_DIR.
        Environment variables can set absolute paths or paths relative to BASE_DIR.
        """
        # If path is already absolute, return it directly
        if v.is_absolute():
            return v

        # Get BASE_DIR value from validation data
        # Note: due to validation order, BASE_DIR may not be validated yet
        data = info.data
        if data and "BASE_DIR" in data:
            base_dir = data["BASE_DIR"]
            if isinstance(base_dir, Path):
                return base_dir / v
        # Fallback: return relative to current working directory
        return v

    @field_validator("BASE_DIR", mode="after")
    @classmethod
    def ensure_absolute_path(cls, v: Path) -> Path:
        """Ensure BASE_DIR is an absolute path"""
        if not v.is_absolute():
            # Convert relative path to absolute (relative to current working directory)
            return v.resolve()
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Create required directories
for directory in [settings.MODELS_DIR, settings.DATA_DIR, settings.STATIC_DIR, settings.EXPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

def validate_paths() -> tuple[bool, list[str]]:
    """
    Validate critical path configuration.
    Returns: (success, list of problem messages)
    """
    problems = []

    # Directories to validate
    critical_dirs = [
        ("MODELS_DIR", settings.MODELS_DIR, True, "Model directory"),
        ("DATA_DIR", settings.DATA_DIR, False, "Data directory"),
        ("STATIC_DIR", settings.STATIC_DIR, True, "Static files directory"),
        ("EXPORTS_DIR", settings.EXPORTS_DIR, True, "Export directory"),
    ]

    for name, path, must_exist, desc in critical_dirs:
        try:
            path = Path(path)
            if must_exist and not path.exists():
                problems.append(f"{desc} does not exist: {path}")
            elif path.exists():
                if not os.access(path, os.R_OK):
                    problems.append(f"{desc} not readable: {path}")
                if name in ["STATIC_DIR", "EXPORTS_DIR"] and not os.access(path, os.W_OK):
                    problems.append(f"{desc} not writable: {path}")
        except Exception as e:
            problems.append(f"Error checking {desc}: {e}")

    return len(problems) == 0, problems
