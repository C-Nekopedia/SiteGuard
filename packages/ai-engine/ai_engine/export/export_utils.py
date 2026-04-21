"""
模型导出工具
"""
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

class ModelExporter:
    """模型导出工具"""

    @staticmethod
    def export_to_onnx(model_path: Path, output_dir: Path,
                      imgsz: int = 640, dynamic: bool = True,
                      simplify: bool = True) -> Optional[Path]:
        """
        导出模型到ONNX格式

        Args:
            model_path: 输入模型路径 (.pt)
            output_dir: 输出目录
            imgsz: 图像大小
            dynamic: 是否使用动态批处理
            simplify: 是否简化模型

        Returns:
            导出的ONNX文件路径，失败返回None
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{model_path.stem}.onnx"

            print(f"🔄 正在导出ONNX模型: {model_path.name} -> {output_path.name}")

            # 使用ultralytics导出
            from ultralytics import YOLO

            model = YOLO(str(model_path))

            # 导出参数
            export_kwargs = {
                "format": "onnx",
                "imgsz": imgsz,
                "dynamic": dynamic,
                "simplify": simplify,
                "opset": 12,
                "workspace": 4,
                "batch": 1 if not dynamic else None
            }

            # 移除None值
            export_kwargs = {k: v for k, v in export_kwargs.items() if v is not None}

            # 执行导出
            success = model.export(**export_kwargs)

            if success:
                # ultralytics导出到当前目录，我们需要移动文件
                exported_file = Path(f"{model_path.stem}.onnx")
                if exported_file.exists():
                    exported_file.rename(output_path)
                    print(f"✅ ONNX导出成功: {output_path}")
                    return output_path
                else:
                    # 检查其他可能的位置
                    for possible_file in Path(".").glob("*.onnx"):
                        if model_path.stem in possible_file.name:
                            possible_file.rename(output_path)
                            print(f"✅ ONNX导出成功 (找到文件): {output_path}")
                            return output_path

            print(f"❌ ONNX导出失败")
            return None

        except Exception as e:
            print(f"❌ ONNX导出异常: {e}")
            return None

    @staticmethod
    def export_to_tensorrt(model_path: Path, output_dir: Path,
                          imgsz: int = 640, workspace: int = 4,
                          fp16: bool = True) -> Optional[Path]:
        """
        导出模型到TensorRT格式

        Args:
            model_path: 输入模型路径 (.pt 或 .onnx)
            output_dir: 输出目录
            imgsz: 图像大小
            workspace: 工作空间大小 (GB)
            fp16: 是否使用FP16精度

        Returns:
            导出的TensorRT引擎文件路径，失败返回None
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            if model_path.suffix == '.pt':
                # 先导出到ONNX
                onnx_path = ModelExporter.export_to_onnx(
                    model_path, output_dir, imgsz=imgsz
                )
                if not onnx_path:
                    return None
                input_path = onnx_path
            else:
                input_path = model_path

            output_path = output_dir / f"{input_path.stem}.engine"

            print(f"🔄 正在导出TensorRT模型: {input_path.name} -> {output_path.name}")

            # 使用ultralytics导出到TensorRT
            from ultralytics import YOLO

            model = YOLO(str(model_path))

            export_kwargs = {
                "format": "engine",
                "imgsz": imgsz,
                "workspace": workspace,
                "half": fp16,
                "verbose": False
            }

            success = model.export(**export_kwargs)

            if success:
                # 查找导出的engine文件
                for possible_file in Path(".").glob("*.engine"):
                    if model_path.stem in possible_file.name:
                        possible_file.rename(output_path)
                        print(f"✅ TensorRT导出成功: {output_path}")
                        return output_path

            print(f"❌ TensorRT导出失败")
            return None

        except Exception as e:
            print(f"❌ TensorRT导出异常: {e}")
            return None

    @staticmethod
    def batch_export(models_dir: Path, output_dir: Path,
                    formats: List[str] = ["onnx", "engine"]) -> Dict[str, List[Path]]:
        """
        批量导出模型

        Args:
            models_dir: 模型目录
            output_dir: 输出目录
            formats: 导出格式列表

        Returns:
            导出的文件路径字典
        """
        results = {fmt: [] for fmt in formats}

        # 查找所有PyTorch模型
        pt_models = list(models_dir.glob("*.pt"))

        print(f"📦 批量导出 {len(pt_models)} 个模型到格式: {formats}")

        for model_path in pt_models:
            print(f"\n🔧 处理模型: {model_path.name}")

            if "onnx" in formats:
                onnx_path = ModelExporter.export_to_onnx(model_path, output_dir)
                if onnx_path:
                    results["onnx"].append(onnx_path)

            if "engine" in formats:
                engine_path = ModelExporter.export_to_tensorrt(model_path, output_dir)
                if engine_path:
                    results["engine"].append(engine_path)

        print(f"\n✅ 批量导出完成:")
        for fmt, files in results.items():
            print(f"   {fmt.upper()}: {len(files)} 个文件")

        return results

    @staticmethod
    def validate_exported_model(model_path: Path, test_image: Optional[Path] = None) -> bool:
        """
        验证导出的模型

        Args:
            model_path: 导出的模型路径
            test_image: 测试图像路径（可选）

        Returns:
            验证是否成功
        """
        try:
            from ultralytics import YOLO

            print(f"🔍 验证模型: {model_path.name}")

            # 加载模型
            model = YOLO(str(model_path))

            # 如果没有提供测试图像，创建虚拟图像
            if test_image is None or not test_image.exists():
                import numpy as np
                import tempfile

                # 创建临时测试图像
                dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                    import cv2
                    cv2.imwrite(f.name, dummy_image)
                    test_image = Path(f.name)

            # 执行推理测试
            results = model(test_image, verbose=False)

            # 清理临时文件
            if "temp" in str(test_image):
                test_image.unlink(missing_ok=True)

            if results and len(results) > 0:
                print(f"✅ 模型验证成功")
                return True
            else:
                print(f"❌ 模型验证失败: 无结果")
                return False

        except Exception as e:
            print(f"❌ 模型验证异常: {e}")
            return False