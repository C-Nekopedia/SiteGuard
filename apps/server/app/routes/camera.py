"""
摄像头相关路由
"""
import asyncio
import base64
import cv2
import numpy as np
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import JSONResponse

from ..services.detection_service import DetectionService
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

# 依赖函数：获取检测服务
def get_detection_service(request: Request) -> DetectionService:
    """从应用状态获取检测服务"""
    return request.app.state.detection_service

# 内部辅助函数：获取或创建连接管理器
def _get_or_create_connection_manager(app) -> "ConnectionManager":
    """从应用状态获取连接管理器，如果不存在则创建"""
    if not hasattr(app.state, 'camera_connection_manager'):
        app.state.camera_connection_manager = ConnectionManager(app.state.detection_service)
    return app.state.camera_connection_manager

# 依赖函数：获取或创建连接管理器（用于HTTP请求）
def get_connection_manager(request: Request) -> "ConnectionManager":
    """从应用状态获取连接管理器，如果不存在则创建"""
    return _get_or_create_connection_manager(request.app)

# 依赖函数：获取或创建连接管理器（用于WebSocket）
def get_connection_manager_for_websocket(websocket: WebSocket) -> "ConnectionManager":
    """从应用状态获取连接管理器，如果不存在则创建（WebSocket版本）"""
    return _get_or_create_connection_manager(websocket.app)

class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self, detection_service: DetectionService):
        self.detection_service = detection_service
        self.active_connections: List[WebSocket] = []
        self.camera_active = False
        self.camera_instance = None

    async def connect(self, websocket: WebSocket):
        """连接WebSocket"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开WebSocket"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket连接断开，剩余连接数: {len(self.active_connections)}")

        # 如果没有活跃连接，停止摄像头
        if not self.active_connections and self.camera_active:
            self.stop_camera()

    async def send_message(self, message: dict, websocket: WebSocket):
        """发送消息到指定WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")

    def start_camera(self, camera_id: int = 0):
        """启动摄像头

        Args:
            camera_id: 摄像头ID (0, 1, 2...)
        """
        try:
            if self.camera_active:
                logger.warning("摄像头已在运行中")
                return False

            # 打开物理摄像头
            self.camera_instance = cv2.VideoCapture(camera_id)
            if not self.camera_instance.isOpened():
                logger.error(f"无法打开摄像头: {camera_id}")
                return False

            self.camera_active = True
            self.test_mode = False
            logger.info(f"摄像头已启动 (ID: {camera_id})")
            return True

        except Exception as e:
            logger.error(f"启动摄像头失败: {e}")
            return False

    def stop_camera(self):
        """停止摄像头"""
        try:
            if self.camera_instance:
                self.camera_instance.release()
                self.camera_instance = None

            self.camera_active = False
            logger.info("摄像头已停止")

        except Exception as e:
            logger.error(f"停止摄像头失败: {e}")

    def read_frame(self):
        """读取摄像头帧"""
        if not self.camera_active or not self.camera_instance:
            return None

        ret, frame = self.camera_instance.read()
        if not ret:
            logger.error("读取摄像头帧失败")
            return None

        return frame

@router.websocket("/stream")
async def camera_stream(
    websocket: WebSocket,
    manager: ConnectionManager = Depends(get_connection_manager_for_websocket)
):
    """
    WebSocket摄像头流
    """
    await manager.connect(websocket)

    # 立即发送连接成功消息
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket连接成功",
            "timestamp": "2024-01-15T10:00:00Z"
        })
    except Exception as e:
        logger.error(f"发送连接成功消息失败: {e}")
        return

    try:
        # 启动摄像头
        if not manager.camera_active:
            if not manager.start_camera(camera_id=0):
                await websocket.send_json({
                    "type": "error",
                    "message": "无法启动摄像头"
                })
                return

        logger.info("开始摄像头流传输")

        # 主循环
        while True:
            # 读取帧
            frame = manager.read_frame()
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            # 调整大小以提高性能
            frame = cv2.resize(frame, (480, 360))

            # 执行检测
            try:
                detection_result = await manager.detection_service.process_camera_frame(frame)
            except Exception as e:
                logger.error(f"摄像头帧检测失败: {e}")
                detection_result = {
                    "success": False,
                    "error": str(e)
                }

            # 准备发送的数据
            frame_base64 = None  # 初始化变量
            if detection_result["success"]:
                # 将标注后的帧转换为base64
                annotated_bytes = detection_result.get("annotated_frame")
                if annotated_bytes:
                    # 解码标注图像
                    nparr = np.frombuffer(annotated_bytes, np.uint8)
                    annotated_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    # 转换为JPEG
                    _, buffer = cv2.imencode('.jpg', annotated_frame, [
                        cv2.IMWRITE_JPEG_QUALITY, 50
                    ])
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                else:
                    # 使用原始帧
                    _, buffer = cv2.imencode('.jpg', frame, [
                        cv2.IMWRITE_JPEG_QUALITY, 50
                    ])
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')

                message = {
                    "type": "frame",
                    "frame": frame_base64,
                    "detections": detection_result["detections"],
                    "risks": detection_result["risks"],
                    "inference_time": detection_result["inference_time"],
                    "timestamp": "2024-01-15T10:00:00Z"
                }
            else:
                message = {
                    "type": "error",
                    "message": detection_result.get("error", "检测失败")
                }
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"发送WebSocket数据失败: {e}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                break

    except WebSocketDisconnect:
        logger.info("📡 WebSocket连接断开")
    except Exception as e:
        logger.error(f"摄像头流异常: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"摄像头流异常: {str(e)}"
        })
    finally:
        manager.disconnect(websocket)

@router.get("/status")
async def camera_status(manager: ConnectionManager = Depends(get_connection_manager)):
    """获取摄像头状态"""
    return {
        "camera_active": manager.camera_active,
        "active_connections": len(manager.active_connections),
        "timestamp": "2024-01-15T10:00:00Z"
    }

@router.post("/start")
async def start_camera(
    camera_id: int = 0,
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """启动摄像头"""
    try:
        if manager.start_camera(camera_id):
            return {
                "success": True,
                "message": f"摄像头已启动 (ID: {camera_id})",
                "camera_id": camera_id
            }
        else:
            return {
                "success": False,
                "message": f"无法启动摄像头 (ID: {camera_id})"
            }
    except Exception as e:
        logger.error(f"启动摄像头API失败: {e}")
        return {
            "success": False,
            "message": f"启动摄像头失败: {str(e)}"
        }

@router.post("/stop")
async def stop_camera(manager: ConnectionManager = Depends(get_connection_manager)):
    """停止摄像头"""
    try:
        manager.stop_camera()
        return {
            "success": True,
            "message": "摄像头已停止"
        }
    except Exception as e:
        logger.error(f"停止摄像头API失败: {e}")
        return {
            "success": False,
            "message": f"停止摄像头失败: {str(e)}"
        }