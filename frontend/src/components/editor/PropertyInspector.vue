<template>
  <aside class="property-inspector">
    <div class="panel-header">
      <span class="header-title">属性检查器</span>
      <span class="active-badge" v-if="activeClip">{{ activeClip.type.toUpperCase() }} 片段</span>
    </div>

    <!-- 1. 未选中片段：展示剪辑全局工程配置 -->
   <!-- 1. 未选中片段：可交互的全局草稿分辨率与基准帧率设置 -->
    <div v-if="!activeClip" class="inspector-content">
      <div class="group-header-row">
        <span class="group-title">全局草稿参数配置</span>
      </div>

      <!-- 截图同款概览卡片（实时联动下方选择） -->
      <div class="spec-summary-card">
        <div class="spec-col">
          <span class="spec-label">分辨率</span>
          <span class="spec-val">{{ timeline.width }} × {{ timeline.height }}</span>
        </div>
        <div class="spec-divider"></div>
        <div class="spec-col">
          <span class="spec-label">基准帧率</span>
          <span class="spec-val">{{ timeline.fps }} FPS</span>
        </div>
      </div>

      <!-- 分辨率预设选择 -->
      <div class="prop-field">
        <label>画布分辨率预设</label>
        <select 
          class="inspector-select" 
          :value="`${timeline.width}x${timeline.height}`"
          @change="handleResolutionChange(($event.target as HTMLSelectElement).value)"
        >
          <optgroup label="16:9 横屏标准">
            <option value="1280x720">720P 高清 (1280 × 720)</option>
            <option value="1920x1080">1080P 全高清 (1920 × 1080)</option>
            <option value="2560x1440">2K 超清 (2560 × 1440)</option>
            <option value="3840x2160">4K 极清 (3840 × 2160)</option>
          </optgroup>
          <optgroup label="9:16 竖屏短视频">
            <option value="720x1280">720P 竖屏 (720 × 1280)</option>
            <option value="1080x1920">1080P 竖屏 (1080 × 1920)</option>
            <option value="2160x3840">4K 竖屏 (2160 × 3840)</option>
          </optgroup>
          <optgroup label="1:1 方形画幅">
            <option value="1080x1080">1080P 方形 (1080 × 1080)</option>
          </optgroup>
        </select>
      </div>

      <!-- 自定义宽高输入 -->
      <div class="prop-field">
        <div class="field-title-row">
          <label>自定义宽高 (px)</label>
          <div class="xy-inputs-group">
            <div class="xy-box">
              <span class="axis-tag">W</span>
              <input 
                type="number" 
                min="320" 
                max="3840" 
                step="2"
                :value="timeline.width"
                @change="applyCustomWidth(parseInt(($event.target as HTMLInputElement).value, 10))"
                class="xy-num-input"
              />
            </div>
            <div class="xy-box">
              <span class="axis-tag">H</span>
              <input 
                type="number" 
                min="320" 
                max="3840" 
                step="2"
                :value="timeline.height"
                @change="applyCustomHeight(parseInt(($event.target as HTMLInputElement).value, 10))"
                class="xy-num-input"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 基准帧率选择 (FPS) -->
      <div class="prop-field">
        <div class="field-title-row">
          <label>基准帧率 (FPS)</label>
          <span class="val-pill">{{ timeline.fps }} FPS</span>
        </div>
        <div class="speed-presets">
          <button 
            v-for="fpsOpt in [24, 25, 30, 60]" 
            :key="fpsOpt" 
            :class="{ active: timeline.fps === fpsOpt }"
            @click="timeline.fps = fpsOpt"
          >
            {{ fpsOpt }} FPS
          </button>
        </div>
      </div>

      <div class="divider-line"></div>

      <div class="prop-row">
        <label>当前工程总时长</label>
        <span class="val-pill">{{ (timeline.duration_ms / 1000).toFixed(2) }} 秒</span>
      </div>

      <p class="select-hint">💡 修改分辨率或帧率将直接作用于实时渲染画布与最终导出的 MP4 成片。点击下方时间轴任意片段可切换至片段属性编辑。</p>
    </div>
    <!-- 2. 选中文本片段时：支持关键帧 + 自由拖拽 + X/Y 轴微调 + 样式调节 -->
    <div v-else-if="activeClip.type === 'text'" class="inspector-content">
      <div class="group-header-row">
        <span class="group-title">文本与字幕样式</span>
        <!-- 全局关键帧控制组 -->
        <div class="kf-control-cluster" title="添加/跳转关键帧">
          <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)" title="上一关键帧">‹</button>
          <button 
            class="kf-diamond-btn" 
            :class="{ active: !!currentKeyframeAtPlayhead }" 
            @click="toggleKeyframeAtPlayhead"
            :title="currentKeyframeAtPlayhead ? '当前帧已是关键帧 (点击删除)' : '在当前帧插入关键帧'"
          >◆</button>
          <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)" title="下一关键帧">›</button>
        </div>
      </div>
      
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
          <div class="right-val-kf">
            <span class="val-pill">{{ (activeClip as any).font_size || 26 }} px</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="12" 
          max="96" 
          step="1"
          :value="(activeClip as any).font_size || 26"
          @input="updateClipProp('font_size', parseFloat(($event.target as HTMLInputElement).value))"
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

      <div class="divider-line"></div>

      <div class="group-header-row">
        <span class="group-title">位置大小与关键帧动画</span>
        <div class="kf-control-cluster">
          <button class="kf-reset-icon" @click="resetClipPosition(activeClip)" title="重置位置">↺</button>
          <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
          <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
          <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
        </div>
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>水平位置 (X)</label>
          <div class="right-val-kf">
            <span class="val-pill">{{ (activeClip as any).position_x ?? 0 }} px</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="-960" 
          max="960" 
          step="5" 
          :value="(activeClip as any).position_x ?? 0"
          @input="updateClipProp('position_x', parseFloat(($event.target as HTMLInputElement).value))"
          class="range-slider"
        />
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>垂直位置 (Y)</label>
          <div class="right-val-kf">
            <span class="val-pill">{{ (activeClip as any).position_y ?? 0 }} px</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="-960" 
          max="500" 
          step="5" 
          :value="(activeClip as any).position_y ?? 0"
          @input="updateClipProp('position_y', parseFloat(($event.target as HTMLInputElement).value))"
          class="range-slider"
        />
      </div>

      <div class="divider-line"></div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>不透明度</label>
          <div class="right-val-kf">
            <span class="val-pill">{{ Math.round(((activeClip as any).opacity ?? 1) * 100) }}%</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="0" 
          max="1.0" 
          step="0.05" 
          :value="(activeClip as any).opacity ?? 1.0"
          @input="updateClipProp('opacity', parseFloat(($event.target as HTMLInputElement).value))"
          class="range-slider"
        />
      </div>
    </div>

    <!-- 3. 选中视频片段时：位置大小关键帧 + 200%音量关键帧 + 不透明度关键帧 -->
    <div v-else-if="activeClip.type === 'video'" class="inspector-content">
      <div class="group-header-row">
        <span class="group-title">位置大小</span>
        <div class="kf-control-cluster">
          <button class="kf-reset-icon" @click="resetVideoTransform(activeClip)" title="重置画面缩放与位置">↺</button>
          <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)" title="上一关键帧">‹</button>
          <button 
            class="kf-diamond-btn" 
            :class="{ active: !!currentKeyframeAtPlayhead }" 
            @click="toggleKeyframeAtPlayhead"
            :title="currentKeyframeAtPlayhead ? '当前帧已是关键帧 (点击移除)' : '添加关键帧'"
          >◆</button>
          <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)" title="下一关键帧">›</button>
        </div>
      </div>

      <!-- 画面缩放 -->
      <div class="prop-field">
        <div class="field-title-row">
          <label>缩放</label>
          <div class="right-val-kf">
            <span class="val-pill">{{ Math.round(((activeClip as any).scale ?? 1.0) * 100) }}%</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="0.2" 
          max="3.0" 
          step="0.02" 
          :value="(activeClip as any).scale ?? 1.0"
          @input="updateClipProp('scale', parseFloat(($event.target as HTMLInputElement).value))"
          class="range-slider"
        />
      </div>

      <!-- 位置 X / Y 双输入框 + 关键帧菱形 (还原图一剪映布局) -->
      <div class="prop-field">
        <div class="field-title-row">
          <label>位置</label>
          <div class="xy-inputs-group">
            <div class="xy-box">
              <span class="axis-tag">X</span>
              <input 
                type="number" 
                :value="Math.round((activeClip as any).position_x ?? 0)"
                @input="updateClipProp('position_x', parseFloat(($event.target as HTMLInputElement).value) || 0)"
                class="xy-num-input"
              />
            </div>
            <div class="xy-box">
              <span class="axis-tag">Y</span>
              <input 
                type="number" 
                :value="Math.round((activeClip as any).position_y ?? 0)"
                @input="updateClipProp('position_y', parseFloat(($event.target as HTMLInputElement).value) || 0)"
                class="xy-num-input"
              />
            </div>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <!-- 保留顺滑拖拽条 -->
        <div class="xy-sliders-sub">
          <input 
            type="range" 
            min="-960" 
            max="960" 
            step="5" 
            :value="(activeClip as any).position_x ?? 0"
            @input="updateClipProp('position_x', parseFloat(($event.target as HTMLInputElement).value))"
            class="range-slider"
            title="水平位置 X"
          />
          <input 
            type="range" 
            min="-960" 
            max="960" 
            step="5" 
            :value="(activeClip as any).position_y ?? 0"
            @input="updateClipProp('position_y', parseFloat(($event.target as HTMLInputElement).value))"
            class="range-slider"
            title="垂直位置 Y"
          />
        </div>
      </div>

      <div class="divider-line"></div>

      <div class="group-header-row">
        <span class="group-title">视频播放与混合属性</span>
      </div>

      <!-- 画面不透明度 + 关键帧 -->
      <div class="prop-field">
        <div class="field-title-row">
          <label>画面不透明度</label>
          <div class="right-val-kf">
            <span class="val-pill">{{ Math.round(((activeClip as any).opacity ?? 1) * 100) }}%</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="0" 
          max="1.0" 
          step="0.05" 
          :value="(activeClip as any).opacity ?? 1.0"
          @input="updateClipProp('opacity', parseFloat(($event.target as HTMLInputElement).value))"
          class="range-slider"
        />
      </div>

      <!-- 视频原始音量 (最高 200%) + 关键帧 -->
      <template v-if="!(activeClip as any).is_image_source">
        <div class="prop-field">
          <div class="field-title-row">
            <label>素材原始音量</label>
            <div class="right-val-kf">
              <span class="val-pill">{{ Math.round(((activeClip as any).volume ?? 1) * 100) }}%</span>
              <div class="kf-control-cluster">
                <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
                <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
                <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
              </div>
            </div>
          </div>
          <input 
            type="range" 
            min="0" 
            max="2.0" 
            step="0.05" 
            :value="(activeClip as any).volume ?? 1.0"
            @input="updateClipProp('volume', parseFloat(($event.target as HTMLInputElement).value))"
            class="range-slider"
          />
        </div>

        <div class="prop-field">
          <div class="field-title-row">
            <label>声音淡入时长</label>
            <span class="val-pill">{{ (((activeClip as any).fade_in_ms ?? 0) / 1000).toFixed(1) }}s</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="5000" 
            step="100" 
            :value="(activeClip as any).fade_in_ms ?? 0"
            @input="(activeClip as any).fade_in_ms = parseFloat(($event.target as HTMLInputElement).value)"
            class="range-slider"
          />
        </div>

        <div class="prop-field">
          <div class="field-title-row">
            <label>声音淡出时长</label>
            <span class="val-pill">{{ (((activeClip as any).fade_out_ms ?? 0) / 1000).toFixed(1) }}s</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="5000" 
            step="100" 
            :value="(activeClip as any).fade_out_ms ?? 0"
            @input="(activeClip as any).fade_out_ms = parseFloat(($event.target as HTMLInputElement).value)"
            class="range-slider"
          />
        </div>

        <div class="prop-field">
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
      </template>
    </div>

    <!-- 4. 选中音频片段时：最高 200% 音量增益（带关键帧）、淡入、淡出 -->
    <div v-else-if="activeClip.type === 'audio'" class="inspector-content">
      <div class="group-header-row">
        <span class="group-title">音频通道与关键帧</span>
        <div class="kf-control-cluster">
          <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)" title="上一关键帧">‹</button>
          <button 
            class="kf-diamond-btn" 
            :class="{ active: !!currentKeyframeAtPlayhead }" 
            @click="toggleKeyframeAtPlayhead"
            :title="currentKeyframeAtPlayhead ? '移除当前关键帧' : '添加音量关键帧'"
          >◆</button>
          <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)" title="下一关键帧">›</button>
        </div>
      </div>

      <div class="prop-field">
        <div class="field-title-row">
          <label>音频音量增益</label>
          <div class="right-val-kf">
            <span class="val-pill">{{ Math.round(((activeClip as any).volume ?? 1) * 100) }}%</span>
            <div class="kf-control-cluster">
              <button class="kf-nav-btn" :disabled="!prevKeyframe" @click="jumpToKeyframe(prevKeyframe)">‹</button>
              <button class="kf-diamond-btn" :class="{ active: !!currentKeyframeAtPlayhead }" @click="toggleKeyframeAtPlayhead">◆</button>
              <button class="kf-nav-btn" :disabled="!nextKeyframe" @click="jumpToKeyframe(nextKeyframe)">›</button>
            </div>
          </div>
        </div>
        <input 
          type="range" 
          min="0" 
          max="2.0" 
          step="0.05" 
          :value="(activeClip as any).volume ?? 1.0"
          @input="updateClipProp('volume', parseFloat(($event.target as HTMLInputElement).value))"
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
          :value="(activeClip as any).fade_in_ms ?? 0"
          @input="(activeClip as any).fade_in_ms = parseFloat(($event.target as HTMLInputElement).value)"
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
          :value="(activeClip as any).fade_out_ms ?? 0"
          @input="(activeClip as any).fade_out_ms = parseFloat(($event.target as HTMLInputElement).value)"
          class="range-slider"
        />
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import type { TimelineDocument, TimelineClip } from '../../types/clip';

const props = defineProps<{
  timeline: TimelineDocument;
  activeClip: TimelineClip | null;
  currentTimeMs?: number;
}>();

const emit = defineEmits<{
  (e: 'seek', timeMs: number): void;
}>();

// 判定两个时间点是否处于同一帧（容差 ±45ms）
const KEYFRAME_TOLERANCE_MS = 45;

// 当前播放指针相对于选中片段起点的毫秒偏移量
const currentClipOffsetMs = computed(() => {
  if (!props.activeClip) return 0;
  const cur = props.currentTimeMs ?? props.activeClip.start_ms;
  return Math.max(0, Math.min(props.activeClip.duration_ms, Math.round(cur - props.activeClip.start_ms)));
});

// 获取当前选中片段已按时间排序的关键帧列表
const sortedKeyframes = computed<any[]>(() => {
  const clip = props.activeClip as any;
  if (!clip || !Array.isArray(clip.keyframes)) return [];
  return [...clip.keyframes].sort((a, b) => a.offset_ms - b.offset_ms);
});

// 检查当前播放指针是否正好停在某个关键帧上
const currentKeyframeAtPlayhead = computed(() => {
  const offset = currentClipOffsetMs.value;
  return sortedKeyframes.value.find(kf => Math.abs(kf.offset_ms - offset) <= KEYFRAME_TOLERANCE_MS) || null;
});

// 查找当前指针左侧的“上一关键帧”
const prevKeyframe = computed(() => {
  const offset = currentClipOffsetMs.value;
  const list = sortedKeyframes.value.filter(kf => kf.offset_ms < offset - KEYFRAME_TOLERANCE_MS);
  return list.length > 0 ? list[list.length - 1] : null;
});

// 查找当前指针右侧的“下一关键帧”
const nextKeyframe = computed(() => {
  const offset = currentClipOffsetMs.value;
  return sortedKeyframes.value.find(kf => kf.offset_ms > offset + KEYFRAME_TOLERANCE_MS) || null;
});

// 点击菱形按钮：在当前帧插入或移除关键帧
function toggleKeyframeAtPlayhead() {
  const clip = props.activeClip as any;
  if (!clip) return;
  if (!Array.isArray(clip.keyframes)) {
    clip.keyframes = [];
  }

  const existing = currentKeyframeAtPlayhead.value;
  if (existing) {
    // 已存在则删除该关键帧
    clip.keyframes = clip.keyframes.filter((k: any) => k.id !== existing.id);
  } else {
    // 不存在则以当前片段的属性状态新建关键帧
    const newKf = {
      id: `kf_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      offset_ms: currentClipOffsetMs.value,
      scale: clip.scale ?? 1.0,
      position_x: clip.position_x ?? 0,
      position_y: clip.position_y ?? 0,
      opacity: clip.opacity ?? 1.0,
      volume: clip.volume ?? 1.0,
      font_size: clip.font_size ?? 26
    };
    clip.keyframes.push(newKf);
    clip.keyframes.sort((a: any, b: any) => a.offset_ms - b.offset_ms);
  }
}

// 点击左右箭头 < > 跳转到上一/下一关键帧，并把该关键帧的数值回填到面板显示
function jumpToKeyframe(kf: any) {
  if (!kf || !props.activeClip) return;
  const targetGlobalMs = props.activeClip.start_ms + kf.offset_ms;
  emit('seek', targetGlobalMs);
}

// 当在面板上拖动滑块修改属性时：更新片段属性；若指针正停在关键帧上，则同步更新该关键帧的值！
function updateClipProp(propName: string, val: number) {
  const clip = props.activeClip as any;
  if (!clip) return;
  clip[propName] = val;

  // 如果当前片段已经开启了关键帧（列表非空）：
  if (Array.isArray(clip.keyframes) && clip.keyframes.length > 0) {
    const curKf = currentKeyframeAtPlayhead.value;
    if (curKf) {
      // 指针正好在关键帧上：直接更新该关键帧记录的数值
      curKf[propName] = val;
    } else {
      // 剪映直觉交互：当片段已有关键帧A，用户把时间指针移到新位置B并直接拉动滑块修改属性时，自动在B处生成关键帧！
      const autoKf = {
        id: `kf_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        offset_ms: currentClipOffsetMs.value,
        scale: clip.scale ?? 1.0,
        position_x: clip.position_x ?? 0,
        position_y: clip.position_y ?? 0,
        opacity: clip.opacity ?? 1.0,
        volume: clip.volume ?? 1.0,
        font_size: clip.font_size ?? 26,
        [propName]: val
      };
      clip.keyframes.push(autoKf);
      clip.keyframes.sort((a: any, b: any) => a.offset_ms - b.offset_ms);
    }
  }
}


function resetVideoTransform(clip: any) {
  if (!clip) return;
  updateClipProp('scale', 1.0);
  updateClipProp('position_x', 0);
  updateClipProp('position_y', 0);
}

function resetClipPosition(clip: any) {
  if (!clip) return;
  updateClipProp('position_x', 0);
  updateClipProp('position_y', 0);
}

function applyPlaybackRate(clip: any, newRate: number) {
  if (!clip || !newRate || newRate <= 0) return;
  const oldRate = clip.playback_rate || 1.0;
  if (!clip._base_duration_ms) {
    clip._base_duration_ms = clip.duration_ms * oldRate;
  }
  clip.playback_rate = Number(newRate.toFixed(2));
  clip.duration_ms = Math.max(200, Math.round(clip._base_duration_ms / clip.playback_rate));

  let maxEnd = 0;
  for (const t of props.timeline.tracks) {
    for (const c of t.clips) {
      const end = c.start_ms + c.duration_ms;
      if (end > maxEnd) maxEnd = end;
    }
  }
  props.timeline.duration_ms = maxEnd;
}

// 切换预设分辨率
function handleResolutionChange(val: string) {
  const [wStr, hStr] = val.split('x');
  const w = parseInt(wStr, 10);
  const h = parseInt(hStr, 10);
  if (w >= 320 && h >= 320) {
    props.timeline.width = w;
    props.timeline.height = h;
  }
}

// 自定义宽度（确保为偶数以兼容视频编码器）
function applyCustomWidth(w: number) {
  if (!Number.isFinite(w)) return;
  const clamped = Math.max(320, Math.min(3840, w));
  props.timeline.width = clamped % 2 === 0 ? clamped : clamped + 1;
}

// 自定义高度
function applyCustomHeight(h: number) {
  if (!Number.isFinite(h)) return;
  const clamped = Math.max(320, Math.min(3840, h));
  props.timeline.height = clamped % 2 === 0 ? clamped : clamped + 1;
}
</script>

<style scoped>
/* 截图同款分辨率与基准帧率双栏展示卡 */
.spec-summary-card {
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 14px 10px;
}

.spec-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.spec-label {
  font-size: 11px;
  color: #71717a;
}

.spec-val {
  font-size: 15px;
  font-weight: 700;
  color: #f4f4f5;
  font-family: 'Times New Roman', serif, monospace;
  letter-spacing: 0.5px;
}

.spec-divider {
  width: 1px;
  height: 28px;
  background: rgba(255, 255, 255, 0.08);
}

.inspector-select {
  width: 100%;
  background: #1a1824;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 7px 10px;
  color: #f4f4f5;
  font-size: 12px;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s;
}

.inspector-select:hover,
.inspector-select:focus {
  border-color: #00e5ff;
}

.inspector-select option,
.inspector-select optgroup {
  background: #17151f;
  color: #f4f4f5;
}
.property-inspector {
  display: flex;
  flex-direction: column;
  background-color: #121118;
  height: 100%;
  min-height: 0;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  user-select: none;
}

.panel-header {
  height: 44px;
  flex-shrink: 0;
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
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.group-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.group-title { font-size: 12px; font-weight: 600; color: #e4e4e7; letter-spacing: 0.5px; }

.field-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.right-val-kf {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 剪映风格关键帧菱形控制簇 < ◆ > */
.kf-control-cluster {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: rgba(255, 255, 255, 0.03);
  padding: 1px 4px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.kf-nav-btn, .kf-reset-icon {
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 13px;
  line-height: 1;
  padding: 2px 3px;
  cursor: pointer;
  transition: color 0.15s;
}

.kf-nav-btn:hover:not(:disabled), .kf-reset-icon:hover {
  color: #ffffff;
}

.kf-nav-btn:disabled {
  opacity: 0.25;
  cursor: default;
}

.kf-diamond-btn {
  background: transparent;
  border: none;
  color: transparent;
  -webkit-text-stroke: 1.3px #a1a1aa;
  font-size: 11px;
  line-height: 1;
  padding: 2px 3px;
  cursor: pointer;
  transition: all 0.15s;
}

.kf-diamond-btn:hover {
  -webkit-text-stroke-color: #22d3ee;
}

/* 激活态：青色实心高亮菱形（还原图二） */
.kf-diamond-btn.active {
  color: #00e5ff;
  -webkit-text-stroke: 0px transparent;
  filter: drop-shadow(0 0 4px rgba(0, 229, 255, 0.6));
}

/* X / Y 坐标双输入框（还原图一） */
.xy-inputs-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.xy-box {
  display: flex;
  align-items: center;
  background: #1c1b24;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 2px 6px;
  width: 62px;
}

.axis-tag {
  font-size: 10px;
  color: #71717a;
  margin-right: 4px;
}

.xy-num-input {
  width: 100%;
  background: transparent;
  border: none;
  color: #fff;
  font-size: 11px;
  font-family: monospace;
  text-align: right;
  outline: none;
}

.xy-sliders-sub {
  display: flex;
  gap: 8px;
}

.divider-line {
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  margin: 2px 0;
}

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
  gap: 6px;
  font-size: 12px;
  color: #a1a1aa;
}

.val-pill {
  font-family: monospace;
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  color: #fff;
  font-size: 11px;
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
  accent-color: #00e5ff;
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