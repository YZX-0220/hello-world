<template>
  <div class="api-config-layout">
    <!-- 顶部导航栏 -->
    <header class="top-nav">
      <router-link to="/" class="brand-link" title="返回首页">
        <div class="brand">
          <div class="brand-avatar">H</div>
          <span class="brand-name">Hello World</span>
          <span class="sub-badge desktop-only">视频 API 接口配置中心</span>
        </div>
      </router-link>
      <router-link to="/workspace" class="link-btn">
        <span class="desktop-only">返回创作工作台</span>
        <span class="mobile-only">返回工作台</span>
      </router-link>
    </header>

    <div class="main-body">
      <!-- 边栏导航：PC 端左侧列表，手机端横向 Tab -->
      <aside class="sidebar">
        <div class="sidebar-title desktop-only">设置与集成</div>
        <nav class="sidebar-menu">
          <a 
            class="menu-item" 
            :class="{ active: activeTab === 'account' }" 
            @click="activeTab = 'account'"
          >
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span>账户信息</span>
          </a>
          <a 
            class="menu-item" 
            :class="{ active: activeTab === 'byok' }" 
            @click="activeTab = 'byok'"
          >
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            <span>自备视频 API (BYOK)</span>
          </a>
        </nav>
      </aside>

      <!-- 选项卡 1：账户信息面板 -->
      <main class="content-panel" v-if="activeTab === 'account'">
        <div class="panel-header">
          <h1 class="page-title">个人账户</h1>
          <p class="page-subtitle">管理您的个人资料、会话状态与登录凭证</p>
        </div>

        <section class="card-section profile-card">
          <div class="profile-header">
            <div class="avatar-box">
              <img :src="profile.avatar" alt="用户头像" class="user-avatar" />
              <span class="status-badge-dot" :class="{ online: isLoggedIn }"></span>
            </div>
            <div class="profile-meta">
              <div class="name-row">
                <h2 class="user-name">{{ profile.nickname }}</h2>
                <span class="login-state-tag" :class="{ active: isLoggedIn }">
                  {{ isLoggedIn ? '已登录' : '未登录' }}
                </span>
              </div>
              <p class="user-email">{{ profile.email }}</p>
              <div class="uid-tag">编号: {{ profile.id }}</div>
            </div>
          </div>

          <div class="account-details-grid">
            <div class="detail-item">
              <span class="detail-label">会员等级</span>
              <span class="detail-value">国际传播先行者 · 永久创作者</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">账号状态</span>
              <span class="detail-value text-success">正常可用 (Active)</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">鉴权模式</span>
              <span class="detail-value">Cookie 会话 (hw_session)</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">注册时间</span>
              <span class="detail-value">{{ profile.createdAt }}</span>
            </div>
          </div>

          <div class="logout-action-box">
            <div class="logout-hint">
              退出登录后将清除本地会话与跨站凭证，下次使用需重新验证。
            </div>
            <button class="logout-action-btn" :disabled="isLoggingOut" @click="handleLogout">
              {{ isLoggingOut ? '正在注销...' : '退出登录' }}
            </button>
          </div>
        </section>
      </main>

      <!-- 选项卡 2：自备视频 API (BYOK) 面板 -->
      <main class="content-panel" v-else>
        <div class="panel-header">
          <h1 class="page-title">添加 / 管理视频 API</h1>
          <p class="page-subtitle">自备 API Key 模式：直接对接火山方舟官方或任意第三方中转协议。</p>
        </div>

        <div class="info-alert">
          <svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
          <span>当前页面仅配置视频生成底模。首期文本叙事 Agent 由服务器环境变量统一托管。</span>
        </div>

        <!-- 卡片 1：基本信息与协议 -->
        <section class="card-section">
          <div class="section-title">基本信息与协议</div>
          <p class="section-desc">选择协议后，表单会自动切换所需填写的对应参数。</p>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>配置显示名称 <span class="required">*</span></label>
              <input type="text" v-model="form.display_name" placeholder="例如：我的 Seedance 视频生成接口" maxlength="40" />
            </div>
            <div class="form-group flex-1">
              <label>接口协议 <span class="required">*</span></label>
              <select v-model="form.protocol_code" @change="handleProtocolChange">
                <option v-for="p in presets" :key="p.code" :value="p.code">
                  {{ p.label }}
                </option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>接口来源 <span class="required">*</span></label>
              <div class="radio-group">
                <label class="radio-label">
                  <input type="radio" value="official" v-model="form.source_type" :disabled="!currentPreset?.source_types.includes('official')" />
                  <span>厂商官方直连</span>
                </label>
                <label class="radio-label">
                  <input type="radio" value="relay" v-model="form.source_type" :disabled="!currentPreset?.source_types.includes('relay')" />
                  <span>第三方兼容中转站</span>
                </label>
              </div>
            </div>

            <div class="form-group flex-1">
              <label>视频模型 <span class="required">*</span></label>
              <select v-if="modelProfiles.length > 0" v-model="form.remote_model_id">
                <option v-for="m in modelProfiles" :key="m.remote_model_id" :value="m.remote_model_id">
                  {{ m.label }}
                </option>
              </select>
              <input v-else type="text" v-model="form.remote_model_id" placeholder="输入模型名称 (如 Doubao-Seedance)" />
            </div>
          </div>

          <div class="form-group" v-if="form.source_type === 'relay' || currentPreset?.supports_custom_base_url">
            <label>API 基础地址 (Base URL) <span class="required">*</span></label>
            <input type="text" v-model="form.base_url" placeholder="https://api.your-relay-service.com" />
            <div class="field-hint">第三方中转域名，末尾无须拼接路径。</div>
          </div>
        </section>

        <!-- 卡片 2：鉴权与连通性 -->
        <section class="card-section">
          <div class="section-title">接口鉴权凭证</div>
          <p class="section-desc">密钥由后端经 AES-256 加密落盘保存，前端不保存明文且仅回显掩码。</p>

          <div class="form-group">
            <label>API Key <span class="required">*</span></label>
            <div class="input-with-action">
              <input :type="showKey ? 'text' : 'password'" v-model="form.auth.api_key" placeholder="填写对应的服务密钥 (sk-...)" />
              <button type="button" class="inline-btn" @click="showKey = !showKey">
                {{ showKey ? '隐藏' : '显示' }}
              </button>
            </div>
          </div>

          <div class="form-group" v-if="form.source_type === 'relay'">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.relay_risk_accepted" />
              <span>我已知晓中转接口可能存在数据被第三方代理中转的风险，并确认允许发送 [必选]</span>
            </label>
          </div>

          <div class="test-connection-bar">
            <div class="test-status-text">
              <span class="loading-spinner" v-if="isTesting"></span>
              <span class="status-dot-icon" v-else>◉</span>
              <span>{{ testMessage || '建议在保存前进行轻量无付费连通性校验。' }}</span>
            </div>
            <button type="button" class="secondary-btn" :disabled="isTesting" @click="handleTest">
              {{ isTesting ? '测试中...' : '无付费检测连通性' }}
            </button>
          </div>
        </section>

        <div class="action-footer">
          <button type="button" class="primary-save-btn" :disabled="isSaving" @click="handleSave">
            {{ isSaving ? '加密保存中...' : '保存视频 API 配置' }}
          </button>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import request from '@/utils/request';

const router = useRouter();
const route = useRoute();

// 根据路由参数自适应激活对应 Tab
const activeTab = ref<'account' | 'byok'>(
  route.query.tab === 'byok' ? 'byok' : 'account'
);

watch(
  () => route.query.tab,
  (newTab) => {
    if (newTab === 'account' || newTab === 'byok') {
      activeTab.value = newTab;
    }
  }
);

// 用户信息
const isLoggedIn = ref(true);
const isLoggingOut = ref(false);
const profile = reactive({
  avatar: 'https://api.dicebear.com/7.x/bottts/svg?seed=HelloWorldCreator',
  nickname: 'Hello World 创作者',
  email: 'creator@helloworld.ai',
  id: 'hw_user_8f49a2e8c071',
  createdAt: '2026-09-08'
});

// BYOK 表单响应式数据
const form = reactive({
  display_name: '我的视频生成接口',
  source_type: 'official' as 'official' | 'relay',
  protocol_code: 'ark_seedance_v1',
  template_code: null as string | null,
  base_url: 'https://ark.cn-beijing.volces.com',
  remote_model_id: '',
  auth: {
    api_key: ''
  },
  options: {},
  capability_profile_code: null as string | null,
  relay_risk_accepted: true
});

const presets = ref<any[]>([]);
const modelProfiles = ref<any[]>([]);
const showKey = ref(false);
const isTesting = ref(false);
const isSaving = ref(false);
const testMessage = ref('');

const currentPreset = computed(() => presets.value.find(p => p.code === form.protocol_code));

onMounted(async () => {
  await fetchUserProfile();
  await loadPresets();
});

async function fetchUserProfile() {
  try {
    const res: any = await request.get('/users/me');
    if (res && res.id) {
      isLoggedIn.value = true;
      profile.id = res.id;
      profile.email = res.email || profile.email;
      if (res.created_at) {
        profile.createdAt = new Date(res.created_at).toLocaleDateString();
      }
    }
  } catch (err) {
    isLoggedIn.value = false;
  }
}

async function handleLogout() {
  isLoggingOut.value = true;
  try {
    await request.post('/auth/logout');
  } catch (e) {
    // 忽略错误
  } finally {
    isLoggingOut.value = false;
    isLoggedIn.value = false;
    router.push('/login');
  }
}

async function loadPresets() {
  try {
    const res: any = await request.get('/video-api-presets');
    presets.value = res.items || [];
    if (presets.value.length > 0) {
      form.protocol_code = presets.value[0].code;
      await handleProtocolChange();
    }
  } catch (err) {
    presets.value = [
      { code: 'ark_seedance_v1', label: '火山引擎 Seedance (官方直连)', source_types: ['official'], supports_custom_base_url: false },
      { code: 'generic_async_json_v1', label: '通用第三方异步 JSON 协议 (中转站)', source_types: ['relay'], supports_custom_base_url: true }
    ];
    form.protocol_code = presets.value[0].code;
  }
}

async function handleProtocolChange() {
  if (currentPreset.value?.official_base_url) {
    form.base_url = currentPreset.value.official_base_url;
  }
  try {
    const res: any = await request.get('/video-model-profiles', {
      params: { protocol_code: form.protocol_code }
    });
    modelProfiles.value = res.items || [];
    if (modelProfiles.value.length > 0) {
      form.remote_model_id = modelProfiles.value[0].remote_model_id;
    }
  } catch (e) {
    modelProfiles.value = [];
  }
}

async function handleTest() {
  if (!form.auth.api_key.trim()) {
    testMessage.value = '请先输入 API 密钥';
    return;
  }
  isTesting.value = true;
  testMessage.value = '正在安全检测网络与鉴权状态...';

  try {
    const res: any = await request.post('/video-api-configs/test', {
      source_type: form.source_type,
      protocol_code: form.protocol_code,
      template_code: form.template_code,
      base_url: form.base_url,
      remote_model_id: form.remote_model_id,
      auth: { api_key: form.auth.api_key },
      options: form.options,
      capability_profile_code: form.capability_profile_code,
      relay_risk_accepted: form.relay_risk_accepted
    });
    testMessage.value = `检测通过：${res.message || '凭证与端点有效'}`;
  } catch (err: any) {
    testMessage.value = `检测失败：${err.message || '请核对 Key 与网络连通性'}`;
  } finally {
    isTesting.value = false;
  }
}

async function handleSave() {
  if (!form.display_name.trim() || !form.auth.api_key.trim()) {
    alert('请补齐配置名称与 API Key');
    return;
  }
  isSaving.value = true;

  try {
    await request.post('/video-api-configs', {
      display_name: form.display_name,
      source_type: form.source_type,
      protocol_code: form.protocol_code,
      template_code: form.template_code,
      base_url: form.base_url,
      remote_model_id: form.remote_model_id,
      auth: { api_key: form.auth.api_key },
      options: form.options,
      capability_profile_code: form.capability_profile_code,
      relay_risk_accepted: form.relay_risk_accepted
    });
    alert('配置已成功加密保存！');
    router.push('/workspace');
  } catch (err: any) {
    alert(err.message || '保存失败');
  } finally {
    isSaving.value = false;
  }
}
</script>

<style scoped>
/* 容器框架 */
.api-config-layout {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100vw;
  background-color: #090c14;
  color: #e2e8f0;
  font-size: 15px;
  overflow-x: hidden;
  box-sizing: border-box;
}

.mobile-only { display: none !important; }
.desktop-only { display: inline-flex; }

/* 顶部导航 */
.top-nav {
  height: clamp(56px, 7vh, 68px);
  border-bottom: 1px solid #1e2638;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(16px, 3vw, 36px);
  background-color: #0f1422;
  position: sticky;
  top: 0;
  z-index: 40;
}
.brand-link { text-decoration: none; }
.brand { display: flex; align-items: center; gap: 10px; }
.brand-avatar {
  width: 32px; height: 32px; background-color: #6366f1; color: #fff;
  font-weight: bold; border-radius: 8px; display: flex;
  align-items: center; justify-content: center; font-size: 16px;
}
.brand-name { font-weight: 600; color: #fff; font-size: 17px; }
.sub-badge {
  font-size: 12px; background-color: #1e293b; color: #94a3b8;
  padding: 3px 8px; border-radius: 6px; border: 1px solid #334155;
}
.link-btn {
  color: #94a3b8; text-decoration: none; font-size: 13px;
  padding: 6px 12px; border: 1px solid #334155; border-radius: 6px;
  white-space: nowrap; transition: all 0.2s;
}
.link-btn:hover { color: #fff; border-color: #64748b; }

/* 主体容器 */
.main-body {
  display: flex;
  max-width: 1360px;
  margin: 0 auto;
  padding: clamp(16px, 3vw, 32px);
  gap: clamp(20px, 3vw, 40px);
}

/* PC 端侧边栏 */
.sidebar { width: 220px; flex-shrink: 0; }
.sidebar-title { color: #64748b; font-size: 13px; margin-bottom: 12px; padding-left: 12px; }
.sidebar-menu { display: flex; flex-direction: column; gap: 6px; }
.menu-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  border-radius: 8px; color: #94a3b8; text-decoration: none; cursor: pointer;
  transition: all 0.2s;
}
.menu-item:hover { background-color: #161e2e; color: #e2e8f0; }
.menu-item .icon { width: 18px; height: 18px; flex-shrink: 0; }
.menu-item.active { background-color: #1f293d; color: #818cf8; font-weight: 600; }

/* 右侧内容面板 */
.content-panel { flex: 1; max-width: 900px; min-width: 0; }
.panel-header { margin-bottom: 20px; }
.page-title { font-size: clamp(20px, 2.2vw, 24px); font-weight: 600; color: #fff; margin-bottom: 4px; }
.page-subtitle { color: #94a3b8; font-size: 13px; }

.info-alert {
  background-color: #10192e; border: 1px solid #1d2c4d; border-radius: 8px;
  padding: 12px 16px; display: flex; gap: 10px; color: #60a5fa; font-size: 13px;
  margin-bottom: 24px; line-height: 1.5;
}
.alert-icon { width: 18px; height: 18px; flex-shrink: 0; margin-top: 1px; }

.card-section {
  background-color: #111624; border: 1px solid #1e273d; border-radius: 12px;
  padding: clamp(16px, 2.5vw, 28px); margin-bottom: 24px; box-sizing: border-box;
}
.section-title { font-size: 16px; font-weight: 600; color: #f8fafc; margin-bottom: 4px; }
.section-desc { font-size: 13px; color: #64748b; margin-bottom: 18px; }

.form-row { display: flex; gap: 16px; margin-bottom: 16px; }
.flex-1 { flex: 1; min-width: 0; }
.form-group { display: flex; flex-direction: column; margin-bottom: 16px; min-width: 0; }
.form-group label { font-size: 13px; font-weight: 500; color: #cbd5e1; margin-bottom: 6px; }
.required { color: #ef4444; }
.field-hint { font-size: 12px; color: #64748b; margin-top: 4px; }

input[type="text"], input[type="password"], select {
  height: 42px; background-color: #182030; border: 1px solid #28354f;
  border-radius: 6px; padding: 0 12px; color: #fff; font-size: 14px; outline: none;
  width: 100%; box-sizing: border-box;
}
input:focus, select:focus { border-color: #6366f1; }

.radio-group { display: flex; align-items: center; gap: 20px; min-height: 42px; flex-wrap: wrap; }
.radio-label, .checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; color: #e2e8f0; font-size: 13px; }
.checkbox-label { line-height: 1.5; }

.input-with-action { position: relative; display: flex; align-items: center; width: 100%; }
.input-with-action input { width: 100%; padding-right: 56px; }
.inline-btn {
  position: absolute; right: 10px; background: transparent; border: none;
  color: #94a3b8; font-size: 13px; cursor: pointer; padding: 6px;
}

.test-connection-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; padding-top: 14px; border-top: 1px solid #1e273d; gap: 12px;
}
.test-status-text { display: flex; align-items: center; gap: 8px; color: #94a3b8; font-size: 13px; }
.status-dot-icon { color: #38bdf8; }
.secondary-btn {
  background-color: #1e273b; color: #fff; border: 1px solid #334155;
  padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; white-space: nowrap;
}
.secondary-btn:hover:not(:disabled) { background-color: #2c3852; }

.action-footer { display: flex; justify-content: flex-end; margin-bottom: 30px; }
.primary-save-btn {
  background-color: #6366f1; color: #fff; border: none; padding: 12px 28px;
  border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}
.primary-save-btn:hover:not(:disabled) { background-color: #4f46e5; }
.primary-save-btn:disabled, .secondary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.loading-spinner {
  width: 14px; height: 14px; border: 2px solid #64748b;
  border-top-color: #38bdf8; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 账户信息卡片样式 */
.profile-card { display: flex; flex-direction: column; gap: 24px; }
.profile-header {
  display: flex; align-items: center; gap: 20px;
  padding-bottom: 20px; border-bottom: 1px solid #1e273d;
}
.avatar-box { position: relative; width: 72px; height: 72px; flex-shrink: 0; }
.user-avatar {
  width: 100%; height: 100%; border-radius: 50%;
  background-color: #1e2738; border: 2px solid #6366f1; padding: 3px; box-sizing: border-box;
}
.status-badge-dot {
  position: absolute; bottom: 2px; right: 2px; width: 13px; height: 13px;
  border-radius: 50%; background-color: #ef4444; border: 2px solid #111624;
}
.status-badge-dot.online { background-color: #10b981; }

.profile-meta { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.name-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.user-name { font-size: 20px; font-weight: 700; color: #f8fafc; }
.login-state-tag {
  font-size: 11px; padding: 2px 7px; border-radius: 4px;
  background-color: #2b1419; color: #f87171; border: 1px solid #4d1d24;
}
.login-state-tag.active {
  background-color: #0d281e; color: #34d399; border: 1px solid #065f46;
}
.user-email { font-size: 13px; color: #94a3b8; word-break: break-all; }
.uid-tag { font-size: 11px; color: #64748b; font-family: monospace; word-break: break-all; }

.account-details-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;
  background-color: #141b2b; border: 1px solid #1d273d; border-radius: 8px; padding: 18px;
}
.detail-item { display: flex; flex-direction: column; gap: 3px; }
.detail-label { font-size: 11px; color: #64748b; }
.detail-value { font-size: 13px; color: #cbd5e1; font-weight: 500; word-break: break-word; }
.text-success { color: #34d399; }

.logout-action-box {
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 16px; border-top: 1px solid #1e273d; gap: 12px;
}
.logout-hint { font-size: 12px; color: #64748b; }
.logout-action-btn {
  background-color: #22151b; border: 1px solid #4d1d24; color: #f87171;
  padding: 8px 18px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap;
}
.logout-action-btn:hover:not(:disabled) { background-color: #3b1922; border-color: #ef4444; }

/* ================= 移动端适配 (<= 768px) ================= */
@media (max-width: 768px) {
  .desktop-only { display: none !important; }
  .mobile-only { display: inline-flex !important; }

  /* 导航收紧 */
  .top-nav { padding: 0 14px; height: 56px; }
  .brand-name { font-size: 16px; }
  .brand-avatar { width: 28px; height: 28px; font-size: 14px; }

  /* 主体纵向堆叠 */
  .main-body {
    flex-direction: column;
    padding: 14px;
    gap: 16px;
  }

  /* 侧边栏转为顶部横向 Segment 控制器 */
  .sidebar {
    width: 100%;
    margin-bottom: 4px;
  }
  .sidebar-menu {
    flex-direction: row;
    background-color: #101625;
    border: 1px solid #1e283d;
    padding: 4px;
    border-radius: 10px;
    gap: 4px;
  }
  .menu-item {
    flex: 1;
    justify-content: center;
    padding: 9px 8px;
    font-size: 13px;
    border-radius: 6px;
    gap: 6px;
    white-space: nowrap;
  }
  .menu-item .icon { width: 16px; height: 16px; }
  .menu-item.active {
    background-color: #1e293b;
    color: #38bdf8;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
  }

  /* 表单双列转单列 */
  .form-row {
    flex-direction: column;
    gap: 0;
  }
  .card-section {
    padding: 16px 14px;
    margin-bottom: 16px;
  }
  .page-title { font-size: 20px; }
  .page-subtitle { font-size: 12px; }

  /* 单选组与连通性检测在手机端换行堆叠 */
  .radio-group {
    gap: 12px;
    margin-top: 2px;
  }
  .test-connection-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  .secondary-btn {
    width: 100%;
    padding: 10px;
  }
  .primary-save-btn {
    width: 100%;
    padding: 13px;
    font-size: 15px;
  }

  /* 账户详情卡片在手机端单列撑满 */
  .profile-header {
    flex-direction: column;
    text-align: center;
    gap: 14px;
  }
  .name-row {
    justify-content: center;
  }
  .account-details-grid {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 14px;
  }
  .logout-action-box {
    flex-direction: column;
    text-align: center;
    gap: 14px;
  }
  .logout-action-btn {
    width: 100%;
    padding: 11px;
  }
}
</style>