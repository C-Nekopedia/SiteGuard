#!/usr/bin/env python3
"""
YOLO26 Model Training Script
For training on the Construction-PPE dataset
"""

import os # noqa: F401
import sys
import argparse
from pathlib import Path
import yaml

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def prepare_dataset_yaml():
    """Prepare dataset YAML configuration file"""
    raw_dir = project_root / "data" / "raw"
    yaml_path = raw_dir / "data.yaml"

    if yaml_path.exists():
        print(f"Using existing data.yaml: {yaml_path}")
        return yaml_path

    # Create new data.yaml
    data_config = {
        "path": str(raw_dir.absolute()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {
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
    }

    with open(yaml_path, 'w') as f:
        yaml.dump(data_config, f, default_flow_style=False)

    print(f"[OK] Created data.yaml: {yaml_path}")
    return yaml_path

def train_model(args):
    """Train model"""
    try:
        import os
        from pathlib import Path

        # ========== Migrate cache to D drive ==========
        print("[Config] Setting up cache directories...")

        # Try to clean up PyTorch and CUDA caches on C drive (if present)
        print("[Clean] Attempting to clean C drive caches...")
        c_pytorch_cache_dirs = [
            Path("~/.cache/torch").expanduser(),
            Path("~/.cache/huggingface").expanduser(),
            Path(os.environ.get("LOCALAPPDATA", "")) / "torch",
            Path(os.environ.get("APPDATA", "")) / "torch",
            Path(os.environ.get("TEMP", "")) if "TEMP" in os.environ else None,
            Path(os.environ.get("TMP", "")) if "TMP" in os.environ else None,
        ]

        for cache_dir in c_pytorch_cache_dirs:
            if cache_dir and cache_dir.exists() and str(cache_dir).startswith("C:"):
                try:
                    # Only delete cache files, not directory structure
                    for item in cache_dir.rglob("*"):
                        if item.is_file():
                            item.unlink(missing_ok=True)
                    print(f"   Cleaned: {cache_dir}")
                except Exception as e:
                    print(f"   Clean failed {cache_dir}: {e}")

        # Define D drive cache root
        d_drive_cache_root = Path("D:/Temp/SiteGuard")

        # Create necessary cache directories
        cache_dirs = {
            "TEMP": d_drive_cache_root / "temp",
            "TMP": d_drive_cache_root / "temp",
            "TORCH_HOME": d_drive_cache_root / "torch",
            "ULTRALYTICS_HOME": d_drive_cache_root / "ultralytics",
            "HF_HOME": d_drive_cache_root / "huggingface",
            "CUDA_CACHE_PATH": d_drive_cache_root / "cuda_cache",
            "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:512",
            "PYTORCH_NO_CUDA_MEMORY_CACHING": "1",
        }

        for env_var, cache_value in cache_dirs.items():
            # If path object, create directory and set env var
            if isinstance(cache_value, Path):
                cache_value.mkdir(parents=True, exist_ok=True)
                os.environ[env_var] = str(cache_value.absolute())
                print(f"   {env_var}: {cache_value}")
            # If string, set env var directly
            else:
                os.environ[env_var] = str(cache_value)
                print(f"   {env_var}: {cache_value}")

        # Ensure Windows temp dir settings (for nvperf_host.dll loading issues)
        # TEMP and TMP are already set via the dict above

        print("[OK] Cache directory configuration complete")

        import torch
        from ultralytics import YOLO

        # Device detection: fall back to CPU if specified GPU is unavailable
        if args.device == "cpu":
            print("[Info] Using CPU for training")
        else:
            if torch.cuda.is_available():
                print(f"[OK]  CUDA available, using GPU {args.device} for training")
            else:
                print("[WARN]  CUDA unavailable, using CPU for training")
                args.device = "cpu"

        # Prepare dataset config
        data_yaml = prepare_dataset_yaml()

        print("    Starting YOLO26 model training")
        print(f"   Dataset: {data_yaml}")
        print(f"   Model size: {args.model_size}")
        print(f"   Epochs: {args.epochs}")
        print(f"   Batch size: {args.batch_size}")
        print(f"   Image size: {args.imgsz}")
        print(f"   Device: {args.device}")

        # Base training parameters (applicable in all cases)
        train_args = {
            "data": str(data_yaml),
            "epochs": args.epochs,
            "batch": args.batch_size,
            "imgsz": args.imgsz,
            "device": args.device,
            "workers": args.workers,
            "name": f"yolo26{args.model_size}_ppe",
            "exist_ok": True,
            "optimizer": args.optimizer,
            "verbose": True,
            "save": True,
            "save_period": 10,
            "cache": False,
            "single_cls": False,
            "rect": False,
            "cos_lr": False,
            "label_smoothing": 0.0,
            "patience": max(10, min(30, args.epochs // 4)),
            "freeze": None,
            "lr0": 0.001,
            "lrf": 0.0001,
            "momentum": 0.937,
            "weight_decay": 0.0005,
            "warmup_epochs": 5.0,
            "warmup_momentum": 0.8,
            "warmup_bias_lr": 0.1,
            "box": 7.5,
            "cls": 0.5,
            "dfl": 1.5,
            "nbs": 64,
            "dropout": 0.0,
            "val": True,
            "plots": True,
            "close_mosaic": 10,
        }

        # Load model
        if args.resume:
            # Resume from checkpoint
            print(f"[Resume] Resuming training from checkpoint: {args.resume}")
            model = YOLO(args.resume)

            # If optimizer is specified and not "auto", force new optimizer
            if args.optimizer != "auto":
                print(f"[Optimizer] Force using new optimizer: {args.optimizer} (overrides checkpoint optimizer)")
                # Try to clear optimizer state from model, forcing re-initialization
                try:
                    # Access model internal optimizer and clear it (if exists and not None)
                    # Note: type: ignore is used because type checker cannot infer ultralytics internal dynamic attributes
                    if hasattr(model, 'model') and model.model is not None and hasattr(model.model, 'optimizer'):
                        model.model.optimizer = None  # type: ignore
                        print("   Cleared optimizer state from checkpoint")
                    # Clear scaler (if exists)
                    if hasattr(model, 'model') and model.model is not None and hasattr(model.model, 'scaler'):
                        model.model.scaler = None  # type: ignore
                except Exception as e:
                    print(f"   Error clearing optimizer state (may have been auto-handled): {e}")

                # Set resume=False, forcing training from scratch with new optimizer
                # This ensures the specified optimizer is used, not the checkpoint's optimizer
                train_args["resume"] = False
                print("   Training from scratch (using checkpoint weights) with new optimizer settings")
            else:
                # Use optimizer settings from checkpoint
                train_args["resume"] = True
                print("[Optimizer] Using optimizer settings from checkpoint")
        elif args.pretrained:
            model_name = f"yolo26{args.model_size}.pt"
            print(f"[Download] Loading pretrained model: {model_name}")
            model = YOLO(model_name)
        else:
            print("[New] Creating new model")
            model = YOLO(f"yolo26{args.model_size}.yaml")

        # Start training (don't store result, access training info via model.trainer)
        model.train(**train_args)

        # Save best model to models directory
        models_dir = project_root / "data" / "models"
        models_dir.mkdir(exist_ok=True)

        # Get save directory via trainer object (plan A)
        if hasattr(model, 'trainer') and model.trainer:
            trainer = model.trainer
            if hasattr(trainer, 'save_dir') and trainer.save_dir:
                save_dir = Path(trainer.save_dir)
                best_model_path = save_dir / "weights" / "best.pt"
                if best_model_path.exists():
                    target_path = models_dir / f"yolo26{args.model_size}_ppe.pt"
                    import shutil
                    shutil.copy2(best_model_path, target_path)
                    print(f"[OK] Best model saved to: {target_path}")
                else:
                    print(f"[WARN]  Best model file not found: {best_model_path}")
            else:
                print("[WARN]  No save directory info in trainer, skipping model save")
        else:
            print("[WARN]  Cannot access trainer info, skipping model save")

        # Validate model
        if args.val:
            print("Validating model...")
            metrics = model.val(end2end=args.end2end)
            print(f"[OK] Validation complete: mAP50-95 = {metrics.box.map}")

        return True

    except Exception as e:
        print(f"[FAIL] Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def export_model(args):
    """Export model"""
    try:
        from ultralytics import YOLO

        models_dir = project_root / "data" / "models"
        model_path = models_dir / f"yolo26{args.model_size}_ppe.pt"

        if not model_path.exists():
            print(f"[FAIL] Model file not found: {model_path}")
            return False

        print(f"Exporting model: {model_path}")
        model = YOLO(str(model_path))

        # Export to ONNX
        if "onnx" in args.formats:
            onnx_path = model_path.with_suffix(".onnx")
            success = model.export(
                format="onnx",
                imgsz=args.imgsz,
                dynamic=True,
                simplify=True,
                opset=12
            )
            if success:
                print(f"[OK] ONNX model exported: {onnx_path}")
            else:
                print("[FAIL] ONNX model export failed")

        # Export to TensorRT
        if "engine" in args.formats:
            engine_path = model_path.with_suffix(".engine")
            success = model.export(
                format="engine",
                imgsz=args.imgsz,
                half=True,
                workspace=4
            )
            if success:
                print(f"[OK] TensorRT model exported: {engine_path}")
            else:
                print("[FAIL] TensorRT model export failed")

        return True

    except Exception as e:
        print(f"[FAIL] Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="YOLO26 Model Training Script")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train model")
    train_parser.add_argument("--model-size", choices=["n", "s", "m", "l", "x"],
                            default="n", help="Model size")
    train_parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    train_parser.add_argument("--batch-size", type=int, default=8, help="Batch size (default 8, suitable for small datasets)")
    train_parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    train_parser.add_argument("--device", default="0", help="Device (GPU ID or 'cpu')")
    train_parser.add_argument("--workers", type=int, default=2, help="Data loader workers (default 2, reduces memory pressure)")
    train_parser.add_argument("--pretrained", action="store_true",
                            help="Use pretrained model")
    train_parser.add_argument("--resume", type=str, default=None,
                            help="Resume training from checkpoint (specify .pt file path)")
    train_parser.add_argument("--no-val", dest="val", action="store_false",
                            help="Skip validation")
    train_parser.add_argument("--optimizer", choices=["auto", "SGD", "MuSGD", "Adam", "AdamW", "NAdam", "RAdam", "RMSProp"],
                            default="Adam", help="Optimizer type (default Adam, suitable for small datasets)")
    train_parser.add_argument("--no-end2end", dest="end2end", action="store_false", default=True,
                            help="Use traditional validation mode (one-to-many head), default is end-to-end mode")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export model")
    export_parser.add_argument("--model-size", choices=["n", "s", "m", "l", "x"],
                             default="n", help="Model size")
    export_parser.add_argument("--formats", nargs="+",
                             choices=["onnx", "engine"], default=["onnx"],
                             help="Export formats")
    export_parser.add_argument("--imgsz", type=int, default=640, help="Image size")

    args = parser.parse_args()

    if args.command == "train":
        success = train_model(args)
        sys.exit(0 if success else 1)
    elif args.command == "export":
        success = export_model(args)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
