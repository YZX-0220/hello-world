<template>
  <div
    class="flip-root"
    ref="rootRef"
    tabindex="0"
    role="region"
    aria-roledescription="carousel"
    aria-label="影像手账"
    @pointerdown="onDown"
    @pointermove="onMove"
    @pointerup="onUp"
    @pointercancel="onUp"
    @wheel.prevent="onWheel"
  >
    <div class="flip-stage" ref="stageRef">
      <div class="flip-deck" aria-hidden="true">
        <span v-for="n in 3" :key="`l${n}`" class="deck-sheet deck-l" :style="deckStyle(-n)" />
        <span v-for="n in 3" :key="`r${n}`" class="deck-sheet deck-r" :style="deckStyle(n)" />
      </div>

      <div class="flip-preload" aria-hidden="true">
        <img v-for="(src, i) in preload || []" :key="`${i}-${src}`" :src="src" alt="" />
      </div>

      <!-- 书：左页文字、右页视频；右页之上盖一张可绕书脊翻动的纸 -->
      <div class="book" ref="sheetRef" :style="sheetStyle">
        <div class="book-page book-left">
          <slot name="left" :item="shown" :index="shownIndex" :active="true" />
        </div>
        <div class="book-page book-right">
          <slot name="right" :item="shown" :index="shownIndex" :active="true" />
        </div>
        <span class="book-spine" aria-hidden="true" />
        <div class="flip-turner" ref="turnerRef" aria-hidden="true">
          <span class="turner-front">
            <img v-if="shot" class="turner-shot" :src="shot" alt="" />
            <span class="turner-shade" />
          </span>
          <span class="turner-back" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    items: T[];
    index: number;
    aspect?: number;
    narrowAspect?: number;
    preload?: string[];
    capture?: () => string | null;
  }>(),
  { aspect: 1.7, narrowAspect: 1.1, preload: () => [] },
);

const emit = defineEmits<{
  (e: 'update:index', value: number): void;
  (e: 'flipstart'): void;
  (e: 'flipend'): void;
}>();

const shot = ref<string | null>(null);

const rootRef = ref<HTMLDivElement | null>(null);
const stageRef = ref<HTMLDivElement | null>(null);
const sheetRef = ref<HTMLElement | null>(null);
const turnerRef = ref<HTMLElement | null>(null);

const shownIndex = ref(props.index);
const shown = computed<T | undefined>(() => props.items[shownIndex.value]);

const width = ref(0);
const height = ref(0);
const busy = ref(false);

const sheetStyle = computed(() => ({
  width: `${width.value}px`,
  height: `${height.value}px`,
}));

function deckStyle(dir: number) {
  const w = width.value;
  const offset = Math.sign(dir);
  const rank = Math.abs(dir);
  return {
    width: `${w}px`,
    height: `${height.value}px`,
    transform: `translate3d(${(14 + rank * 10) * offset}px, ${rank * 2}px, 0) scale(${1 - rank * 0.008})`,
    opacity: `${0.5 - rank * 0.12}`,
  };
}

function applyTurn(deg: number, visible: boolean) {
  const el = turnerRef.value;
  if (!el) return;
  el.style.opacity = visible ? '1' : '0';
  el.style.transform = `rotateY(${deg.toFixed(2)}deg)`;
}

function applyShade(deg: number) {
  const el = turnerRef.value;
  if (!el) return;
  const abs = Math.abs(deg);
  const rad = (abs * Math.PI) / 180;
  // 越接近垂直，纸面越背光
  el.style.setProperty('--shade', (0.06 + 0.5 * Math.sin(rad)).toFixed(3));
  // 过了 90° 只剩纸背，避免上一页画面以镜像形式透出来
  el.style.setProperty('--shot-alpha', abs < 88 ? '1' : '0');
}

interface Anim {
  t0: number;
  dur: number;
  from: number;
  to: number;
  ease: (t: number) => number;
  onFrame?: (k: number) => void;
  done: () => void;
}

let rafId = 0;
let anim: Anim | null = null;

const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const easeFold = (t: number) => t * t;

function tick(t: number) {
  rafId = 0;
  const a = anim;
  if (!a) return;
  const k = a.dur > 0 ? Math.min(1, Math.max(0, (t - a.t0) / a.dur)) : 1;
  const e = a.ease(k);
  applyTurn(a.from + (a.to - a.from) * e, true);
  a.onFrame?.(k);
  if (k < 1) {
    rafId = requestAnimationFrame(tick);
  } else {
    anim = null;
    a.done();
  }
}

function runTurn(
  from: number,
  to: number,
  dur: number,
  onFrame?: (k: number) => void,
  ease: (t: number) => number = easeInOut,
): Promise<void> {
  return new Promise((resolve) => {
    if (rafId) cancelAnimationFrame(rafId);
    const current: Anim = {
      t0: performance.now(),
      dur,
      from,
      to,
      ease,
      onFrame,
      done: resolve,
    };
    anim = current;
    applyTurn(from, true);
    rafId = requestAnimationFrame(tick);
    // 兜底：后台标签页会暂停 rAF，超时直接落到终点
    window.setTimeout(() => {
      if (anim !== current) return;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      anim = null;
      applyTurn(to, true);
      current.done();
    }, dur + 300);
  });
}

async function waitPaint() {
  const el = sheetRef.value;
  if (el) {
    const imgs = Array.from(el.querySelectorAll('img'));
    await Promise.all(
      imgs.map((img) => (img.decode ? img.decode().catch(() => undefined) : Promise.resolve())),
    );
  }
  await new Promise<void>((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
  );
}

async function flipTo(next: number) {
  if (busy.value || next === shownIndex.value) return;
  if (next < 0 || next >= props.items.length) return;
  busy.value = true;
  const forward = next > shownIndex.value;
  let swapped = false;

  shot.value = props.capture?.() ?? null;
  emit('flipstart');

  const swap = async () => {
    if (swapped) return;
    swapped = true;
    shownIndex.value = next;
    await nextTick();
    await waitPaint();
  };

  const dur = 560;
  const FOLD = 176;
  if (forward) {
    await runTurn(0, -FOLD, dur, (k) => {
      applyShade(FOLD * k);
      if (k > 0.5) void swap();
    }, easeFold);
  } else {
    await runTurn(-FOLD, 0, dur, (k) => {
      applyShade(FOLD * (1 - k));
      if (k > 0.5) void swap();
    }, easeFold);
  }
  await swap();
  await fadeOutTurner();
  applyTurn(0, false);
  shot.value = null;
  busy.value = false;
  emit('flipend');
}

function fadeOutTurner(): Promise<void> {
  const el = turnerRef.value;
  if (!el) return Promise.resolve();
  el.style.transition = 'opacity 150ms ease';
  el.style.opacity = '0';
  return new Promise((resolve) =>
    window.setTimeout(() => {
      el.style.transition = '';
      resolve();
    }, 160),
  );
}

function goTo(target: number) {
  if (target === shownIndex.value) return;
  void flipTo(target);
  if (target !== props.index) emit('update:index', target);
}

function next() {
  goTo(shownIndex.value + 1);
}

function prev() {
  goTo(shownIndex.value - 1);
}

watch(
  () => props.index,
  (v) => {
    if (v !== shownIndex.value) void flipTo(v);
  },
);

/* 拖拽 / 滚轮 */
let drag: null | { id: number; x: number; moved: boolean } = null;
function onDown(e: PointerEvent) {
  if (e.button !== 0 || busy.value) return;
  drag = { id: e.pointerId, x: e.clientX, moved: false };
}
function onMove(e: PointerEvent) {
  if (!drag || drag.id !== e.pointerId) return;
  if (Math.abs(e.clientX - drag.x) > 8) drag.moved = true;
}
function onUp(e: PointerEvent) {
  const d = drag;
  if (!d || d.id !== e.pointerId) return;
  drag = null;
  const dx = e.clientX - d.x;
  if (Math.abs(dx) < 42) return;
  if (dx < 0) next();
  else prev();
}

let wheelAcc = 0;
let wheelAt = 0;
function onWheel(e: WheelEvent) {
  if (busy.value) return;
  if (Math.abs(e.deltaX) < Math.abs(e.deltaY)) return;
  wheelAcc += e.deltaX;
  const now = Date.now();
  if (now - wheelAt < 300 || Math.abs(wheelAcc) < 40) return;
  wheelAt = now;
  const dir = wheelAcc > 0 ? 1 : -1;
  wheelAcc = 0;
  if (dir > 0) next();
  else prev();
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowRight' || e.key === 'PageDown') {
    e.preventDefault();
    next();
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    e.preventDefault();
    prev();
  } else if (e.key === 'Home') {
    e.preventDefault();
    goTo(0);
  } else if (e.key === 'End') {
    e.preventDefault();
    goTo(props.items.length - 1);
  }
}

let observer: ResizeObserver | null = null;
function measure() {
  const stage = stageRef.value;
  if (!stage) return;
  const rect = stage.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const aspect = rect.width < 640 ? props.narrowAspect : props.aspect;
  const w = Math.min(rect.width * 0.88, rect.height * 0.88 * aspect, 1060);
  width.value = Math.round(w);
  height.value = Math.round(w / aspect);
}

onMounted(() => {
  measure();
  if (stageRef.value) {
    observer = new ResizeObserver(measure);
    observer.observe(stageRef.value);
  }
  window.addEventListener('keydown', onKey);
  applyTurn(0, false);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  window.removeEventListener('keydown', onKey);
  if (rafId) cancelAnimationFrame(rafId);
});

defineExpose({ next, prev, goTo });
</script>

<style scoped>
.flip-root {
  position: relative;
  width: 100%;
  height: 100%;
  outline: none;
  touch-action: pan-y;
  user-select: none;
  overflow: hidden;
}
.flip-stage {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  perspective: 2200px;
  perspective-origin: 50% 45%;
}
.flip-deck {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
}
.deck-sheet {
  position: absolute;
  border-radius: 14px;
  background: linear-gradient(160deg, #d9d0bd 0%, #b9ae98 100%);
  box-shadow: 0 18px 40px rgba(8, 10, 20, 0.45);
}
.flip-preload {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}
.book {
  position: relative;
  overflow: hidden;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-radius: 14px;
  background: #ece7dc;
  box-shadow:
    0 30px 70px rgba(6, 8, 18, 0.55),
    0 2px 0 rgba(255, 255, 255, 0.5) inset;
}
.book-page {
  position: relative;
  overflow: visible;
}
.book-left {
  border-radius: 14px 0 0 14px;
}
.book-right {
  border-radius: 0 14px 14px 0;
  background: #ece7dc;
}
.book-spine {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 26px;
  transform: translateX(-50%);
  pointer-events: none;
  background: linear-gradient(
    90deg,
    rgba(28, 22, 12, 0) 0%,
    rgba(28, 22, 12, 0.14) 42%,
    rgba(28, 22, 12, 0.24) 50%,
    rgba(28, 22, 12, 0.14) 58%,
    rgba(28, 22, 12, 0) 100%
  );
}
.flip-turner {
  position: absolute;
  left: 50%;
  top: 0;
  width: 50%;
  height: 100%;
  z-index: 3;
  transform-origin: left center;
  transform-style: preserve-3d;
  opacity: 0;
  pointer-events: none;
  will-change: transform, opacity;
}
.turner-front,
.turner-back {
  position: absolute;
  inset: 0;
  border-radius: 0 14px 14px 0;
  backface-visibility: hidden;
}
.turner-front {
  background: linear-gradient(100deg, #f2ede2 0%, #e8e1d3 60%, #d8cfbd 100%);
  box-shadow: 0 26px 60px rgba(6, 8, 18, 0.42);
  overflow: hidden;
}
.turner-shot {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: var(--shot-alpha, 1);
}
.turner-shade {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: var(--shade, 0);
  background: linear-gradient(90deg, rgba(20, 23, 41, 0.05) 0%, rgba(20, 23, 41, 0.86) 100%);
}
.turner-back {
  transform: rotateY(180deg);
  border-radius: 14px 0 0 14px;
  background: linear-gradient(260deg, #f2ede2 0%, #e9e2d4 55%, #dcd3c0 100%);
  box-shadow: 0 20px 50px rgba(6, 8, 18, 0.35);
}
@media (prefers-reduced-motion: reduce) {
  .flip-turner {
    display: none;
  }
}
</style>
