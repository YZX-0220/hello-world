<template>
  <Teleport to="body">
    <div v-if="open" class="director-modal-mask" @click.self="emit('close')">
      <div class="director-modal-box" role="dialog" aria-modal="true" aria-labelledby="director-modal-title">
        <!-- 顶部标题与步骤条 -->
        <div class="director-header">
          <div class="title-area">
            <span class="director-badge">AI DIRECTOR WORKFLOW</span>
            <h3 id="director-modal-title" class="director-title">全片 AI 统筹规划向导</h3>
          </div>
          <div class="step-indicator">
            <div class="step-item" :class="{ active: step === 1, done: step > 1 }">
              <span class="step-num">1</span>
              <span class="step-label">总时长与剧本共创</span>
            </div>
            <div class="step-line" :class="{ done: step > 1 }"></div>
            <div class="step-item" :class="{ active: step === 2, done: step > 2 }">
              <span class="step-num">2</span>
              <span class="step-label">片段数与传播/风格</span>
            </div>
            <div class="step-line" :class="{ done: step > 2 }"></div>
            <div class="step-item" :class="{ active: step === 3 }">
              <span class="step-num">3</span>
              <span class="step-label">秒级分镜与节点生成</span>
            </div>
          </div>
          <button class="close-btn" @click="emit('close')" aria-label="关闭向导">✕</button>
        </div>

        <div v-if="errorMsg" class="director-error-bar" role="alert">
          <span>{{ errorMsg }}</span>
          <button type="button" @click="errorMsg = ''">×</button>
        </div>

        <!-- ================= STEP 1：设定总时长、输入创意、共创修改剧本 ================= -->
        <div v-if="step === 1" class="director-body">
          <div class="form-row-grid">
            <div class="field-block duration-block">
              <label for="total-duration-input">视频总时长（秒）</label>
              <div class="duration-input-wrap">
                <input
                  id="total-duration-input"
                  v-model.number="totalDuration"
                  type="number"
                  min="5"
                  max="300"
                  step="5"
                  :disabled="loading"
                />
                <span class="unit-tag">秒（推荐拆分为 {{ recommendedSegments }} 个片段）</span>
              </div>
              <div class="quick-duration-pills">
                <button
                  v-for="sec in [15, 30, 45, 60, 90]"
                  :key="sec"
                  type="button"
                  class="pill-btn"
                  :class="{ active: totalDuration === sec }"
                  @click="totalDuration = sec"
                >
                  {{ sec }}秒 ({{ Math.ceil(sec / 15) }}段)
                </button>
              </div>
            </div>

            <div class="field-block idea-block">
              <label for="user-idea-input">视频核心内容 / 想表达的思想</label>
              <div class="idea-input-row">
                <textarea
                  id="user-idea-input"
                  v-model="userIdea"
                  rows="3"
                  placeholder="简单描述你的视频内容或想表达的核心思想（例如：展示中国非遗竹编如何融入现代欧洲家庭，传递环保与东方美学）…"
                  :disabled="loading"
                ></textarea>
                <button
                  type="button"
                  class="primary-action-btn generate-outline-btn"
                  :disabled="loading || !userIdea.trim()"
                  @click="handleGenerateOutline(false)"
                >
                  {{ loading && !scriptDraft ? 'AI 构思中…' : scriptDraft ? '重新生成剧本' : '✨ AI 展开剧本' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 剧本主内容编辑与 AI 二次修改区 -->
          <div class="script-editor-section">
            <div class="section-header-row">
              <label for="script-draft-textarea">剧本主要内容（可直接在下方文本框内手动修改，或让 AI 按方向修改）</label>
              <span v-if="scriptDraft" class="status-tag">已生成草稿 · 可直接编辑</span>
            </div>
            <textarea
              id="script-draft-textarea"
              v-model="scriptDraft"
              class="script-textarea"
              rows="8"
              placeholder="点击上方“AI 展开剧本”后，AI 设计的剧本大纲将显示在这里。您可以直接在此修改文字…"
              :disabled="loading"
            ></textarea>

            <!-- 告诉 AI 修改方向 -->
            <div class="ai-revision-bar">
              <input
                v-model="revisionInstruction"
                type="text"
                class="revision-input"
                placeholder="觉得不够理想？输入你想改变的方向（如：开头节奏再快一点、加入人物特写反转），点击右侧确定让 AI 修改…"
                :disabled="loading || !scriptDraft.trim()"
                @keydown.enter.prevent="handleGenerateOutline(true)"
              />
              <button
                type="button"
                class="secondary-action-btn"
                :disabled="loading || !scriptDraft.trim() || !revisionInstruction.trim()"
                @click="handleGenerateOutline(true)"
              >
                {{ loading ? 'AI 修改中…' : '确定让 AI 修改' }}
              </button>
            </div>
          </div>
        </div>

        <!-- ================= STEP 2：选择片段数、传播方向（国家）与整体风格（多选） ================= -->
        <div v-else-if="step === 2" class="director-body">
          <div class="field-block">
            <label>1. 确认视频片段数量（以每片段 15 秒计算，{{ totalDuration }} 秒推荐 {{ recommendedSegments }} 个片段）</label>
            <div class="segment-counter-row">
              <button type="button" class="step-ctrl-btn" :disabled="segmentCount <= 1" @click="segmentCount--">−</button>
              <input v-model.number="segmentCount" type="number" min="1" max="20" class="segment-num-input" />
              <button type="button" class="step-ctrl-btn" :disabled="segmentCount >= 20" @click="segmentCount++">+</button>
              <span class="recommend-badge" @click="segmentCount = recommendedSegments">
                使用推荐值：{{ recommendedSegments }} 个片段（共约 {{ segmentCount * 15 }} 秒）
              </span>
            </div>
          </div>

          <div class="field-block">
            <div class="section-header-row">
              <label>2. 选择目标传播方向 / 国家地区（支持多选，自动关联文化禁忌与负面提示词库）</label>
              <span class="status-tag">已选 {{ selectedCountryCodes.length }} 个地区</span>
            </div>
            <div v-if="!countries.length" class="empty-hint">暂无国家配置数据，将使用全球通用传播规范</div>
            <div v-else class="pills-Wrap">
              <button
                v-for="c in countries"
                :key="c.code"
                type="button"
                class="select-pill"
                :class="{ active: selectedCountryCodes.includes(c.code) }"
                @click="toggleCountryCode(c.code)"
              >
                <span>{{ c.name }}</span>
                <span v-if="selectedCountryCodes.includes(c.code)" class="check-icon">✓</span>
              </button>
            </div>
            <div v-if="mergedNegativePreview" class="preview-mini-box">
              <strong>负面提示词：</strong>{{ mergedNegativePreview }}
            </div>
          </div>

          <div class="field-block">
            <div class="section-header-row">
              <label>3. 选择或描述视频整体视觉风格（支持多选，关联现有提示词模板库）</label>
              <span v-if="loadingTemplates" class="status-tag">正在读取模板库…</span>
              <span v-else class="status-tag">已选 {{ selectedStyleIds.length }} 个模板</span>
            </div>
            <div v-if="styleTemplates.length" class="pills-Wrap">
              <button
                v-for="tpl in styleTemplates"
                :key="tpl.id"
                type="button"
                class="select-pill style-pill"
                :class="{ active: selectedStyleIds.includes(tpl.id) }"
                @click="toggleStyleTemplate(tpl)"
              >
                <span>{{ tpl.name || tpl.title }}</span>
                <span v-if="selectedStyleIds.includes(tpl.id)" class="check-icon">✓</span>
              </button>
            </div>
            <textarea
              v-model="customStyleDesc"
              rows="3"
              class="style-textarea"
              placeholder="点击上方模板可多选组合，也可在此直接输入或修改整体视觉风格（如：4K纪录片质感、暖调丁达尔光效、平稳推轨镜头）…"
            ></textarea>
          </div>
        </div>

        <!-- ================= STEP 3：预览/微调各片段秒级提示词与全局节点 ================= -->
        <div v-else-if="step === 3 && planResult" class="director-body step3-body">
          <div class="step3-intro">
            已按 <strong>{{ planResult.segments.length }} 个片段</strong> 完成 AI 视频可执行语言转换（精确到 0-5秒 / 5-10秒 / 10-15秒）。确认无误后点击右下角按钮，将自动在画布上生成所有对应节点。
          </div>

          <!-- 三个全局提示词节点预览（均可微调） -->
          <div class="global-nodes-preview-grid">
            <div class="node-preview-card global-card">
              <div class="card-head">🎨 整体风格节点</div>
              <textarea v-model="planResult.style_node_content" rows="4"></textarea>
            </div>
            <div class="node-preview-card global-card">
              <div class="card-head">🚫 负面提示词节点</div>
              <textarea v-model="planResult.cultural_node_content" rows="4"></textarea>
            </div>
            <div class="node-preview-card global-card">
              <div class="card-head">🖼 图片素材提示词节点</div>
              <textarea v-model="planResult.image_asset_prompts" rows="4"></textarea>
            </div>
          </div>

          <!-- 分镜片段节点列表 -->
          <div class="segments-list-title">🎬 分镜片段节点（生成后节点名严格对应“片段一 ~ 片段N”）</div>
          <div class="segments-preview-list">
            <div v-for="seg in planResult.segments" :key="seg.index" class="node-preview-card segment-card">
              <div class="card-head">
                <span class="seg-badge">{{ seg.title }}</span>
                <span class="seg-duration">{{ seg.duration }} 秒（0-5s / 5-10s / 10-15s 动作拆解）</span>
              </div>
              <textarea v-model="seg.timeline_prompt" rows="4"></textarea>
            </div>
          </div>
        </div>

        <!-- 底部导航按钮栏 -->
        <div class="director-footer">
          <button type="button" class="ghost-btn" @click="emit('close')">取消</button>
          <div class="footer-right">
            <button v-if="step > 1" type="button" class="secondary-action-btn" :disabled="loading" @click="step--">
              ← 上一步
            </button>
            <button
              v-if="step === 1"
              type="button"
              class="primary-action-btn"
              :disabled="loading || !scriptDraft.trim()"
              @click="goToStep2"
            >
              下一步：配置片段与风格 →
            </button>
            <button
              v-else-if="step === 2"
              type="button"
              class="primary-action-btn"
              :disabled="loading || segmentCount < 1"
              @click="handleBreakdownScript"
            >
              {{ loading ? 'AI 正在拆解秒级分镜…' : '下一步：AI 拆解具体片段 →' }}
            </button>
            <button
              v-else-if="step === 3"
              type="button"
              class="confirm-create-btn"
              :disabled="loading || !planResult"
              @click="handleFinishAndCreateNodes"
            >
              ✓ 完成并生成全部画布节点
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import request from '@/utils/request';
import type { CulturalGuidanceItem } from '@/services/culturalGuidance';
import {
  generateDirectorOutline,
  generateDirectorBreakdown,
  type DirectorBreakdownResponse,
} from '@/services/director';

interface StyleTemplateOption {
  id: string;
  name?: string;
  title?: string;
  category?: string;
  content: string;
  negative_prompt?: string;
}

const props = defineProps<{
  open: boolean;
  conversationId: string;
  countries: CulturalGuidanceItem[];
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'apply-plan', payload: DirectorBreakdownResponse): void;
}>();

const step = ref<1 | 2 | 3>(1);
const loading = ref(false);
const errorMsg = ref('');

// Step 1 状态
const totalDuration = ref<number>(45);
const userIdea = ref('');
const scriptDraft = ref('');
const revisionInstruction = ref('');

// Step 2 状态（国家多选 + 模板多选）
const segmentCount = ref<number>(3);
const selectedCountryCodes = ref<string[]>([]);
const styleTemplates = ref<StyleTemplateOption[]>([]);
const loadingTemplates = ref(false);
const selectedStyleIds = ref<string[]>([]);
const customStyleDesc = ref<string>('4K高清电影质感，柔和自然光影，平稳镜头运动，画面色调统一');

// Step 3 状态
const planResult = ref<DirectorBreakdownResponse | null>(null);

const recommendedSegments = computed(() => {
  const dur = Number(totalDuration.value) || 15;
  return Math.max(1, Math.min(20, Math.ceil(dur / 15)));
});

watch(recommendedSegments, (val) => {
  if (step.value === 1) {
    segmentCount.value = val;
  }
});

// 打开弹窗时加载提示词模板库
watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return;
    errorMsg.value = '';
    if (!styleTemplates.value.length) {
      loadingTemplates.value = true;
      try {
        const res: any = await request.get('/prompt-templates');
        const items = Array.isArray(res) ? res : res?.items || [];
        styleTemplates.value = items;
      } catch {
        // 忽略错误，允许用户直接手填
      } finally {
        loadingTemplates.value = false;
      }
    }
  }
);

const selectedCountriesList = computed(() =>
  props.countries.filter((c) => selectedCountryCodes.value.includes(c.code))
);

const selectedTemplatesList = computed(() =>
  styleTemplates.value.filter((t) => selectedStyleIds.value.includes(t.id))
);

// 合并选中国家的负面提示词 + 选中模板中的负面提示词
const mergedNegativePreview = computed(() => {
  const parts: string[] = [];

  for (const c of selectedCountriesList.value) {
    if (c.negative_prompt?.trim()) {
      parts.push(c.negative_prompt.trim());
    }
  }

  for (const tpl of selectedTemplatesList.value) {
    if (tpl.category === 'negative' && tpl.content?.trim()) {
      parts.push(tpl.content.trim().replace(/^负面提示词[：:]\s*/, ''));
    }
    if (tpl.negative_prompt?.trim()) {
      parts.push(tpl.negative_prompt.trim().replace(/^负面提示词[：:]\s*/, ''));
    }
  }

  return [...new Set(parts.filter(Boolean))].join('、');
});

function toggleCountryCode(code: string) {
  const idx = selectedCountryCodes.value.indexOf(code);
  if (idx > -1) selectedCountryCodes.value.splice(idx, 1);
  else selectedCountryCodes.value.push(code);
}

/**
 * 切换模板多选状态，并将选中的多个模板内容实时同步到下方输入框
 */
function toggleStyleTemplate(tpl: StyleTemplateOption) {
  const idx = selectedStyleIds.value.indexOf(tpl.id);
  if (idx > -1) {
    selectedStyleIds.value.splice(idx, 1);
  } else {
    selectedStyleIds.value.push(tpl.id);
  }

  // 将所有已选中的模板内容合并到下方文本框供用户预览与二次编辑
  const combinedTexts = styleTemplates.value
    .filter((item) => selectedStyleIds.value.includes(item.id))
    .map((item) => item.content?.trim())
    .filter(Boolean);

  if (combinedTexts.length > 0) {
    customStyleDesc.value = combinedTexts.join('\n');
  } else {
    customStyleDesc.value = '4K高清电影质感，柔和自然光影，平稳镜头运动，画面色调统一';
  }
}

async function handleGenerateOutline(isRevision: boolean) {
  if (!props.conversationId) return;
  if (!isRevision && !userIdea.value.trim()) {
    errorMsg.value = '请先输入您的视频核心内容或想表达的思想';
    return;
  }
  loading.value = true;
  errorMsg.value = '';
  try {
    const res = await generateDirectorOutline(props.conversationId, {
      total_duration: Math.max(5, Number(totalDuration.value) || 45),
      user_idea: userIdea.value.trim() || '视频创作方案',
      current_draft: isRevision ? scriptDraft.value : null,
      revision_instruction: isRevision ? revisionInstruction.value.trim() : null,
    });
    scriptDraft.value = res.script_draft;
    if (isRevision) {
      revisionInstruction.value = '';
    }
  } catch (err: any) {
    errorMsg.value = err?.message || 'AI 生成剧本失败，请稍后重试';
  } finally {
    loading.value = false;
  }
}

function goToStep2() {
  if (!scriptDraft.value.trim()) {
    errorMsg.value = '请先让 AI 展开剧本或直接编写剧本主要内容';
    return;
  }
  segmentCount.value = recommendedSegments.value;
  step.value = 2;
}

async function handleBreakdownScript() {
  if (!props.conversationId) return;
  loading.value = true;
  errorMsg.value = '';
  try {
    const countryNames = selectedCountriesList.value.map((c) => c.name).join('、');
    const res = await generateDirectorBreakdown(
      props.conversationId,
      {
        total_duration: Math.max(5, Number(totalDuration.value) || 45),
        segment_count: Math.max(1, Math.min(20, Number(segmentCount.value) || 1)),
        script_draft: scriptDraft.value.trim(),
        country_codes: selectedCountryCodes.value,
        style_template_ids: selectedStyleIds.value,
        style_template_id: selectedStyleIds.value[0] || null,
        custom_style_desc: customStyleDesc.value.trim() || null,
      },
      {
        countryNames,
        negativePrompts: mergedNegativePreview.value,
        styleContent: customStyleDesc.value.trim(),
      }
    );

    // 确保负面提示词节点内容严格以“负面提示词：”开头
    if (res.cultural_node_content && !res.cultural_node_content.trim().startsWith('负面提示词：')) {
      res.cultural_node_content = `负面提示词：${res.cultural_node_content.trim()}`;
    }

    planResult.value = res;
    step.value = 3;
  } catch (err: any) {
    errorMsg.value = err?.message || '分镜拆解失败，请重试';
  } finally {
    loading.value = false;
  }
}

function handleFinishAndCreateNodes() {
  if (!planResult.value) return;
  emit('apply-plan', planResult.value);
  emit('close');
}
</script>

<style scoped>
.director-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(4, 6, 12, 0.82);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.director-modal-box {
  width: min(920px, 100%);
  max-height: 90vh;
  background: #0f1524;
  border: 1px solid rgba(129, 140, 248, 0.4);
  border-radius: 18px;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: #f1f5f9;
}

.director-header {
  padding: 18px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #131b2e;
}

.director-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.4px;
  color: #38bdf8;
}

.director-title {
  font-size: 18px;
  font-weight: 700;
  margin: 2px 0 0;
  color: #fff;
}

.step-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.step-item.active {
  color: #fff;
  font-weight: 600;
}

.step-item.done {
  color: #38bdf8;
}

.step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #1e293b;
  border: 1px solid #334155;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}

.step-item.active .step-num {
  background: #6366f1;
  border-color: #818cf8;
  color: #fff;
}

.step-item.done .step-num {
  background: rgba(56, 189, 248, 0.2);
  border-color: #38bdf8;
  color: #38bdf8;
}

.step-line {
  width: 24px;
  height: 1px;
  background: #334155;
}

.step-line.done {
  background: #38bdf8;
}

.close-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 18px;
  cursor: pointer;
}

.director-error-bar {
  background: rgba(239, 68, 68, 0.15);
  border-bottom: 1px solid rgba(239, 68, 68, 0.4);
  color: #fca5a5;
  padding: 8px 24px;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.director-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-row-grid {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-block label {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
}

.duration-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.duration-input-wrap input {
  width: 90px;
  background: #161f33;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 8px 10px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}

.unit-tag {
  font-size: 12px;
  color: #94a3b8;
}

.quick-duration-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill-btn {
  background: #172033;
  border: 1px solid #28354d;
  color: #94a3b8;
  padding: 4px 9px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
}

.pill-btn.active {
  background: rgba(99, 102, 241, 0.25);
  border-color: #818cf8;
  color: #fff;
}

.idea-input-row {
  display: flex;
  gap: 10px;
}

.idea-input-row textarea,
.script-textarea,
.style-textarea,
.node-preview-card textarea {
  width: 100%;
  background: #141c2e;
  border: 1px solid #2d3b55;
  border-radius: 10px;
  padding: 10px 12px;
  color: #f1f5f9;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
  outline: none;
}

.idea-input-row textarea:focus,
.script-textarea:focus,
.style-textarea:focus,
.node-preview-card textarea:focus {
  border-color: #818cf8;
}

.generate-outline-btn {
  flex-shrink: 0;
  align-self: stretch;
  padding: 0 18px;
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-tag {
  font-size: 11px;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
  padding: 2px 8px;
  border-radius: 4px;
}

.ai-revision-bar {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.revision-input {
  flex: 1;
  background: #141c2e;
  border: 1px solid #2d3b55;
  border-radius: 8px;
  padding: 8px 12px;
  color: #fff;
  font-size: 13px;
}

.segment-counter-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-ctrl-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
}

.segment-num-input {
  width: 70px;
  text-align: center;
  background: #141c2e;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 7px;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
}

.recommend-badge {
  font-size: 12px;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.15);
  border: 1px dashed rgba(129, 140, 248, 0.5);
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
}

.pills-Wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.select-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #172033;
  border: 1px solid #2b3954;
  color: #cbd5e1;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.select-pill:hover {
  border-color: #6366f1;
  color: #ffffff;
}

.select-pill.active {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-color: #818cf8;
  color: #fff;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}

.check-icon {
  font-size: 12px;
  font-weight: 700;
}

.preview-mini-box {
  background: #0b0f19;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: #a5f3fc;
}

.step3-intro {
  font-size: 13px;
  color: #cbd5e1;
  background: rgba(56, 189, 248, 0.08);
  border-left: 3px solid #38bdf8;
  padding: 8px 12px;
  border-radius: 4px;
}

.global-nodes-preview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.node-preview-card {
  background: #151d30;
  border: 1px solid #283652;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-head {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.segments-list-title {
  font-size: 14px;
  font-weight: 700;
  color: #c7d2fe;
  margin-top: 4px;
}

.segments-preview-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.seg-badge {
  background: #4f46e5;
  color: #fff;
  padding: 2px 10px;
  border-radius: 6px;
  font-size: 12px;
}

.seg-duration {
  font-size: 11px;
  color: #94a3b8;
}

.director-footer {
  padding: 14px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: #131b2e;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-right {
  display: flex;
  gap: 12px;
}

.primary-action-btn {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  border: none;
  padding: 9px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.secondary-action-btn {
  background: #24324d;
  color: #e2e8f0;
  border: 1px solid #3b4f75;
  padding: 9px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}

.confirm-create-btn {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  border: none;
  padding: 9px 22px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.35);
}

.ghost-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>