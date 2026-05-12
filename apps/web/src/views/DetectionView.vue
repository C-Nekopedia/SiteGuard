<template>
  <div class="detection-container">
    <!-- Sidebar -->
    <nav class="sidebar">
      <div class="logo-area">
        <div class="logo-dot"></div>
        <span>SiteGuard</span>
      </div>

      <div class="menu-item active">
        <span>{{ $t('menu.monitor') }}</span>
      </div>

      <div class="lang-switch">
        <button class="lang-btn" @click="switchLocale">
          {{ $t('lang.switch') }}
        </button>
      </div>
    </nav>

    <!-- Main content -->
    <div class="main-container">
      <!-- Header with source tabs -->
      <header class="main-header">
        <h1>{{ $t('menu.monitor') }}</h1>
        <div class="source-tabs">
          <button class="tab" :class="{ active: activeInputType === 'camera' }" @click="switchInputType('camera')">
            {{ $t('input.camera') }}
          </button>
          <button class="tab" :class="{ active: activeInputType === 'image' }" @click="switchInputType('image')">
            {{ $t('input.localImage') }}
          </button>
        </div>
      </header>

      <!-- Core display area -->
      <div class="main-display">
        <!-- Left: detection visualization -->
        <div class="display-card viewer-panel">
          <div class="viewer-area">
            <!-- Image upload area -->
            <div v-if="activeInputType === 'image' && !currentImageUrl" class="upload-placeholder"
              @click="triggerImageUpload" @dragover.prevent="handleDragOver" @drop.prevent="handleImageDrop">
              <div class="upload-icon">
                <el-icon>
                  <FolderOpened />
                </el-icon>
              </div>
              <p style="margin: 0; font-weight: 600;">{{ $t('upload.dragDrop') }}</p>
              <p style="margin: 4px 0 0; font-size: 0.8rem;">{{ $t('upload.hint') }}</p>
              <input ref="imageInput" type="file" accept="image/*" @change="handleImageUpload" style="display: none" />
            </div>

            <!-- Camera area -->
            <div v-if="activeInputType === 'camera'" class="camera-placeholder">
              <div v-if="!isCameraActive" class="camera-prompt">
                <div class="upload-icon">
                  <el-icon>
                    <VideoCamera />
                  </el-icon>
                </div>
                <p style="margin: 0; font-weight: 600;">{{ $t('camera.notStarted') }}</p>
                <p style="margin: 4px 0 0; font-size: 0.8rem;">{{ $t('camera.startHint') }}</p>
              </div>
              <div v-else class="camera-active">
                <div class="camera-status">
                  <el-tag type="success" size="small">{{ $t('camera.running') }}</el-tag>
                  <p>{{ $t('camera.fps') }} {{ fps }} FPS</p>
                </div>
                <div v-if="cameraStreamUrl" class="camera-stream-container">
                  <img :src="cameraStreamUrl" alt="Camera live feed" class="camera-stream-image" />
                </div>
                <div v-else class="camera-placeholder-image">
                  <div class="upload-icon">
                    <el-icon>
                      <VideoCamera />
                    </el-icon>
                  </div>
                  <p style="margin: 4px 0 0; font-size: 0.8rem;">{{ $t('camera.connecting') }}</p>
                </div>
              </div>
            </div>

            <!-- Detection result display -->
            <div v-if="activeInputType === 'image' && currentImageUrl" class="detection-result">
              <img :src="currentImageUrl" alt="Detection result" class="result-image" />
            </div>

            <!-- Loading state -->
            <div v-if="detectionLoading" class="detection-loading">
              <el-icon class="loading-icon">
                <Loading />
              </el-icon>
              <p>{{ $t('detection.loading') }}</p>
            </div>
          </div>

          <!-- Bottom toolbar -->
          <div class="viewer-controls">
            <div class="model-info">
              {{ $t('model.currentWeight') }}
              <span class="model-name">
                {{ selectedModelLabel || 'yolo26n_ppe.pt' }}
              </span>
            </div>
            <div class="control-buttons">
              <!-- Camera mode controls -->
              <template v-if="activeInputType === 'camera'">
                <button class="btn btn-secondary" @click="toggleCamera" :disabled="cameraLoading || !isCameraActive">
                  {{ $t('camera.stop') }}
                </button>
                <button class="btn btn-primary" @click="toggleCamera" :disabled="cameraLoading || isCameraActive"
                  v-loading="cameraLoading">
                  {{ cameraLoading ? $t('camera.starting') : $t('camera.start') }}
                </button>
              </template>
              <!-- Image mode controls -->
              <template v-else>
                <button class="btn btn-secondary" @click="clearResult" :disabled="!currentImageUrl && !detectionLoading">
                  {{ $t('action.clearResult') }}
                </button>
                <button class="btn btn-primary" @click="startDetection" :disabled="detectionLoading || !canStartDetection"
                  v-loading="detectionLoading">
                  {{ detectionLoading ? $t('action.detecting') : $t('action.startDetection') }}
                </button>
              </template>
            </div>
          </div>
        </div>

        <!-- Right: detection log panel -->
        <div class="alert-panel">
          <div class="alert-header">
            <span>{{ activeInputType === 'camera' ? $t('panel.liveStatus') : $t('panel.detectionLog') }}</span>
            <button v-if="activeInputType !== 'camera'" class="btn-clear-logs" @click="clearLogs" :disabled="detectionHistory.length === 0">
              {{ $t('action.clearLogs') }}
            </button>
          </div>
          <div class="alert-list">
            <!-- Camera mode: live status overview -->
            <template v-if="activeInputType === 'camera'">
              <div v-if="!isCameraActive" class="empty-alerts">
                <p>{{ $t('status.notStarted') }}</p>
                <p class="hint">{{ $t('status.startHint') }}</p>
              </div>
              <div v-else class="camera-status-summary">
                <div class="summary-row">
                  <span class="summary-label">{{ $t('label.person') }}</span>
                  <span class="summary-value">{{ cameraSummary.person }}</span>
                </div>
                <div class="summary-row" v-for="risk in activeRisks" :key="risk.type">
                  <span class="summary-label">{{ risk.message }}</span>
                  <span class="summary-value summary-risk">{{ risk.count }}</span>
                </div>
                <div class="summary-row" v-if="activeRisks.length === 0">
                  <span class="summary-label summary-safe">{{ $t('status.allSafe') }}</span>
                </div>
              </div>
            </template>

            <!-- Image mode: detection history list -->
            <template v-else>
              <div v-if="detectionHistory.length === 0" class="empty-alerts">
                <p>{{ $t('log.noRecords') }}</p>
                <p class="hint">{{ $t('log.uploadHint') }}</p>
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
                      {{ item.expanded ? $t('action.collapse') : $t('action.expand') }}
                    </button>
                  </div>
                  <div class="alert-details">
                    <span class="source">{{ $t('log.source') }} {{ item.source }}</span>
                    <span class="time">{{ item.timestamp }}</span>
                  </div>
                  <div v-if="item.expanded && (item.detections?.length > 0 || item.risks?.length > 0)" class="detection-details">
                    <div v-if="item.detections?.length > 0" class="detection-section">
                      <h4>{{ $t('log.detectedObjects', { count: item.detections.length }) }}</h4>
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
                      <h4>{{ $t('log.riskAlerts', { count: item.risks.length }) }}</h4>
                      <div class="risk-list">
                        <div v-for="(risk, riskIndex) in item.risks" :key="riskIndex" class="risk-item">
                          <span class="risk-level" :style="{ color: risk.level === 'critical' ? '#DC2626' : risk.level === 'high' ? '#EF4444' : '#F59E0B' }">
                            {{ risk.level === 'critical' ? $t('risk.critical') : risk.level === 'high' ? $t('risk.high') : $t('risk.medium') }}
                          </span>
                          <span class="risk-message">{{ risk.message }}</span>
                          <span v-if="risk.count" class="risk-count">{{ $t('label.count') }} {{ risk.count }}</span>
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

      <!-- Performance stats -->
      <div class="performance-stats">
        <div class="stat-item">
          <span class="stat-label">{{ $t('stats.inferenceLatency') }}</span>
          <span class="stat-value">{{ inferenceLatency }}ms</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">{{ $t('stats.detectionCount') }}</span>
          <span class="stat-value">{{ detectionCount }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">{{ $t('stats.riskAlerts') }}</span>
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
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import {
  VideoCamera,
  FolderOpened,
  Loading
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const { t, locale } = useI18n()

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// State
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

// Separate image detection logs
const imageLogs = ref<any[]>([])
const cameraLogs = ref<any[]>([])
const detectionHistory = computed(() => imageLogs.value)

// Camera stream state
const cameraStreamUrl = ref<string>('')
const cameraWebSocket = ref<WebSocket | null>(null)
const lastFrameTime = ref<number>(0)
const frameTimes = ref<number[]>([])

// Refs
const imageInput = ref<HTMLInputElement>()

// API config
const API_BASE = '/api/v1'

// Computed
const selectedModelLabel = computed(() => {
  const model = availableModels.value.find((m: any) => m.name === selectedModel.value)
  return model?.display_name || selectedModel.value || 'yolo26n_ppe.pt'
})

const canStartDetection = computed(() => {
  if (detectionLoading.value) return false
  if (activeInputType.value === 'image' && currentImageUrl.value) return true
  if (activeInputType.value === 'camera') return false
  return false
})

// Camera live status summary
const cameraSummary = computed(() => {
  const summary: Record<string, number> = { person: 0 }
  for (const det of detections.value) {
    const cls = (det.class || '').toLowerCase()
    if (cls === 'person') summary.person++
  }
  return summary
})

// Color mapping: safe gear = green, missing gear = red
const classColors: Record<string, string> = {
  person: '#94A3B8',
  helmet: '#10B981',
  no_helmet: '#EF4444',
  vest: '#10B981',
  no_vest: '#EF4444',
  none: '#EF4444',
  gloves: '#10B981',
  no_gloves: '#EF4444',
  boots: '#10B981',
  no_boots: '#EF4444',
  goggles: '#10B981',
  no_goggle: '#EF4444'
}

// Localized class labels
const classLabels = computed<Record<string, string>>(() => ({
  person: t('classLabel.person'),
  helmet: t('classLabel.helmet'),
  no_helmet: t('classLabel.no_helmet'),
  vest: t('classLabel.vest'),
  no_vest: t('classLabel.no_vest'),
  none: t('classLabel.none'),
  gloves: t('classLabel.gloves'),
  no_gloves: t('classLabel.no_gloves'),
  boots: t('classLabel.boots'),
  no_boots: t('classLabel.no_boots'),
  goggles: t('classLabel.goggles'),
  no_goggle: t('classLabel.no_goggle')
}))

// Locale switching
const switchLocale = () => {
  locale.value = locale.value === 'zh-CN' ? 'en' : 'zh-CN'
  localStorage.setItem('siteguard-locale', locale.value)
}

// Methods
const switchInputType = (type: string) => {
  if (activeInputType.value === 'image' && currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
    currentImageUrl.value = ''
    currentImageFile.value = null
  }

  activeInputType.value = type
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
    ElMessage.error(t('message.uploadImageFile'))
    return
  }

  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error(t('message.fileTooLarge'))
    return
  }

  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }
  currentImageUrl.value = URL.createObjectURL(file)
  currentImageFile.value = file
  ElMessage.success(t('message.imageLoaded'))
}

const handleImageUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return

  const file = input.files[0]
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error(t('message.fileTooLarge'))
    return
  }

  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }
  currentImageUrl.value = URL.createObjectURL(file)
  currentImageFile.value = file
  ElMessage.success(t('message.imageLoaded'))
}

const toggleCamera = () => {
  if (isCameraActive.value) {
    disconnectCameraWebSocket()
    isCameraActive.value = false
    cameraStreamUrl.value = ''
    fps.value = 0
    frameTimes.value = []
    ElMessage.success(t('message.cameraStopped'))
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
      ElMessage.success(t('message.cameraConnected'))
    }

    cameraWebSocket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (cameraLoading.value) {
          cameraLoading.value = false
        }
        if (!isCameraActive.value) {
          isCameraActive.value = true
        }

        if (data.type === 'connected') {
          ElMessage.success(t('message.cameraReady'))
        } else if (data.type === 'frame') {
          cameraStreamUrl.value = `data:image/jpeg;base64,${data.frame}`

          if (data.detections) {
            detections.value = data.detections
            activeRisks.value = data.risks || []
            inferenceLatency.value = data.inference_time || 0
            detectionCount.value = detections.value.length
          }

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
          ElMessage.error(t('message.cameraError', { msg: data.message }))
        }
      } catch (error) {
        console.error('Failed to parse camera data:', error)
      }
    }

    cameraWebSocket.value.onerror = (error) => {
      console.error('Camera WebSocket error:', error)
      cameraLoading.value = false
      ElMessage.error(t('message.cameraFailed'))
    }

    cameraWebSocket.value.onclose = () => {
      if (isCameraActive.value) {
        ElMessage.warning(t('message.cameraDisconnected'))
        isCameraActive.value = false
        cameraStreamUrl.value = ''
      }
    }

    // Timeout: camera startup + model loading may take time
    setTimeout(() => {
      if (cameraLoading.value && !isCameraActive.value) {
        cameraLoading.value = false
        if (cameraWebSocket.value) {
          cameraWebSocket.value.close()
        }
        ElMessage.error(t('message.cameraTimeout'))
      }
    }, 15000)

  } catch (error) {
    console.error('Failed to start camera:', error)
    cameraLoading.value = false
    ElMessage.error(t('message.cameraStartFailed', { error: String(error) }))
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
    ElMessage.error(t('message.detectionFailed', { error: String(error) }))
  } finally {
    detectionLoading.value = false
  }
}

const detectImage = async () => {
  try {
    const file = currentImageFile.value
    if (!file) {
      ElMessage.error(t('message.selectImageFirst'))
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

      // Update detection history (image mode)
      imageLogs.value.unshift({
        timestamp: new Date().toLocaleTimeString(),
        source: file.name,
        message: activeRisks.value.length > 0 ? t('log.riskDetected') : t('log.detectionComplete'),
        riskLevel: activeRisks.value.length > 0 ? 'high' : 'success',
        detections: [...detections.value],
        risks: [...activeRisks.value],
        expanded: false
      })
      if (imageLogs.value.length > 10) {
        imageLogs.value = imageLogs.value.slice(0, 10)
      }

      const annotatedUrl = result.annotated_image_url
        ? (result.annotated_image_url.startsWith('http')
            ? result.annotated_image_url
            : `${API_BASE_URL}${result.annotated_image_url}`)
        : `${API_BASE_URL}/static/temp/annotated_${Date.now()}.jpg`

      if (currentImageUrl.value && currentImageUrl.value.startsWith('blob:')) {
        URL.revokeObjectURL(currentImageUrl.value)
      }

      currentImageUrl.value = annotatedUrl

      ElMessage.success(t('message.detectionComplete'))
    } else {
      ElMessage.error(t('message.detectionError', { msg: response.data.detail || 'Unknown error' }))
    }
  } catch (error: any) {
    console.error('Detection failed:', error)
    ElMessage.error(t('message.detectionFailed', { error: error.response?.data?.detail || error.message }))
  }
}

const clearResult = () => {
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }

  currentImageUrl.value = ''
  currentImageFile.value = null
  detections.value = []
  activeRisks.value = []
  detectionCount.value = 0
  inferenceLatency.value = 0
  ElMessage.info(t('message.resultCleared'))
}

const clearLogs = () => {
  if (activeInputType.value === 'camera') {
    cameraLogs.value = []
  } else {
    imageLogs.value = []
  }
  ElMessage.success(t('message.logsCleared'))
}

const toggleExpand = (index: number) => {
  detectionHistory.value[index].expanded = !detectionHistory.value[index].expanded
}

const sortDetections = (detections: any[]) => {
  if (!detections || detections.length === 0) return []
  return [...detections].sort((a, b) => {
    // Person first
    if (a.class === 'person' && b.class !== 'person') return -1
    if (a.class !== 'person' && b.class === 'person') return 1
    return 0
  })
}


const loadModels = async () => {
  try {
    const response = await axios.get(`${API_BASE}/models/list`)
    if (response.data.success && response.data.models) {
      availableModels.value = response.data.models
      if (response.data.current_model && availableModels.value.length > 0) {
        selectedModel.value = response.data.current_model
      }
    }
  } catch (error) {
    console.error('Failed to load model list:', error)
    // Fallback mock data
    availableModels.value = [
      { name: 'yolo26n_ppe.pt', display_name: 'YOLO26n-PPE (Default)' },
      { name: 'yolo26s_ppe.pt', display_name: 'YOLO26s-PPE' },
      { name: 'yolo26m_ppe.pt', display_name: 'YOLO26m-PPE' }
    ]
  }
}

// Lifecycle
onMounted(async () => {
  await loadModels()
})

onUnmounted(() => {
  if (currentImageUrl.value) {
    URL.revokeObjectURL(currentImageUrl.value)
  }
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

/* Sidebar */
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

/* Language switch */
.lang-switch {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1.5px solid var(--border);
}

.lang-btn {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  border: 1.5px solid var(--border);
  background: var(--card-bg);
  color: var(--text-body);
  transition: all 0.2s ease;
}

.lang-btn:hover {
  background: #F1F5F9;
  border-color: var(--brand-color);
  color: var(--brand-color);
}

/* Main content */
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

/* Source tabs */
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

/* Core display */
.main-display {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  grid-template-rows: 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

/* Display panel */
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

/* Upload placeholder */
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

/* Detection result */
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

/* Loading state */
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
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* Bottom toolbar */
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

/* Alert panel */
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

/* Camera status summary */
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

/* Performance stats */
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

/* Responsive */
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

  .lang-switch {
    margin-top: 0;
    padding-top: 0;
    border-top: none;
    margin-left: 8px;
  }

  .lang-btn {
    width: auto;
    padding: 6px 10px;
    font-size: 0.8rem;
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
