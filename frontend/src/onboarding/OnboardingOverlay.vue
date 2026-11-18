<template>
  <Teleport to="body">
    <Transition name="tour-fade">
      <div
        v-if="open && step"
        class="hw-tour-root"
        role="dialog"
        aria-modal="true"
        :aria-label="step.title"
      >
        <!-- 1. 全屏 SVG 聚光灯挖空遮罩（高亮区可穿透点击真实按钮） -->
        <svg class="hw-tour-svg" :width="vw" :height="vh">
          <defs>
            <mask id="hw-spotlight-mask">
              <rect x="0" y="0" :width="vw" :height="vh" fill="white" />
              <rect
                v-if="spotRect.visible"
                :x="spotRect.x"
                :y="spotRect.y"
                :width="spotRect.w"
                :height="spotRect.h"
                :rx="spotRect.radius"
                fill="black"
              />
            </mask>
          </defs>
          <!-- 四周遮罩拦截背景误触，但挖空区域允许鼠标穿透操作真实按钮 -->
          <rect
            x="0"
            y="0"
            :width="vw"
            :height="vh"
            fill="rgba(5, 8, 17, 0.76)"
            mask="url(#hw-spotlight-mask)"
            class="hw-backdrop-rect"
          />
        </svg>

        <!-- 2. 目标元素外围呼吸脉冲光环（pointer-events: none 不阻挡真实点击） -->
        <div
          v-if="spotRect.visible"
          class="hw-spotlight-ring"
          :style="{
            left: `${spotRect.x}px`,
            top: `${spotRect.y}px`,
            width: `${spotRect.w}px`,
            height: `${spotRect.h}px`,
            borderRadius: `${spotRect.radius}px`,
          }"
        ></div>

        <!-- 3. 悬浮引导说明气泡卡片 -->
        <div class="hw-tour-card" :style="cardStyle" @mousedown.stop @click.stop>
          <div class="card-top-row">
            <span class="step-badge">{{ step.badge }}</span>
            <button type="button" class="skip-btn" @click="$emit('skip')">
              跳过教程
            </button>
          </div>

          <h3 class="card-title">{{ step.title }}</h3>
          <p class="card-desc">{{ step.content }}</p>

          <!-- 第一步专属：一键加载示例分镜节点 -->
          <div v-if="step.showSampleBtn" class="sample-action-box">
            <button
              type="button"
              class="sample-load-btn"
              @click="$emit('load-sample')"
            >
              ✨ 一键加载「非遗竹编出海」示例节点到画布
            </button>
          </div>

          <div class="card-footer">
            <!-- 进度圆点 -->
            <div class="progress-dots">
              <span
                v-for="idx in totalSteps"
                :key="idx"
                class="dot"
                :class="{ active: idx - 1 === stepIndex, done: idx - 1 < stepIndex }"
              ></span>
            </div>

            <div class="nav-btns">
              <button
                v-if="stepIndex > 0"
                type="button"
                class="tour-btn secondary"
                @click="$emit('prev')"
              >
                上一步
              </button>
              <button
                type="button"
                class="tour-btn primary"
                @click="$emit('next')"
              >
                {{ stepIndex === totalSteps - 1 ? '🎉 完成并开始创作' : '下一步 →' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import type { TourStep } from './tourConfig';

const props = defineProps<{
  open: boolean;
  step: TourStep | null;
  stepIndex: number;
  totalSteps: number;
}>();

const emit = defineEmits<{
  (e: 'next'): void;
  (e: 'prev'): void;
  (e: 'skip'): void;
  (e: 'load-sample'): void;
}>();

const vw = ref(typeof window !== 'undefined' ? window.innerWidth : 1440);
const vh = ref(typeof window !== 'undefined' ? window.innerHeight : 900);

const spotRect = reactive({
  visible: false,
  x: 0,
  y: 0,
  w: 0,
  h: 0,
  radius: 12,
});

let rafId: number | null = null;

function measureTarget() {
  vw.value = window.innerWidth;
  vh.value = window.innerHeight;

  if (!props.open || !props.step) {
    spotRect.visible = false;
    return;
  }

  const el = document.querySelector(props.step.targetSelector) as HTMLElement | null;
  if (!el) {
    spotRect.visible = false;
    return;
  }

  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) {
    spotRect.visible = false;
    return;
  }

  const pad = 8;
  spotRect.visible = true;
  spotRect.x = Math.max(4, Math.round(rect.left - pad));
  spotRect.y = Math.max(4, Math.round(rect.top - pad));
  spotRect.w = Math.round(rect.width + pad * 2);
  spotRect.h = Math.round(rect.height + pad * 2);
  spotRect.radius = rect.width > 200 ? 16 : 999;
}

/** 连续追踪 450ms（适配右侧抽屉滑出动画期间的位置变化） */
function trackDuringTransition() {
  const start = performance.now();
  const loop = (now: number) => {
    measureTarget();
    if (now - start < 480) {
      rafId = requestAnimationFrame(loop);
    }
  };
  if (rafId) cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(loop);
}

const cardStyle = computed(() => {
  const cardW = 360;
  const cardH = props.step?.showSampleBtn ? 270 : 220;
  const gap = 18;

  if (!spotRect.visible || !props.step) {
    return {
      left: `${Math.round((vw.value - cardW) / 2)}px`,
      top: `${Math.round((vh.value - cardH) / 2)}px`,
    };
  }

  let left = spotRect.x;
  let top = spotRect.y + spotRect.h + gap;

  switch (props.step.placement) {
    case 'bottom':
      left = spotRect.x + spotRect.w / 2 - cardW / 2;
      top = spotRect.y + spotRect.h + gap;
      break;
    case 'right':
      left = spotRect.x + spotRect.w + gap;
      top = spotRect.y + spotRect.h / 2 - cardH / 2;
      break;
    case 'left':
      left = spotRect.x - cardW - gap;
      top = spotRect.y + spotRect.h / 2 - cardH / 2;
      break;
    case 'top-left':
      left = spotRect.x - cardW - gap;
      top = spotRect.y - cardH + spotRect.h;
      break;
  }

  // 视口边界安全钳制
  const clampedLeft = Math.max(16, Math.min(vw.value - cardW - 16, Math.round(left)));
  const clampedTop = Math.max(16, Math.min(vh.value - cardH - 16, Math.round(top)));

  return {
    left: `${clampedLeft}px`,
    top: `${clampedTop}px`,
  };
});

function handleKeydown(e: KeyboardEvent) {
  if (!props.open) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    emit('skip');
  } else if (e.key === 'ArrowRight' || e.key === 'Enter') {
    e.preventDefault();
    emit('next');
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    emit('prev');
  }
}

watch(
  () => [props.open, props.stepIndex, props.step?.targetSelector],
  async () => {
    await nextTick();
    trackDuringTransition();
  },
  { immediate: true }
);

onMounted(() => {
  window.addEventListener('resize', measureTarget);
  window.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId);
  window.removeEventListener('resize', measureTarget);
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped>
.hw-tour-root {
  position: fixed;
  inset: 0;
  z-index: 9500;
  pointer-events: none;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
}

.hw-tour-svg {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
}

.hw-backdrop-rect {
  pointer-events: auto;
}

.hw-spotlight-ring {
  position: fixed;
  pointer-events: none;
  border: 2px solid #38bdf8;
  box-shadow:
    0 0 0 4px rgba(56, 189, 248, 0.25),
    0 0 24px rgba(99, 102, 241, 0.75);
  transition: all 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  animation: tourPulse 1.6s infinite alternate ease-in-out;
}

@keyframes tourPulse {
  from {
    box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2), 0 0 18px rgba(99, 102, 241, 0.55);
  }
  to {
    box-shadow: 0 0 0 7px rgba(56, 189, 248, 0.38), 0 0 32px rgba(56, 189, 248, 0.9);
  }
}

.hw-tour-card {
  position: fixed;
  width: 360px;
  background: linear-gradient(165deg, #131b2e 0%, #0d1322 100%);
  border: 1px solid rgba(129, 140, 248, 0.55);
  border-radius: 16px;
  padding: 18px 20px;
  color: #f8fafc;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.85), 0 0 25px rgba(99, 102, 241, 0.25);
  pointer-events: auto;
  transition: left 0.28s cubic-bezier(0.16, 1, 0.3, 1), top 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  box-sizing: border-box;
}

.card-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.3);
  padding: 2px 8px;
  border-radius: 999px;
}

.skip-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 6px;
}

.skip-btn:hover {
  color: #f8fafc;
  text-decoration: underline;
}

.card-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
}

.card-desc {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.65;
  color: #cbd5e1;
  white-space: pre-line;
}

.sample-action-box {
  margin-bottom: 14px;
}

.sample-load-btn {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px dashed rgba(56, 189, 248, 0.6);
  background: rgba(56, 189, 248, 0.12);
  color: #7dd3fc;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.sample-load-btn:hover {
  background: rgba(56, 189, 248, 0.22);
  color: #ffffff;
  border-style: solid;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.progress-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #334155;
  transition: all 0.2s;
}

.dot.active {
  width: 18px;
  border-radius: 4px;
  background: #38bdf8;
}

.dot.done {
  background: #6366f1;
}

.nav-btns {
  display: flex;
  gap: 8px;
}

.tour-btn {
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.tour-btn.secondary {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.14);
  color: #cbd5e1;
}

.tour-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.tour-btn.primary {
  background: linear-gradient(135deg, #6366f1, #0ea5e9);
  color: #ffffff;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}

.tour-btn.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.6);
}

.tour-fade-enter-active,
.tour-fade-leave-active {
  transition: opacity 0.22s ease;
}

.tour-fade-enter-from,
.tour-fade-leave-to {
  opacity: 0;
}
</style>