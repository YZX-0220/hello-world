<template>
  <div ref="rootRef" class="js-root" tabindex="0" role="region" aria-roledescription="carousel" aria-label="影像手账" @keydown="onKeyDown">
    <div
      ref="stageRef"
      class="js-stage"
      :data-drag="dragging ? '' : undefined"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    >
      <div class="js-floor" aria-hidden="true" />
      <div class="js-view">
        <div class="js-scene">
          <div
            v-for="(item, i) in items"
            :key="i"
            class="js-item"
            :ref="(el) => setItemEl(i, el)"
            :aria-hidden="i !== index"
            :data-active="i === index ? 'true' : undefined"
          >
            <div
              v-for="side in SIDES"
              :key="side"
              class="js-page"
              :data-side="side"
              :ref="(el) => setPageEl(i * 2 + (side === 'l' ? 0 : 1), el)"
            >
              <div class="js-sheet" :data-side="side">
                <slot
                  v-if="side === 'l'"
                  name="left"
                  :item="item"
                  :index="i"
                  :active="i === index"
                  :near="Math.abs(i - index) <= 1"
                />
                <slot
                  v-else
                  name="right"
                  :item="item"
                  :index="i"
                  :active="i === index"
                  :near="Math.abs(i - index) <= 1"
                />
              </div>
              <div class="js-gutter" />
              <div class="js-shade" />
            </div>
            <div class="js-canvas" :ref="(el) => setCanvasEl(i, el)">
              <slot
                name="spread"
                :item="item"
                :index="i"
                :active="i === index"
                :near="Math.abs(i - index) <= 1"
              />
            </div>
            <div class="js-dim" aria-hidden="true" :ref="(el) => setDimEl(i, el)" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';

const props = withDefaults(
  defineProps<{
    items: T[];
    index: number;
    /** 宽舞台下的跨页宽高比 */
    aspect?: number;
    /** 窄屏（手机竖屏）下的跨页宽高比 */
    narrowAspect?: number;
    height?: string;
  }>(),
  { aspect: 1.28, narrowAspect: 0.9, height: '100%' },
);

const emit = defineEmits<{ (e: 'update:index', value: number): void }>();

const OPEN = 0; // 跨页视频铺满整张纸，正文页保持平整
const SIDE = 80;
const FOLD = SIDE; // 正文页不折，左右两侧的纸一起侧立

function clamp(v: number, lo: number, hi: number) {
  return v < lo ? lo : v > hi ? hi : v;
}

function poseFor(p: number, w: number) {
  const d = Math.abs(p);
  const a = d < 1 ? d : 1;
  const sign = p < 0 ? -1 : 1;
  const out = d > 1 ? d - 1 : 0;
  const x = sign * (a * w * 0.62 + out * w * 0.06);
  const z = -(a * 130 + out * 70);
  // 只在快要落位时才把侧页转开，飞行途中保持平摊，避免两页在空中互相穿插
  const bend = a <= 0.78 ? 0 : (a - 0.78) / 0.22;
  const rot = sign * (OPEN + (SIDE - OPEN) * (bend * bend * (3 - 2 * bend)));
  const shade = clamp(0.05 + a * 0.22, 0, 0.45);
  return {
    x,
    z,
    rot,
    shade,
    opacity: clamp(1.25 - Math.max(0, d - 0.9) * 1.2, 0, 1),
    hidden: d > 2.6,
  };
}

function settle(pos: number, velocity: number, n: number) {
  return clamp(Math.round(pos + clamp(velocity * 0.18, -1.5, 1.5)), 0, Math.max(0, n - 1));
}

function durationFor(steps: number) {
  return steps <= 0 ? 0 : Math.round(560 * Math.sqrt(Math.min(steps, 12)));
}

function easeInOut(t: number) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function easeOut(t: number) {
  return 1 - Math.pow(1 - t, 3);
}

const rootRef = ref<HTMLDivElement | null>(null);
const stageRef = ref<HTMLDivElement | null>(null);
const itemEls: (HTMLElement | null)[] = [];
const pageEls: (HTMLElement | null)[] = [];
const canvasEls: (HTMLElement | null)[] = [];
const dimEls: (HTMLElement | null)[] = [];
let spreadW = 0;
let pos = props.index;
let raf = 0;
let tween: null | { from: number; to: number; t0: number; dur: number; ease: (t: number) => number } = null;
const dragging = ref(false);
let drag: null | { id: number; x: number; from: number; lastX: number; lastT: number; v: number; moved: boolean } = null;
let observer: ResizeObserver | null = null;

const SIDES = ['l', 'r'] as const;

function setItemEl(i: number, el: any) {
  itemEls[i] = (el as HTMLElement | null) ?? null;
}
function setPageEl(i: number, el: any) {
  pageEls[i] = (el as HTMLElement | null) ?? null;
}
function setCanvasEl(i: number, el: any) {
  canvasEls[i] = (el as HTMLElement | null) ?? null;
}
function setDimEl(i: number, el: any) {
  dimEls[i] = (el as HTMLElement | null) ?? null;
}

function paint() {
  const w = spreadW;
  if (!w) return;
  for (let i = 0; i < itemEls.length; i++) {
    const el = itemEls[i];
    if (!el) continue;
    const q = poseFor(i - pos, w);
    if (q.hidden) {
      el.style.visibility = 'hidden';
      continue;
    }
    el.style.visibility = 'visible';
    el.style.opacity = String(q.opacity);
    el.style.transform = `translate3d(${q.x.toFixed(2)}px,0,${q.z.toFixed(2)}px) rotateY(${q.rot.toFixed(2)}deg)`;
    const dim = dimEls[i];
    if (dim) dim.style.opacity = q.shade.toFixed(3);
  }
}

function frame(t: number) {
  raf = 0;
  const tw = tween;
  if (tw) {
    const k = tw.dur > 0 ? clamp((t - tw.t0) / tw.dur, 0, 1) : 1;
    pos = tw.from + (tw.to - tw.from) * tw.ease(k);
    if (k >= 1) tween = null;
  }
  paint();
  if (tween) raf = requestAnimationFrame(frame);
}

function kick() {
  if (!raf) raf = requestAnimationFrame(frame);
}

function go(to: number, ease = easeInOut) {
  const next = clamp(to, 0, Math.max(0, props.items.length - 1));
  const dur = durationFor(Math.abs(next - pos));
  tween = { from: pos, to: next, t0: performance.now(), dur, ease };
  kick();
  if (next !== props.index) emit('update:index', next);
}

function onPointerDown(e: PointerEvent) {
  if (e.button !== 0 || props.items.length < 1) return;
  tween = null;
  drag = { id: e.pointerId, x: e.clientX, from: pos, lastX: e.clientX, lastT: e.timeStamp, v: 0, moved: false };
}

function onPointerMove(e: PointerEvent) {
  const d = drag;
  if (!d || d.id !== e.pointerId || !spreadW) return;
  const dx = e.clientX - d.x;
  if (!d.moved && Math.abs(dx) > 6) {
    d.moved = true;
    dragging.value = true;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  if (!d.moved) return;
  const dt = Math.max(1, e.timeStamp - d.lastT);
  d.v = d.v * 0.6 + (-(e.clientX - d.lastX) / (spreadW * 0.42) / (dt / 1000)) * 0.4;
  d.lastX = e.clientX;
  d.lastT = e.timeStamp;
  pos = clamp(d.from - dx / (spreadW * 0.42), -0.3, props.items.length - 0.7);
  kick();
}

function onPointerUp(e: PointerEvent) {
  const d = drag;
  if (!d || d.id !== e.pointerId) return;
  drag = null;
  if (dragging.value) {
    dragging.value = false;
    go(settle(pos, d.v, props.items.length), easeOut);
  }
}

function onKeyDown(e: KeyboardEvent) {
  const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'PageDown' ? 1
    : e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp' ? -1 : 0;
  if (step) {
    e.preventDefault();
    go(props.index + step);
  } else if (e.key === 'Home') {
    e.preventDefault();
    go(0);
  } else if (e.key === 'End') {
    e.preventDefault();
    go(props.items.length - 1);
  }
}

function measure() {
  const stage = stageRef.value;
  const root = rootRef.value;
  if (!stage || !root) return;
  const rect = stage.getBoundingClientRect();
  const sw = rect.width;
  const sh = rect.height;
  if (!sw || !sh) return;
  const narrow = sw < 760;
  const aspect = narrow ? props.narrowAspect : props.aspect;
  const w = Math.round(
    Math.min(sw * (narrow ? 0.88 : 0.6), sh * 0.88 * aspect, 1080),
  );
  spreadW = w;
  root.style.setProperty('--js-w', `${w}px`);
  root.style.setProperty('--js-h', `${Math.round(w / aspect)}px`);
  paint();
}

watch(
  () => props.index,
  (v) => {
    if (Math.abs(pos - v) < 0.001) return;
    if (tween && Math.abs(tween.to - v) < 0.001) return;
    go(v);
  },
);

watch(
  () => props.items.length,
  (n) => {
    if (pos > n - 1) go(Math.max(0, n - 1));
  },
);

onMounted(() => {
  measure();
  observer = new ResizeObserver(() => measure());
  if (stageRef.value) observer.observe(stageRef.value);
  paint();
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
  cancelAnimationFrame(raf);
  raf = 0;
});

defineExpose({ goTo: go });
</script>

<style scoped>
.js-root {
  --js-w: 720px;
  --js-h: 560px;
  position: relative;
  width: 100%;
  height: 100%;
  outline: none;
  user-select: none;
  -webkit-user-select: none;
  touch-action: pan-y;
}
.js-root:focus-visible {
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.4);
  border-radius: 24px;
}
.js-stage {
  position: absolute;
  inset: 0;
  cursor: grab;
}
.js-stage[data-drag] {
  cursor: grabbing;
}
.js-floor {
  position: absolute;
  left: 50%;
  top: 50%;
  width: calc(var(--js-w) * 1.5);
  height: calc(var(--js-h) * 0.56);
  transform: translate(-50%, calc(var(--js-h) * 0.22));
  background: #171a2b;
  opacity: 0.55;
  filter: blur(calc(var(--js-w) * 0.028));
  border-radius: calc(var(--js-w) * 0.045);
  pointer-events: none;
}
.js-view {
  position: absolute;
  inset: 0;
  perspective: calc(var(--js-w) * 2.1);
  perspective-origin: 50% 46%;
}
.js-scene {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0;
  height: 0;
  transform-style: preserve-3d;
}
.js-item {
  position: absolute;
  left: 0;
  top: 0;
  transform-style: preserve-3d;
  visibility: hidden;
}
.js-canvas {
  position: absolute;
  left: calc(var(--js-w) * -0.5);
  top: calc(var(--js-h) * -0.5);
  width: var(--js-w);
  height: var(--js-h);
  transform-origin: 50% 50%;
  pointer-events: none;
}
.js-canvas :deep(*) {
  pointer-events: auto;
}
.js-dim {
  will-change: opacity;
  position: absolute;
  left: calc(var(--js-w) * -0.5);
  top: calc(var(--js-h) * -0.5);
  width: var(--js-w);
  height: var(--js-h);
  background: #141729;
  opacity: var(--js-s, 0);
  pointer-events: none;
  border-radius: calc(var(--js-w) * 0.016);
}
.js-page {
  position: absolute;
  top: calc(var(--js-h) * -0.5);
  width: calc(var(--js-w) * 0.5);
  height: var(--js-h);
  overflow: hidden;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  background: #ece7dc;
}
.js-page[data-side='l'] {
  left: calc(var(--js-w) * -0.5);
  transform-origin: 100% 50%;
  border-radius: calc(var(--js-w) * 0.016) 0 0 calc(var(--js-w) * 0.016);
}
.js-page[data-side='r'] {
  left: 0;
  transform-origin: 0 50%;
  border-radius: 0 calc(var(--js-w) * 0.016) calc(var(--js-w) * 0.016) 0;
}
.js-sheet {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.js-gutter {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.js-page[data-side='l'] .js-gutter {
  background: linear-gradient(90deg, rgba(255, 255, 255, 0) 78%, rgba(20, 18, 30, 0.1) 92%, rgba(20, 18, 30, 0.3));
}
.js-page[data-side='r'] .js-gutter {
  background: linear-gradient(270deg, rgba(255, 255, 255, 0) 78%, rgba(20, 18, 30, 0.1) 92%, rgba(20, 18, 30, 0.3));
}
.js-shade {
  position: absolute;
  inset: 0;
  background: #141729;
  opacity: var(--js-s, 0);
  pointer-events: none;
}
@media (prefers-reduced-motion: reduce) {
  .js-stage {
    cursor: default;
  }
}
</style>
