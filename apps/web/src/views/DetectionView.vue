<template>
  <div class="detection-container">
    <!-- 左侧导航 -->
    <nav class="sidebar">
      <div class="logo-area">
        <div class="logo-dot"></div>
        <span>SiteGuard</span>
      </div>

      <div class="menu-item active">
        <span>Monitor</span>
      </div>
    </nav>

    <!-- 主内容区 -->
    <div class="main-container">
      <!-- 顶部标题和输入源切换 -->
      <header class="main-header">
        <h1>Monitor</h1>
        <div class="source-tabs">
          <button class="tab" :class="{ active: activeInputType === 'camera' }" @click="switchInputType('camera')">
            摄像头
          </button>
          <button class="tab" :class="{ active: activeInputType === 'image' }" @click="switchInputType('image')">
            本地图片
          </button>
        </div>
      </header>

      <!-- 核心监测展示区 -->
      <div class="main-display">
        <!-- 左侧：检测可视化区域 -->
        <div class="display-card viewer-panel">
          <div class="viewer-area">
            <!-- 图片上传区域 -->
            <div v-if="activeInputType === 'image' && !currentImageUrl" class="upload-placeholder"
              @click="triggerImageUpload" @dragover.prevent="handleDragOver" @drop.prevent="handleImageDrop">
              <div class="upload-icon">
                <el-icon>
                  <FolderOpened />
                </el-icon>
              </div>
              <p style="margin: 0; font-weight: 600;">点击或将图片拖拽至此处</p>
              <p style="margin: 4px 0 0; font-size: 0.8rem;">支持 JPG, PNG 格式进行单张识别</p>
              <input ref="imageInput" type="file" accept="image/*" @change="handleImageUpload" style="display: none" />
            </div>

            <!-- 摄像头区域 -->
            <div v-if="activeInputType === 'camera'" class="camera-placeholder">
              <div v-if="!isCameraActive" class="camera-prompt">
                <div class="upload-icon">
                  <el-icon>
                    <VideoCamera />
                  </el-icon>
                </div>
                <p style="margin: 0; font-weight: 600;">摄像头未启动</p>
                <p style="margin: 4px 0 0; font-size: 0.8rem;">使用按钮启动实时摄像头检测</p>
              </div>
              <div v-else class="camera-active">
                <div class="camera-status">
                  <el-tag type="success" size="small">摄像头运行中</el-tag>
                  <p>实时帧率: {{ fps }} FPS</p>
                </div>
                <!-- 摄像头视频流显示区域 -->
                <div v-if="cameraStreamUrl" class="camera-stream-container">
                  <img :src="cameraStreamUrl" alt="摄像头实时画面" class="camera-stream-image" />
                </div>
                <div v-else class="camera-placeholder-image">
                  <div class="upload-icon">
                    <el-icon>
                      <VideoCamera />
                    </el-icon>
                  </div>
                  <p style="margin: 4px 0 0; font-size: 0.8rem;">正在连接摄像头流...</p>
                </div>
              </div>
            </div>

            <!-- 检测结果显示 -->
            <div v-if="activeInputType === 'image' && currentImageUrl" class="detection-result">
              <img :src="currentImageUrl" alt="检测结果" class="result-image" />
            </div>

            <!-- 检测中状态 -->
            <div v-if="detectionLoading" class="detection-loading">
              <el-icon class="loading-icon">
                <Loading />
              </el-icon>
              <p>正在检测中...</p>
            </div>
          </div>

          <!-- 底部操作栏 -->
          <div class="viewer-controls">
            <div class="model-info">
              当前权重:
              <span class="model-name">
                {{ selectedModelLabel || 'yolo26n_ppe.pt' }}
              </span>
            </div>
            <div class="control-buttons">
              <!-- 摄像头模式 -->
              <template v-if="activeInputType === 'camera'">
                <button class="btn btn-secondary" @click="toggleCamera" :disabled="cameraLoading || !isCameraActive">
                  关闭摄像头
                </button>
                <button class="btn btn-primary" @click="toggleCamera" :disabled="cameraLoading || isCameraActive"
                  v-loading="cameraLoading">
                  {{ cameraLoading ? '启动中...' : '启用摄像头' }}
                </button>
              </template>
              <!-- 图片和视频模式 -->
              <template v-else>
                <button class="btn btn-secondary" @click="clearResult" :disabled="!currentImageUrl && !detectionLoading">
                  清除结果
                </button>
                <button class="btn btn-primary" @click="startDetection" :disabled="detectionLoading || !canStartDetection"
                  v-loading="detectionLoading">
                  {{ detectionLoading ? '检测中...' : '开始检测' }}
                </button>
              </template>
            </div>
          </div>
        </div>

        <!-- 右侧：实时检测日志 -->
        <div class="alert-panel">
          <div class="alert-header">
            <span>{{ activeInputType === 'camera' ? '实时状态' : '检测日志' }}</span>
            <button v-if="activeInputType !== 'camera'" class="btn-clear-logs" @click="clearLogs" :disabled="detectionHistory.length === 0">
              清理日志
            </button>
          </div>
          <div class="alert-list">
            <!-- 摄像头模式：实时状态概览 -->
            <template v-if="activeInputType === 'camera'">
              <div v-if="!isCameraActive" class="empty-alerts">
                <p>摄像头未启动</p>
                <p class="hint">使用按钮启动实时检测</p>
              </div>
              <div v-else class="camera-status-summary">
                <div class="summary-row">
                  <span class="summary-label">人员</span>
                  <span class="summary-value">{{ cameraSummary.person }}</span>
                </div>
                <div class="summary-row" v-for="risk in activeRisks" :key="risk.type">
                  <span class="summary-label">{{ risk.message }}</span>
                  <span class="summary-value summary-risk">{{ risk.count }}</span>
                </div>
                <div class="summary-row" v-if="activeRisks.length === 0">
                  <span class="summary-label summary-safe">所有人员防护到位</span>
                </div>
              </div>
            </template>

            <!-- 图片模式：检测记录列表 -->
            <template v-else>
              <div v-if="detectionHistory.length === 0" class="empty-alerts">
                <p>暂无检测记录</p>
                <p class="hint">上传图片开始检测</p>
              </div>
              <div v-for="(item, index) in detectionHistory" :key="index" class="alert-item">
                <div class="status-dot" :style="{
                  background: item.riskLevel === 'high' ? 'var(--danger)' :
                    item.riskLevel === 'critical' ? 'var(--danger)' : 'var(--success)'
                }"></div>
                <div class="alert-content">
                  <div class="alert-title">
                    {{ item.message }}
                    <button class="btn-expand" @click.stop="toggleExpand(index)">
                      {{ item.expanded ? '收起' : '展开' }}
                    </button>
                  </div>
                  <div class="alert-details">
                    <span class="source">来源: {{ item.source }}</span>
                    <span class="time">{{ item.timestamp }}</span>
                  </div>
                  <div v-if="item.expanded && (item.detections?.length > 0 || item.risks?.length > 0)" class="detection-details">
                    <div v-if="item.detections?.length > 0" class="detection-section">
                      <h4>检测到的对象 ({{ item.detections.length }}个):</h4>
                      <div class="detection-list">
                        <div v-for="(det, detIndex) in sortDetections(item.detections)" :key="detIndex" class="detection-item">
                          <span class="detection-class" :style="{ color: classColors[det.class] || '#94A3B8' }">
                            {{ classLabels[det.class] || det.class }}
                          </span>
                          <span class="detection-confidence">{{ (det.confidence * 100).toFixed(0) }}%</span>
                          <span class="detection-bbox">[{{ det.bbox.map((c: number) => c.toFixed(1)).join(', ') }}]</span>
                        </div>
                      </div>
                    </div>
                    <div v-if="item.risks?.length > 0" class="risk-section">
                      <h4>风险告警 ({{ item.risks.length }}个):</h4>
                      <div class="risk-list">
                        <div v-for="(risk, riskIndex) in item.risks" :key="riskIndex" class="risk-item">
                          <span class="risk-level" :style="{ color: risk.level === 'critical' ? '#DC2626' : risk.level === 'high' ? '#EF4444' : '#F59E0B' }">
                            {{ risk.level === 'critical' ? '严重' : risk.level === 'high' ? '高危' : '中危' }}
                          </span>
                          <span class="risk-message">{{ risk.message }}</span>
                          <span v-if="risk.count" class="risk-count">数量: {{ risk.count }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 性能统计 -->
      <div class="performance-stats">
        <div class="stat-item">
          <span class="stat-label">推理延迟:</span>
          <span class="stat-value">{{ inferenceLatency }}ms</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">检测数量:</span>
          <span class="stat-value">{{ detectionCount }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">风险告警:</span>
          <span class="stat-value" :style="{ color: activeRisks.length > 0 ? 'var(--danger)' : 'var(--success)' }">
            {{ activeRisks.length }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import {
  VideoCamera,
  FolderOpened,
  Loading
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// API基础URL，通过环境变量配置
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// 状态定义
const activeInputType = ref('image')
const selectedModel = ref('yolo26n_ppe')
const currentImageUrl = ref('')
const currentImageFile = ref<File | null>(null)
const detections = ref<any[]>([])
const activeRisks = ref<any[]>([])
const inferenceLatency = ref(0)
const fps = ref(0)
const detectionCount = ref(0)
const isCameraActive = ref(false)
const cameraLoading = ref(false)
const detectionLoading = ref(false)
const availableModels = ref<any[]>([])

// 分离图片检测日志
const imageLogs = ref<any[]>([])
const cameraLogs = ref<any[]>([])
const detectionHistory = computed(() => imageLogs.value)

// 摄像头流相关状态
const cameraStreamUrl = ref<string>('')
const cameraWebSocket = ref<WebSocket | null>(null)
const lastFrameTime = ref<number>(0)
const frameTimes = ref<number[]>([])

// Refs
const imageInput = ref<HTMLInputElement>()

// API配置
const API_BASE = '/api/v1'

// 计算属性
const selectedModelLabel = computed(() => {
  const model = availableModels.value.find((m: any) => m.name === selectedModel.value)
  return model?.display_name || selectedModel.value || 'yolo26n_ppe.pt'
})

const canStartDetection = computed(() => {
  if (detectionLoading.value) return false
  if (activeInputType.value === 'image' && currentImageUrl.value) return true
  // 摄像头实时检测自动进行，不需要手动开始
  if (activeInputType.value === 'camera') return false
  return false
})

// 摄像头实时状态摘要
const cameraSummary = computed(() => {
  const summary: Record<string, number> = { person: 0 }
  for (const det of detections.value) {
    const cls = (det.class || '').toLowerCase()
    if (cls === 'person') summary.person++
  }
  return summary
})

// 颜色映射：无危险（有防护）为绿色，有危险（无防护）为红色
const classColors: Record<string, string> = {
  person: '#94A3B8',      // 中性色
  helmet: '#10B981',      // 绿色：有安全帽
  no_helmet: '#EF4444',   // 红色：无安全帽
  vest: '#10B981',        // 绿色：有反光衣
  no_vest: '#EF4444',     // 红色：无反光衣
  none: '#EF4444',        // 红色：无防护
  gloves: '#10B981',      // 绿色：有手套
  no_gloves: '#EF4444',   // 红色：无手套
  boots: '#10B981',       // 绿色：有安全靴
  no_boots: '#EF4444',    // 红色：无安全靴
  goggles: '#10B981',     // 绿色：有护目镜
  no_goggle: '#EF4444'    // 红色：无护目镜
}

const classLabels: Record<string, string> = {
  person: '人员',
  helmet: '安全帽',
  no_helmet: '未戴安全帽',
  vest: '反光衣',
  no_vest: '未穿反光衣',
  none: '无防护',
  gloves: '手套',
  no_gloves: '未戴手套',
  boots: '安全靴',
  no_boots: '未穿安全靴',
  goggles: '护目镜',
  no_goggle: '未戴护目镜'
}

// 方法
const switchInputType = (type: string) => {
  // 清除当前内容并撤销URL
  if (activeInputType.value === 'image' && currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
    currentImageUrl.value = ''
    currentImageFile.value = null
  }

  activeInputType.value = type
  // 停止摄像头如果切换到其他输入源
  if (type !== 'camera' && isCameraActive.value) {
    toggleCamera()
  }
}

const triggerImageUpload = () => {
  imageInput.value?.click()
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'copy'
}

const handleImageDrop = async (event: DragEvent) => {
  event.preventDefault()
  const files = event.dataTransfer?.files
  if (!files || files.length === 0) return

  const file = files[0]
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请上传图片文件')
    return
  }

  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 20MB')
    return
  }

  // 撤销之前的URL
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }
  currentImageUrl.value = URL.createObjectURL(file)
  currentImageFile.value = file
  ElMessage.success('图片已加载，点击"开始检测"进行分析')
}

const handleImageUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return

  const file = input.files[0]
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 20MB')
    return
  }

  // 撤销之前的URL
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }
  // 创建临时URL用于预览并保存文件对象
  currentImageUrl.value = URL.createObjectURL(file)
  currentImageFile.value = file
  ElMessage.success('图片已加载，点击"开始检测"进行分析')
}

const toggleCamera = () => {
  if (isCameraActive.value) {
    disconnectCameraWebSocket()
    isCameraActive.value = false
    cameraStreamUrl.value = ''
    fps.value = 0
    frameTimes.value = []
    ElMessage.success('摄像头已停止')
  } else {
    cameraLoading.value = true
    connectCameraWebSocket()
  }
}

const connectCameraWebSocket = () => {
  try {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/camera/stream`

    cameraWebSocket.value = new WebSocket(wsUrl)

    cameraWebSocket.value.onopen = () => {
      cameraLoading.value = false
      isCameraActive.value = true
      lastFrameTime.value = Date.now()
      ElMessage.success('摄像头连接成功')
    }

    cameraWebSocket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        // 确保摄像头状态已激活
        if (cameraLoading.value) {
          cameraLoading.value = false
        }
        if (!isCameraActive.value) {
          isCameraActive.value = true
        }

        if (data.type === 'connected') {
          ElMessage.success('摄像头连接已就绪')
        } else if (data.type === 'frame') {
          // 更新摄像头流URL
          cameraStreamUrl.value = `data:image/jpeg;base64,${data.frame}`

          // 更新检测结果
          if (data.detections) {
            detections.value = data.detections
            activeRisks.value = data.risks || []
            inferenceLatency.value = data.inference_time || 0
            detectionCount.value = detections.value.length
          }

          // 计算FPS
          const now = Date.now()
          const frameTime = now - lastFrameTime.value
          lastFrameTime.value = now

          frameTimes.value.push(frameTime)
          if (frameTimes.value.length > 30) {
            frameTimes.value.shift()
          }

          const avgFrameTime = frameTimes.value.reduce((sum, time) => sum + time, 0) / frameTimes.value.length
          fps.value = frameTimes.value.length > 0 ? Math.round(1000 / avgFrameTime) : 0
        } else if (data.type === 'error') {
          ElMessage.error(`摄像头错误: ${data.message}`)
        }
      } catch (error) {
        console.error('解析摄像头数据失败:', error)
      }
    }

    cameraWebSocket.value.onerror = (error) => {
      console.error('摄像头WebSocket错误:', error)
      cameraLoading.value = false
      ElMessage.error('摄像头连接失败，请检查后端服务')
    }

    cameraWebSocket.value.onclose = () => {
      if (isCameraActive.value) {
        ElMessage.warning('摄像头连接已断开')
        isCameraActive.value = false
        cameraStreamUrl.value = ''
      }
    }

    // 设置超时（增加到15秒，因为摄像头启动和模型加载需要时间）
    setTimeout(() => {
      if (cameraLoading.value && !isCameraActive.value) {
        cameraLoading.value = false
        if (cameraWebSocket.value) {
          cameraWebSocket.value.close()
        }
        ElMessage.error('摄像头连接超时（15秒）')
      }
    }, 15000)

  } catch (error) {
    console.error('启动摄像头失败:', error)
    cameraLoading.value = false
    ElMessage.error('启动摄像头失败: ' + error)
  }
}

const disconnectCameraWebSocket = () => {
  if (cameraWebSocket.value) {
    cameraWebSocket.value.close()
    cameraWebSocket.value = null
  }
}

const startDetection = async () => {
  if (!canStartDetection.value) return

  detectionLoading.value = true

  try {
    if (activeInputType.value === 'image') {
      await detectImage()
    }
  } catch (error) {
    ElMessage.error(`检测失败: ${error}`)
  } finally {
    detectionLoading.value = false
  }
}

const detectImage = async () => {
  try {
    // 获取图片文件
    const file = currentImageFile.value
    if (!file) {
      ElMessage.error('请先选择图片文件')
      return
    }
    const formData = new FormData()
    formData.append('file', file)

    const response = await axios.post(`${API_BASE}/detection/image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    if (response.data.success) {
      const result = response.data
      detections.value = result.detections || []
      activeRisks.value = result.risks || []
      inferenceLatency.value = result.inference_time || 0
      detectionCount.value = detections.value.length

      // 更新检测历史（图片模式）
      imageLogs.value.unshift({
        timestamp: new Date().toLocaleTimeString(),
        source: file.name,
        message: activeRisks.value.length > 0 ? '检测到风险' : '检测完成',
        riskLevel: activeRisks.value.length > 0 ? 'high' : 'success',
        detections: [...detections.value],
        risks: [...activeRisks.value],
        expanded: false
      })
      if (imageLogs.value.length > 10) {
        imageLogs.value = imageLogs.value.slice(0, 10)
      }

      // 更新标注图片URL - 后端始终返回标注图片
      const annotatedUrl = result.annotated_image_url
        ? (result.annotated_image_url.startsWith('http')
            ? result.annotated_image_url
            : `${API_BASE_URL}${result.annotated_image_url}`)
        : `${API_BASE_URL}/static/temp/annotated_${Date.now()}.jpg`

      // 撤销之前的对象URL（如果是blob URL）
      if (currentImageUrl.value && currentImageUrl.value.startsWith('blob:')) {
        URL.revokeObjectURL(currentImageUrl.value)
      }

      currentImageUrl.value = annotatedUrl

      ElMessage.success('图片检测完成')
    } else {
      ElMessage.error('检测失败: ' + (response.data.detail || '未知错误'))
    }
  } catch (error: any) {
    console.error('检测失败:', error)
    ElMessage.error(`检测失败: ${error.response?.data?.detail || error.message}`)
  }
}

const clearResult = () => {
  // 撤销对象URL以释放内存
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }

  currentImageUrl.value = ''
  currentImageFile.value = null
  detections.value = []
  activeRisks.value = []
  detectionCount.value = 0
  inferenceLatency.value = 0
  ElMessage.info('已清除检测结果')
}

const clearLogs = () => {
  if (activeInputType.value === 'camera') {
    cameraLogs.value = []
  } else {
    imageLogs.value = []
  }
  ElMessage.success('已清空检测日志')
}

const toggleExpand = (index: number) => {
  detectionHistory.value[index].expanded = !detectionHistory.value[index].expanded
}

const sortDetections = (detections: any[]) => {
  if (!detections || detections.length === 0) return []
  return [...detections].sort((a, b) => {
    // person排在最前面
    if (a.class === 'person' && b.class !== 'person') return -1
    if (a.class !== 'person' && b.class === 'person') return 1
    // 其他保持原顺序
    return 0
  })
}


const loadModels = async () => {
  try {
    const response = await axios.get(`${API_BASE}/models/list`)
    if (response.data.success && response.data.models) {
      availableModels.value = response.data.models
      // 设置默认选中模型
      if (response.data.current_model && availableModels.value.length > 0) {
        selectedModel.value = response.data.current_model
      }
    }
  } catch (error) {
    console.error('加载模型列表失败:', error)
    // 使用模拟数据作为后备
    availableModels.value = [
      { name: 'yolo26n_ppe.pt', display_name: 'YOLO26n-PPE (默认)' },
      { name: 'yolo26s_ppe.pt', display_name: 'YOLO26s-PPE' },
      { name: 'yolo26m_ppe.pt', display_name: 'YOLO26m-PPE' }
    ]
  }
}

// 生命周期
onMounted(async () => {
  await loadModels()
})

onUnmounted(() => {
  // 清理资源
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }
  // 清理摄像头资源
  disconnectCameraWebSocket()
})
</script>

<style>
:root {
  --brand-color: #4F46E5;
  --bg-main: #F8FAFC;
  --card-bg: #FFFFFF;
  --text-title: #1E293B;
  --text-body: #64748B;
  --danger: #EF4444;
  --success: #10B981;
  --warning: #F59E0B;
  --border: #CBD5E1;
  --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
}

html, body {
  height: 100%;
  margin: 0;
  padding: 0;
}

* {
  box-sizing: border-box;
}
</style>

<style scoped>
.detection-container * {
  transition: all 0.2s ease;
}

.detection-container {
  margin: 0;
  font-family: 'Inter', -apple-system, sans-serif;
  background-color: var(--bg-main);
  color: var(--text-body);
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* 侧边导航 */
.sidebar {
  width: 260px;
  background: var(--card-bg);
  border-right: 1.5px solid var(--border);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 48px;
}

.logo-dot {
  width: 12px;
  height: 12px;
  background: var(--brand-color);
  border-radius: 50%;
}

.menu-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.95rem;
  color: var(--text-body);
  transition: all 0.2s ease;
}

.menu-item:hover {
  background: #F1F5F9;
}

.menu-item.active {
  background: #EEF2FF;
  color: var(--brand-color);
  font-weight: 600;
}

.menu-item .el-icon {
  font-size: 1.1rem;
}

/* 主内容区 */
.main-container {
  flex: 1;
  padding: 32px 40px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: hidden;
}

.main-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.main-header h1 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-title);
  font-weight: 600;
}

/* 输入源切换 Tab */
.source-tabs {
  display: flex;
  background: #F1F5F9;
  padding: 4px;
  border-radius: 10px;
  gap: 4px;
}

.tab {
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 0.875rem;
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--text-body);
  font-weight: 500;
}

.tab:hover {
  background: rgba(255, 255, 255, 0.5);
}

.tab.active {
  background: var(--card-bg);
  color: var(--brand-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  font-weight: 600;
}

/* 核心监测展示区 */
.main-display {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  grid-template-rows: 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

/* 显示面板 */
.display-card,
.viewer-panel {
  background: var(--card-bg);
  border-radius: 20px;
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 0;
}

.viewer-area {
  flex: 1;
  background: #0F172A;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  overflow: hidden;
}

/* 上传占位样式 */
.upload-placeholder {
  text-align: center;
  color: #94A3B8;
  padding: 40px;
  border: 2px dashed #334155;
  border-radius: 12px;
  cursor: pointer;
  width: 80%;
  max-width: 500px;
}

.upload-placeholder:hover {
  border-color: var(--brand-color);
  color: #CBD5E1;
}

.upload-icon {
  font-size: 2.5rem;
  margin-bottom: 12px;
  display: block;
  color: #94A3B8;
}

.upload-icon .el-icon {
  font-size: 2.5rem;
}

.camera-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-prompt {
  text-align: center;
  color: #94A3B8;
}

.camera-active {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.camera-status {
  position: absolute;
  top: 20px;
  left: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(0, 0, 0, 0.7);
  padding: 8px 12px;
  border-radius: 8px;
  color: white;
  font-size: 0.8rem;
  z-index: 10;
}

.camera-stream-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-stream-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 8px;
  background: #000;
}

.camera-placeholder-image {
  text-align: center;
  color: #94A3B8;
  padding: 40px;
}

/* 检测结果显示 */
.detection-result {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}


/* 检测中状态 */
.detection-loading {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.9);
  color: #94A3B8;
  z-index: 10;
}

.loading-icon {
  font-size: 3rem;
  margin-bottom: 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

/* 底部操作栏 */
.viewer-controls {
  padding: 16px 24px;
  background: var(--card-bg);
  border-top: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-info {
  font-size: 0.875rem;
  color: var(--text-body);
}

.model-name {
  font-weight: 600;
  color: var(--brand-color);
}

.control-buttons {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: white;
  color: var(--text-body);
  border: 1.5px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.btn-primary {
  background: var(--brand-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #4338CA;
}

/* 告警面板 */
.alert-panel {
  background: var(--card-bg);
  border-radius: 20px;
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.alert-header {
  padding: 20px;
  border-bottom: 1.5px solid var(--border);
  font-weight: 700;
  color: var(--text-title);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 摄像头实时状态摘要 */
.camera-status-summary {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-label {
  font-size: 0.9rem;
  color: var(--text-body);
}

.summary-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text-title);
}

.summary-risk {
  color: var(--danger);
}

.summary-safe {
  color: var(--success);
  font-weight: 500;
}

.summary-meta .summary-value {
  font-size: 0.9rem;
  font-weight: 600;
}

.btn-clear-logs {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  border: 1.5px solid var(--border);
  background: var(--card-bg);
  color: var(--text-body);
  transition: all 0.2s ease;
}

.btn-clear-logs:hover:not(:disabled) {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.btn-clear-logs:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.alert-list {
  flex: 1;
  overflow-y: auto;
}

.empty-alerts {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-body);
}

.empty-alerts .hint {
  font-size: 0.875rem;
  color: #94A3B8;
  margin-top: 8px;
}

.alert-item {
  padding: 16px 20px;
  border-bottom: 1.5px solid var(--border);
  display: flex;
  gap: 12px;
  transition: background-color 0.2s ease;
}

.alert-item:hover {
  background: #F8FAFC;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
}

.alert-title {
  color: var(--text-title);
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 4px;
}


.alert-details {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--text-body);
}

.alert-details .source {
  color: #94A3B8;
}

.alert-details .time {
  color: #64748B;
}

.btn-expand {
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-body);
  transition: all 0.2s ease;
}

.btn-expand:hover {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.detection-details {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: #F8FAFC;
  border: 1px solid var(--border);
}

.detection-section h4,
.risk-section h4 {
  margin: 0 0 8px 0;
  font-size: 0.85rem;
  color: var(--text-title);
  font-weight: 600;
}

.detection-list,
.risk-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detection-item,
.risk-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.8rem;
  padding: 4px 0;
}

.detection-class {
  font-weight: 600;
  min-width: 80px;
}

.detection-confidence {
  color: var(--text-body);
  min-width: 40px;
}

.detection-bbox {
  color: #94A3B8;
  font-family: monospace;
  font-size: 0.75rem;
}

.risk-level {
  font-weight: 600;
  min-width: 40px;
}

.risk-message {
  flex: 1;
  color: var(--text-title);
}

.risk-count {
  color: var(--text-body);
  font-size: 0.75rem;
}

/* 性能统计 */
.performance-stats {
  padding: 16px 24px;
  background: var(--card-bg);
  border-radius: 12px;
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  margin-top: 24px;
  display: flex;
  justify-content: space-around;
  align-items: center;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 0.875rem;
  color: var(--text-body);
}

.stat-value {
  font-weight: 600;
  color: var(--text-title);
  font-size: 0.875rem;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .main-display {
    grid-template-columns: 1fr;
  }

  .sidebar {
    width: 200px;
    padding: 24px 16px;
  }
}

@media (max-width: 768px) {
  .detection-container {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    flex-direction: row;
    padding: 16px;
    border-right: none;
    border-bottom: 1.5px solid var(--border);
  }

  .logo-area {
    margin-bottom: 0;
    margin-right: auto;
  }

  .menu-item {
    margin-bottom: 0;
    margin-right: 8px;
  }

  .main-container {
    padding: 20px;
  }

  .main-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  .source-tabs {
    justify-content: center;
  }
}
</style>
