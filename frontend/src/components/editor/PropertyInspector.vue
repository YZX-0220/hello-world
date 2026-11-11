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

// 当时间轴指针移动且当前片段含有关键帧时，自动将插值后的数值同步展示到右侧面板滑块上
watch(
  () => props.currentTimeMs,
  () => {
    const clip = props.activeClip as any;
    if (!clip || !Array.isArray(clip.keyframes) || clip.keyframes.length === 0) return;

    const kfs = sortedKeyframes.value;
    const offset = currentClipOffsetMs.value;

    const interp = (key: string, fallback: number): number => {
      if (kfs.length === 1) return kfs[0][key] ?? fallback;
      if (offset <= kfs[0].offset_ms) return kfs[0][key] ?? fallback;
      if (offset >= kfs[kfs.length - 1].offset_ms) return kfs[kfs.length - 1][key] ?? fallback;

      for (let i = 0; i < kfs.length - 1; i++) {
        const a = kfs[i];
        const b = kfs[i + 1];
        if (offset >= a.offset_ms && offset <= b.offset_ms) {
          const span = Math.max(1, b.offset_ms - a.offset_ms);
          const ratio = (offset - a.offset_ms) / span;
          const va = a[key] ?? fallback;
          const vb = b[key] ?? fallback;
          return Number((va + (vb - va) * ratio).toFixed(2));
        }
      }
      return fallback;
    };

    if (clip.type === 'video') {
      clip.scale = interp('scale', clip.scale ?? 1.0);
      clip.position_x = Math.round(interp('position_x', clip.position_x ?? 0));
      clip.position_y = Math.round(interp('position_y', clip.position_y ?? 0));
      clip.opacity = interp('opacity', clip.opacity ?? 1.0);
      clip.volume = interp('volume', clip.volume ?? 1.0);
    } else if (clip.type === 'text') {
      clip.position_x = Math.round(interp('position_x', clip.position_x ?? 0));
      clip.position_y = Math.round(interp('position_y', clip.position_y ?? 0));
      clip.opacity = interp('opacity', clip.opacity ?? 1.0);
      clip.font_size = Math.round(interp('font_size', clip.font_size ?? 26));
    } else if (clip.type === 'audio') {
      clip.volume = interp('volume', clip.volume ?? 1.0);
    }
  }
);

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
</script>

<style scoped>
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