/**
 * SiteGuard AI 共享类型定义
 */

// ==================== 基础类型 ====================
export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

// ==================== 检测相关 ====================
export interface Detection {
  bbox: BoundingBox;
  confidence: number;
  classId: number;
  className: string;
}

export interface Risk {
  type: string;
  level: RiskLevel;
  message: string;
  detectionIds: number[];
  metadata?: Record<string, any>;
}

export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface DetectionResult {
  detections: Detection[];
  risks: Risk[];
  inferenceTime: number;
  imageInfo: Size;
  timestamp: string;
}

// ==================== 模型相关 ====================
export interface ModelInfo {
  name: string;
  displayName: string;
  type: ModelType;
  size: number;
  isCurrent: boolean;
  path?: string;
}

export enum ModelType {
  PYTORCH = 'pytorch',
  ONNX = 'onnx',
  TENSORRT = 'tensorrt'
}

export interface ModelStats {
  totalModels: number;
  pytorchModels: number;
  onnxModels: number;
  totalSizeMB: number;
}

// ==================== 输入源相关 ====================
export enum InputType {
  IMAGE = 'image',
  CAMERA = 'camera',
  RTSP = 'rtsp'
}

// ==================== API 请求/响应 ====================
export interface ImageDetectionRequest {
  image: File | Blob;
  modelName?: string;
  confidenceThreshold?: number;
}

export interface ImageDetectionResponse {
  success: boolean;
  detections: Detection[];
  risks: Risk[];
  inferenceTime: number;
  annotatedImageUrl: string;
  imageInfo: Size;
}

export interface CameraStreamConfig {
  cameraId: number;
  resolution: Size;
  frameRate: number;
  modelName?: string;
}

export interface CameraFrameResult {
  type: 'frame' | 'error';
  frame?: string; // base64 encoded
  detections?: Detection[];
  risks?: Risk[];
  inferenceTime?: number;
  timestamp: string;
}

// ==================== 规则引擎 ====================
export interface Rule {
  name: string;
  condition: string;
  level: RiskLevel;
  message: string;
  description?: string;
  actions?: string[];
  metadata?: Record<string, any>;
}

export interface RuleGroup {
  name: string;
  description: string;
  enabled: boolean;
  rules: string[];
}

// ==================== 系统状态 ====================
export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  components: {
    api: boolean;
    model: boolean;
    camera: boolean;
    storage: boolean;
  };
  metrics: {
    uptime: number;
    memoryUsage: number;
    cpuUsage: number;
    activeConnections: number;
  };
  timestamp: string;
}

export interface PerformanceStats {
  avgInferenceTime: number;
  avgFPS: number;
  avgDetections: number;
  totalPredictions: number;
  recentSampleSize: number;
}

// ==================== 配置相关 ====================
export interface AppConfig {
  maxUploadSize: number;
  allowedImageTypes: string[];
  defaultModel: string;
  confidenceThreshold: number;
  iouThreshold: number;
  maxDetections: number;
}

// ==================== 工具函数 ====================
export function formatBoundingBox(bbox: [number, number, number, number]): BoundingBox {
  return {
    x1: bbox[0],
    y1: bbox[1],
    x2: bbox[2],
    y2: bbox[3]
  };
}

export function formatSize(width: number, height: number): Size {
  return { width, height };
}

export function getRiskLevelColor(level: RiskLevel): string {
  const colors = {
    [RiskLevel.LOW]: '#909399',
    [RiskLevel.MEDIUM]: '#409EFF',
    [RiskLevel.HIGH]: '#E6A23C',
    [RiskLevel.CRITICAL]: '#F56C6C'
  };
  return colors[level] || '#909399';
}

export function getRiskLevelText(level: RiskLevel): string {
  const texts = {
    [RiskLevel.LOW]: '低风险',
    [RiskLevel.MEDIUM]: '中风险',
    [RiskLevel.HIGH]: '高风险',
    [RiskLevel.CRITICAL]: '严重风险'
  };
  return texts[level] || '未知风险';
}

// ==================== 常量 ====================
export const CONSTRUCTION_PPE_CLASSES = {
  0: 'helmet',
  1: 'gloves',
  2: 'vest',
  3: 'boots',
  4: 'goggles',
  5: 'none',
  6: 'Person',
  7: 'no_helmet',
  8: 'no_goggle',
  9: 'no_gloves',
  10: 'no_boots'
} as const;

export const DEFAULT_CONFIG: AppConfig = {
  maxUploadSize: 20 * 1024 * 1024, // 20MB
  allowedImageTypes: ['image/jpeg', 'image/png', 'image/jpg'],
  defaultModel: 'yolo26n_ppe.pt',
  confidenceThreshold: 0.5,
  iouThreshold: 0.5,
  maxDetections: 300
};