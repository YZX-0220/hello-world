<template>
  <aside class="property-inspector">
    <div class="panel-header">
      <span class="header-title">属性检查器</span>
      <span class="active-badge" v-if="activeClip">{{ activeClip.type.toUpperCase() }} 片段</span>
    </div>

    <!-- 1. 未选中片段：展示剪辑全局工程配置 -->
    <div v-if="!activeClip" class="inspector-content empty-selection">
      <div class="group-title">全局草稿参数</div>
      <div class="prop-row">
        <label>分辨率宽度</label>
        <span class="val-pill">{{ timeline.width }} px</span>
      </div>
      <div class="prop-row">
        <label>分辨率高度</label>
        <span class="val-pill">{{ timeline.height }} px</span>
      </div>
      <div class="prop-row">
        <label>基准帧率</label>
        <span class="val-pill">{{ timeline.fps }} FPS</span>
      </div>
      <div class="prop-row">
        <label>总时长</label>
        <span class="val-pill">{{ (timeline.duration_ms / 1000).toFixed(1) }} 秒</span>
      </div>
      <p class="select-hint">在下方时间轴点击任意片段以展开对应属性</p>
    </div>

    <!-- 2. 选中文本片段时：实时响应文字、字号、颜色、背景、位置、透明度 -->
    <div v-else-if="activeClip.type === 'text'" class="inspector-content">
      <div class="group-title">文本与字幕样式</div>
      
      <div class="prop-field">
        <label>字幕文案内容</label>
        <textarea 
          v-model="(activeClip as any).text" 
          rows="3" 
          class="text-input"
          placeholder="请输入文本..."
        ></textarea>
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>字号大小</label>
          <span class="val-pill">{{ (activeClip as any).font_size || 26 }} px</span>
        </div>
        <input 
          type="range" 
          min="12" 
          max="96" 
          step="1"
          v-model.number="(activeClip as any).font_size" 
          class="range-slider"
        />
      </div>

      <div class="prop-row">
        <label>文字颜色</label>
        <input type="color" v-model="(activeClip as any).color" class="color-picker" />
      </div>

      <div class="prop-row">
        <label>对齐方式</label>
        <div class="align-group">
          <button 
            :class="{ active: (activeClip as any).align === 'left' }" 
            @click="(activeClip as any).align = 'left'"
          >左</button>
          <button 
            :class="{ active: !(activeClip as any).align || (activeClip as any).align === 'center' }" 
            @click="(activeClip as any).align = 'center'"
          >中</button>
          <button 
            :class="{ active: (activeClip as any).align === 'right' }" 
            @click="(activeClip as any).align = 'right'"
          >右</button>
        </div>
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>垂直位置微调 (Y)</label>
          <span class="val-pill">{{ (activeClip as any).position_y ?? 0 }} px</span>
        </div>
        <input 
          type="range" 
          min="-800" 
          max="300" 
          step="5" 
          v-model.number="(activeClip as any).position_y" 
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>不透明度</label>
          <span class="val-pill">{{ Math.round(((activeClip as any).opacity ?? 1) * 100) }}%</span>
        </div>
        <input 
          type="range" 
          min="0.1" 
          max="1.0" 
          step="0.05" 
          v-model.number="(activeClip as any).opacity" 
          class="range-slider"
        />
      </div>
    </div>

    <!-- 3. 选中视频片段时：缩放、位置拖动、倍速、音量、淡入淡出 -->
    <div v-else-if="activeClip.type === 'video'" class="inspector-content">
      <div class="group-title">画面变换与自由拖拽</div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>画面缩放</label>
          <span class="val-pill">{{ Math.round(((activeClip as any).scale ?? 1.0) * 100) }}%</span>
        </div>
        <input 
          type="range" 
          min="0.2" 
          max="3.0" 
          step="0.02" 
          :value="(activeClip as any).scale ?? 1.0"
          @input="(activeClip as any).scale = parseFloat(($event.target as HTMLInputElement).value)"
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>水平位置 (X)</label>
          <span class="val-pill">{{ (activeClip as any).position_x ?? 0 }} px</span>
        </div>
        <input 
          type="range" 
          min="-960" 
          max="960" 
          step="5" 
          :value="(activeClip as any).position_x ?? 0"
          @input="(activeClip as any).position_x = parseFloat(($event.target as HTMLInputElement).value)"
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>垂直位置 (Y)</label>
          <span class="val-pill">{{ (activeClip as any).position_y ?? 0 }} px</span>
        </div>
        <input 
          type="range" 
          min="-960" 
          max="960" 
          step="5" 
          :value="(activeClip as any).position_y ?? 0"
          @input="(activeClip as any).position_y = parseFloat(($event.target as HTMLInputElement).value)"
          class="range-slider"
        />
      </div>

      <div class="prop-row">
        <button class="reset-transform-btn" @click="resetVideoTransform(activeClip)">
          ↺ 重置画面缩放与位置
        </button>
      </div>

      <div class="divider-line"></div>

      <div class="group-title">视频播放属性</div>

      <div class="prop-field" v-if="!(activeClip as any).is_image_source">
        <div class="field-title-row">
          <label>播放倍速</label>
          <span class="val-pill">{{ (activeClip as any).playback_rate ?? 1 }}x</span>
        </div>
        <div class="speed-presets">
          <button 
            v-for="rate in [0.5, 1.0, 1.5, 2.0]" 
            :key="rate" 
            :class="{ active: ((activeClip as any).playback_rate ?? 1) === rate }"
            @click="applyPlaybackRate(activeClip, rate)"
          >
            {{ rate }}x
          </button>
        </div>
        <input 
          type="range" 
          min="0.2" 
          max="4.0" 
          step="0.1" 
          :value="(activeClip as any).playback_rate ?? 1.0"
          @input="applyPlaybackRate(activeClip, parseFloat(($event.target as HTMLInputElement).value))"
          class="range-slider"
        />
      </div>

      <div class="prop-field" v-if="!(activeClip as any).is_image_source">
        <div class="field-title-row">
          <label>素材原始音量</label>
          <span class="val-pill">{{ Math.round(((activeClip as any).volume ?? 1) * 100) }}%</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="1.0" 
          step="0.05" 
          v-model.number="(activeClip as any).volume" 
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>画面不透明度</label>
          <span class="val-pill">{{ Math.round(((activeClip as any).opacity ?? 1) * 100) }}%</span>
        </div>
        <input 
          type="range" 
          min="0.1" 
          max="1.0" 
          step="0.05" 
          v-model.number="(activeClip as any).opacity" 
          class="range-slider"
        />
      </div>
    </div>

    <!-- 4. 选中音频片段时：音量增益、淡入时长、淡出时长 -->
    <div v-else-if="activeClip.type === 'audio'" class="inspector-content">
      <div class="group-title">音频通道属性</div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>音频音量增益</label>
          <span class="val-pill">{{ Math.round(((activeClip as any).volume ?? 1) * 100) }}%</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="1.0" 
          step="0.05" 
          v-model.number="(activeClip as any).volume" 
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>淡入时长</label>
          <span class="val-pill">{{ (((activeClip as any).fade_in_ms ?? 0) / 1000).toFixed(1) }}s</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="5000" 
          step="100" 
          v-model.number="(activeClip as any).fade_in_ms" 
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>淡出时长</label>
          <span class="val-pill">{{ (((activeClip as any).fade_out_ms ?? 0) / 1000).toFixed(1) }}s</span>
        </div>
        <input 
          type="range" 
          min="0" 
          max="5000" 
          step="100" 
          v-model.number="(activeClip as any).fade_out_ms" 
          class="range-slider"
        />
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { TimelineDocument, TimelineClip } from '../../types/clip';

const props = defineProps<{
  timeline: TimelineDocument;
  activeClip: TimelineClip | null;
}>();

function resetVideoTransform(clip: any) {
  if (!clip) return;
  clip.scale = 1.0;
  clip.position_x = 0;
  clip.position_y = 0;
}

// 修改播放倍速时，同步调整片段在时间轴上的实际持续时长并重算总时长
function applyPlaybackRate(clip: any, newRate: number) {
  if (!clip || !newRate || newRate <= 0) return;
  const oldRate = clip.playback_rate || 1.0;
  // 记录原始基准时长
  if (!clip._base_duration_ms) {
    clip._base_duration_ms = clip.duration_ms * oldRate;
  }
  clip.playback_rate = Number(newRate.toFixed(2));
  clip.duration_ms = Math.max(200, Math.round(clip._base_duration_ms / clip.playback_rate));

  // 同步更新工程总时长
  let maxEnd = 0;
  for (const t of props.timeline.tracks) {
    for (const c of t.clips) {
      const end = c.start_ms + c.duration_ms;
      if (end > maxEnd) maxEnd = end;
    }
  }
  props.timeline.duration_ms = maxEnd;
}
</script>

<style scoped>
.field-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.divider-line {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 0;
}

.reset-transform-btn {
  width: 100%;
  padding: 6px 0;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.reset-transform-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: #6366f1;
  color: #fff;
}

.property-inspector {
  display: flex;
  flex-direction: column;
  background-color: #121118;
  height: 100%;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  user-select: none;
}

.panel-header {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #17151f;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-title { font-size: 13px; font-weight: 600; color: #e4e4e7; }
.active-badge { font-size: 10px; background: rgba(99, 102, 241, 0.2); color: #818cf8; padding: 2px 6px; border-radius: 4px; }

.inspector-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.group-title { font-size: 12px; font-weight: 600; color: #818cf8; letter-spacing: 0.5px; }

.prop-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #a1a1aa;
}

.prop-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: #a1a1aa;
}

.val-pill {
  font-family: monospace;
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
  color: #fff;
}

.text-input {
  background: #1a1824;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 8px;
  color: #fff;
  font-size: 12px;
  resize: vertical;
}

.range-slider {
  width: 100%;
  accent-color: #6366f1;
}

.color-picker {
  background: transparent;
  border: none;
  width: 32px;
  height: 24px;
  cursor: pointer;
}

.align-group, .speed-presets {
  display: flex;
  gap: 4px;
}

.align-group button, .speed-presets button {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  padding: 4px 0;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

.align-group button.active, .speed-presets button.active {
  background: #6366f1;
  color: #fff;
}

.empty-selection {
  justify-content: center;
  align-items: center;
  text-align: center;
}

.select-hint { font-size: 12px; color: #52525b; margin-top: 24px; }
</style>