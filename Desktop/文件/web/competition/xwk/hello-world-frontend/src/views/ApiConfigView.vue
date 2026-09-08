<template>
  <div class="api-config-layout">
    <!-- 顶部极简导航栏 -->
    <header class="top-nav">
      <div class="brand">
        <div class="brand-avatar">H</div>
        <span class="brand-name">Hello World</span>
      </div>
      <div class="account-link">账户设置</div>
    </header>

    <div class="main-body">
      <!-- 左侧边栏 -->
      <aside class="sidebar">
        <div class="sidebar-title">设置</div>
        <nav class="sidebar-menu">
          <a class="menu-item">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span>账户</span>
          </a>
          <a class="menu-item active">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
            <span>视频 API</span>
          </a>
          <a class="menu-item">
            <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span>隐私与安全</span>
          </a>
        </nav>
      </aside>

      <!-- 右侧表单主内容区 -->
      <main class="content-panel">
        <div class="panel-header">
          <div>
            <h1 class="page-title">添加视频 API</h1>
            <p class="page-subtitle">选择协议模板后，只填写该协议真正需要的信息。</p>
          </div>
          <button class="link-btn" @click="goBack">返回配置列表</button>
        </div>

        <!-- 提示横幅 -->
        <div class="info-alert">
          <svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
          <span>本项目只配置视频生成 API。首期文本 Agent 使用平台统一 API，由管理员在服务器环境变量中配置。</span>
        </div>

        <!-- 卡片 1：基本信息 -->
        <section class="card-section">
          <div class="section-title">基本信息</div>
          <p class="section-desc">名称只用于你自己识别，不会发送给视频厂商。</p>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>配置名称 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="form.display_name" 
                placeholder="我的 Wan 视频接口" 
                maxlength="40"
              />
            </div>
            <div class="form-group flex-1">
              <label>接口来源 <span class="required">*</span></label>
              <div class="radio-group">
                <label class="radio-label">
                  <input type="radio" value="official" v-model="form.source_type" />
                  <span>官方接口</span>
                </label>
                <label class="radio-label">
                  <input type="radio" value="relay" v-model="form.source_type" />
                  <span>兼容中转站</span>
                </label>
              </div>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>接口协议 <span class="required">*</span></label>
              <select v-model="form.protocol_code" @change="onProtocolChange">
                <option v-for="item in presets" :key="item.code" :value="item.code">
                  {{ item.label }}
                </option>
              </select>
              <div class="field-hint">{{ currentProtocol?.description || '适合文生视频、首帧、首尾帧与参考素材。' }}</div>
            </div>
            <div class="form-group flex-1">
              <label>模型 ID <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="form.remote_model_id" 
                placeholder="wan3.0-video" 
                @input="fetchModelProfiles"
              />
              <div class="field-hint">必须填写接口文档中的真实模型名称。</div>
            </div>
          </div>

          <div class="form-group">
            <label>Base URL <span class="required">*</span></label>
            <input 
              type="text" 
              v-model="form.base_url" 
              :disabled="form.source_type === 'official'"
              :placeholder="officialBaseUrlPlaceholder" 
            />
            <div class="field-hint">官方接口自动填写；选择中转站后才能修改。</div>
          </div>
        </section>

        <!-- 卡片 2：鉴权信息 -->
        <section class="card-section">
          <div class="section-title">鉴权信息</div>
          <p class="section-desc">密钥提交后加密保存，页面以后只显示末四位。</p>

          <div class="form-row">
            <div class="form-group flex-1">
              <label>DashScope API Key <span class="required">*</span></label>
              <div class="input-with-action">
                <input 
                  :type="showApiKey ? 'text' : 'password'" 
                  v-model="form.auth.api_key" 
                  placeholder="sk-••••••••••••••••"
                />
                <button type="button" class="inline-btn" @click="showApiKey = !showApiKey">
                  {{ showApiKey ? '隐藏' : '显示' }}
                </button>
              </div>
            </div>
            <div class="form-group flex-1">
              <label>Workspace ID <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="form.options.workspace_id" 
                placeholder="WS-XXXXXXXX" 
              />
              <div class="field-hint">必须与 API Key 和所选地域一致。</div>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group flex-half">
              <label>地域 <span class="required">*</span></label>
              <select v-model="form.options.region">
                <option value="cn-beijing">北京</option>
                <option value="cn-shanghai">上海</option>
                <option value="ap-southeast-1">新加坡</option>
              </select>
            </div>
          </div>

          <!-- 检测按钮与状态行 -->
          <div class="test-connection-bar">
            <div class="test-status-text">
              <span class="loading-spinner" v-if="isTesting"></span>
              <span class="status-icon" v-else>◌</span>
              <span>{{ testMessage || '尚未检测。检测不会自动创建付费视频任务。' }}</span>
            </div>
            <button 
              type="button" 
              class="secondary-btn" 
              :disabled="isTesting" 
              @click="handleTestConnection"
            >
              {{ isTesting ? '检测中...' : '检测连接' }}
            </button>
          </div>
        </section>

        <!-- 卡片 3：配置结果 -->
        <section class="card-section">
          <div class="section-title">配置结果</div>
          <p class="section-desc">协议决定如何调用；能力来自后台模型注册表，未知中转模型会标记为未验证。</p>

          <div class="result-summary-box">
            <div class="summary-col">
              <div class="summary-label">协议</div>
              <div class="summary-value">{{ currentProtocol?.label || 'DashScope Async v1' }}</div>
            </div>
            <div class="summary-col">
              <div class="summary-label">模型</div>
              <div class="summary-value">{{ form.remote_model_id || 'wan3.0-video' }}</div>
            </div>
            <div class="summary-col">
              <div class="summary-label">状态</div>
              <div class="summary-value" :class="'status-' + verificationStatus">
                {{ formatStatusText(verificationStatus) }}
              </div>
            </div>
          </div>

          <!-- 动态能力胶囊展示 -->
          <div class="capability-badges">
            <span 
              v-for="cap in renderedCapabilities" 
              :key="cap.code" 
              class="cap-tag"
              :class="{ active: cap.active }"
            >
              <svg class="tag-icon" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              {{ cap.label }}
            </span>
          </div>

          <!-- 保存提交主按钮 -->
          <div class="action-footer">
            <button 
              type="button" 
              class="primary-save-btn" 
              :disabled="isSaving" 
              @click="handleSaveConfig"
            >
              {{ isSaving ? '保存中...' : '保存视频 API 配置' }}
            </button>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import request from '../utils/request';

const router = useRouter();

// 1. 响应式表单数据（字段与后端规范一致）
const form = reactive({
  display_name: '我的 Wan 视频接口',
  source_type: 'official' as 'official' | 'relay',
  protocol_code: 'dashscope_async_v1',
  template_code: null as string | null,
  base_url: 'https://{workspace_id}.cn-beijing.maas.aliyuncs.com',
  remote_model_id: 'wan3.0-video',
  auth: {
    api_key: '',
  },
  options: {
    workspace_id: '',
    region: 'cn-beijing'
  },
  capability_profile_code: 'text_reference_media',
  relay_risk_accepted: true // 契约：中转必填确认
});

const showApiKey = ref(false);
const isTesting = ref(false);
const isSaving = ref(false);
const testMessage = ref('');
const verificationStatus = ref<'unverified' | 'verified' | 'invalid'>('unverified');

// 后端预设列表与模型能力
const presets = ref<any[]>([]);
const modelCapabilities = ref<string[]>(['text_to_video', 'first_frame_to_video', 'first_last_frame_to_video', 'reference_image_to_video']);

// 计算当前选中的协议定义
const currentProtocol = computed(() => {
  return presets.value.find(p => p.code === form.protocol_code);
});

// 计算 Base URL 的占位符
const officialBaseUrlPlaceholder = computed(() => {
  const ws = form.options.workspace_id || '{workspace_id}';
  const reg = form.options.region || 'cn-beijing';
  return `https://${ws}.${reg}.maas.aliyuncs.com`;
});

// 核心胶囊列表（模拟图片中下方四个特征）
const renderedCapabilities = computed(() => {
  return [
    { code: 'text_to_video', label: '文生视频', active: modelCapabilities.value.includes('text_to_video') },
    { code: 'first_frame_to_video', label: '首帧生成', active: modelCapabilities.value.includes('first_frame_to_video') },
    { code: 'first_last_frame_to_video', label: '首尾帧生成', active: modelCapabilities.value.includes('first_last_frame_to_video') },
    { code: 'reference_image_to_video', label: '参考素材', active: modelCapabilities.value.includes('reference_image_to_video') },
  ];
});

function formatStatusText(status: string) {
  if (status === 'verified') return '已验证';
  if (status === 'invalid') return '验证失败';
  return '待检测';
}

// 2. 初始化：读取已启用的协议预设
onMounted(async () => {
  try {
    const res: any = await request.get('/video-api-presets');
    if (res.items && res.items.length > 0) {
      presets.value = res.items;
      form.protocol_code = res.items[0].code;
    } else {
      // 本地演示降级数据，保持界面与图片一致
      presets.value = [
        { code: 'dashscope_async_v1', label: '阿里云 DashScope / Wan', description: '适合文生视频、首帧、首尾帧与参考素材。' },
        { code: 'fal_queue_v1', label: 'fal Queue', description: '适合高并发快速排队生成。' },
        { code: 'generic_async_json_v1', label: '通用第三方异步 JSON 协议', description: '支持聚合转接中转站。' }
      ];
    }
  } catch (err) {
    // 降级兜底展示
    presets.value = [
      { code: 'dashscope_async_v1', label: '阿里云 DashScope / Wan', description: '适合文生视频、首帧、首尾帧与参考素材。' }
    ];
  }
});

function onProtocolChange() {
  if (form.source_type === 'official') {
    form.base_url = officialBaseUrlPlaceholder.value;
  }
  fetchModelProfiles();
}

// 3. 动态获取模型能力
async function fetchModelProfiles() {
  if (!form.remote_model_id) return;
  try {
    const res: any = await request.get('/video-model-profiles', {
      params: { protocol_code: form.protocol_code }
    });
    if (res.items && res.items.length > 0) {
      const matched = res.items.find((m: any) => m.remote_model_id === form.remote_model_id);
      if (matched && matched.modes) {
        modelCapabilities.value = matched.modes;
      }
    }
  } catch (e) {
    // 保持当前已知能力不变
  }
}

// 4. 连通性测试（POST /video-api-configs/test）
async function handleTestConnection() {
  if (!form.auth.api_key) {
    testMessage.value = '请先填写 DashScope API Key';
    return;
  }
  isTesting.value = true;
  testMessage.value = '正在向网关发送无付费验证...';

  // 组装符合 Pydantic 契约的入参
  const payload = {
    source_type: form.source_type,
    protocol_code: form.protocol_code,
    template_code: form.template_code,
    base_url: form.source_type === 'official' ? officialBaseUrlPlaceholder.value : form.base_url,
    remote_model_id: form.remote_model_id,
    auth: {
      api_key: form.auth.api_key
    },
    options: form.options,
    capability_profile_code: form.capability_profile_code,
    relay_risk_accepted: form.relay_risk_accepted
  };

  try {
    const res: any = await request.post('/video-api-configs/test', payload);
    verificationStatus.value = res.verification_status;
    testMessage.value = res.message || '接口地址和鉴权可以正常使用';
  } catch (err: any) {
    verificationStatus.value = 'invalid';
    testMessage.value = err.message || '检测失败，请核实 API Key 与地域配置';
  } finally {
    isTesting.value = false;
  }
}

// 5. 保存并落盘（POST /video-api-configs）[cite: 1]
async function handleSaveConfig() {
  if (!form.display_name.trim()) {
    alert('请填写配置名称');
    return;
  }
  if (!form.auth.api_key.trim()) {
    alert('请填写 API 密钥');
    return;
  }

  isSaving.value = true;
  const payload = {
    display_name: form.display_name,
    source_type: form.source_type,
    protocol_code: form.protocol_code,
    template_code: form.template_code,
    base_url: form.source_type === 'official' ? officialBaseUrlPlaceholder.value : form.base_url,
    remote_model_id: form.remote_model_id,
    auth: {
      api_key: form.auth.api_key
    },
    options: form.options,
    capability_profile_code: form.capability_profile_code,
    relay_risk_accepted: form.relay_risk_accepted
  };

  try {
    await request.post('/video-api-configs', payload);
    alert('配置已成功加密保存！');
    router.push('/workspace');
  } catch (err: any) {
    alert(err.message || '保存失败，请核对输入格式');
  } finally {
    isSaving.value = false;
  }
}

function goBack() {
  router.back();
}
</script>

<style scoped>
.api-config-layout {
  min-height: 100vh;
  width: 100vw;
  background-color: #090c14;
  color: #e2e8f0;
  font-size: 15px;
  line-height: 1.6;
}

/* 顶部状态栏（64px） */
.top-nav {
  height: 64px;
  border-bottom: 1px solid #1e2638;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 36px;
  background-color: #0f1422;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-avatar {
  width: 32px;
  height: 32px;
  background-color: #6366f1;
  color: #fff;
  font-weight: bold;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.brand-name {
  font-weight: 600;
  color: #fff;
  font-size: 18px;
}
.account-link {
  color: #cbd5e1;
  font-size: 15px;
  cursor: pointer;
}

/* 左右两栏容器：放宽至 1500px，不再缩成一条缝 */
.main-body {
  display: flex;
  max-width: 1500px;
  margin: 0 auto;
  padding: 36px 32px;
  gap: 48px;
}

/* 左侧栏（宽 240px） */
.sidebar {
  width: 240px;
  flex-shrink: 0;
}
.sidebar-title {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 14px;
  padding-left: 14px;
}
.sidebar-menu {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  color: #94a3b8;
  font-size: 15px;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
}
.menu-item .icon {
  width: 20px;
  height: 20px;
}
.menu-item:hover {
  background-color: #172033;
  color: #f1f5f9;
}
.menu-item.active {
  background-color: #1f293d;
  color: #818cf8;
  font-weight: 600;
}

/* 右侧内容面板（主容器加大到 980px） */
.content-panel {
  flex: 1;
  max-width: 980px;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.page-title {
  font-size: 26px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 6px;
}
.page-subtitle {
  color: #94a3b8;
  font-size: 15px;
}
.link-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  font-size: 15px;
}
.link-btn:hover { color: #f8fafc; }

/* 提示横幅 */
.info-alert {
  background-color: #10192e;
  border: 1px solid #1d2c4d;
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: #60a5fa;
  font-size: 14px;
  margin-bottom: 28px;
}
.alert-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  margin-top: 1px;
}

/* 卡片模块通用样式 */
.card-section {
  background-color: #111624;
  border: 1px solid #1e273d;
  border-radius: 12px;
  padding: 28px 32px;
  margin-bottom: 28px;
}
.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 6px;
}
.section-desc {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 24px;
}

/* 表单栅格与大号控件 */
.form-row {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
}
.flex-1 { flex: 1; }
.flex-half { width: calc(50% - 12px); }

.form-group {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
}
.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 8px;
}
.required { color: #ef4444; }
.field-hint {
  font-size: 13px;
  color: #64748b;
  margin-top: 6px;
}

/* 输入控件：加大高到 44px */
input[type="text"],
input[type="password"],
select {
  height: 44px;
  background-color: #182030;
  border: 1px solid #28354f;
  border-radius: 8px;
  padding: 0 16px;
  color: #f8fafc;
  font-size: 15px;
  outline: none;
  transition: border-color 0.15s ease;
}
input:disabled {
  background-color: #121824;
  color: #64748b;
  cursor: not-allowed;
}
input:focus,
select:focus {
  border-color: #6366f1;
}

/* 单选组 */
.radio-group {
  display: flex;
  align-items: center;
  gap: 28px;
  height: 44px;
}
.radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #e2e8f0;
  font-size: 15px;
}

/* 密码内嵌按钮 */
.input-with-action {
  position: relative;
  display: flex;
  align-items: center;
}
.input-with-action input {
  width: 100%;
  padding-right: 60px;
}
.inline-btn {
  position: absolute;
  right: 14px;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 14px;
  cursor: pointer;
}

/* 连通测试条 */
.test-connection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 18px;
  border-top: 1px solid #1e273d;
}
.test-status-text {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #cbd5e1;
  font-size: 14px;
}
.secondary-btn {
  background-color: #1e273b;
  color: #f8fafc;
  border: 1px solid #334155;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.secondary-btn:hover:not(:disabled) {
  background-color: #2c3852;
}

/* 结果配置三列展示区 */
.result-summary-box {
  display: flex;
  background-color: #151b2a;
  border: 1px solid #202a3f;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.summary-col { flex: 1; }
.summary-label {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 6px;
}
.summary-value {
  font-size: 15px;
  color: #f8fafc;
  font-weight: 600;
}
.status-verified { color: #10b981; }
.status-invalid { color: #ef4444; }
.status-unverified { color: #f59e0b; }

/* 底部胶囊标签 */
.capability-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 28px;
}
.cap-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: #0f2920;
  color: #34d399;
  border: 1px solid #065f46;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 14px;
  font-weight: 500;
}
.tag-icon { width: 16px; height: 16px; }

/* 保存按钮 */
.action-footer {
  display: flex;
  justify-content: flex-end;
}
.primary-save-btn {
  background-color: #6366f1;
  color: #ffffff;
  border: none;
  padding: 12px 32px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.primary-save-btn:hover:not(:disabled) { background-color: #4f46e5; }
.primary-save-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #64748b;
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>