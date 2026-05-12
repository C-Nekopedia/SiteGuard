"""
Camera routes
"""
import asyncio
import base64
import traceback
import cv2
import numpy as np
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Depends
from websockets.exceptions import ConnectionClosedOK

from ..core.config import settings
from ..services.detection_service import DetectionService
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()

# Dependency: get detection service
def get_detection_service(request: Request) -> DetectionService:
    """Get detection service from app state"""
    return request.app.state.detection_service

# Internal helper: get or create connection manager
def _get_or_create_connection_manager(app) -> "ConnectionManager":
    """Get connection manager from app state, creating if needed"""
    if not hasattr(app.state, 'camera_connection_manager'):
        app.state.camera_connection_manager = ConnectionManager(app.state.detection_service)
    return app.state.camera_connection_manager

# Dependency: get or create connection manager (for HTTP requests)
def get_connection_manager(request: Request) -> "ConnectionManager":
    """Get connection manager from app state, creating if needed"""
    return _get_or_create_connection_manager(request.app)

# Dependency: get or create connection manager (for WebSocket)
def get_connection_manager_for_websocket(websocket: WebSocket) -> "ConnectionManager":
    """Get connection manager from app state, creating if needed (WebSocket version)"""
    return _get_or_create_connection_manager(websocket.app)

class ConnectionManager:
    """WebSocket connection manager"""

    def __init__(self, detection_service: DetectionService):
        self.detection_service = detection_service
        self.active_connections: List[WebSocket] = []
        self.camera_active = False
        self.camera_instance = None

    async def connect(self, websocket: WebSocket):
        """Connect WebSocket"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected, active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Disconnect WebSocket"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected, remaining connections: {len(self.active_connections)}")

        # Stop camera if no active connections
        if not self.active_connections and self.camera_active:
            self.stop_camera()

    async def send_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connections"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast message failed: {e}")

    def start_camera(self, camera_id: int = 0):
        """Start camera

        Args:
            camera_id: Camera ID (0, 1, 2...)
        """
        try:
            if self.camera_active:
                logger.warning("Camera is already running")
                return False

            # Open physical camera
            self.camera_instance = cv2.VideoCapture(camera_id)
            if not self.camera_instance.isOpened():
                logger.error(f"Cannot open camera: {camera_id}")
                return False

            self.camera_active = True
            logger.info(f"Camera started (ID: {camera_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to start camera: {e}")
            return False

    def stop_camera(self):
        """Stop camera"""
        try:
            if self.camera_instance:
                self.camera_instance.release()
                self.camera_instance = None

            self.camera_active = False
            logger.info("Camera stopped")

        except Exception as e:
            logger.error(f"Failed to stop camera: {e}")

    def read_frame(self):
        """Read camera frame"""
        if not self.camera_active or not self.camera_instance:
            return None

        ret, frame = self.camera_instance.read()
        if not ret:
            logger.error("Failed to read camera frame")
            return None

        return frame

@router.websocket("/stream")
async def camera_stream(
    websocket: WebSocket,
    manager: ConnectionManager = Depends(get_connection_manager_for_websocket)
):
    """
    WebSocket camera stream
    """
    await manager.connect(websocket)

    loop = asyncio.get_event_loop()

    # Send connection success message immediately
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to send connection success message: {e}")
        return

    try:
        # Start camera
        if not manager.camera_active:
            if not manager.start_camera(camera_id=0):
                await websocket.send_json({
                    "type": "error",
                    "message": "Cannot start camera"
                })
                return

        logger.info("Camera stream transmission started")

        # Main loop
        while True:
            # Non-blocking frame read (cv2.VideoCapture.read() is blocking, use executor to avoid event loop deadlock)
            frame = await loop.run_in_executor(None, manager.read_frame)
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            # Check client disconnected each frame
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.001)
            except asyncio.TimeoutError:
                pass  # No message, continue normally
            except WebSocketDisconnect:
                raise

            # Resize for performance
            frame = cv2.resize(frame, (settings.CAMERA_FRAME_WIDTH, settings.CAMERA_FRAME_HEIGHT))

            # Run detection
            try:
                detection_result = await manager.detection_service.process_camera_frame(frame)
            except Exception as e:
                logger.error(f"Camera frame detection failed: {e}")
                detection_result = {
                    "success": False,
                    "error": str(e)
                }

            # Prepare data to send
            frame_base64 = None  # Initialize variable
            if detection_result["success"]:
                # Convert annotated frame to base64
                annotated_bytes = detection_result.get("annotated_frame")
                if annotated_bytes:
                    # Decode annotated image
                    nparr = np.frombuffer(annotated_bytes, np.uint8)
                    annotated_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    # Convert to JPEG
                    _, buffer = cv2.imencode('.jpg', annotated_frame, [
                        cv2.IMWRITE_JPEG_QUALITY, settings.CAMERA_JPEG_QUALITY
                    ])
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')
                else:
                    # Use raw frame
                    _, buffer = cv2.imencode('.jpg', frame, [
                        cv2.IMWRITE_JPEG_QUALITY, settings.CAMERA_JPEG_QUALITY
                    ])
                    frame_base64 = base64.b64encode(buffer).decode('utf-8')

                message = {
                    "type": "frame",
                    "frame": frame_base64,
                    "detections": detection_result["detections"],
                    "risks": detection_result["risks"],
                    "inference_time": detection_result["inference_time"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                message = {
                    "type": "error",
                    "message": detection_result.get("error", "Detection failed")
                }
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, ConnectionClosedOK):
                raise
            except Exception as e:
                logger.error(f"Failed to send WebSocket data: {e}")
                logger.error(f"Error details: {traceback.format_exc()}")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Camera stream error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Camera stream error: {str(e)}"
        })
    finally:
        manager.disconnect(websocket)

@router.get("/status")
async def camera_status(manager: ConnectionManager = Depends(get_connection_manager)):
    """Get camera status"""
    return {
        "camera_active": manager.camera_active,
        "active_connections": len(manager.active_connections),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/start")
async def start_camera(
    camera_id: int = 0,
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """Start camera"""
    try:
        if manager.start_camera(camera_id):
            return {
                "success": True,
                "message": f"Camera started (ID: {camera_id})",
                "camera_id": camera_id
            }
        else:
            return {
                "success": False,
                "message": f"Cannot start camera (ID: {camera_id})"
            }
    except Exception as e:
        logger.error(f"Start camera API failed: {e}")
        return {
            "success": False,
            "message": f"Failed to start camera: {str(e)}"
        }

@router.post("/stop")
async def stop_camera(manager: ConnectionManager = Depends(get_connection_manager)):
    """Stop camera"""
    try:
        manager.stop_camera()
        return {
            "success": True,
            "message": "Camera stopped"
        }
    except Exception as e:
        logger.error(f"Stop camera API failed: {e}")
        return {
            "success": False,
            "message": f"Failed to stop camera: {str(e)}"
        }
