<script setup lang="ts" generic="T extends { id: string; title?: string }">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

/**
 * 环形卡片轮播（参考 Warp Carousel 的姿态函数与节奏）。
 * 世界坐标里卡片是 CW x CH，站位函数 poseAt 直接移植参考实现的拟合曲线，
 * 渲染用 CSS 3D（perspective + translate3d + rotateY），因此卡片里可以放真视频。
 */
const props = withDefaults(
  defineProps<{
    items: T[]
    index: number
    /** 世界像素缩放：卡片宽度 = stage 宽度 * zoomRatio */
    zoomRatio?: number
    /** 环形横向收拢系数（1 = 参考原值） */
    spread?: number
    aspect?: number
  }>(),
  { zoomRatio: 0.58, spread: 0.82, aspect: 1.6 },
)

const emit = defineEmits<{ 'update:index': [number]; spinstart: []; spinend: [] }>()

const CW = 320
const CH = CW / props.aspect
const FOCAL = 734.103
const G = {
  qA: 0.46401,
  XLA: 165.774,
  zA: 35.354,
  psiA: 1.44638,
  a1: 1.31454,
  a2: 1.10948,
  qB: 0.74999,
  XB: 204.525,
  ZB: 355.405,
  bB: 0.69311,
  bE: 0.04614,
  vC: 203.134,
  aC: 229.26,
  kB: 0.01087,
  bP: 0.99129,
  qPR: 1.01828,
  bPL: 1.0092,
  qPL: 1.07139,
}

const KS = CW / 256

function poseAt(q0: number): [number, number, number] {
  let q = q0
  if (Math.abs(q) < 1) q -= G.kB * Math.sin(Math.PI * q) ** 2
  const s = q < 0 ? -1 : 1
  const a = Math.abs(q)
  const half = CW / 2
  const XLA = G.XLA * KS
  const zA = G.zA * KS
  const XB = G.XB * KS
  const ZB = G.ZB * KS
  const vC = G.vC * KS
  const aC = G.aC * KS

  if (a <= G.qA) {
    const t = a / G.qA
    const xl = -half + (XLA + half) * Math.pow(t, G.a1)
    const zl = zA * t ** 4
    const psi = G.psiA * Math.pow(t, G.a2)
    return [s * (xl + half * Math.cos(psi)), zl + half * Math.sin(psi), s * psi]
  }

  const dXL = ((XLA + half) * G.a1) / G.qA
  const dZL = (zA * 4) / G.qA
  const dps = (G.psiA * G.a2) / G.qA

  let Hx: number
  let Hz: number
  if (a <= G.qB) {
    const L = G.qB - G.qA
    const t = (a - G.qA) / L
    const hx = XLA + CW * Math.cos(G.psiA)
    const hz = zA + CW * Math.sin(G.psiA)
    const dhx = dXL - CW * Math.sin(G.psiA) * dps
    const dhz = dZL + CW * Math.cos(G.psiA) * dps
    const h00 = 2 * t ** 3 - 3 * t ** 2 + 1
    const h10 = t ** 3 - 2 * t ** 2 + t
    const h01 = -2 * t ** 3 + 3 * t ** 2
    const h11 = t ** 3 - t ** 2
    Hx = h00 * hx + h10 * L * dhx * G.bB + h01 * XB + h11 * L * vC * G.bE
    Hz = h00 * hz + h10 * L * dhz * G.bB + h01 * ZB
  } else {
    const d = a - G.qB
    Hx = XB + vC * d + aC * d * d
    Hz = ZB
  }

  const qP = s < 0 ? G.qPL : G.qPR
  const bP = s < 0 ? G.bPL : G.bP
  const LP = qP - G.qA
  const tp = Math.min(1, (a - G.qA) / LP)
  const psi =
    (2 * tp ** 3 - 3 * tp ** 2 + 1) * G.psiA +
    (tp ** 3 - 2 * tp ** 2 + tp) * LP * dps * bP +
    (-2 * tp ** 3 + 3 * tp ** 2) * Math.PI

  return [s * (Hx - half * Math.cos(psi)), Hz - half * Math.sin(psi), s * psi]
}

const stageRef = ref<HTMLElement | null>(null)
const scale = ref(1)
const pos = ref(props.index)
let anim = 0
let tween: { from: number; to: number; t0: number; dur: number } | null = null

const DUR = 720
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

function measure() {
  const el = stageRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  scale.value = (r.width * props.zoomRatio) / CW
  el.style.setProperty('--ring-perspective', `${FOCAL * scale.value}px`)
  el.style.setProperty('--ring-card-w', `${CW * scale.value}px`)
  el.style.setProperty('--ring-card-h', `${CH * scale.value}px`)
}

function tick(now: number) {
  anim = 0
  if (!tween) return
  const k = Math.min(1, (now - tween.t0) / tween.dur)
  pos.value = tween.from + (tween.to - tween.from) * easeInOut(k)
  if (k < 1) anim = requestAnimationFrame(tick)
  else {
    pos.value = tween.to
    tween = null
    emit('spinend')
  }
}

function spinTo(next: number) {
  if (Math.abs(next - pos.value) < 0.0001) return
  if (anim) cancelAnimationFrame(anim)
  emit('spinstart')
  tween = { from: pos.value, to: next, t0: performance.now(), dur: DUR }
  anim = requestAnimationFrame(tick)
}

/** 环形上走最近的方向：2 -> 0 是 +1 而不是 -2 */
function spinToCircular(v: number) {
  const n = props.items.length
  if (!n) return
  const target = ((v % n) + n) % n
  const cur = ((pos.value % n) + n) % n
  let d = target - cur
  if (d > n / 2) d -= n
  if (d < -n / 2) d += n
  spinTo(pos.value + d)
}

watch(
  () => props.index,
  (v) => spinToCircular(v),
)

const visible = computed(() => {
  const base = Math.round(pos.value)
  const out: { item: T; index: number; wrapped: number; q: number; style: Record<string, string> }[] = []
  for (let i = base - 2; i <= base + 2; i += 1) {
    const n = props.items.length
    if (!n) break
    const wrapped = ((i % n) + n) % n
    const item = props.items[wrapped]
    if (!item) continue
    const q = i - pos.value
    const [rawX, z, psi] = poseAt(q)
    const x = rawX * props.spread
    const near = 1 - Math.min(1, Math.abs(q))
    out.push({
      item,
      index: i,
      wrapped,
      q,
      style: {
        transform: `translate3d(${(x * scale.value).toFixed(2)}px, 0, ${(-z * scale.value).toFixed(2)}px) rotateY(${psi.toFixed(4)}rad)`,
        filter: `brightness(${(0.55 + 0.45 * near).toFixed(3)}) saturate(${(0.7 + 0.3 * near).toFixed(3)})`,
        opacity: String(Math.max(0, Math.min(1, 1.6 - Math.abs(q) * 0.8))),
        zIndex: String(1000 - Math.round(z)),
      },
    })
  }
  return out.sort((a, b) => a.style.zIndex.localeCompare(b.style.zIndex))
})

/* ---------- 拖拽 ---------- */
let drag: { x0: number; p0: number; moved: boolean } | null = null

function onDown(e: PointerEvent) {
  if (e.button > 0) return
  drag = { x0: e.clientX, p0: pos.value, moved: false }
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
}

function onMove(e: PointerEvent) {
  if (!drag) return
  const dx = e.clientX - drag.x0
  if (Math.abs(dx) > 4) drag.moved = true
  if (!drag.moved) return
  if (anim) cancelAnimationFrame(anim)
  pos.value = drag.p0 - dx / (scale.value * 300)
}

function onUp() {
  if (!drag) return
  const moved = drag.moved
  drag = null
  const target = Math.round(pos.value)
  if (moved) {
    if (target !== props.index) emit('update:index', ((target % props.items.length) + props.items.length) % props.items.length)
    spinTo(target)
  } else {
    spinTo(props.index)
  }
}

let ro: ResizeObserver | null = null
onMounted(() => {
  measure()
  ro = new ResizeObserver(measure)
  if (stageRef.value) ro.observe(stageRef.value)
})
onBeforeUnmount(() => {
  ro?.disconnect()
  if (anim) cancelAnimationFrame(anim)
})
</script>

<template>
  <div
    class="ring-stage"
    ref="stageRef"
    @pointerdown="onDown"
    @pointermove="onMove"
    @pointerup="onUp"
    @pointercancel="onUp"
  >
    <div class="ring-plane">
      <div
        v-for="c in visible"
        :key="`${c.item.id}-${c.index}`"
        class="ring-card"
        :style="c.style"
        :data-active="Math.abs(c.q) < 0.02 ? 'true' : undefined"
      >
        <slot name="card" :item="c.item" :index="c.wrapped" :active="Math.abs(c.q) < 0.02" :near="Math.abs(c.q) < 1" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.ring-stage {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  perspective: var(--ring-perspective, 1600px);
  perspective-origin: 50% 50%;
  touch-action: pan-y;
  -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 11%, #000 89%, transparent 100%);
  mask-image: linear-gradient(90deg, transparent 0%, #000 11%, #000 89%, transparent 100%);
}
.ring-plane {
  position: absolute;
  inset: 0;
  transform-style: preserve-3d;
}
.ring-card {
  position: absolute;
  left: 50%;
  top: 50%;
  width: var(--ring-card-w, 520px);
  height: var(--ring-card-h, 325px);
  margin-left: calc(var(--ring-card-w, 520px) / -2);
  margin-top: calc(var(--ring-card-h, 325px) / -2);
  transform-style: preserve-3d;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 26px 60px rgba(6, 8, 18, 0.5);
}
</style>
