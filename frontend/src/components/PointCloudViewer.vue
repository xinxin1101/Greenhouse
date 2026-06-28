<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js'
import type { PointCloudRecord } from '../types/sensor'
import { pointCloudFileUrl } from '../api/client'

const props = defineProps<{
  records: PointCloudRecord[]
  activeIndex: number
  playing: boolean
}>()

const emit = defineEmits<{
  updateIndex: [index: number]
}>()

const container = ref<HTMLDivElement | null>(null)
const pointSize = ref(0.003)
const pointOpacity = ref(1)
const backgroundColor = ref('#ffffff')
const colorMode = ref<'source' | 'custom'>('source')
const pointColor = ref('#2d7d46')
const autoRotate = ref(false)
const rotateSpeed = ref(0.004)
const controlsCollapsed = ref(false)
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let pointCloud: THREE.Points | null = null
let timer: number | null = null
let resizeObserver: ResizeObserver | null = null
let currentMaxDim = 1
let currentTargetY = 0.5
const baseRotationX = THREE.MathUtils.degToRad(-4)
const baseRotationZ = THREE.MathUtils.degToRad(3.78)

function initScene() {
  if (!container.value || renderer) return
  scene = new THREE.Scene()
  scene.background = new THREE.Color(backgroundColor.value)

  const width = container.value.clientWidth
  const height = container.value.clientHeight
  camera = new THREE.PerspectiveCamera(50, width / height, 0.01, 1000)
  camera.position.set(0, 1.2, 2.4)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(width, height)
  container.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true

  scene.add(new THREE.AmbientLight(0xffffff, 1.4))
  const light = new THREE.DirectionalLight(0xffffff, 0.8)
  light.position.set(1, 2, 1)
  scene.add(light)

  animate()
}

function animate() {
  requestAnimationFrame(animate)
  if (autoRotate.value && pointCloud) {
    pointCloud.rotation.z += rotateSpeed.value
  }
  controls?.update()
  if (scene && camera && renderer) {
    renderer.render(scene, camera)
  }
}

function getMaterial() {
  if (!pointCloud || Array.isArray(pointCloud.material)) return null
  return pointCloud.material as THREE.PointsMaterial
}

function applyVisualSettings() {
  if (scene) {
    scene.background = new THREE.Color(backgroundColor.value)
  }

  const material = getMaterial()
  if (!material || !pointCloud) return

  const hasVertexColor = pointCloud.geometry.hasAttribute('color')
  material.size = pointSize.value
  material.opacity = pointOpacity.value
  material.transparent = pointOpacity.value < 1
  material.depthWrite = pointOpacity.value >= 0.85
  material.vertexColors = colorMode.value === 'source' && hasVertexColor
  if (!material.vertexColors) {
    material.color.set(pointColor.value)
  }
  material.needsUpdate = true
}

function resetView() {
  if (pointCloud) {
    pointCloud.rotation.x = baseRotationX
    pointCloud.rotation.z = baseRotationZ
  }
  if (camera && controls) {
    camera.position.set(0, currentMaxDim * 0.7, currentMaxDim * 2)
    controls.target.set(0, currentTargetY, 0)
    controls.update()
  }
}

async function loadRecord(record?: PointCloudRecord) {
  if (!record || !scene) return
  const loader = new PLYLoader()
  const geometry = await loader.loadAsync(pointCloudFileUrl(record))
  geometry.computeBoundingBox()
  const box = geometry.boundingBox
  if (!box) return

  const center = new THREE.Vector3()
  const size = new THREE.Vector3()
  box.getCenter(center)
  box.getSize(size)
  geometry.translate(-center.x, -box.min.y, -center.z)

  const materialOptions: THREE.PointsMaterialParameters = {
    size: pointSize.value,
    vertexColors: geometry.hasAttribute('color'),
    opacity: pointOpacity.value,
    transparent: pointOpacity.value < 1,
    depthWrite: pointOpacity.value >= 0.85,
    sizeAttenuation: true
  }
  if (!geometry.hasAttribute('color') || colorMode.value === 'custom') {
    materialOptions.vertexColors = false
    materialOptions.color = new THREE.Color('#2d7d46')
  }
  const material = new THREE.PointsMaterial(materialOptions)

  if (pointCloud) {
    scene.remove(pointCloud)
    pointCloud.geometry.dispose()
    Array.isArray(pointCloud.material)
      ? pointCloud.material.forEach((m) => m.dispose())
      : pointCloud.material.dispose()
  }

  pointCloud = new THREE.Points(geometry, material)
  pointCloud.rotation.x = baseRotationX
  pointCloud.rotation.z = baseRotationZ
  scene.add(pointCloud)

  const maxDim = Math.max(size.x, size.y, size.z)
  currentMaxDim = maxDim
  currentTargetY = size.y / 2
  resetView()
  applyVisualSettings()
}

function resize() {
  if (!container.value || !camera || !renderer) return
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function updatePlayback() {
  if (timer) {
    window.clearInterval(timer)
    timer = null
  }
  if (props.playing && props.records.length > 1) {
    timer = window.setInterval(() => {
      emit('updateIndex', (props.activeIndex + 1) % props.records.length)
    }, 1200)
  }
}

onMounted(() => {
  initScene()
  resize()
  if (container.value) {
    resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(container.value)
  }
  void loadRecord(props.records[props.activeIndex])
  updatePlayback()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', resize)
  if (timer) window.clearInterval(timer)
  renderer?.dispose()
  resizeObserver = null
})

watch(() => props.records[props.activeIndex]?.fileName, () => loadRecord(props.records[props.activeIndex]))
watch(() => [props.playing, props.records.length, props.activeIndex], updatePlayback)
watch([pointSize, pointOpacity, backgroundColor, colorMode, pointColor], applyVisualSettings)
</script>

<template>
  <div class="point-cloud-viewer">
    <div v-if="!records.length" class="empty-state">当前时间范围内没有点云记录</div>
    <div ref="container" class="point-cloud-canvas"></div>
    <form class="cloud-tuning-panel" :class="{ collapsed: controlsCollapsed }" @submit.prevent>
      <header>
        <strong>点云控制</strong>
        <div>
          <button type="button" @click="controlsCollapsed = !controlsCollapsed">
            {{ controlsCollapsed ? '展开' : '收起' }}
          </button>
          <button v-if="!controlsCollapsed" type="button" @click="resetView">重置视角</button>
        </div>
      </header>
      <template v-if="!controlsCollapsed">
        <label>
          <span>点大小</span>
          <input v-model.number="pointSize" type="range" min="0.001" max="0.012" step="0.001" />
          <b>{{ pointSize.toFixed(3) }}</b>
        </label>
        <label>
          <span>透明度</span>
          <input v-model.number="pointOpacity" type="range" min="0.2" max="1" step="0.05" />
          <b>{{ Math.round(pointOpacity * 100) }}%</b>
        </label>
        <label>
          <span>背景</span>
          <input v-model="backgroundColor" type="color" />
        </label>
        <label>
          <span>颜色</span>
          <select v-model="colorMode">
            <option value="source">原始颜色</option>
            <option value="custom">自定义颜色</option>
          </select>
        </label>
        <label v-if="colorMode === 'custom'">
          <span>点颜色</span>
          <input v-model="pointColor" type="color" />
        </label>
        <label class="switch-row">
          <span>自动旋转</span>
          <input v-model="autoRotate" type="checkbox" />
        </label>
        <label>
          <span>旋转速度</span>
          <input v-model.number="rotateSpeed" type="range" min="0.001" max="0.03" step="0.001" />
          <b>{{ rotateSpeed.toFixed(3) }}</b>
        </label>
      </template>
    </form>
    <div v-if="records[activeIndex]" class="point-cloud-info">
      <strong>{{ records[activeIndex].fileName }}</strong>
      <span>{{ records[activeIndex].recordTime }}</span>
    </div>
  </div>
</template>
