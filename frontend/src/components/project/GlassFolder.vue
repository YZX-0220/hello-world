<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { paintFolderArt } from './folderArt'

interface FolderFile {
  name: string
  meta?: string
  art?: boolean
  danger?: boolean
  disabled?: boolean
  kind?: 'text' | 'image' | 'video' | 'perspective'
  body?: string
  image?: string
}

const props = withDefaults(
  defineProps<{
    label: string
    meta?: string
    seed?: string
    tone?: 'light' | 'dark'
    width?: number
    files?: FolderFile[]
    action?: 'add' | 'menu' | 'none'
    art?: boolean
    renaming?: boolean
    renamingValue?: string
    appear?: boolean
    disabled?: boolean
  }>(),
  {
    tone: 'dark',
    width: 300,
    files: () => [],
    action: 'none',
    art: true,
    appear: true,
    disabled: false,
  },
)

const emit = defineEmits<{
  (e: 'select', file: FolderFile, index: number): void
  (e: 'add'): void
  (e: 'rename'): void
  (e: 'delete'): void
  (e: 'open-change', open: boolean): void
  (e: 'rename-submit', value: string): void
  (e: 'rename-cancel'): void
}>()

const W = 340
const H = 272
const HEADROOM = 54
const FRONT_TOP = 74
const FRONT_H = H - FRONT_TOP

const BACK_PATH =
  'M0 56A22 22 0 0 1 22 34L146 34C170 34 172 0 198 0L318 0A22 22 0 0 1 340 22L340 250A22 22 0 0 1 318 272L22 272A22 22 0 0 1 0 250Z'
const FRONT_PATH =
  'M0 22A22 22 0 0 1 22 0L118 0C144 0 146 32 172 32L318 32A22 22 0 0 1 340 54L340 ' +
  (FRONT_H - 22) +
  'A22 22 0 0 1 318 ' +
  FRONT_H +
  'L22 ' +
  FRONT_H +
  'A22 22 0 0 1 0 ' +
  (FRONT_H - 22) +
  'Z'

const rootRef = ref<HTMLElement | null>(null)
const artRef = ref<HTMLCanvasElement | null>(null)
const open = ref(false)
const menuOpen = ref(false)
const entered = ref(!props.appear)
const renameValue = ref(props.renamingValue ?? props.label)

const rimId = `gf-rim-${Math.random().toString(36).slice(2, 9)}`
const k = computed(() => props.width / W)
const density = computed(() => Math.min(1.6, Math.max(1, typeof window === 'undefined' ? 1 : window.devicePixelRatio || 1)))

const rootStyle = computed(() => ({
  width: props.width + 'px',
  height: (H + HEADROOM) * k.value + 'px',
}))

const stageStyle = computed(() => ({
  transform: `translateY(${HEADROOM * k.value}px) scale(${k.value})`,
}))

const metaText = computed(() => props.meta ?? `${props.files.length} 项`)

const visible = computed(() => props.files.slice(0, 6))

function sheetStyle(index: number, count: number) {
  const slot = count <= 1 ? 0 : (index / (count - 1)) * 2 - 1
  const depth = index
  return {
    '--gf-slot': String(slot),
    '--gf-depth': String(depth),
    zIndex: String(count - index),
  } as Record<string, string>
}

function artCanvas(): HTMLCanvasElement | null {
  if (!artRef.value) return null
  if (!props.art) return null
  return artRef.value
}

function paintArt() {
  const el = artRef.value
  if (!el || !props.art) return
  const key = props.seed || props.label
  const src = paintFolderArt(key, W + 24, H + 24)
  el.width = src.width
  el.height = src.height
  const ctx = el.getContext('2d')
  if (!ctx) return
  ctx.drawImage(src, 0, 0)
  el.dataset.ready = 'true'
}

function onRootClick(e: MouseEvent) {
  if (menuOpen.value) {
    menuOpen.value = false
    return
  }
  if (!open.value) return
  if (e.target === rootRef.value) close()
}

function toggleMenu() {
  if (props.disabled || props.renaming) return
  menuOpen.value = !menuOpen.value
}

function pick(kind: 'rename' | 'delete') {
  menuOpen.value = false
  if (kind === 'rename') emit('rename')
  else emit('delete')
}

function toggle() {
  if (props.disabled || props.renaming) return
  open.value = !open.value
  emit('open-change', open.value)
}

function close() {
  if (!open.value) return
  open.value = false
  emit('open-change', false)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

let io: IntersectionObserver | null = null

onMounted(() => {
  paintArt()
  if (!props.appear) {
    entered.value = true
  } else if (typeof IntersectionObserver === 'undefined' || !rootRef.value) {
    entered.value = true
  } else {
    io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return
        io?.disconnect()
        io = null
        entered.value = true
      },
      { threshold: 0.2 },
    )
    io.observe(rootRef.value)
  }
  document.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  io?.disconnect()
  document.removeEventListener('keydown', onKey)
})

watch(
  () => [props.seed, props.art],
  () => paintArt(),
)

watch(
  () => props.renamingValue,
  (v) => {
    if (v !== undefined) renameValue.value = v
  },
)

watch(
  () => props.renaming,
  () => close(),
)

function submitRename() {
  const v = renameValue.value.trim()
  if (!v) {
    emit('rename-cancel')
    return
  }
  emit('rename-submit', v)
}
</script>

<template>
  <div
    ref="rootRef"
    class="gf-root"
    :data-tone="tone"
    :data-open="open || undefined"
    :data-entered="entered || undefined"
    :data-disabled="disabled || undefined"
    :style="rootStyle"
    @click="onRootClick"
  >
    <div class="gf-stage" :style="stageStyle">
      <div class="gf-tilt">
        <div class="gf-shadow" aria-hidden="true" />

        <div class="gf-back" :style="{ clipPath: `path('${BACK_PATH}')` }" aria-hidden="true">
          <canvas v-if="art" ref="artRef" class="gf-art" />
          <div class="gf-back-sheen" />
        </div>

        <div class="gf-front" :style="{ clipPath: `path('${FRONT_PATH}')` }">
          <div class="gf-tint" aria-hidden="true" />
          <div class="gf-spec" aria-hidden="true" />

        <svg class="gf-rim" :viewBox="`0 0 ${W} ${FRONT_H}`" aria-hidden="true">
          <defs>
            <linearGradient :id="rimId" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#ffffff" stop-opacity="0.72" />
              <stop offset="0.35" stop-color="#ffffff" stop-opacity="0.24" />
              <stop offset="1" stop-color="#ffffff" stop-opacity="0.08" />
            </linearGradient>
          </defs>
          <path :d="FRONT_PATH" :stroke="`url(#${rimId})`" />
        </svg>

          <button
            v-if="!renaming"
            type="button"
            class="gf-hit"
            :aria-expanded="open"
            :aria-label="`${open ? '收起' : '展开'} ${label}`"
            @click.stop="toggle"
          />

          <div v-if="renaming" class="gf-label gf-label--editing">
            <input
              v-model="renameValue"
              class="gf-rename"
              type="text"
              maxlength="120"
              autofocus
              @click.stop
              @keydown.enter.prevent="submitRename"
              @keydown.esc.stop="emit('rename-cancel')"
              @blur="submitRename"
            />
          </div>
          <div v-else class="gf-label">
            <span class="gf-title" :title="label">{{ label }}</span>
            <span class="gf-meta">{{ metaText }}</span>
          </div>
        </div>

        <div class="gf-files" :class="{ 'is-open': open }" role="list" :aria-label="`${label} 的内容`">
          <button
            v-for="(file, i) in visible"
            :key="`sheet-${i}`"
            type="button"
            role="listitem"
            class="gf-sheet"
            :class="{ 'gf-sheet--art': file.art, 'gf-sheet--danger': file.danger }"
            :style="sheetStyle(i, visible.length)"
            :tabindex="open ? 0 : -1"
            :disabled="!open || file.disabled"
            @click.stop="emit('select', file, i)"
          >
            <span class="gf-sheet-head">
              <span class="gf-sheet-name">{{ file.name }}</span>
              <span v-if="file.meta" class="gf-sheet-meta">{{ file.meta }}</span>
            </span>
            <img
              v-if="file.kind === 'image' && file.image"
              class="gf-sheet-image"
              :src="file.image"
              alt=""
              loading="lazy"
              draggable="false"
            />
            <p v-else-if="file.body" class="gf-sheet-body">{{ file.body }}</p>
            <span v-else-if="file.kind === 'video' || file.kind === 'perspective'" class="gf-sheet-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M9 7.5v9l7.5-4.5Z" /></svg>
            </span>
            <span v-else-if="!file.art" class="gf-lines" aria-hidden="true">
              <i style="width: 86%" />
              <i style="width: 92%" />
              <i style="width: 64%" />
            </span>
          </button>
        </div>

        <button
          v-if="action === 'add'"
          type="button"
          class="gf-key gf-key--add"
          :aria-label="`新建项目`"
          @click.stop="emit('add')"
        >
          <svg class="gf-glyph" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 4.5v15M4.5 12h15" />
          </svg>
        </button>

        <div v-else-if="action === 'menu' && !renaming" class="gf-key-wrap">
          <div v-if="menuOpen" class="gf-menu" role="menu">
            <button type="button" role="menuitem" class="gf-menu-item" @click.stop="pick('rename')">重命名</button>
            <button type="button" role="menuitem" class="gf-menu-item gf-menu-item--danger" @click.stop="pick('delete')">删除项目</button>
          </div>
          <button
            type="button"
            class="gf-key gf-key--menu"
            :aria-label="`${label} 的设置`"
            :aria-expanded="menuOpen"
            @click.stop="toggleMenu"
          >
            <svg class="gf-glyph" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4.6 19.4l4.3-1.1 9.2-9.2a2.2 2.2 0 0 0-3.1-3.1l-9.2 9.2-1.2 4.2Z" />
              <path d="M13.4 6.9l3.1 3.1" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gf-root {
  --gf-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  --gf-spring: cubic-bezier(0.34, 1.36, 0.5, 1);
  --gf-hinge: 0deg;
  --gf-lift: 30px;
  --gf-spread: 0px;
  --gf-fan: 0deg;
  --gf-stack: 15px;
  --gf-ink: #f4f4f6;
  --gf-ink-soft: rgba(244, 244, 246, 0.55);
  position: relative;
  display: inline-block;
  flex: none;
  vertical-align: top;
  isolation: isolate;
}

.gf-root:hover,
.gf-root:focus-within {
  --gf-hinge: -10deg;
  --gf-lift: -44px;
  --gf-spread: 8px;
  --gf-fan: 1.4deg;
  --gf-stack: 10px;
}

.gf-root[data-open] {
  --gf-hinge: -24deg;
  --gf-lift: -118px;
  --gf-spread: 42px;
  --gf-fan: 5.5deg;
  --gf-stack: 15px;
}

.gf-root[data-disabled] {
  opacity: 0.55;
  pointer-events: none;
}

.gf-stage {
  position: absolute;
  left: 0;
  top: 0;
  width: 340px;
  height: 272px;
  transform-origin: 0 0;
}

.gf-tilt {
  position: absolute;
  inset: 0;
}

.gf-shadow {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: -6px;
  height: 60px;
  border-radius: 40px;
  background: rgba(0, 0, 0, 0.62);
  filter: blur(22px);
  transition: opacity 0.9s var(--gf-ease);
}

.gf-back {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: linear-gradient(180deg, #23232a 0%, #101014 100%);
}

.gf-art {
  position: absolute;
  left: -12px;
  top: -12px;
  width: 364px;
  height: 296px;
  max-width: none;
  opacity: 0;
  filter: blur(12px);
  transition: opacity 1s var(--gf-ease), filter 1s var(--gf-ease);
}

.gf-art[data-ready] {
  opacity: 1;
  filter: none;
}

.gf-back-sheen {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.14) 0%, rgba(255, 255, 255, 0) 24%),
    radial-gradient(120% 80% at 80% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 60%);
  pointer-events: none;
}

.gf-front {
  position: absolute;
  left: 0;
  top: 74px;
  width: 340px;
  height: 198px;
  z-index: 10;
  -webkit-backdrop-filter: blur(22px) saturate(1.5);
  backdrop-filter: blur(22px) saturate(1.5);
  transform-origin: 50% 100%;
  transform: perspective(760px) rotateX(var(--gf-hinge));
  transition: transform 0.8s var(--gf-spring);
}

.gf-tint {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(18, 18, 22, 0.1) 0%,
    rgba(14, 14, 18, 0.42) 46%,
    rgba(8, 8, 10, 0.84) 100%
  );
}

.gf-spec {
  position: absolute;
  inset: 0;
  background: radial-gradient(260px 200px at 50% 26%, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0) 70%);
  mix-blend-mode: screen;
  opacity: 0.4;
  pointer-events: none;
}

.gf-rim {
  position: absolute;
  left: 0;
  top: 0;
  width: 340px;
  height: 198px;
  overflow: visible;
  pointer-events: none;
  fill: none;
}

.gf-rim path {
  stroke-width: 1.6;
  vector-effect: non-scaling-stroke;
}

.gf-root[data-open] .gf-front {
  pointer-events: none;
}

.gf-hit {
  all: unset;
  position: absolute;
  inset: 0;
  z-index: 1;
  cursor: pointer;
}

.gf-hit:focus-visible {
  outline: 2px solid #818cf8;
  outline-offset: -4px;
  border-radius: 18px;
}

.gf-label {
  position: absolute;
  z-index: 2;
  left: 26px;
  bottom: 30px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 200px;
  pointer-events: none;
  color: var(--gf-ink);
}

.gf-label--editing {
  pointer-events: auto;
}

.gf-title {
  font-size: 18px;
  font-weight: 500;
  letter-spacing: -0.012em;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gf-meta {
  font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 11.5px;
  letter-spacing: 0.03em;
  color: var(--gf-ink-soft);
  white-space: nowrap;
}

.gf-rename {
  width: 190px;
  padding: 6px 9px;
  border-radius: 8px;
  border: 1px solid rgba(129, 140, 248, 0.8);
  background: rgba(10, 12, 20, 0.92);
  color: #fff;
  font-size: 14px;
  outline: none;
}

.gf-files {
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  clip-path: inset(-400px -400px 10px -400px);
}

.gf-sheet {
  all: unset;
  box-sizing: border-box;
  position: absolute;
  left: 34px;
  top: 96px;
  width: 272px;
  height: 184px;
  border-radius: 16px;
  overflow: hidden;
  pointer-events: auto;
  cursor: default;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045) 0%, rgba(255, 255, 255, 0) 34%),
    linear-gradient(178deg, #23232b 0%, #1b1b22 52%, #141419 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.09),
    inset 0 0 0 0.5px rgba(255, 255, 255, 0.06);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 0 0 0.5px rgba(0, 0, 0, 0.18),
    0 12px 28px -8px rgba(0, 0, 0, 0.55);
  transform-origin: 50% 100%;
  transform: translate(calc(var(--gf-slot) * var(--gf-spread)), calc(var(--gf-lift) + var(--gf-depth) * var(--gf-stack)))
    rotate(calc(var(--gf-slot) * var(--gf-fan)));
  transition: transform 0.75s var(--gf-spring) calc(var(--gf-depth) * 40ms), box-shadow 0.4s var(--gf-ease);
}

.gf-files.is-open .gf-sheet {
  cursor: pointer;
}

.gf-files.is-open .gf-sheet:hover,
.gf-files.is-open .gf-sheet:focus-visible {
  transform: translate(calc(var(--gf-slot) * var(--gf-spread)), calc(var(--gf-lift) + var(--gf-depth) * var(--gf-stack) - 18px))
    rotate(calc(var(--gf-slot) * var(--gf-fan) * 0.6));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95), 0 0 0 0.5px rgba(0, 0, 0, 0.2), 0 22px 40px -12px rgba(0, 0, 0, 0.6);
}

.gf-sheet:focus-visible {
  outline: 2px solid #818cf8;
  outline-offset: 2px;
}

.gf-sheet--danger:not(:disabled) .gf-sheet-name {
  color: #b3261e;
}

.gf-sheet-head {
  position: absolute;
  left: 14px;
  right: 14px;
  top: 12px;
  z-index: 1;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  white-space: nowrap;
}

.gf-sheet-name {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12.5px;
  font-weight: 600;
  color: rgba(246, 245, 250, 0.92);
}

.gf-sheet-meta {
  flex: none;
  font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 10px;
  letter-spacing: 0.02em;
  color: rgba(246, 245, 250, 0.42);
}

.gf-lines {
  position: absolute;
  left: 14px;
  right: 14px;
  top: 44px;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.gf-lines i {
  display: block;
  height: 5px;
  border-radius: 3px;
  background: rgba(246, 245, 250, 0.1);
}

.gf-lines i:first-child {
  height: 9px;
  margin-bottom: 4px;
  background: rgba(246, 245, 250, 0.18);
}

.gf-key {
  all: unset;
  box-sizing: border-box;
  position: absolute;
  right: 22px;
  bottom: 22px;
  z-index: 12;
  width: 58px;
  height: 58px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  cursor: pointer;
  color: #111113;
  background: radial-gradient(120% 90% at 50% 0%, #ffffff 0%, #ececee 55%, #d2d2d6 100%);
  box-shadow:
    inset 0 1px 0 #fff,
    inset 0 -3px 8px rgba(0, 0, 0, 0.14),
    0 0 0 1px rgba(0, 0, 0, 0.4),
    0 14px 22px -8px rgba(0, 0, 0, 0.7);
  transition: transform 0.35s var(--gf-spring), opacity 0.6s var(--gf-ease);
}

.gf-delete {
  all: unset;
  position: absolute;
  right: 4px;
  bottom: -26px;
  padding: 4px 2px;
  font-size: 11.5px;
  letter-spacing: 0.02em;
  color: #b3261e;
  cursor: pointer;
}

.gf-delete:hover {
  text-decoration: underline;
}

.gf-key:hover {
  transform: translateY(-2px);
}

.gf-key:active {
  transform: translateY(0) scale(0.93);
}

.gf-key-wrap {
  position: absolute;
  right: 22px;
  bottom: 22px;
  z-index: 12;
}

.gf-key-wrap .gf-key {
  position: static;
  right: auto;
  bottom: auto;
}

.gf-menu {
  position: absolute;
  right: 0;
  bottom: 68px;
  min-width: 132px;
  padding: 6px;
  border-radius: 14px;
  background: rgba(22, 22, 26, 0.94);
  box-shadow: 0 18px 34px -10px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(14px);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.gf-menu-item {
  all: unset;
  padding: 7px 10px;
  border-radius: 9px;
  font-size: 12.5px;
  color: rgba(246, 245, 250, 0.9);
  cursor: pointer;
}

.gf-menu-item:hover {
  background: rgba(255, 255, 255, 0.09);
}

.gf-menu-item--danger {
  color: #ff8b80;
}

.gf-sheet-image {
  position: absolute;
  left: 0;
  right: 0;
  top: 38px;
  bottom: 0;
  width: 100%;
  height: calc(100% - 38px);
  object-fit: cover;
  display: block;
}

.gf-sheet-body {
  position: absolute;
  left: 14px;
  right: 14px;
  top: 38px;
  bottom: 12px;
  margin: 0;
  overflow: hidden;
  font-size: 11.5px;
  line-height: 1.62;
  letter-spacing: 0.002em;
  color: rgba(236, 234, 242, 0.68);
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
  word-break: break-word;
}

.gf-sheet-mark {
  position: absolute;
  inset: 38px 0 0;
  display: grid;
  place-items: center;
}

.gf-sheet-mark svg {
  width: 30px;
  height: 30px;
  fill: rgba(246, 245, 250, 0.3);
}

.gf-glyph {
  width: 26px;
  height: 26px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
}

.gf-root:not([data-entered]) .gf-back,
.gf-root:not([data-entered]) .gf-back-sheen {
  translate: 0 22px;
  opacity: 0;
}

.gf-root:not([data-entered]) .gf-sheet {
  translate: 0 -120px;
  opacity: 0;
}

.gf-root:not([data-entered]) .gf-front {
  translate: 0 46px;
  opacity: 0;
}

.gf-root:not([data-entered]) .gf-key {
  opacity: 0;
  scale: 0.6;
}

.gf-back,
.gf-back-sheen {
  transition: translate 1s var(--gf-ease), opacity 0.9s var(--gf-ease);
}

.gf-sheet {
  transition:
    transform 0.75s var(--gf-spring) calc(var(--gf-depth) * 40ms),
    box-shadow 0.4s var(--gf-ease),
    translate 0.9s var(--gf-ease) calc(0.18s + var(--gf-depth) * 90ms),
    opacity 0.9s var(--gf-ease) calc(0.18s + var(--gf-depth) * 90ms);
}

.gf-front {
  transition: transform 0.8s var(--gf-spring), translate 1s var(--gf-ease) 0.42s, opacity 1s var(--gf-ease) 0.42s;
}

@media (prefers-reduced-motion: reduce) {
  .gf-root,
  .gf-root * {
    transition-duration: 0.001s !important;
    transition-delay: 0s !important;
    animation: none !important;
  }
}
</style>
