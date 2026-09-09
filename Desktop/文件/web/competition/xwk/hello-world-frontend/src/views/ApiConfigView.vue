<template>
  <div class="api-config-layout">
    <header class="top-nav">
     <router-link to="/" class="brand-link">
  <div class="brand">
    <div class="brand-avatar">H</div>
    <span class="brand-name">Hello World</span>
    <span class="sub-badge">视频 API 接口配置中心</span>
  </div>
</router-link>
      <router-link to="/workspace" class="link-btn">返回创作工作台</router-link>
    </header>

    <div class="main-body">
      <!-- 左侧边栏 -->
      <aside class="sidebar">
        <div class="sidebar-title">设置与集成</div>
        <nav class="sidebar-menu">
          <a class="menu-item">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span>账户信息</span>
          </a>
          <a class="menu-item active">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            <span>自备视频 API (BYOK)</span>
          </a>
        </nav>
      </aside>

      <!-- 主配置表单区 -->
      <main class="content-panel">
        <div class="panel-header">
          <div>
            <h1 class="page-title">添加 / 管理视频 API</h1>
            <p class="page-subtitle">自备 API Key 模式：直接对接火山方舟官方或任意第三方中转协议。</p>
          </div>
        </div>

        <div class="info-alert">
          <svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
          <span>当前页面配置视频生成底模接口。本平台首期文本叙事 Agent 由服务器环境变量统一托管。</span>
        </div>

        <!-- 卡片 1：基础协议与来源 -->
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
              <input v-else type="text" v-model="form.remote_model_id" placeholder="输入真实模型名称 (如 Doubao-Seedance)" />
            </div>
          </div>

          <!-- Base URL（中转必填，官方自动匹配） -->
          <div class="form-group" v-if="form.source_type === 'relay' || currentPreset?.supports_custom_base_url">
            <label>API 基础地址 (Base URL) <span class="required">*</span></label>
            <input type="text" v-model="form.base_url" placeholder="https://api.your-relay-service.com" />
            <div class="field-hint">中转服务的基础域名，末尾不需要带 /v1 或路径。</div>
          </div>
        </section>

        <!-- 卡片 2：鉴权与高级选项 -->
        <section class="card-section">
          <div class="section-title">接口鉴权凭证</div>
          <p class="section-desc">密钥由后端经 AES-256 加密落盘保存，前端不保存明文且仅回显掩码。</p>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>API Key <span class="required">*</span></label>
              <div class="input-with-action">
                <input :type="showKey ? 'text' : 'password'" v-model="form.auth.api_key" placeholder="填写对应的服务密钥 (sk-...)" />
                <button type="button" class="inline-btn" @click="showKey = !showKey">
                  {{ showKey ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 中转风险强制确认 -->
          <div class="form-group" v-if="form.source_type === 'relay'">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.relay_risk_accepted" />
              <span>我已知晓中转接口可能存在数据被第三方代理中转的风险，并确认允许发送 [必勾选]</span>
            </label>
          </div>

          <!-- 无付费连通性检测 -->
          <div class="test-connection-bar">
            <div class="test-status-text">
              <span class="loading-spinner" v-if="isTesting"></span>
              <span v-else>◉</span>
              <span>{{ testMessage || '建议在保存前进行轻量无付费连通性校验。' }}</span>
            </div>
            <button type="button" class="secondary-btn" :disabled="isTesting" @click="handleTest">
              {{ isTesting ? '测试中...' : '无付费检测连通性' }}
            </button>
          </div>
        </section>

        <!-- 提交与保存 -->
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
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import request from '@/utils/request';

const router = useRouter();

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
  await loadPresets();
});

async function loadPresets() {
  try {
    const res: any = await request.get('/video-api-presets');
    presets.value = res.items || [];
    if (presets.value.length > 0) {
      form.protocol_code = presets.value[0].code;
      await handleProtocolChange();
    }
  } catch (err) {
    // 降级支持火山方舟和通用中转
    presets.value = [
      { code: 'ark_seedance_v1', label: '火山引擎 Seedance (官方协议)', source_types: ['official'], supports_custom_base_url: false },
      { code: 'generic_async_json_v1', label: '通用第三方异步 JSON 协议 (中转站)', source_types: ['relay'], supports_custom_base_url: true }
    ];
    form.protocol_code = presets.value[0].code;
  }
}

async function handleProtocolChange() {
  if (currentPreset.value?.official_base_url) {
    form.base_url = currentPreset.value.official_base_url;
  }
  // 加载该协议下的可选模型列表
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
.brand-link {
  text-decoration: none;
  cursor: pointer;
  display: inline-block;
}
.brand-link:hover .brand-name {
  color: #818cf8;
}
.api-config-layout {
  min-height: 100vh;
  width: 100vw;
  background-color: #090c14;
  color: #e2e8f0;
  font-size: 15px;
}
.top-nav {
  height: 64px;
  border-bottom: 1px solid #1e2638;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 36px;
  background-color: #0f1422;
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand-avatar {
  width: 32px; height: 32px; background-color: #6366f1; color: #fff;
  font-weight: bold; border-radius: 8px; display: flex;
  align-items: center; justify-content: center; font-size: 16px;
}
.brand-name { font-weight: 600; color: #fff; font-size: 18px; }
.sub-badge {
  font-size: 13px; background-color: #1e293b; color: #94a3b8;
  padding: 4px 10px; border-radius: 6px; border: 1px solid #334155;
}
.link-btn {
  color: #94a3b8; text-decoration: none; font-size: 14px;
  padding: 6px 14px; border: 1px solid #334155; border-radius: 6px;
}
.link-btn:hover { color: #fff; border-color: #64748b; }
.main-body { display: flex; max-width: 1400px; margin: 0 auto; padding: 32px; gap: 40px; }
.sidebar { width: 220px; flex-shrink: 0; }
.sidebar-title { color: #64748b; font-size: 13px; margin-bottom: 12px; padding-left: 12px; }
.sidebar-menu { display: flex; flex-direction: column; gap: 6px; }
.menu-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px;
  border-radius: 8px; color: #94a3b8; text-decoration: none; cursor: pointer;
}
.menu-item .icon { width: 18px; height: 18px; }
.menu-item.active { background-color: #1f293d; color: #818cf8; font-weight: 600; }
.content-panel { flex: 1; max-width: 900px; }
.panel-header { margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 600; color: #fff; margin-bottom: 4px; }
.page-subtitle { color: #94a3b8; font-size: 14px; }
.info-alert {
  background-color: #10192e; border: 1px solid #1d2c4d; border-radius: 8px;
  padding: 12px 16px; display: flex; gap: 10px; color: #60a5fa; font-size: 13px;
  margin-bottom: 24px;
}
.alert-icon { width: 18px; height: 18px; flex-shrink: 0; }
.card-section {
  background-color: #111624; border: 1px solid #1e273d; border-radius: 10px;
  padding: 24px; margin-bottom: 24px;
}
.section-title { font-size: 17px; font-weight: 600; color: #f8fafc; margin-bottom: 4px; }
.section-desc { font-size: 13px; color: #64748b; margin-bottom: 20px; }
.form-row { display: flex; gap: 20px; margin-bottom: 16px; }
.flex-1 { flex: 1; }
.form-group { display: flex; flex-direction: column; margin-bottom: 16px; }
.form-group label { font-size: 13px; font-weight: 500; color: #cbd5e1; margin-bottom: 6px; }
.required { color: #ef4444; }
.field-hint { font-size: 12px; color: #64748b; margin-top: 4px; }
input[type="text"], input[type="password"], select {
  height: 42px; background-color: #182030; border: 1px solid #28354f;
  border-radius: 6px; padding: 0 14px; color: #fff; font-size: 14px; outline: none;
}
input:focus, select:focus { border-color: #6366f1; }
.radio-group { display: flex; align-items: center; gap: 24px; height: 42px; }
.radio-label, .checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; color: #e2e8f0; font-size: 14px; }
.input-with-action { position: relative; display: flex; align-items: center; }
.input-with-action input { width: 100%; padding-right: 50px; }
.inline-btn { position: absolute; right: 12px; background: transparent; border: none; color: #94a3b8; font-size: 13px; cursor: pointer; }
.test-connection-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; padding-top: 14px; border-top: 1px solid #1e273d;
}
.test-status-text { display: flex; align-items: center; gap: 8px; color: #94a3b8; font-size: 13px; }
.secondary-btn {
  background-color: #1e273b; color: #fff; border: 1px solid #334155;
  padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;
}
.secondary-btn:hover:not(:disabled) { background-color: #2c3852; }
.action-footer { display: flex; justify-content: flex-end; }
.primary-save-btn {
  background-color: #6366f1; color: #fff; border: none; padding: 12px 28px;
  border-radius: 6px; font-size: 15px; font-weight: 600; cursor: pointer;
}
.primary-save-btn:hover:not(:disabled) { background-color: #4f46e5; }
.primary-save-btn:disabled, .secondary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-spinner {
  width: 14px; height: 14px; border: 2px solid #64748b;
  border-top-color: #38bdf8; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>