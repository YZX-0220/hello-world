<template>
  <Teleport to="body">
    <div v-if="open" class="p3d-modal-mask" @mousedown.stop @contextmenu.prevent>
      <div class="p3d-modal-container">
        <!-- 顶部栏 -->
        <header class="p3d-header">
          <div class="p3d-brand">
            <span class="p3d-badge">3D PRE-VIS</span>
            <h3>三维视角与空间构图搭建器</h3>
            <span class="p3d-sub">左键旋转机位 · 右键平移画面 · 滚轮推拉景别 · 点击几何体拖拽位置</span>
          </div>
          <div class="p3d-header-actions">
            <div class="aspect-switch">
              <span class="switch-label">画幅取景框：</span>
              <button
                v-for="ratio in (['16:9', '9:16', '1:1'] as const)"
                :key="ratio"
                type="button"
                class="ratio-btn"
                :class="{ active: sceneState.aspectRatio === ratio }"
                @click="sceneState.aspectRatio = ratio"
              >
                {{ ratio }}
              </button>
            </div>
            <button type="button" class="p3d-close-btn" @click="emit('close')">✕</button>
          </div>
        </header>

        <!-- 主体三栏布局 -->
        <div class="p3d-body">
          <!-- 左侧：几何体工具栏与选中物体属性 -->
          <aside class="p3d-left-panel">
            <div class="panel-section">
              <div class="section-title">1. 添加空间几何体</div>
              <div class="shape-grid">
                <button type="button" class="shape-add-btn" @click="addShape('box')">
                  <span class="shape-icon">🧊</span>
                  <span>正方体</span>
                  <small>建筑/车/桌椅</small>
                </button>
                <button type="button" class="shape-add-btn" @click="addShape('cylinder')">
                  <span class="shape-icon">🛢️</span>
                  <span>圆柱体</span>
                  <small>人物/树木/立柱</small>
                </button>
                <button type="button" class="shape-add-btn" @click="addShape('sphere')">
                  <span class="shape-icon">🔮</span>
                  <span>球体</span>
                  <small>核心焦点/头部</small>
                </button>
                <button type="button" class="shape-add-btn" @click="addShape('cone')">
                  <span class="shape-icon">📐</span>
                  <span>圆锥体</span>
                  <small>山峰/指向物</small>
                </button>
              </div>
            </div>

            <div class="panel-section">
              <div class="section-title">2. 地面背景颜色</div>
              <div class="color-row">
                <button
                  v-for="g in groundPalette"
                  :key="g.hex"
                  type="button"
                  class="color-dot"
                  :class="{ active: sceneState.groundColor === g.hex }"
                  :style="{ background: g.hex }"
                  :title="g.name"
                  @click="setGroundColor(g.hex)"
                ></button>
              </div>
            </div>

            <!-- 选中几何体属性调节 -->
            <div v-if="selectedObj" class="panel-section active-obj-panel">
              <div class="section-header-row">
                <span class="section-title">当前选中：{{ getObjectFullLabel(selectedObj) }}</span>
                <button type="button" class="del-obj-btn" @click="deleteSelectedObject">删除</button>
              </div>

              <div class="control-group">
                <label>区分色块</label>
                <div class="color-row">
                  <button
                    v-for="c in objectPalette"
                    :key="c.hex"
                    type="button"
                    class="color-dot"
                    :class="{ active: selectedObj.color === c.hex }"
                    :style="{ background: c.hex }"
                    :title="c.name"
                    @click="updateSelectedColor(c.hex, c.name)"
                  ></button>
                </div>
              </div>

              <div class="control-group">
                <label>
                  <span>代表主体代称（可选，自动替换描述）</span>
                </label>
                <input
                  v-model="selectedObj.alias"
                  type="text"
                  class="alias-input"
                  placeholder="如：红衣侠客 / 悬崖古亭"
                  @input="recalculateDescription"
                />
              </div>

              <div class="control-group">
                <label>离地高度 (Y): {{ selectedObj.position[1].toFixed(1) }}</label>
                <input
                  type="range"
                  min="0"
                  max="8"
                  step="0.2"
                  :value="selectedObj.position[1]"
                  @input="updateSelectedTransform('posY', +($event.target as HTMLInputElement).value)"
                />
              </div>

              <div class="control-group">
                <label>左右位置 (X): {{ selectedObj.position[0].toFixed(1) }}</label>
                <input
                  type="range"
                  min="-10"
                  max="10"
                  step="0.2"
                  :value="selectedObj.position[0]"
                  @input="updateSelectedTransform('posX', +($event.target as HTMLInputElement).value)"
                />
              </div>

              <div class="control-group">
                <label>前后纵深 (Z): {{ selectedObj.position[2].toFixed(1) }}</label>
                <input
                  type="range"
                  min="-10"
                  max="10"
                  step="0.2"
                  :value="selectedObj.position[2]"
                  @input="updateSelectedTransform('posZ', +($event.target as HTMLInputElement).value)"
                />
              </div>

              <div class="control-group">
                <label>宽度缩放: {{ selectedObj.scale[0].toFixed(1) }}x</label>
                <input
                  type="range"
                  min="0.3"
                  max="5"
                  step="0.1"
                  :value="selectedObj.scale[0]"
                  @input="updateSelectedTransform('scaleXZ', +($event.target as HTMLInputElement).value)"
                />
              </div>

              <div class="control-group">
                <label>高度拉伸: {{ selectedObj.scale[1].toFixed(1) }}x</label>
                <input
                  type="range"
                  min="0.3"
                  max="6"
                  step="0.1"
                  :value="selectedObj.scale[1]"
                  @input="updateSelectedTransform('scaleY', +($event.target as HTMLInputElement).value)"
                />
              </div>
            </div>
            <div v-else class="panel-section empty-obj-tip">
              点击画面中的 3D 几何体可调整其高度、大小、颜色或拖拽位置
            </div>
          </aside>

          <!-- 中间：Three.js 3D 交互视口 + 画幅安全框 -->
          <main class="p3d-viewport-wrap" ref="viewportWrapRef">
            <div ref="canvasMountRef" class="p3d-canvas-mount"></div>

            <!-- 画幅比例取景安全框遮罩 -->
            <div class="viewfinder-overlay">
              <div class="viewfinder-frame" :style="viewfinderStyle">
                <!-- 九宫格辅助线（仅预览，不进截图） -->
                <div class="grid-line-h h1"></div>
                <div class="grid-line-h h2"></div>
                <div class="grid-line-v v1"></div>
                <div class="grid-line-v v2"></div>
                <span class="frame-badge">{{ sceneState.aspectRatio }} 取景安全框</span>
              </div>
            </div>

            <!-- 底部快捷视角重置 -->
            <div class="viewport-floating-bar">
              <button type="button" class="mini-cam-btn" @click="setPresetCamera('eye')">平视正前</button>
              <button type="button" class="mini-cam-btn" @click="setPresetCamera('high')">40° 高位俯拍</button>
              <button type="button" class="mini-cam-btn" @click="setPresetCamera('low')">低角度仰拍</button>
              <button type="button" class="mini-cam-btn" @click="setPresetCamera('Dutch')">过肩斜侧</button>
            </div>
          </main>

          <!-- 右侧：双机位定格截图 + 6维空间描述自动解算 -->
          <aside class="p3d-right-panel">
            <div class="panel-section">
              <div class="section-title">3. 定格机位截图（自动隐藏网格辅助线）</div>
              <div class="capture-slots">
                <!-- 起始视角槽 -->
                <div class="capture-card">
                  <div class="slot-header">
                    <span class="slot-tag primary">起始视角（首帧构图）</span>
                    <button type="button" class="capture-action-btn" @click="captureFrame('start')">
                      📷 定格当前视角
                    </button>
                  </div>
                  <div v-if="startFrameDataUrl" class="slot-preview">
                    <img :src="startFrameDataUrl" alt="起始视角" />
                  </div>
                  <div v-else class="slot-empty">转动 3D 视角后点击上方按钮截图</div>
                </div>

                <!-- 结束视角槽（可选，用于运镜） -->
                <div class="capture-card">
                  <div class="slot-header">
                    <span class="slot-tag">结束视角（可选 · 运镜终点）</span>
                    <div class="slot-btn-group">
                      <button type="button" class="capture-action-btn secondary" @click="captureFrame('end')">
                        🎥 定格终点
                      </button>
                      <button
                        v-if="endFrameDataUrl"
                        type="button"
                        class="clear-end-btn"
                        @click="clearEndFrame"
                        title="清除结束视角"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  <div v-if="endFrameDataUrl" class="slot-preview">
                    <img :src="endFrameDataUrl" alt="结束视角" />
                  </div>
                  <div v-else class="slot-empty">若需推拉/环绕运镜，可移动相机再拍一张终点视角</div>
                </div>
              </div>
            </div>

            <!-- 色块代称快捷填空列表 -->
            <div v-if="sceneState.objects.length > 0" class="panel-section alias-quick-section">
              <div class="section-title">4. 色块代表主体替换（选填）</div>
              <div class="alias-list">
                <div v-for="obj in sceneState.objects" :key="obj.id" class="alias-item">
                  <span class="color-chip" :style="{ background: obj.color }"></span>
                  <span class="shape-label">{{ obj.colorName }}{{ shapeNameMap[obj.shape] }} →</span>
                  <input
                    v-model="obj.alias"
                    type="text"
                    placeholder="填具体事物自动替换下文"
                    @input="recalculateDescription"
                  />
                </div>
              </div>
            </div>

            <!-- 6 维摄影级空间描述预览与微调 -->
            <div class="panel-section desc-section">
              <div class="section-header-row">
                <span class="section-title">5. 摄影级 6 维空间与运镜解算描述</span>
                <button type="button" class="recalc-btn" @click="recalculateDescription">↻ 重新解算</button>
              </div>
              <textarea
                v-model="spatialDescription"
                class="spatial-textarea"
                rows="8"
                placeholder="定格视角后，系统将自动根据三维坐标、九宫格投影、画面占比与遮挡关系生成精确描述..."
              ></textarea>
            </div>

            <div class="p3d-footer">
              <button type="button" class="cancel-btn" @click="emit('close')">取消</button>
              <button
                type="button"
                class="confirm-btn"
                :disabled="isSaving"
                @click="handleConfirmSave"
              >
                {{ isSaving ? '正在保存视角...' : '✓ 确认并写入视角节点' }}
              </button>
            </div>
          </aside>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { Perspective3DObject, PerspectiveSceneData } from '@/types/api';

const props = defineProps<{
  open: boolean;
  initialData?: PerspectiveSceneData | null;
  initialUrl?: string;
  initialDescription?: string;
  isSaving?: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (
    e: 'confirm',
    payload: {
      startDataUrl: string;
      endDataUrl: string | null;
      description: string;
      sceneData: PerspectiveSceneData;
    }
  ): void;
}>();

const shapeNameMap: Record<Perspective3DObject['shape'], string> = {
  box: '正方体',
  cylinder: '圆柱体',
  sphere: '球体',
  cone: '圆锥体',
};

const groundPalette = [
  { hex: '#ffffff', name: '纯白平面' },
  { hex: '#e2e8f0', name: '浅灰地面' },
  { hex: '#1e293b', name: '暗夜黑底' },
  { hex: '#dcfce7', name: '草地浅绿' },
  { hex: '#e0f2fe', name: '水天浅蓝' },
];

const objectPalette = [
  { hex: '#ef4444', name: '红色' },
  { hex: '#3b82f6', name: '蓝色' },
  { hex: '#10b981', name: '绿色' },
  { hex: '#f59e0b', name: '黄色' },
  { hex: '#a855f7', name: '紫色' },
  { hex: '#64748b', name: '灰色' },
];

const sceneState = reactive<PerspectiveSceneData>({
  aspectRatio: '16:9',
  groundColor: '#ffffff',
  objects: [],
  startCamera: { position: [0, 4.5, 10], target: [0, 1, 0] },
  endCamera: null,
  endFrameUrl: null,
});

const selectedObjectId = ref<string>('');
const startFrameDataUrl = ref<string>('');
const endFrameDataUrl = ref<string | null>(null);
const spatialDescription = ref<string>('');

const selectedObj = computed(() =>
  sceneState.objects.find((o) => o.id === selectedObjectId.value) || null
);

// 计算取景安全框尺寸
const viewportWrapRef = ref<HTMLElement | null>(null);
const canvasMountRef = ref<HTMLElement | null>(null);
const viewportSize = reactive({ w: 800, h: 600 });

const viewfinderRect = computed(() => {
  const pad = 48;
  const maxW = Math.max(200, viewportSize.w - pad * 2);
  const maxH = Math.max(200, viewportSize.h - pad * 2);
  const ratioMap = { '16:9': 16 / 9, '9:16': 9 / 16, '1:1': 1 };
  const targetRatio = ratioMap[sceneState.aspectRatio];

  let w = maxW;
  let h = w / targetRatio;
  if (h > maxH) {
    h = maxH;
    w = h * targetRatio;
  }
  return {
    w: Math.round(w),
    h: Math.round(h),
    left: Math.round((viewportSize.w - w) / 2),
    top: Math.round((viewportSize.h - h) / 2),
  };
});

const viewfinderStyle = computed(() => ({
  width: `${viewfinderRect.value.w}px`,
  height: `${viewfinderRect.value.h}px`,
}));

// ==================== Three.js 核心实例 ====================
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let renderer: THREE.WebGLRenderer | null = null;
let controls: OrbitControls | null = null;
let groundMesh: THREE.Mesh | null = null;
let gridHelper: THREE.GridHelper | null = null;
let selectionBoxHelper: THREE.BoxHelper | null = null;
let animFrameId = 0;
let resizeObserver: ResizeObserver | null = null;

const meshMap = new Map<string, THREE.Mesh>();
const raycaster = new THREE.Raycaster();
const mouseNDC = new THREE.Vector2();
const dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
let isDraggingMesh = false;
const dragOffset = new THREE.Vector3();

function initThreeScene() {
  const mount = canvasMountRef.value;
  const wrap = viewportWrapRef.value;
  if (!mount || !wrap) return;

  cleanupThree();

  const rect = wrap.getBoundingClientRect();
  viewportSize.w = Math.max(400, Math.round(rect.width || wrap.clientWidth || 800));
  viewportSize.h = Math.max(300, Math.round(rect.height || wrap.clientHeight || 600));

  scene = new THREE.Scene();
  scene.background = new THREE.Color(sceneState.groundColor);

  camera = new THREE.PerspectiveCamera(45, viewportSize.w / viewportSize.h, 0.1, 200);
  camera.position.set(...sceneState.startCamera.position);

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    preserveDrawingBuffer: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(viewportSize.w, viewportSize.h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  renderer.domElement.style.display = 'block';
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';

  mount.innerHTML = '';
  mount.appendChild(renderer.domElement);

  // 灯光（半球光 + 环境光 + 平行光，确保任何背景色下明暗清晰不发黑）
  const hemiLight = new THREE.HemisphereLight(0xffffff, 0xe2e8f0, 0.85);
  hemiLight.position.set(0, 20, 0);
  scene.add(hemiLight);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.35);
  scene.add(ambientLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.85);
  dirLight.position.set(12, 22, 14);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 1024;
  dirLight.shadow.mapSize.height = 1024;
  scene.add(dirLight);

  // 无限感大平面
  const planeGeo = new THREE.PlaneGeometry(200, 200);
  const planeMat = new THREE.MeshStandardMaterial({
    color: sceneState.groundColor,
    roughness: 0.9,
    metalness: 0.05,
  });
  groundMesh = new THREE.Mesh(planeGeo, planeMat);
  groundMesh.rotation.x = -Math.PI / 2;
  groundMesh.receiveShadow = true;
  scene.add(groundMesh);

  // 辅助空间网格（截图时自动隐藏）
  gridHelper = new THREE.GridHelper(60, 60, 0x94a3b8, 0xcbd5e1);
  gridHelper.position.y = 0.01;
  scene.add(gridHelper);

  // 轨道控制器
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(...sceneState.startCamera.target);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI / 2 + 0.15;
  controls.update();

  // 恢复或初始化默认几何体
  meshMap.clear();
  if (sceneState.objects.length === 0) {
    sceneState.objects.push(
      {
        id: 'obj_1',
        shape: 'cylinder',
        color: '#ef4444',
        colorName: '红色',
        alias: '',
        position: [-1.6, 1.1, 1.5],
        scale: [1, 1.4, 1],
      },
      {
        id: 'obj_2',
        shape: 'box',
        color: '#3b82f6',
        colorName: '蓝色',
        alias: '',
        position: [2.2, 1.5, -2.5],
        scale: [1.8, 2.0, 1.8],
      }
    );
  }

  for (const obj of sceneState.objects) {
    createMeshForObject(obj);
  }
  if (sceneState.objects.length > 0) {
    selectObjectById(sceneState.objects[0].id);
  }

  // 绑定画布内鼠标点选与拖拽物体事件
  const dom = renderer.domElement;
  dom.addEventListener('pointerdown', onPointerDown);
  dom.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('resize', onWindowResize);

  // 监听中间视口容器自身尺寸变化，防止弹窗挂载瞬间宽高为 0 导致黑屏
  resizeObserver = new ResizeObserver(() => {
    onWindowResize();
  });
  resizeObserver.observe(wrap);

  // 立即渲染首帧
  renderer.render(scene, camera);

  const animate = () => {
    animFrameId = requestAnimationFrame(animate);
    controls?.update();
    if (selectionBoxHelper) selectionBoxHelper.update();
    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  };
  animate();

  // 初始若无截图，待容器布局稳定后自动定格一张起始视角
  if (!startFrameDataUrl.value) {
    setTimeout(() => {
      onWindowResize();
      captureFrame('start');
    }, 180);
  }
}

function createGeometry(shape: Perspective3DObject['shape']): THREE.BufferGeometry {
  switch (shape) {
    case 'box':
      return new THREE.BoxGeometry(1.5, 1.5, 1.5);
    case 'cylinder':
      return new THREE.CylinderGeometry(0.65, 0.65, 1.6, 32);
    case 'sphere':
      return new THREE.SphereGeometry(0.85, 32, 32);
    case 'cone':
      return new THREE.ConeGeometry(0.85, 1.8, 32);
  }
}

function createMeshForObject(obj: Perspective3DObject) {
  if (!scene) return;
  const geo = createGeometry(obj.shape);
  const mat = new THREE.MeshStandardMaterial({
    color: obj.color,
    roughness: 0.4,
    metalness: 0.1,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.position.set(...obj.position);
  mesh.scale.set(...obj.scale);
  mesh.userData = { objectId: obj.id };
  scene.add(mesh);
  meshMap.set(obj.id, mesh);
}

function selectObjectById(id: string) {
  selectedObjectId.value = id;
  if (!scene) return;
  if (selectionBoxHelper) {
    scene.remove(selectionBoxHelper);
    selectionBoxHelper = null;
  }
  const mesh = meshMap.get(id);
  if (mesh) {
    selectionBoxHelper = new THREE.BoxHelper(mesh, 0x38bdf8);
    scene.add(selectionBoxHelper);
  }
}

// 鼠标点击选中几何体并在水平面上直接拖拽移动
function onPointerDown(e: PointerEvent) {
  if (e.button !== 0 || !renderer || !camera || !controls) return;
  const rect = renderer.domElement.getBoundingClientRect();
  mouseNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  mouseNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(mouseNDC, camera);
  const meshes = Array.from(meshMap.values());
  const intersects = raycaster.intersectObjects(meshes, false);

  if (intersects.length > 0) {
    const hitMesh = intersects[0].object as THREE.Mesh;
    const objId = hitMesh.userData.objectId;
    if (objId) {
      selectObjectById(objId);
      isDraggingMesh = true;
      controls.enabled = false;
      dragPlane.setFromNormalAndCoplanarPoint(new THREE.Vector3(0, 1, 0), hitMesh.position);
      const planeHit = new THREE.Vector3();
      if (raycaster.ray.intersectPlane(dragPlane, planeHit)) {
        dragOffset.copy(hitMesh.position).sub(planeHit);
      }
    }
  }
}

function onPointerMove(e: PointerEvent) {
  if (!isDraggingMesh || !renderer || !camera || !selectedObj.value) return;
  const rect = renderer.domElement.getBoundingClientRect();
  mouseNDC.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  mouseNDC.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

  raycaster.setFromCamera(mouseNDC, camera);
  const planeHit = new THREE.Vector3();
  if (raycaster.ray.intersectPlane(dragPlane, planeHit)) {
    const newPos = planeHit.add(dragOffset);
    const clampedX = Math.max(-12, Math.min(12, Number(newPos.x.toFixed(2))));
    const clampedZ = Math.max(-12, Math.min(12, Number(newPos.z.toFixed(2))));
    selectedObj.value.position[0] = clampedX;
    selectedObj.value.position[2] = clampedZ;
    const mesh = meshMap.get(selectedObj.value.id);
    if (mesh) {
      mesh.position.x = clampedX;
      mesh.position.z = clampedZ;
    }
  }
}

function onPointerUp() {
  if (isDraggingMesh) {
    isDraggingMesh = false;
    if (controls) controls.enabled = true;
    recalculateDescription();
  }
}

function onWindowResize() {
  if (!viewportWrapRef.value || !renderer || !camera) return;
  const w = viewportWrapRef.value.clientWidth;
  const h = viewportWrapRef.value.clientHeight;
  if (!w || !h) return;
  viewportSize.w = w;
  viewportSize.h = h;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  if (scene) renderer.render(scene, camera);
}

// ==================== 左侧工具栏操作 ====================
function addShape(shape: Perspective3DObject['shape']) {
  const paletteItem = objectPalette[sceneState.objects.length % objectPalette.length];
  const id = `obj_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`;
  const offset = (sceneState.objects.length % 3 - 1) * 1.5;
  const newObj: Perspective3DObject = {
    id,
    shape,
    color: paletteItem.hex,
    colorName: paletteItem.name,
    alias: '',
    position: [offset, 0.9, 0],
    scale: [1, 1, 1],
  };
  sceneState.objects.push(newObj);
  createMeshForObject(newObj);
  selectObjectById(id);
  recalculateDescription();
}

function deleteSelectedObject() {
  if (!selectedObj.value || !scene) return;
  const id = selectedObj.value.id;
  const mesh = meshMap.get(id);
  if (mesh) {
    scene.remove(mesh);
    mesh.geometry.dispose();
    meshMap.delete(id);
  }
  if (selectionBoxHelper) {
    scene.remove(selectionBoxHelper);
    selectionBoxHelper = null;
  }
  sceneState.objects = sceneState.objects.filter((o) => o.id !== id);
  selectedObjectId.value = sceneState.objects[0]?.id || '';
  if (selectedObjectId.value) selectObjectById(selectedObjectId.value);
  recalculateDescription();
}

function setGroundColor(hex: string) {
  sceneState.groundColor = hex;
  if (scene) scene.background = new THREE.Color(hex);
  if (groundMesh) {
    (groundMesh.material as THREE.MeshStandardMaterial).color.set(hex);
  }
}

function updateSelectedColor(hex: string, name: string) {
  if (!selectedObj.value) return;
  selectedObj.value.color = hex;
  selectedObj.value.colorName = name;
  const mesh = meshMap.get(selectedObj.value.id);
  if (mesh) {
    (mesh.material as THREE.MeshStandardMaterial).color.set(hex);
  }
  recalculateDescription();
}

function updateSelectedTransform(
  type: 'posX' | 'posY' | 'posZ' | 'scaleXZ' | 'scaleY',
  val: number
) {
  if (!selectedObj.value) return;
  const obj = selectedObj.value;
  if (type === 'posX') obj.position[0] = val;
  if (type === 'posY') obj.position[1] = val;
  if (type === 'posZ') obj.position[2] = val;
  if (type === 'scaleXZ') {
    obj.scale[0] = val;
    obj.scale[2] = val;
  }
  if (type === 'scaleY') obj.scale[1] = val;

  const mesh = meshMap.get(obj.id);
  if (mesh) {
    mesh.position.set(...obj.position);
    mesh.scale.set(...obj.scale);
  }
  recalculateDescription();
}

function setPresetCamera(preset: 'eye' | 'high' | 'low' | 'Dutch') {
  if (!camera || !controls) return;
  controls.target.set(0, 1.0, 0);
  if (preset === 'eye') camera.position.set(0, 1.4, 9.5);
  if (preset === 'high') camera.position.set(0, 7.5, 8.5);
  if (preset === 'low') camera.position.set(0, 0.25, 7.5);
  if (preset === 'Dutch') camera.position.set(-5.5, 2.8, 7.5);
  controls.update();
  recalculateDescription();
}

// ==================== 纯净画幅裁切截图（自动隐藏网格与选中框） ====================
function capturePureViewfinderDataUrl(): string {
  if (!renderer || !scene || !camera) return '';

  // 1. 临时隐藏网格线与选中高亮框，保证给 AI 的参考图 100% 纯净
  if (gridHelper) gridHelper.visible = false;
  if (selectionBoxHelper) selectionBoxHelper.visible = false;
  renderer.render(scene, camera);

  // 2. 严格按取景安全框区域裁切导出
  const sourceCanvas = renderer.domElement;
  const dpr = renderer.getPixelRatio();
  const rect = viewfinderRect.value;

  const cropCanvas = document.createElement('canvas');
  const outWidth = sceneState.aspectRatio === '9:16' ? 720 : 960;
  const ratioMap = { '16:9': 16 / 9, '9:16': 9 / 16, '1:1': 1 };
  const outHeight = Math.round(outWidth / ratioMap[sceneState.aspectRatio]);

  cropCanvas.width = outWidth;
  cropCanvas.height = outHeight;
  const ctx = cropCanvas.getContext('2d');
  if (ctx) {
    ctx.drawImage(
      sourceCanvas,
      rect.left * dpr,
      rect.top * dpr,
      rect.w * dpr,
      rect.h * dpr,
      0,
      0,
      outWidth,
      outHeight
    );
  }

  // 3. 恢复网格线与选中框
  if (gridHelper) gridHelper.visible = true;
  if (selectionBoxHelper) selectionBoxHelper.visible = true;
  renderer.render(scene, camera);

  return cropCanvas.toDataURL('image/png');
}

function captureFrame(slot: 'start' | 'end') {
  if (!camera || !controls) return;
  const dataUrl = capturePureViewfinderDataUrl();
  const camSnapshot = {
    position: [
      Number(camera.position.x.toFixed(2)),
      Number(camera.position.y.toFixed(2)),
      Number(camera.position.z.toFixed(2)),
    ] as [number, number, number],
    target: [
      Number(controls.target.x.toFixed(2)),
      Number(controls.target.y.toFixed(2)),
      Number(controls.target.z.toFixed(2)),
    ] as [number, number, number],
  };

  if (slot === 'start') {
    startFrameDataUrl.value = dataUrl;
    sceneState.startCamera = camSnapshot;
  } else {
    endFrameDataUrl.value = dataUrl;
    sceneState.endCamera = camSnapshot;
  }
  recalculateDescription();
}

function clearEndFrame() {
  endFrameDataUrl.value = null;
  sceneState.endCamera = null;
  recalculateDescription();
}

function getObjectFullLabel(obj: Perspective3DObject): string {
  const base = `${obj.colorName}${shapeNameMap[obj.shape]}`;
  return obj.alias?.trim() ? `${obj.alias.trim()}（${base}色块）` : `[${base}]`;
}

// ==================== 摄影级 6 维空间与运镜自动解算器 ====================
function recalculateDescription() {
  if (!camera || !controls) return;

  const tempCam = camera.clone();
  if (sceneState.startCamera) {
    tempCam.position.set(...sceneState.startCamera.position);
    tempCam.lookAt(...sceneState.startCamera.target);
    tempCam.updateMatrixWorld();
  }

  const camPos = tempCam.position.clone();
  const targetPos = new THREE.Vector3(...(sceneState.startCamera?.target || [0, 1, 0]));
  const toCam = camPos.clone().sub(targetPos);
  const dist = toCam.length();

  // 维度 1 & 4：精确俯仰角 (Pitch) 与视距透视畸变判定
  const pitchRad = Math.asin(Math.max(-1, Math.min(1, toCam.y / (dist || 1))));
  const pitchDeg = Math.round((pitchRad * 180) / Math.PI);

  let angleDesc = '';
  if (pitchDeg > 45) angleDesc = `${pitchDeg}° 高角度大俯拍（鸟瞰全局视野）`;
  else if (pitchDeg >= 15) angleDesc = `${pitchDeg}° 中高角度俯拍`;
  else if (pitchDeg > -10) angleDesc = `${pitchDeg}° 平视机位（自然人眼高度）`;
  else angleDesc = `仰角 ${Math.abs(pitchDeg)}° 低角度仰拍（强化主体崇高感与视觉张力）`;

  let shotScaleDesc = '标准中景';
  if (dist < 5.5) shotScaleDesc = '近景特写（广角近大远小透视感强烈，前景极具视觉冲击力）';
  else if (dist > 13.5) shotScaleDesc = '大远景/全景（展现宏大空间环境纵深）';
  else shotScaleDesc = '中景构图（空间透视自然均衡）';

  interface ProjectedItem {
    obj: Perspective3DObject;
    label: string;
    cxPct: number;
    cyPct: number;
    depth: number;
    areaPct: number;
    gridName: string;
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    isCutLeft: boolean;
    isCutRight: boolean;
    isCutTop: boolean;
    isCutBottom: boolean;
  }

  const vf = viewfinderRect.value;
  const projectedList: ProjectedItem[] = [];

  for (const obj of sceneState.objects) {
    const mesh = meshMap.get(obj.id);
    if (!mesh) continue;
    mesh.updateMatrixWorld();

    const box3 = new THREE.Box3().setFromObject(mesh);
    const corners = [
      new THREE.Vector3(box3.min.x, box3.min.y, box3.min.z),
      new THREE.Vector3(box3.min.x, box3.min.y, box3.max.z),
      new THREE.Vector3(box3.min.x, box3.max.y, box3.min.z),
      new THREE.Vector3(box3.min.x, box3.max.y, box3.max.z),
      new THREE.Vector3(box3.max.x, box3.min.y, box3.min.z),
      new THREE.Vector3(box3.max.x, box3.min.y, box3.max.z),
      new THREE.Vector3(box3.max.x, box3.max.y, box3.min.z),
      new THREE.Vector3(box3.max.x, box3.max.y, box3.max.z),
    ];

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;

    for (const c of corners) {
      c.project(tempCam);
      const px = ((c.x + 1) / 2) * viewportSize.w;
      const py = ((1 - c.y) / 2) * viewportSize.h;
      const u = (px - vf.left) / vf.w;
      const v = (py - vf.top) / vf.h;
      minX = Math.min(minX, u);
      maxX = Math.max(maxX, u);
      minY = Math.min(minY, v);
      maxY = Math.max(maxY, v);
    }

    const center3D = new THREE.Vector3(...obj.position);
    const depth = center3D.distanceTo(camPos);

    const clampedMinX = Math.max(0, Math.min(1, minX));
    const clampedMaxX = Math.max(0, Math.min(1, maxX));
    const clampedMinY = Math.max(0, Math.min(1, minY));
    const clampedMaxY = Math.max(0, Math.min(1, maxY));
    const areaPct = Math.round(
      Math.max(0, clampedMaxX - clampedMinX) * Math.max(0, clampedMaxY - clampedMinY) * 100
    );

    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const cxPct = Math.round(Math.max(0, Math.min(100, cx * 100)));
    const cyPct = Math.round(Math.max(0, Math.min(100, cy * 100)));

    const colName = cx < 0.36 ? '左' : cx > 0.64 ? '右' : '中';
    const rowName = cy < 0.36 ? '上' : cy > 0.64 ? '下' : '中';
    let gridName = `${colName}${rowName}区域`;
    if (colName === '中' && rowName === '中') gridName = '视觉正中心';
    else if (colName === '中') gridName = `正${rowName}方`;
    else if (rowName === '中') gridName = `画面${colName}侧黄金分割区`;

    projectedList.push({
      obj,
      label: getObjectFullLabel(obj),
      cxPct,
      cyPct,
      depth,
      areaPct,
      gridName,
      minX,
      maxX,
      minY,
      maxY,
      isCutLeft: minX < 0 && maxX > 0.05,
      isCutRight: maxX > 1 && minX < 0.95,
      isCutTop: minY < 0 && maxY > 0.05,
      isCutBottom: maxY > 1 && minY < 0.95,
    });
  }

  projectedList.sort((a, b) => a.depth - b.depth);

  const itemLines: string[] = [];
  projectedList.forEach((item, idx) => {
    const layerTag =
      projectedList.length === 1
        ? '核心主体'
        : idx === 0
        ? '近景前景'
        : idx === projectedList.length - 1
        ? '深远背景'
        : '中景层次';

    let sizeDesc = `约占画面 ${Math.max(1, item.areaPct)}% 面积`;
    if (item.areaPct >= 35) sizeDesc = `占据画面主导地位（约 ${item.areaPct}% 面积，贴近镜头大体量）`;
    else if (item.areaPct <= 6) sizeDesc = `占画面约 ${Math.max(1, item.areaPct)}% 面积（远景深处点缀）`;

    const heightNote =
      item.obj.position[1] > 2.2
        ? '悬浮/伫立于高处'
        : item.obj.scale[1] >= 1.8
        ? '呈纵向高耸形态立于地面'
        : '稳固置于地面';

    const cutEdges: string[] = [];
    if (item.isCutLeft) cutEdges.push('左侧延伸出画外');
    if (item.isCutRight) cutEdges.push('右侧延伸出画外');
    if (item.isCutTop) cutEdges.push('顶部延伸出画外');
    if (item.isCutBottom) cutEdges.push('底部延伸出画外');
    const edgeNote = cutEdges.length
      ? `，呈【边缘半入画构图】（${cutEdges.join('、')}，作为前景引导框架）`
      : '';

    itemLines.push(
      `${idx + 1}. 【${layerTag}】${item.label}：位于${item.gridName}（横轴 ${item.cxPct}%，纵轴 ${item.cyPct}%），${heightNote}，${sizeDesc}${edgeNote}。`
    );
  });

  const relationNotes: string[] = [];
  for (let i = 0; i < projectedList.length; i++) {
    for (let j = i + 1; j < projectedList.length; j++) {
      const front = projectedList[i];
      const back = projectedList[j];

      const ix0 = Math.max(front.minX, back.minX);
      const iy0 = Math.max(front.minY, back.minY);
      const ix1 = Math.min(front.maxX, back.maxX);
      const iy1 = Math.min(front.maxY, back.maxY);

      if (ix1 > ix0 && iy1 > iy0) {
        const interArea = (ix1 - ix0) * (iy1 - iy0);
        const backArea = Math.max(0.001, (back.maxX - back.minX) * (back.maxY - back.minY));
        const overlapRatio = Math.round((interArea / backArea) * 100);
        if (overlapRatio >= 8) {
          relationNotes.push(
            `近处的 ${front.label} 局部遮挡了后方 ${back.label} 约 ${Math.min(95, overlapRatio)}% 的画面区域，形成强烈的前后景深叠加层次`
          );
        }
      }

      const depthGap = (back.depth - front.depth).toFixed(1);
      const horizontalRel = back.cxPct > front.cxPct ? '右后方' : '左后方';
      relationNotes.push(
        `${back.label} 位于 ${front.label} 的${horizontalRel}（纵深拉开约 ${depthGap} 米距离）`
      );
    }
  }

  let cameraMotionLine = '固定机位拍摄（保持上述透视构图稳定呈现，画面内部主体自然运动）。';
  if (sceneState.endCamera && endFrameDataUrl.value) {
    const startP = new THREE.Vector3(...sceneState.startCamera.position);
    const startT = new THREE.Vector3(...sceneState.startCamera.target);
    const endP = new THREE.Vector3(...sceneState.endCamera.position);
    const endT = new THREE.Vector3(...sceneState.endCamera.target);

    const startVec = startP.clone().sub(startT);
    const endVec = endP.clone().sub(endT);

    const d0 = startVec.length();
    const d1 = endVec.length();
    const distDiffPct = Math.round(((d1 - d0) / (d0 || 1)) * 100);

    const az0 = Math.atan2(startVec.x, startVec.z);
    const az1 = Math.atan2(endVec.x, endVec.z);
    let azDiffDeg = Math.round(((az1 - az0) * 180) / Math.PI);
    if (azDiffDeg > 180) azDiffDeg -= 360;
    if (azDiffDeg < -180) azDiffDeg += 360;

    const p0 = Math.round((Math.asin(startVec.y / (d0 || 1)) * 180) / Math.PI);
    const p1 = Math.round((Math.asin(endVec.y / (d1 || 1)) * 180) / Math.PI);
    const pitchDiff = p1 - p0;

    const moves: string[] = [];
    if (distDiffPct <= -12) {
      moves.push(`镜头向前大幅推进（视距拉近 ${Math.abs(distDiffPct)}%，由远及近聚焦主体）`);
    } else if (distDiffPct >= 12) {
      moves.push(`镜头向后平稳拉远（视距拉开 ${distDiffPct}%，逐步展露全局环境）`);
    }

    if (Math.abs(azDiffDeg) >= 10) {
      const dir = azDiffDeg > 0 ? '向右顺时针环绕' : '向左逆时针环绕';
      moves.push(`相机${dir} ${Math.abs(azDiffDeg)}°（展现空间三维立体感）`);
    }

    if (Math.abs(pitchDiff) >= 8) {
      const tiltDir =
        pitchDiff > 0
          ? `机位向上升起俯拍（俯角由 ${p0}° 升至 ${p1}°）`
          : `机位向下沉降平视/仰拍（俯角由 ${p0}° 降至 ${p1}°）`;
      moves.push(tiltDir);
    }

    cameraMotionLine =
      moves.length > 0
        ? `一镜到底复合运镜：${moves.join('，同时')}。`
        : '镜头作轻微呼吸感平移推进，平稳过渡至结束视角。';
  }

  const lines = [
    `【机位与透视】${sceneState.aspectRatio} 画幅，${angleDesc}，${shotScaleDesc}。`,
    `【主体空间排布（共 ${projectedList.length} 个空间体块）】`,
    ...(itemLines.length ? itemLines : ['画面中央为空旷场景平面。']),
  ];

  if (relationNotes.length > 0) {
    lines.push(`【前后遮挡与相对空间】${relationNotes.slice(0, 3).join('；')}。`);
  }

  lines.push(`【首尾帧运镜轨迹】${cameraMotionLine}`);

  spatialDescription.value = lines.join('\n');
}

function handleConfirmSave() {
  if (!startFrameDataUrl.value) {
    captureFrame('start');
  }
  if (!spatialDescription.value?.trim()) {
    recalculateDescription();
  }

  const finalStartUrl = startFrameDataUrl.value || capturePureViewfinderDataUrl();
  const payload = {
    startDataUrl: finalStartUrl,
    endDataUrl: endFrameDataUrl.value,
    description: spatialDescription.value,
    sceneData: JSON.parse(JSON.stringify(sceneState)),
  };

  cleanupThree();
  emit('confirm', payload);
  emit('close');
}

function cleanupThree() {
  if (animFrameId) cancelAnimationFrame(animFrameId);
  animFrameId = 0;
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  window.removeEventListener('pointerup', onPointerUp);
  window.removeEventListener('resize', onWindowResize);
  if (renderer) {
    if (renderer.domElement) {
      renderer.domElement.removeEventListener('pointerdown', onPointerDown);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
    }
    renderer.forceContextLoss();
    renderer.dispose();
  }
  meshMap.clear();
  scene = null;
  camera = null;
  renderer = null;
  controls = null;
}

function hydrateAndInit() {
  if (props.initialData) {
    sceneState.aspectRatio = props.initialData.aspectRatio || '16:9';
    sceneState.groundColor = props.initialData.groundColor || '#ffffff';
    sceneState.objects = JSON.parse(JSON.stringify(props.initialData.objects || []));
    sceneState.startCamera = props.initialData.startCamera || {
      position: [0, 4.5, 10],
      target: [0, 1, 0],
    };
    sceneState.endCamera = props.initialData.endCamera || null;
    endFrameDataUrl.value = props.initialData.endFrameUrl || null;
  } else {
    sceneState.aspectRatio = '16:9';
    sceneState.groundColor = '#ffffff';
    sceneState.objects = [];
    sceneState.startCamera = { position: [0, 4.5, 10], target: [0, 1, 0] };
    sceneState.endCamera = null;
    endFrameDataUrl.value = null;
  }
  startFrameDataUrl.value = props.initialUrl || '';
  spatialDescription.value = props.initialDescription || '';

  initThreeScene();
  if (!spatialDescription.value) {
    recalculateDescription();
  }
}

watch(
  () => props.open,
  async (val) => {
    if (val) {
      await nextTick();
      hydrateAndInit();
    } else {
      cleanupThree();
    }
  }
);

// 兼容父组件使用 v-if="perspectiveModal.open" 挂载时立即触发初始化
onMounted(async () => {
  if (props.open) {
    await nextTick();
    hydrateAndInit();
  }
});

watch(
  () => sceneState.aspectRatio,
  () => {
    recalculateDescription();
  }
);

onBeforeUnmount(() => {
  cleanupThree();
});
</script>

<style scoped>
.p3d-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 2200;
  background: rgba(6, 10, 22, 0.82);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.p3d-modal-container {
  width: min(1440px, 96vw);
  height: min(880px, 92vh);
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.65);
  color: #f8fafc;
}

.p3d-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: rgba(15, 23, 42, 0.95);
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.p3d-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.p3d-badge {
  background: linear-gradient(135deg, #6366f1, #0ea5e9);
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}

.p3d-brand h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.p3d-sub {
  font-size: 12px;
  color: #94a3b8;
}

.p3d-header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.aspect-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(30, 41, 59, 0.8);
  padding: 4px 8px;
  border-radius: 8px;
}

.switch-label {
  font-size: 12px;
  color: #94a3b8;
}

.ratio-btn {
  background: transparent;
  border: 1px solid transparent;
  color: #cbd5e1;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.ratio-btn.active {
  background: rgba(56, 189, 248, 0.2);
  border-color: #38bdf8;
  color: #fff;
  font-weight: 600;
}

.p3d-close-btn {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  color: #cbd5e1;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  cursor: pointer;
}

.p3d-body {
  flex: 1;
  display: grid;
  grid-template-columns: 270px 1fr 370px;
  min-height: 0;
}

.p3d-left-panel,
.p3d-right-panel {
  background: rgba(15, 23, 42, 0.9);
  padding: 14px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.p3d-left-panel {
  border-right: 1px solid rgba(148, 163, 184, 0.15);
}

.p3d-right-panel {
  border-left: 1px solid rgba(148, 163, 184, 0.15);
}

.panel-section {
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 10px;
  padding: 12px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: 10px;
}

.shape-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.shape-add-btn {
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  padding: 8px 6px;
  color: #f1f5f9;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: all 0.15s;
}

.shape-add-btn:hover {
  border-color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
}

.shape-icon {
  font-size: 18px;
}

.shape-add-btn small {
  font-size: 10px;
  color: #94a3b8;
}

.color-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.color-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.25);
  cursor: pointer;
}

.color-dot.active {
  border-color: #38bdf8;
  transform: scale(1.15);
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.35);
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.del-obj-btn {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.45);
  color: #fca5a5;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 5px;
  cursor: pointer;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
}

.alias-input {
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 6px;
  padding: 5px 8px;
  color: #fff;
  font-size: 12px;
}

.empty-obj-tip {
  font-size: 12px;
  color: #94a3b8;
  text-align: center;
  padding: 20px 12px;
}

/* 视口与取景框 */
.p3d-viewport-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  background: #090d16;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.p3d-canvas-mount {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
}

.viewfinder-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.viewfinder-frame {
  position: relative;
  border: 2px solid rgba(56, 189, 248, 0.85);
  box-shadow: 0 0 0 9999px rgba(6, 10, 22, 0.58);
  border-radius: 4px;
}

.frame-badge {
  position: absolute;
  top: -24px;
  left: 0;
  background: rgba(14, 165, 233, 0.9);
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.grid-line-h,
.grid-line-v {
  position: absolute;
  background: rgba(255, 255, 255, 0.18);
}

.grid-line-h {
  left: 0;
  right: 0;
  height: 1px;
}
.grid-line-h.h1 {
  top: 33.33%;
}
.grid-line-h.h2 {
  top: 66.66%;
}

.grid-line-v {
  top: 0;
  bottom: 0;
  width: 1px;
}
.grid-line-v.v1 {
  left: 33.33%;
}
.grid-line-v.v2 {
  left: 66.66%;
}

.viewport-floating-bar {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  display: flex;
  gap: 8px;
  background: rgba(15, 23, 42, 0.82);
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.25);
}

.mini-cam-btn {
  background: transparent;
  border: none;
  color: #e2e8f0;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 999px;
  cursor: pointer;
}

.mini-cam-btn:hover {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
}

/* 右侧截图槽与描述 */
.capture-slots {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.capture-card {
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  padding: 8px;
}

.slot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.slot-tag {
  font-size: 11px;
  color: #94a3b8;
}
.slot-tag.primary {
  color: #38bdf8;
  font-weight: 600;
}

.slot-btn-group {
  display: flex;
  gap: 4px;
}

.capture-action-btn {
  background: linear-gradient(135deg, #0284c7, #4f46e5);
  border: none;
  color: #fff;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.capture-action-btn.secondary {
  background: rgba(56, 189, 248, 0.18);
  border: 1px solid rgba(56, 189, 248, 0.4);
}

.clear-end-btn {
  background: rgba(239, 68, 68, 0.2);
  border: none;
  color: #fca5a5;
  border-radius: 5px;
  padding: 2px 6px;
  cursor: pointer;
}

.slot-preview img {
  width: 100%;
  max-height: 115px;
  object-fit: contain;
  border-radius: 6px;
  background: #090d16;
}

.slot-empty {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #64748b;
  border: 1px dashed rgba(148, 163, 184, 0.2);
  border-radius: 6px;
}

.alias-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alias-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.color-chip {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.shape-label {
  color: #cbd5e1;
  white-space: nowrap;
}

.alias-item input {
  flex: 1;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 5px;
  padding: 3px 6px;
  color: #fff;
  font-size: 11px;
}

.recalc-btn {
  background: transparent;
  border: 1px solid rgba(56, 189, 248, 0.4);
  color: #38bdf8;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 5px;
  cursor: pointer;
}

.spatial-textarea {
  width: 100%;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  padding: 8px;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
}

.p3d-footer {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  color: #cbd5e1;
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
}

.confirm-btn {
  background: linear-gradient(135deg, #4f46e5, #0ea5e9);
  border: none;
  color: #fff;
  font-weight: 600;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>