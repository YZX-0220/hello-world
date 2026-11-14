<template>
  <div class="admin-shell">
    <div class="admin-ambient" aria-hidden="true" />

    <header class="admin-top">
      <button class="pill-btn" @click="router.push('/tv')" title="返回 TV 频道">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        <span>返回 TV 频道</span>
      </button>

      <div class="top-center">
        <p class="kicker">HELLO WORLD · TV</p>
        <h1 class="admin-title">素材管理</h1>
      </div>

      <button class="pill-btn pill-primary" @click="openCreateModal">+ 录入新素材</button>
    </header>

    <main class="admin-main">
      <section class="admin-sheet">
        <div class="sheet-head">
          <span class="sheet-label">全部作品</span>
          <span class="sheet-count">{{ adminItems.length }} 条</span>
        </div>

        <p v-if="loading" class="state-hint">正在读取素材列表…</p>
        <p v-else-if="adminItems.length === 0" class="state-hint">还没有素材，点右上角「录入新素材」开始。</p>

        <ul v-else class="item-list">
          <li v-for="item in adminItems" :key="item.id" class="item-row">
            <div class="item-main">
              <p class="item-title">{{ item.title }}</p>
              <p class="item-meta">
                <span class="chip">{{ item.model_name }}</span>
                <span class="dot-sep" aria-hidden="true">·</span>
                <span>{{ new Date(item.updated_at).toLocaleString() }}</span>
              </p>
            </div>
            <span :class="['status-pill', item.status]">
              <i class="status-dot" aria-hidden="true" />
              {{ item.status === 'published' ? '已发布' : '草稿' }}
            </span>
            <div class="row-actions">
              <button class="ghost-btn" @click="togglePublish(item)">
                {{ item.status === 'published' ? '下架' : '发布' }}
              </button>
              <button class="ghost-btn is-danger" @click="deleteItem(item)">删除</button>
            </div>
          </li>
        </ul>
      </section>
    </main>

    <div v-if="showModal" class="modal-mask" @click.self="showModal = false">
      <div class="modal-box" role="dialog" aria-modal="true" aria-label="录入新视频素材">
        <div class="modal-head">
          <p class="kicker">NEW ENTRY</p>
          <h3 class="modal-title">录入新视频素材</h3>
        </div>

        <label class="field">
          <span class="field-label">作品标题</span>
          <input v-model="form.title" placeholder="如：赛博朋克雨夜街道" />
        </label>

        <label class="field">
          <span class="field-label">使用模型</span>
          <input v-model="form.model_name" placeholder="如：Veo 2 或 Seedance 2.5" />
        </label>

        <label class="field">
          <span class="field-label">提示词 / Markdown 描述</span>
          <textarea v-model="form.description" rows="4" placeholder="填写生成该视频的 Prompt" />
        </label>

        <label class="field">
          <span class="field-label">MP4 视频文件</span>
          <input class="file-input" type="file" accept="video/mp4" @change="handleFileChange" />
        </label>

        <div class="modal-actions">
          <button class="ghost-btn" @click="showModal = false">取消</button>
          <button class="pill-btn pill-primary" :disabled="submitting" @click="submitCreate">
            {{ submitting ? '正在上传保存…' : '立即发布' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const loading = ref(false);
const submitting = ref(false);
const adminItems = ref<any[]>([]);
const showModal = ref(false);
const selectedFile = ref<File | null>(null);

const form = ref({
  title: '',
  model_name: '',
  description: ''
});

// 获取所有作品（草稿 + 已发布）
async function loadAdminList() {
  loading.value = true;
  try {
    const res = await fetch('/api/v1/admin/material-library?limit=50', {
      credentials: 'include'
    });
    if (res.status === 403 || res.status === 401) {
      alert('非管理员禁止访问该页面');
      router.push('/tv');
      return;
    }
    const data = await res.json();
    adminItems.value = data.items || [];
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function openCreateModal() {
  form.value = { title: '', model_name: '', description: '' };
  selectedFile.value = null;
  showModal.value = true;
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files?.[0]) {
    selectedFile.value = target.files[0];
  }
}

// 获取 CSRF Cookie 保护
function getCsrfToken(): string {
  const match = document.cookie.match(/hw_csrf=([^;]+)/);
  return match ? match[1] : '';
}

// 提交上传与录入
async function submitCreate() {
  if (!form.value.title || !form.value.model_name || !form.value.description || !selectedFile.value) {
    alert('请将表单项及 MP4 文件填写完整');
    return;
  }

  submitting.value = true;
  try {
    // 1. 上传视频资产
    const formData = new FormData();
    formData.append('file', selectedFile.value);
    formData.append('kind', 'video');

    const uploadRes = await fetch('/api/v1/admin/material-library/uploads', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'X-CSRF-Token': getCsrfToken()
      },
      body: formData
    });

    if (!uploadRes.ok) throw new Error('视频文件上传失败');
    const assetData = await uploadRes.json();

    // 2. 录入作品并直接发布
    const createRes = await fetch('/api/v1/admin/material-library', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfToken()
      },
      body: JSON.stringify({
        title: form.value.title,
        model_name: form.value.model_name,
        description: form.value.description,
        video_asset_id: assetData.id,
        cover_asset_id: null,
        status: 'published'
      })
    });

    if (!createRes.ok) throw new Error('录入作品条目失败');
    showModal.value = false;
    await loadAdminList();
  } catch (err: any) {
    alert(err.message || '操作失败');
  } finally {
    submitting.value = false;
  }
}

// 切换发布/下架
async function togglePublish(item: any) {
  const nextStatus = item.status === 'published' ? 'draft' : 'published';
  try {
    const res = await fetch(`/api/v1/admin/material-library/${item.id}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfToken()
      },
      body: JSON.stringify({
        expected_version: item.version,
        status: nextStatus
      })
    });
    if (!res.ok) throw new Error('修改状态失败，请刷新重试');
    await loadAdminList();
  } catch (e: any) {
    alert(e.message);
  }
}

// 软删除
async function deleteItem(item: any) {
  if (!confirm(`确定删除《${item.title}》吗？`)) return;
  try {
    const res = await fetch(`/api/v1/admin/material-library/${item.id}?expected_version=${item.version}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: {
        'X-CSRF-Token': getCsrfToken()
      }
    });
    if (!res.ok) throw new Error('删除失败');
    await loadAdminList();
  } catch (e: any) {
    alert(e.message);
  }
}

onMounted(() => {
  loadAdminList();
});
</script>

<style scoped>
.admin-shell {
  position: relative;
  min-height: 100dvh;
  padding: 26px clamp(20px, 4vw, 56px) 56px;
  box-sizing: border-box;
  overflow: hidden;
  background: radial-gradient(120% 85% at 50% 12%, #191b26 0%, #0d0e14 46%, #040406 100%);
  color: #f2f1ee;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.admin-ambient {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(58% 42% at 18% 8%, rgba(139, 127, 245, 0.13), transparent 70%),
    radial-gradient(50% 40% at 84% 82%, rgba(240, 214, 176, 0.07), transparent 70%);
}

.admin-top {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 18px;
}

.admin-top > .pill-btn:first-child {
  justify-self: start;
  width: fit-content;
}

.admin-top > .pill-btn:last-child {
  justify-self: end;
  width: fit-content;
}

.top-center {
  text-align: center;
}

.kicker {
  margin: 0 0 6px;
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: rgba(226, 224, 240, 0.45);
}

.admin-title {
  margin: 0;
  font-family: 'Songti SC', 'Noto Serif SC', 'Source Han Serif SC', Georgia, serif;
  font-size: clamp(26px, 3vw, 34px);
  font-weight: 600;
  letter-spacing: 0.12em;
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 15px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: #f2f1ee;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.pill-btn svg {
  width: 15px;
  height: 15px;
}

.pill-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.24);
}

.pill-primary {
  border-color: rgba(167, 155, 255, 0.45);
  background: linear-gradient(180deg, rgba(139, 127, 245, 0.34) 0%, rgba(99, 88, 210, 0.26) 100%);
  color: #f6f4ff;
}

.pill-primary:hover {
  background: linear-gradient(180deg, rgba(139, 127, 245, 0.48) 0%, rgba(99, 88, 210, 0.38) 100%);
}

.admin-main {
  position: relative;
  z-index: 1;
  max-width: 1080px;
  margin: clamp(22px, 3.4vh, 38px) auto 0;
}

.admin-sheet {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.028);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(10px);
  padding: 8px 8px 18px;
}

.sheet-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 16px 18px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.sheet-label {
  font-size: 13px;
  letter-spacing: 0.16em;
  color: rgba(240, 238, 246, 0.66);
}

.sheet-count {
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: rgba(240, 238, 246, 0.4);
}

.state-hint {
  margin: 0;
  padding: 56px 18px;
  text-align: center;
  color: rgba(240, 238, 246, 0.45);
  font-size: 13px;
}

.item-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.item-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 18px;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: background 0.2s ease;
}

.item-row:last-child {
  border-bottom: none;
}

.item-row:hover {
  background: rgba(255, 255, 255, 0.035);
}

.item-main {
  min-width: 0;
}

.item-title {
  margin: 0 0 6px;
  font-family: 'Songti SC', 'Noto Serif SC', 'Source Han Serif SC', Georgia, serif;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.02em;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 12px;
  color: rgba(240, 238, 246, 0.42);
}

.chip {
  padding: 2px 9px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 11px;
  letter-spacing: 0.04em;
  color: rgba(226, 224, 240, 0.72);
}

.dot-sep {
  color: rgba(240, 238, 246, 0.24);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 11px;
  border-radius: 999px;
  font-size: 11.5px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.status-pill.published {
  color: #7ee2b8;
  background: rgba(45, 212, 160, 0.12);
  border: 1px solid rgba(45, 212, 160, 0.22);
}

.status-pill.draft {
  color: #f2c879;
  background: rgba(240, 190, 90, 0.11);
  border: 1px solid rgba(240, 190, 90, 0.22);
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.row-actions {
  display: flex;
  gap: 8px;
}

.ghost-btn {
  height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  background: transparent;
  color: rgba(240, 238, 246, 0.72);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}

.ghost-btn:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}

.ghost-btn.is-danger {
  border-color: rgba(240, 120, 120, 0.24);
  color: rgba(248, 150, 150, 0.9);
}

.ghost-btn.is-danger:hover {
  background: rgba(240, 90, 90, 0.14);
  color: #ffb4b4;
}

.ghost-btn:disabled,
.pill-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(3, 4, 8, 0.72);
  backdrop-filter: blur(6px);
}

.modal-box {
  width: min(520px, 100%);
  max-height: 86dvh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 26px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: linear-gradient(180deg, #1a1a24 0%, #101017 100%);
  box-shadow: 0 40px 90px rgba(0, 0, 0, 0.65);
}

.modal-head .kicker {
  margin-bottom: 4px;
}

.modal-title {
  margin: 0;
  font-family: 'Songti SC', 'Noto Serif SC', 'Source Han Serif SC', Georgia, serif;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.field-label {
  font-size: 12px;
  letter-spacing: 0.08em;
  color: rgba(240, 238, 246, 0.52);
}

.field input,
.field textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 13px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.035);
  color: #f4f2ef;
  font-family: inherit;
  font-size: 13.5px;
  outline: none;
  resize: vertical;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.field input:focus,
.field textarea:focus {
  border-color: rgba(167, 155, 255, 0.55);
  background: rgba(255, 255, 255, 0.05);
}

.field input::placeholder,
.field textarea::placeholder {
  color: rgba(240, 238, 246, 0.3);
}

.file-input {
  padding: 9px 12px;
  cursor: pointer;
  color: rgba(240, 238, 246, 0.6);
  font-size: 12.5px;
}

.file-input::file-selector-button {
  margin-right: 12px;
  height: 28px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  color: #f2f1ee;
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.file-input::file-selector-button:hover {
  background: rgba(255, 255, 255, 0.13);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}

@media (max-width: 760px) {
  .admin-top {
    grid-template-columns: 1fr;
    justify-items: center;
    gap: 12px;
  }
  .admin-top > .pill-btn:last-child {
    justify-self: center;
  }
  .item-row {
    grid-template-columns: minmax(0, 1fr) auto;
    row-gap: 12px;
  }
  .row-actions {
    grid-column: 1 / -1;
  }
}
</style>
