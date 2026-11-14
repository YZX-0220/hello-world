<template>
  <Teleport to="body">
    <div v-if="open" class="tpl-drawer-mask" @click.self="$emit('close')">
      <aside class="tpl-drawer-panel" role="dialog" aria-label="提示词模板库">
        <!-- 顶部栏 -->
        <div class="tpl-header">
          <div class="tpl-title-group">
            <span class="tpl-badge">PROMPT TEMPLATES</span>
            <h3>提示词模板库与版本管理</h3>
          </div>
          <div class="tpl-header-btns">
            <button v-if="viewMode === 'list'" class="primary-mini-btn" @click="openCreateForm">+ 新建模板</button>
            <button v-else class="ghost-mini-btn" @click="viewMode = 'list'">← 返回列表</button>
            <button class="close-btn" aria-label="关闭模板库" @click="$emit('close')">✕</button>
          </div>
        </div>

        <!-- 全局提示条 -->
        <div v-if="errorMsg" class="tpl-alert error">{{ errorMsg }}</div>
        <div v-if="successMsg" class="tpl-alert success">{{ successMsg }}</div>

        <!-- ================= 视图 1：模板列表与引用 ================= -->
        <div v-if="viewMode === 'list'" class="tpl-body">
          <!-- 筛选栏 -->
          <div class="filter-bar">
            <select v-model="filterScope" @change="fetchTemplates">
              <option value="all">全部来源</option>
              <option value="system">平台预置</option>
              <option value="user">我的模板</option>
            </select>
            <select v-model="filterCategory" @change="fetchTemplates">
              <option value="all">全部分类</option>
              <option value="positive">正向提示词</option>
              <option value="negative">负面提示词</option>
              <option value="cultural">国际文化</option>
              <option value="storyboard">分镜脚本</option>
            </select>
            <input
              v-model="searchKeyword"
              type="search"
              placeholder="搜索标题或内容…"
              @keydown.enter="fetchTemplates"
            />
          </div>

          <div v-if="loading" class="tpl-empty">正在加载模板列表…</div>
          <div v-else-if="!templates.length" class="tpl-empty">暂无匹配的提示词模板，点击右上角“+ 新建模板”创建</div>

          <div v-else class="tpl-cards">
            <div v-for="tpl in templates" :key="tpl.id" class="tpl-card">
              <div class="tpl-card-top">
                <div class="tpl-tags">
                  <span class="scope-tag" :class="tpl.scope">{{ tpl.scope === 'system' ? '预置' : '自定义' }}</span>
                  <span class="cat-tag">{{ categoryLabel(tpl.category) }}</span>
                  <span class="ver-tag">v{{ tpl.current_version }}</span>
                </div>
                <div class="tpl-card-ops">
                  <button class="text-op-btn" @click="openVersionHistory(tpl)" title="查看版本历史与回滚">历史版本</button>
                  <button v-if="tpl.scope === 'user'" class="text-op-btn" @click="openEditForm(tpl)">编辑</button>
                  <button v-if="tpl.scope === 'user'" class="text-op-btn danger" @click="handleDelete(tpl)">删除</button>
                </div>
              </div>

              <h4 class="tpl-name">{{ tpl.name }}</h4>
              <p v-if="tpl.description" class="tpl-desc">{{ tpl.description }}</p>

              <div class="tpl-preview-box">
                <div class="preview-line"><strong>正文：</strong>{{ tpl.content }}</div>
                <div v-if="tpl.negative_prompt" class="preview-line neg"><strong>负面词：</strong>{{ tpl.negative_prompt }}</div>
              </div>

              <div class="tpl-card-footer">
                <button class="inject-btn" @click="handleApplyTemplate(tpl, 'positive')">仅注入正文</button>
                <button
                  v-if="tpl.negative_prompt"
                  class="inject-btn secondary"
                  @click="handleApplyTemplate(tpl, 'negative')"
                >仅注入负面词</button>
                <button class="inject-btn accent" @click="handleApplyTemplate(tpl, 'both')">注入节点</button>
              </div>
            </div>
          </div>
        </div>

        <!-- ================= 视图 2：新建 / 编辑模板（自动递增版本号） ================= -->
        <form v-else-if="viewMode === 'form'" class="tpl-body tpl-form" @submit.prevent="handleSubmitForm">
          <h4 class="section-heading">{{ editingTemplate ? `编辑模板：${editingTemplate.name} (当前 v${editingTemplate.current_version})` : '新建自定义提示词模板' }}</h4>

          <div class="form-row">
            <label>模板标题 *</label>
            <input v-model="formState.name" required maxlength="100" placeholder="例如：东方山水写意分镜模板" />
          </div>

          <div class="form-row">
            <label>分类 *</label>
            <select v-model="formState.category">
              <option value="positive">正向提示词 (positive)</option>
              <option value="negative">负面提示词 (negative)</option>
              <option value="cultural">国际文化 (cultural)</option>
              <option value="storyboard">分镜脚本 (storyboard)</option>
            </select>
          </div>

          <div class="form-row">
            <label>模板描述</label>
            <input v-model="formState.description" maxlength="500" placeholder="简要说明适用场景…" />
          </div>

          <!-- 从当前工作台文本节点快速录入面板 -->
          <div v-if="availableTextNodes.length > 0" class="workspace-node-import-box">
            <div class="import-box-header">
              <span class="import-box-title">📥 从当前工作台文本节点快速录入：</span>
              <span class="import-box-sub">点击即可将节点内容填入下方表单</span>
            </div>
            <div class="import-node-pills">
              <div v-for="node in availableTextNodes" :key="node.id" class="import-node-item">
                <span class="node-badge-name" :title="node.content">{{ node.title }}</span>
                <button
                  type="button"
                  class="import-action-btn"
                  title="写入提示词正文"
                  @click="importNodeToForm(node, 'content')"
                >
                  + 填入正文
                </button>
                <button
                  type="button"
                  class="import-action-btn neg"
                  title="写入配套负面提示词"
                  @click="importNodeToForm(node, 'negative')"
                >
                  + 填入负面词
                </button>
              </div>
            </div>
          </div>
          <div v-else class="workspace-node-empty-tip">
            💡 当前工作台暂无已填写文字的文本节点，您可直接在下方输入或先在画布编写节点内容。
          </div>

          <div class="form-row">
            <label>提示词正文 * <small>（支持 <code v-pre>{{变量名}}</code> 占位符）</small></label>
            <textarea v-model="formState.content" rows="5" required placeholder="输入提示词或脚本正文…"></textarea>
          </div>

          <div class="form-row">
            <label>配套负面提示词（可选）</label>
            <textarea v-model="formState.negative_prompt" rows="3" placeholder="输入需规避的负面提示词…"></textarea>
          </div>

          <div v-if="editingTemplate" class="form-row">
            <label>版本变更说明（保存后将自动生成 v{{ editingTemplate.current_version + 1 }} 快照）</label>
            <input v-model="formState.change_note" maxlength="500" placeholder="例如：补充运镜细节描述" />
          </div>

          <div class="form-actions">
            <button type="button" class="ghost-mini-btn" @click="viewMode = 'list'">取消</button>
            <button type="submit" class="primary-mini-btn" :disabled="submitting">
              {{ submitting ? '保存中…' : editingTemplate ? '保存并生成新版本' : '创建模板 (v1)' }}
            </button>
          </div>
        </form>

        <!-- ================= 视图 3：多版本快照历史与一键回滚 ================= -->
        <div v-else-if="viewMode === 'versions' && activeVersionTemplate" class="tpl-body">
          <div class="version-banner">
            <div>
              <strong>{{ activeVersionTemplate.name }}</strong>
              <span> · 当前生效版本：v{{ activeVersionTemplate.current_version }}</span>
            </div>
          </div>

          <div v-if="loadingVersions" class="tpl-empty">正在读取版本快照历史…</div>
          <div v-else class="versions-layout">
            <!-- 左侧版本时间线 -->
            <div class="version-list">
              <div
                v-for="ver in versions"
                :key="ver.id"
                class="version-item"
                :class="{ selected: selectedSnapshot?.version === ver.version }"
                @click="selectVersionSnapshot(ver)"
              >
                <div class="ver-item-top">
                  <span class="ver-num">v{{ ver.version }}</span>
                  <span class="ver-source" :class="ver.source_type">{{ sourceTypeLabel(ver.source_type) }}</span>
                </div>
                <div class="ver-note">{{ ver.change_note || '无变更备注' }}</div>
                <div class="ver-time">{{ formatTime(ver.created_at) }}</div>
              </div>
            </div>

            <!-- 右侧快照详情与一键回滚 -->
            <div v-if="selectedSnapshot" class="snapshot-detail">
              <div class="snapshot-header">
                <h4>v{{ selectedSnapshot.version }} 快照详情</h4>
                <button
                  v-if="activeVersionTemplate.scope === 'user' && selectedSnapshot.version !== activeVersionTemplate.current_version"
                  class="rollback-btn"
                  :disabled="submitting"
                  @click="handleRollback(selectedSnapshot.version)"
                >
                  {{ submitting ? '回滚中…' : `↺ 一键回滚至此版本` }}
                </button>
                <span v-else-if="selectedSnapshot.version === activeVersionTemplate.current_version" class="current-badge">
                  当前生效版本
                </span>
              </div>

              <div class="snapshot-block">
                <label>标题快照</label>
                <div class="snapshot-box">{{ selectedSnapshot.name }}</div>
              </div>
              <div class="snapshot-block">
                <label>正文快照</label>
                <pre class="snapshot-box">{{ selectedSnapshot.content }}</pre>
              </div>
              <div v-if="selectedSnapshot.negative_prompt" class="snapshot-block">
                <label>负面提示词快照</label>
                <pre class="snapshot-box">{{ selectedSnapshot.negative_prompt }}</pre>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import {
  promptTemplateApi,
  type PromptTemplateItem,
  type PromptTemplateVersionItem,
  type TemplateCategory,
} from '@/services/promptTemplates';
import type { FlowNode } from '@/types/canvas';

const props = withDefaults(
  defineProps<{
    open: boolean;
    nodes?: FlowNode[];
  }>(),
  {
    nodes: () => [],
  }
);

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'inject', payload: { text: string; title?: string }): void;
}>();

const viewMode = ref<'list' | 'form' | 'versions'>('list');
const loading = ref(false);
const submitting = ref(false);
const errorMsg = ref('');
const successMsg = ref('');

const filterScope = ref('all');
const filterCategory = ref('all');
const searchKeyword = ref('');
const templates = ref<PromptTemplateItem[]>([]);

// 表单状态
const editingTemplate = ref<PromptTemplateItem | null>(null);
const formState = reactive({
  name: '',
  category: 'positive' as TemplateCategory,
  description: '',
  content: '',
  negative_prompt: '',
  change_note: '',
});

// 过滤出当前工作台中所有非空的文本节点
const availableTextNodes = computed(() =>
  (props.nodes || []).filter((n) => n.type === 'text' && n.content?.trim())
);

/**
 * 将选中的画布文本节点内容录入到新建/编辑模板表单中
 */
function importNodeToForm(node: FlowNode, targetField: 'content' | 'negative' | 'auto' = 'auto') {
  const rawText = (node.content || '').trim();
  if (!rawText) return;

  const isNegativeNode =
    targetField === 'negative' ||
    (targetField === 'auto' && (node.title.includes('负面') || rawText.startsWith('负面提示词：')));

  if (isNegativeNode) {
    const cleanedNeg = rawText.replace(/^负面提示词[：:]\s*/, '').trim();
    formState.negative_prompt = formState.negative_prompt?.trim()
      ? `${formState.negative_prompt.trim()}、${cleanedNeg}`
      : cleanedNeg;
  } else {
    formState.content = formState.content?.trim()
      ? `${formState.content.trim()}\n${rawText}`
      : rawText;

    if (!formState.name?.trim() && node.title) {
      formState.name = `${node.title}模板`;
    }
  }
}

// 版本历史状态
const activeVersionTemplate = ref<PromptTemplateItem | null>(null);
const loadingVersions = ref(false);
const versions = ref<PromptTemplateVersionItem[]>([]);
const selectedSnapshot = ref<PromptTemplateVersionItem | null>(null);

function clearMessages() {
  errorMsg.value = '';
  successMsg.value = '';
}

function categoryLabel(cat: string) {
  return ({
    positive: '正向提示词',
    negative: '负面提示词',
    cultural: '国际文化',
    storyboard: '分镜脚本',
  }[cat] || cat);
}

function sourceTypeLabel(type: string) {
  return ({
    init: '初始创建',
    edit: '内容修改',
    rollback: '版本回滚',
  }[type] || type);
}

function formatTime(iso: string) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

async function fetchTemplates() {
  loading.value = true;
  clearMessages();
  try {
    templates.value = await promptTemplateApi.list({
      scope: filterScope.value,
      category: filterCategory.value,
      q: searchKeyword.value,
    });
  } catch (err: any) {
    errorMsg.value = err?.message || '加载模板列表失败';
  } finally {
    loading.value = false;
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      viewMode.value = 'list';
      void fetchTemplates();
    }
  }
);

function openCreateForm() {
  clearMessages();
  editingTemplate.value = null;
  formState.name = '';
  formState.category = 'positive';
  formState.description = '';
  formState.content = '';
  formState.negative_prompt = '';
  formState.change_note = '';
  viewMode.value = 'form';
}

function openEditForm(tpl: PromptTemplateItem) {
  clearMessages();
  editingTemplate.value = tpl;
  formState.name = tpl.name;
  formState.category = tpl.category;
  formState.description = tpl.description || '';
  formState.content = tpl.content;
  formState.negative_prompt = tpl.negative_prompt || '';
  formState.change_note = '';
  viewMode.value = 'form';
}

async function handleSubmitForm() {
  submitting.value = true;
  clearMessages();
  try {
    if (editingTemplate.value) {
      const updated = await promptTemplateApi.update(editingTemplate.value.id, {
        name: formState.name,
        category: formState.category,
        description: formState.description,
        content: formState.content,
        negative_prompt: formState.negative_prompt,
        change_note: formState.change_note,
      });
      successMsg.value = `模板已更新至 v${updated.current_version}`;
    } else {
      await promptTemplateApi.create({
        name: formState.name,
        category: formState.category,
        description: formState.description,
        content: formState.content,
        negative_prompt: formState.negative_prompt,
      });
      successMsg.value = '新提示词模板创建成功 (v1)';
    }
    viewMode.value = 'list';
    await fetchTemplates();
  } catch (err: any) {
    errorMsg.value = err?.message || '保存失败';
  } finally {
    submitting.value = false;
  }
}

async function handleDelete(tpl: PromptTemplateItem) {
  if (!confirm(`确定删除自定义模板“${tpl.name}”吗？`)) return;
  clearMessages();
  try {
    await promptTemplateApi.remove(tpl.id);
    successMsg.value = '模板已删除';
    await fetchTemplates();
  } catch (err: any) {
    errorMsg.value = err?.message || '删除失败';
  }
}

async function openVersionHistory(tpl: PromptTemplateItem) {
  clearMessages();
  activeVersionTemplate.value = tpl;
  viewMode.value = 'versions';
  loadingVersions.value = true;
  versions.value = [];
  selectedSnapshot.value = null;
  try {
    const list = await promptTemplateApi.listVersions(tpl.id);
    versions.value = list;
    if (list.length > 0) {
      await selectVersionSnapshot(list[0]);
    }
  } catch (err: any) {
    errorMsg.value = err?.message || '获取版本历史失败';
  } finally {
    loadingVersions.value = false;
  }
}

async function selectVersionSnapshot(ver: PromptTemplateVersionItem) {
  if (!activeVersionTemplate.value) return;
  try {
    selectedSnapshot.value = await promptTemplateApi.getVersionDetail(activeVersionTemplate.value.id, ver.version);
  } catch {
    selectedSnapshot.value = ver;
  }
}

async function handleRollback(targetVersion: number) {
  if (!activeVersionTemplate.value) return;
  if (!confirm(`确定将“${activeVersionTemplate.value.name}”一键回滚至 v${targetVersion} 吗？系统将生成一条新的回滚版本记录。`)) return;
  submitting.value = true;
  clearMessages();
  try {
    const updated = await promptTemplateApi.rollback(
      activeVersionTemplate.value.id,
      targetVersion,
      `回滚至 v${targetVersion}`
    );
    activeVersionTemplate.value = updated;
    successMsg.value = `已成功回滚至 v${targetVersion}，当前最新为 v${updated.current_version}`;
    await openVersionHistory(updated);
    await fetchTemplates();
  } catch (err: any) {
    errorMsg.value = err?.message || '回滚失败';
  } finally {
    submitting.value = false;
  }
}

function handleApplyTemplate(tpl: PromptTemplateItem, mode: 'positive' | 'negative' | 'both') {
  const parts: string[] = [];
  if (mode === 'positive' || mode === 'both') {
    if (tpl.content?.trim()) parts.push(tpl.content.trim());
  }
  if (mode === 'negative' || mode === 'both') {
    if (tpl.negative_prompt?.trim()) {
      const rawNeg = tpl.negative_prompt.trim().replace(/^负面提示词[：:]\s*/, '');
      parts.push(`负面提示词：${rawNeg}`);
    }
  }
  const finalText = parts.join('\n\n');
  if (!finalText) return;
  emit('inject', { text: finalText, title: tpl.name });
  emit('close');
}
</script>

<style scoped>
.tpl-drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(4, 6, 12, 0.65);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: flex-start;
}

.tpl-drawer-panel {
  width: min(720px, 92vw);
  height: 100vh;
  background: #0f1524;
  border-right: 1px solid rgba(99, 102, 241, 0.35);
  box-shadow: 20px 0 50px rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  color: #f1f5f9;
  overflow: hidden;
}

.tpl-header {
  padding: 18px 22px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #131a2c;
}

.tpl-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.4px;
  color: #38bdf8;
}

.tpl-title-group h3 {
  margin: 2px 0 0;
  font-size: 17px;
  color: #f8fafc;
}

.tpl-header-btns {
  display: flex;
  align-items: center;
  gap: 10px;
}

.primary-mini-btn {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border: none;
  color: #fff;
  padding: 7px 14px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.ghost-mini-btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid #334155;
  color: #cbd5e1;
  padding: 6px 12px;
  border-radius: 7px;
  font-size: 12px;
  cursor: pointer;
}

.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 6px;
}

.tpl-alert {
  padding: 9px 22px;
  font-size: 12px;
}

.tpl-alert.error {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border-bottom: 1px solid rgba(239, 68, 68, 0.3);
}

.tpl-alert.success {
  background: rgba(16, 185, 129, 0.15);
  color: #6ee7b7;
  border-bottom: 1px solid rgba(16, 185, 129, 0.3);
}

.tpl-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.filter-bar {
  display: grid;
  grid-template-columns: 110px 130px 1fr;
  gap: 10px;
}

.filter-bar select,
.filter-bar input,
.tpl-form input,
.tpl-form select,
.tpl-form textarea {
  background: #172033;
  border: 1px solid #2c3b57;
  border-radius: 7px;
  color: #f1f5f9;
  padding: 8px 10px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
}

.tpl-empty {
  margin: auto;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  padding: 40px 0;
}

.tpl-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tpl-card {
  background: #151d30;
  border: 1px solid #263450;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tpl-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.tpl-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.scope-tag,
.cat-tag,
.ver-tag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
}

.scope-tag.system {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}

.scope-tag.user {
  background: rgba(129, 140, 248, 0.2);
  color: #a5b4fc;
}

.cat-tag {
  background: rgba(255, 255, 255, 0.07);
  color: #cbd5e1;
}

.ver-tag {
  background: rgba(16, 185, 129, 0.15);
  color: #6ee7b7;
  font-family: monospace;
}

.tpl-card-ops {
  display: flex;
  gap: 10px;
}

.text-op-btn {
  background: none;
  border: none;
  color: #93c5fd;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.text-op-btn:hover {
  text-decoration: underline;
}

.text-op-btn.danger {
  color: #fca5a5;
}

.tpl-name {
  margin: 0;
  font-size: 15px;
  color: #f8fafc;
}

.tpl-desc {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.tpl-preview-box {
  background: #0b101d;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 10px;
  font-size: 12px;
  line-height: 1.55;
  color: #cbd5e1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-line {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.preview-line.neg {
  color: #fda4af;
}

.tpl-card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

.inject-btn {
  background: #1e293b;
  border: 1px solid #334155;
  color: #e2e8f0;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.inject-btn.secondary {
  color: #fda4af;
  border-color: rgba(244, 63, 94, 0.35);
}

.inject-btn.accent {
  background: linear-gradient(135deg, #10b981, #059669);
  border: none;
  color: #fff;
  font-weight: 600;
}

.tpl-form .form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tpl-form label {
  font-size: 12px;
  color: #cbd5e1;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

.version-banner {
  padding: 10px 14px;
  background: #162038;
  border-radius: 8px;
  font-size: 13px;
  color: #c7d2fe;
}

.versions-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.version-item {
  padding: 10px 12px;
  background: #141c2e;
  border: 1px solid #26344e;
  border-radius: 8px;
  cursor: pointer;
}

.version-item.selected {
  border-color: #818cf8;
  background: #1c2742;
}

.ver-item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ver-num {
  font-weight: 700;
  color: #fff;
  font-size: 13px;
}

.ver-source {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  color: #94a3b8;
}

.ver-source.rollback {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.ver-note {
  font-size: 12px;
  color: #cbd5e1;
  margin-bottom: 4px;
}

.ver-time {
  font-size: 10px;
  color: #64748b;
}

.snapshot-detail {
  background: #131a2b;
  border: 1px solid #26344e;
  border-radius: 10px;
  padding: 14px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.snapshot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.snapshot-header h4 {
  margin: 0;
  font-size: 14px;
}

.rollback-btn {
  background: #d97706;
  border: none;
  color: #fff;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.current-badge {
  font-size: 11px;
  color: #34d399;
  background: rgba(16, 185, 129, 0.15);
  padding: 3px 8px;
  border-radius: 4px;
}

.snapshot-block label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.snapshot-box {
  background: #0b0f1a;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 9px 10px;
  font-size: 12px;
  line-height: 1.55;
  color: #e2e8f0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 0;
  font-family: inherit;
}

.workspace-node-import-box {
  background: rgba(99, 102, 241, 0.08);
  border: 1px dashed rgba(129, 140, 248, 0.4);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 4px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.import-box-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.import-box-title {
  color: #c7d2fe;
  font-weight: 600;
}

.import-box-sub {
  color: #64748b;
  font-size: 11px;
}

.import-node-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.import-node-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #141b2d;
  border: 1px solid #2b3954;
  border-radius: 8px;
  padding: 4px 6px 4px 10px;
}

.node-badge-name {
  font-size: 12px;
  color: #e2e8f0;
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 4px;
}

.import-action-btn {
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(129, 140, 248, 0.4);
  color: #a5b4fc;
  border-radius: 5px;
  padding: 2px 7px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.import-action-btn:hover {
  background: #6366f1;
  color: #fff;
}

.import-action-btn.neg {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}

.import-action-btn.neg:hover {
  background: #ef4444;
  color: #fff;
}

.workspace-node-empty-tip {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 4px;
}
</style>