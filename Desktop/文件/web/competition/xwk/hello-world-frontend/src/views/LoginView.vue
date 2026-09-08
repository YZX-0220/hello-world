<template>
  <div class="login-layout">
    <!-- 顶部极简品牌标识 -->
    <header class="top-nav">
      <div class="brand">
        <div class="brand-avatar">H</div>
        <span class="brand-name">Hello World</span>
        <span class="sub-badge">国际传播特化 AI 视频生成平台</span>
      </div>
    </header>

    <!-- 居中认证卡片容器 -->
    <main class="login-container">
      <div class="auth-card">
        <!-- 头部标题区 -->
        <div class="auth-header">
          <h1 class="auth-title">
            {{ activeTab === 'register' ? '创建新账号' : '登录 Hello World' }}
          </h1>
          <p class="auth-subtitle">
            跨文化叙事 AI 工作台 · 自由配置多模型视频 API
          </p>
        </div>

        <!-- 模式切换标签：密码登录 / 验证码登录 / 注册 -->
        <div class="tab-switcher">
          <button 
            type="button" 
            :class="{ active: activeTab === 'password_login' }" 
            @click="switchTab('password_login')"
          >
            密码登录
          </button>
          <button 
            type="button" 
            :class="{ active: activeTab === 'code_login' }" 
            @click="switchTab('code_login')"
          >
            验证码登录
          </button>
          <button 
            type="button" 
            :class="{ active: activeTab === 'register' }" 
            @click="switchTab('register')"
          >
            免费注册
          </button>
        </div>

        <!-- 统一错误提示条 -->
        <div v-if="errorMessage" class="error-banner">
          <svg class="error-icon" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <span>{{ errorMessage }}</span>
        </div>

        <!-- 表单区域 -->
        <form class="auth-form" @submit.prevent="handleSubmit">
          <!-- 邮箱输入项（所有模式共用） -->
          <div class="form-group">
            <label>注册邮箱 <span class="required">*</span></label>
            <input 
              type="text" 
              v-model.trim="form.email" 
              placeholder="name@example.com"
              autocomplete="email"
              required
            />
          </div>

          <!-- 验证码输入项（验证码登录与注册模式可用） -->
          <div v-if="activeTab === 'code_login' || activeTab === 'register'" class="form-group">
            <label>6 位邮箱验证码 <span class="required">*</span></label>
            <div class="code-input-row">
              <input 
                type="text" 
                v-model.trim="form.code" 
                placeholder="123456" 
                maxlength="6"
                required
              />
              <button 
                type="button" 
                class="send-code-btn" 
                :disabled="countdown > 0 || isSendingCode" 
                @click="handleSendCode"
              >
                {{ countdown > 0 ? `${countdown}s 后重新获取` : (isSendingCode ? '发送中...' : '获取验证码') }}
              </button>
            </div>
            <div class="field-hint">验证码将发送到您的收件箱，有效时长为 10 分钟。</div>
          </div>

          <!-- 密码输入项（密码登录与注册模式可用） -->
          <div v-if="activeTab === 'password_login' || activeTab === 'register'" class="form-group">
            <label>
              {{ activeTab === 'register' ? '设置登录密码' : '登录密码' }}
              <span class="required">*</span>
            </label>
            <div class="password-wrapper">
              <input 
                :type="showPassword ? 'text' : 'password'" 
                v-model="form.password" 
                placeholder="8~128 位字符" 
                autocomplete="current-password"
                required
              />
              <button 
                type="button" 
                class="toggle-eye-btn" 
                @click="showPassword = !showPassword"
              >
                {{ showPassword ? '隐藏' : '显示' }}
              </button>
            </div>
            <div v-if="activeTab === 'register'" class="field-hint">长度在 8 到 128 位之间。</div>
          </div>

          <!-- 提交主按钮 -->
          <button 
            type="submit" 
            class="submit-auth-btn" 
            :disabled="isSubmitting"
          >
            {{ isSubmitting ? '正在处理...' : submitButtonText }}
          </button>
        </form>

        <!-- 卡片底部附加说明 -->
        <footer class="card-footer">
          <p>
            登录即代表您已阅读并同意
            <a href="javascript:void(0)" class="text-link">《用户服务协议》</a>
            与
            <a href="javascript:void(0)" class="text-link">《跨文化生成合规准则》</a>
          </p>
        </footer>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import request from '@/utils/request';

const router = useRouter();

type TabType = 'password_login' | 'code_login' | 'register';

const activeTab = ref<TabType>('password_login');
const showPassword = ref(false);
const isSubmitting = ref(false);
const isSendingCode = ref(false);
const errorMessage = ref('');
const countdown = ref(0);
let timer: number | null = null;

// 表单响应式数据
const form = reactive({
  email: '',
  code: '',
  password: '',
});

// 动态主按钮文字
const submitButtonText = computed(() => {
  if (activeTab.value === 'password_login') return '立即登录';
  if (activeTab.value === 'code_login') return '验证码安全登录';
  return '立即注册并登录';
});

// 切换标签时清理错误
function switchTab(tab: TabType) {
  activeTab.value = tab;
  errorMessage.value = '';
}

// 发送邮箱验证码 (POST /auth/email-codes)
async function handleSendCode() {
  errorMessage.value = '';
  if (!form.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errorMessage.value = '请输入格式正确的邮箱地址';
    return;
  }

  isSendingCode.value = true;
  // 根据当前标签区分用途：login 还是 register
  const purpose = activeTab.value === 'register' ? 'register' : 'login';

  try {
    const res: any = await request.post('/auth/email-codes', {
      email: form.email.toLowerCase(),
      purpose: purpose,
    });

    // 契约：后端返回 retry_after_seconds，通常为 60s
    startCountdown(res.retry_after_seconds || 60);
  } catch (err: any) {
    errorMessage.value = err.message || '验证码发送失败，请稍后重试';
  } finally {
    isSendingCode.value = false;
  }
}

// 倒计时逻辑
function startCountdown(seconds: number) {
  countdown.value = seconds;
  if (timer) clearInterval(timer);
  timer = window.setInterval(() => {
    countdown.value--;
    if (countdown.value <= 0) {
      if (timer) clearInterval(timer);
      timer = null;
    }
  }, 1000);
}

// 提交表单（严格对齐后端 3 个入口）
async function handleSubmit() {
  errorMessage.value = '';
  isSubmitting.value = true;

  try {
    const normalizedEmail = form.email.toLowerCase();

    // 1. 密码登录
    if (activeTab.value === 'password_login') {
      await request.post('/auth/login/password', {
        email: normalizedEmail,
        password: form.password,
      });
    } 
    // 2. 验证码登录
    else if (activeTab.value === 'code_login') {
      await request.post('/auth/login/email-code', {
        email: normalizedEmail,
        code: form.code,
      });
    } 
    // 3. 注册账号
    else {
      await request.post('/auth/register', {
        email: normalizedEmail,
        code: form.code,
        password: form.password,
      });
    }

    // 后端已自动写入 HttpOnly Cookie (hw_session) 与 hw_csrf
    // 登录/注册成功后，直接跳转到创作工作台
    router.push('/workspace');
  } catch (err: any) {
    errorMessage.value = err.message || '操作失败，请检查输入';
  } finally {
    isSubmitting.value = false;
  }
}

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.login-layout {
  min-height: 100vh;
  width: 100vw;
  background-color: #090c14;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
}

/* 顶部导航 */
.top-nav {
  height: 64px;
  border-bottom: 1px solid #1e2638;
  display: flex;
  align-items: center;
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
.sub-badge {
  font-size: 13px;
  background-color: #1e293b;
  color: #94a3b8;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #334155;
}

/* 居中内容区域 */
.login-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
}

/* 认证卡片 */
.auth-card {
  width: 100%;
  max-width: 480px;
  background-color: #111624;
  border: 1px solid #1e273d;
  border-radius: 12px;
  padding: 36px 32px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
}

.auth-header {
  text-align: center;
  margin-bottom: 24px;
}
.auth-title {
  font-size: 24px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 8px;
}
.auth-subtitle {
  font-size: 14px;
  color: #94a3b8;
}

/* 切换 Tab */
.tab-switcher {
  display: flex;
  background-color: #182030;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 24px;
  gap: 4px;
}
.tab-switcher button {
  flex: 1;
  padding: 9px 0;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.tab-switcher button.active {
  background-color: #26334d;
  color: #f8fafc;
  font-weight: 600;
}

/* 错误提示横幅 */
.error-banner {
  background-color: #2b1419;
  border: 1px solid #4d1d24;
  border-radius: 8px;
  padding: 10px 14px;
  color: #f87171;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}
.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* 表单组件 */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.form-group {
  display: flex;
  flex-direction: column;
}
.form-group label {
  font-size: 14px;
  color: #cbd5e1;
  margin-bottom: 8px;
  font-weight: 500;
}
.required {
  color: #ef4444;
}
.field-hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 6px;
}

input[type="text"],
input[type="password"] {
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
input:focus {
  border-color: #6366f1;
}

/* 验证码组合行 */
.code-input-row {
  display: flex;
  gap: 12px;
}
.code-input-row input {
  flex: 1;
}
.send-code-btn {
  background-color: #1e273b;
  color: #38bdf8;
  border: 1px solid #334155;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.send-code-btn:hover:not(:disabled) {
  background-color: #27354d;
}
.send-code-btn:disabled {
  color: #64748b;
  cursor: not-allowed;
  opacity: 0.6;
}

/* 密码内嵌显示/隐藏切换按钮 */
.password-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.password-wrapper input {
  width: 100%;
  padding-right: 60px;
}
.toggle-eye-btn {
  position: absolute;
  right: 14px;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 13px;
  cursor: pointer;
}

/* 提交主按钮 */
.submit-auth-btn {
  margin-top: 10px;
  height: 46px;
  background-color: #6366f1;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}
.submit-auth-btn:hover:not(:disabled) {
  background-color: #4f46e5;
}
.submit-auth-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 底部声明 */
.card-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}
.text-link {
  color: #818cf8;
  text-decoration: none;
}
.text-link:hover {
  text-decoration: underline;
}
</style>