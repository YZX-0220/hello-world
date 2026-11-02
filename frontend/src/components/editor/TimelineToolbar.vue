<template>
  <nav class="timeline-toolbar">
    <!-- 左侧快捷动作组 -->
    <div class="tools-left">
      <!-- 分割/剪切 -->
      <button 
        class="tool-btn" 
        :disabled="!hasSelectedClip" 
        @click="$emit('split')" 
        title="分割片段 (快捷键: C)"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M9.64 7.64c.23-.5.36-1.05.36-1.64 0-2.21-1.79-4-4-4S2 3.79 2 6s1.79 4 4 4c.59 0 1.14-.13 1.64-.36L10 12l-2.36 2.36C7.14 14.13 6.59 14 6 14c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4c0-.59-.13-1.14-.36-1.64L12 14l7 7h3v-1L9.64 7.64zM6 8c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm0 12c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm9.5-9c-.41 0-.75-.17-1-.41L18 7.09V4h-3.09l-3.5 3.5c-.24-.25-.41-.59-.41-1 0-1.66 1.34-3 3-3s3 1.34 3 3-1.34 3-3 3z"/>
        </svg>
        <span>剪切</span>
      </button>

      <!-- 删除 -->
      <button 
        class="tool-btn" 
        :disabled="!hasSelectedClip" 
        @click="$emit('delete')" 
        title="删除选中片段 (快捷键: Delete)"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
        </svg>
        <span>删除</span>
      </button>

      <span class="tool-sep"></span>

      <!-- 撤销 -->
      <button class="tool-btn" @click="$emit('undo')" title="撤销操作 (Ctrl+Z)">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/>
        </svg>
      </button>

      <!-- 重做 -->
      <button class="tool-btn" @click="$emit('redo')" title="恢复操作 (Ctrl+Shift+Z)">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z"/>
        </svg>
      </button>

      <span class="tool-sep"></span>

      <!-- 添加标记 -->
      <button class="tool-btn" @click="$emit('addMarker')" title="添加时间标记 (M)">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z"/>
        </svg>
        <span>标记</span>
      </button>
    </div>

    <!-- 右侧吸附开关与轴缩放滑块 -->
    <div class="tools-right">
      <!-- 磁吸吸附开关 -->
      <button 
        class="tool-btn icon-toggle" 
        :class="{ active: isSnappingEnabled }" 
        @click="$emit('toggleSnap')" 
        title="自动吸附开关"
      >
        <span>🧲 吸附</span>
      </button>

      <span class="tool-sep"></span>

      <!-- 放宽/变窄轴长度控制 -->
      <div class="zoom-controller">
        <button class="zoom-step-btn" @click="$emit('zoomOut')" title="轴变窄 (缩小)">−</button>
        <input 
          type="range" 
          min="0.2" 
          max="5.0" 
          step="0.1" 
          :value="zoomScale" 
          @input="$emit('setZoom', Number(($event.target as HTMLInputElement).value))"
          class="zoom-slider"
          title="时间轴视图比例"
        />
        <button class="zoom-step-btn" @click="$emit('zoomIn')" title="轴放宽 (放大)">+</button>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
defineProps<{
  hasSelectedClip: boolean;
  zoomScale: number;
  isSnappingEnabled: boolean;
}>();

defineEmits<{
  (e: 'split'): void;
  (e: 'delete'): void;
  (e: 'undo'): void;
  (e: 'redo'): void;
  (e: 'addMarker'): void;
  (e: 'toggleSnap'): void;
  (e: 'zoomIn'): void;
  (e: 'zoomOut'): void;
  (e: 'setZoom', val: number): void;
}>();
</script>

<style scoped>
.timeline-toolbar {
  height: 40px;
  background-color: #17151f;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  user-select: none;
}

.tools-left, .tools-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  color: #cbd5e1;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.tool-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.tool-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.tool-sep {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}

.icon-toggle.active {
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
}

.zoom-controller {
  display: flex;
  align-items: center;
  gap: 6px;
}

.zoom-step-btn {
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 16px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.zoom-step-btn:hover { color: #fff; }

.zoom-slider {
  width: 90px;
  accent-color: #6366f1;
}
</style>