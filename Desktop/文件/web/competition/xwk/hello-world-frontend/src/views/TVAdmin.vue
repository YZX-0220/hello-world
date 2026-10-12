<template>
  <div class="tv-admin-layout">
    <!-- 顶栏 -->
    <header class="admin-header">
      <div class="left-action">
        <button class="back-tv-btn" @click="router.push('/tv')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          <span>返回 TV 频道</span>
        </button>
        <h2 class="page-title">TV 素材管理控制台</h2>
      </div>
      <button class="create-btn" @click="openCreateModal">+ 录入新视频素材</button>
    </header>

    <!-- 列表展示区 -->
    <main class="admin-main">
      <div v-if="loading" class="state-hint">加载素材列表中...</div>
      <div v-else-if="adminItems.length === 0" class="state-hint">暂无素材，请点击右上角录入。</div>
      
      <table v-else class="admin-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>模型</th>
            <th>状态</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in adminItems" :key="item.id">
            <td class="item-title">{{ item.title }}</td>
            <td><span class="badge">{{ item.model_name }}</span></td>
            <td>
              <span :class="['status-pill', item.status]">
                {{ item.status === 'published' ? '已发布' : '草稿' }}
              </span>
            </td>
            <td class="date-col">{{ new Date(item.updated_at).toLocaleString() }}</td>
            <td class="action-cell">
              <button 
                class="btn-toggle" 
                @click="togglePublish(item)"
              >
                {{ item.status === 'published' ? '下架' : '发布' }}
              </button>
              <button class="btn-del" @click="deleteItem(item)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </main>

    <!-- 上传录入弹窗 -->
    <div v-if="showModal" class="modal-mask" @click.self="showModal = false">
      <div class="modal-box">
        <h3>录入新视频素材</h3>

        <div class="form-group">
          <label>作品标题 *</label>
          <input v-model="form.title" placeholder="如：赛博朋克雨夜街道" />
        </div>

        <div class="form-group">
          <label>使用模型 *</label>
          <input v-model="form.model_name" placeholder="如：Veo 2 或 Seedance 2.5" />
        </div>

        <div class="form-group">
          <label>提示词 / Markdown 描述 *</label>
          <textarea v-model="form.description" rows="4" placeholder="填写生成该视频的 Prompt"></textarea>
        </div>

        <div class="form-group">
          <label>MP4 视频文件 *</label>
          <input type="file" accept="video/mp4" @change="handleFileChange" />
        </div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="showModal = false">取消</button>
          <button class="btn-submit" :disabled="submitting" @click="submitCreate">
            {{ submitting ? '正在上传保存...' : '立即发布' }}
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
.tv-admin-layout {
  min-height: 100vh;
  background-color: #0c0b0e;
  color: #fff;
  padding: 32px 48px;
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.left-action {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-tv-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #94a3b8;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
}

.back-tv-btn svg {
  width: 16px;
  height: 16px;
}

.back-tv-btn:hover {
  color: #fff;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
}

.create-btn {
  background: #6366f1;
  color: #fff;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.admin-main {
  margin-top: 24px;
}

.state-hint {
  color: #64748b;
  padding: 48px;
  text-align: center;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.admin-table th, .admin-table td {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.admin-table th {
  color: #64748b;
  font-size: 13px;
}

.item-title {
  font-weight: 600;
  color: #f1f5f9;
}

.badge {
  background: rgba(255, 255, 255, 0.06);
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.status-pill {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
}

.status-pill.published {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.status-pill.draft {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.date-col {
  font-size: 12px;
  color: #64748b;
}

.action-cell {
  display: flex;
  gap: 10px;
}

.btn-toggle, .btn-del {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-toggle {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}

.btn-del {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.2);
}

/* 弹窗 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-box {
  background: #18171d;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 28px;
  width: 480px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  color: #94a3b8;
}

.form-group input, .form-group textarea {
  background: #0f0e13;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #fff;
  padding: 10px 12px;
  border-radius: 8px;
  outline: none;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 10px;
}

.btn-cancel {
  background: transparent;
  color: #94a3b8;
  border: none;
  cursor: pointer;
}

.btn-submit {
  background: #6366f1;
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
}
</style>