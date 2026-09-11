<template>
  <div class="landing-page">
    <!-- 动态科技背景层：星光 + 流动斜线 + 氛围柔光 (全局 fixed) -->
    <div class="stars-layer">
      <div v-for="i in 18" :key="'star-' + i" :class="'star star-' + i"></div>
    </div>
    
    <div class="lines-layer">
      <div class="light-line line-1"></div>
      <div class="light-line line-2"></div>
      <div class="light-line line-3"></div>
      <div class="light-line line-4"></div>
    </div>

    <div class="ambient-glow"></div>

    <!-- 顶部固定导航 -->
    <header class="landing-nav">
      <div class="brand" @click="scrollToTop">
        <div class="brand-avatar">H</div>
        <span class="brand-name">Hello World</span>
      </div>
      <div class="nav-right">
        <a href="javascript:void(0)" class="nav-btn nav-link-about" @click="scrollToAbout">关于项目</a>
        <a href="javascript:void(0)" class="nav-btn nav-link-pricing" @click="scrollToPricing">价格优势</a>
        <router-link to="/settings/api" class="nav-btn nav-link-api">API 配置中心</router-link>

        <!-- 已登录：展示用户头像 SVG 徽章 -->
        <router-link 
          v-if="isLoggedIn" 
          to="/settings/api?tab=account" 
          class="user-avatar-btn" 
          title="点击进入个人账户信息"
        >
          <div class="avatar-circle">
            <svg class="user-avatar-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span class="online-status-dot"></span>
          </div>
        </router-link>

        <!-- 未登录：展示登录/注册按钮 -->
        <router-link 
          v-else 
          to="/login" 
          class="nav-btn login-btn"
        >
          登录 / 注册
        </router-link>
      </div>
    </header>

    <!-- 主体整屏吸附滚动容器 -->
    <main class="snap-container" ref="scrollContainerRef">
      
      <!-- ================= 第一屏：主视觉 Hero ================= -->
      <section class="snap-section hero-screen">
        <div class="hero-container">
          <div class="badge-tag">
            <span class="pulse-point"></span>
            <span class="badge-text">国际传播特化 · 新一代 AI 视频叙事创作引擎</span>
          </div>

          <h1 class="main-title">
            让每一种文化声量，<br />
            <span class="gradient-text">被世界清晰看见。</span>
          </h1>

          <p class="sub-title">
            破除跨文化叙事壁垒 · 托管模型与自备凭证双轨范式 · 零门槛视听语言构建[cite: 9]
          </p>

          <div class="cta-wrapper">
            <button class="launch-btn" @click="enterWorkspace">
              <span class="btn-text">立即进入创作工作台</span>
              <svg class="btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              <div class="btn-glow"></div>
            </button>
          </div>

          <div class="feature-metrics">
            <div class="metric-item">
              <span class="metric-value">Managed & BYOK</span>
              <span class="metric-desc">多模型自备 Key 自由调度[cite: 9]</span>
            </div>
            <div class="divider"></div>
            <div class="metric-item">
              <span class="metric-value">Agent 叙事引擎</span>
              <span class="metric-desc">跨文化分镜精准转译[cite: 2]</span>
            </div>
            <div class="divider"></div>
            <div class="metric-item">
              <span class="metric-value">国际传播特化</span>
              <span class="metric-desc">提供专业海外受众指导[cite: 2]</span>
            </div>
          </div>
        </div>

        <div class="scroll-down-hint" @click="scrollToAbout">
          <span>了解更多项目初衷</span>
          <svg class="scroll-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </section>

      <!-- ================= 第二屏：关于与产品介绍 ================= -->
      <section class="snap-section about-screen" ref="aboutSectionRef">
        <div class="about-container">
          
          <div class="external-header">
            <h2 class="platform-main-title">
              <span class="en-title">Hello World</span>
              <span class="logo-symbol">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
                </svg>
              </span>
              <span class="cn-title">国际传播特化平台</span>
            </h2>
          </div>

          <div class="tapnow-card">
            <div class="card-left-content">
              <h3 class="left-big-heading">你的跨文化 AI 执行导演</h3>
              <p class="left-desc-text">
                从海外受众心理分析、易误解符号规避，到镜头光影与分镜编排[cite: 2]。“Hello World” Agent 通过自然语言对话驱动你的全流程视听创作，打破西方话语壁垒，讲好新时代中国故事[cite: 2, 9]。
              </p>
              <button class="left-action-btn" @click="enterWorkspace">
                开始创作
              </button>
            </div>

            <div class="card-right-preview">
              <div class="brief-preview-box">
                <div class="preview-header-row">
                  <span class="preview-title">分镜与视频方案</span>
                  <span class="preview-version-pill">版本 v0</span>
                </div>

                <div class="preview-status-strip">
                  <div class="strip-left">
                    <span class="strip-dot"></span>
                    <span>方案有更新，请先确认</span>
                  </div>
                  <button class="strip-confirm-btn">确认当前方案</button>
                </div>

                <div class="preview-fields-container">
                  <div class="field-block">
                    <div class="field-title">传播目标 / 受众 / 语言</div>
                    <div class="field-desc">
                      <strong>目标：</strong>未指定<br />
                      <strong>受众：</strong>大众受众 · <strong>语言：</strong>zh-CN
                    </div>
                  </div>

                  <div class="field-block">
                    <div class="field-title">生成规格与视觉风格</div>
                    <div class="field-desc">
                      <strong>模式：</strong>text_to_video | <strong>画幅：</strong>16:9 | <strong>时长：</strong>5s<br />
                      <strong>风格：</strong>写实电影质感
                    </div>
                  </div>

                  <div class="field-block">
                    <div class="field-title">视觉主体与场景环境</div>
                    <div class="field-desc">
                      <strong>主体：</strong>无特定主体<br />
                      <strong>场景：</strong>默认背景
                    </div>
                  </div>

                  <div class="field-block">
                    <div class="field-title">镜头运镜、动作与光影</div>
                    <div class="field-desc">
                      <strong>运镜：</strong>缓慢推进<br />
                      <strong>动作：</strong>自然动态<br />
                      <strong>光影：</strong>电影氛围光
                    </div>
                  </div>

                  <div class="field-block">
                    <div class="field-title">推荐视频提示词 (Suggested Prompt)</div>
                    <div class="prompt-preview-shell">
                      等待 Agent 整理提示词...
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>

        </div>

        <div class="scroll-down-hint" @click="scrollToPricing">
          <span>查看价格与成本优势</span>
          <svg class="scroll-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </section>

      <!-- ================= 第三屏：核心价格与成本优势 (新增) ================= -->
      <section class="snap-section pricing-screen" ref="pricingSectionRef">
        <div class="pricing-container">
          
          <!-- 第三屏：价格优势看板的外部标题 -->
<div class="external-header pricing-header">
  <div class="section-badge-pill">COST & PRICING ADVANTAGE</div>
  <h2 class="platform-main-title">
    <span class="en-title">高质高效</span>
    <span class="cn-title">极致性价比的创作底座</span>
  </h2>
  <p class="pricing-sub-desc">
    依托底层直连与 BYOK 范式，剔除中心化转售溢价，单条生成成本最高直降 30%
  </p>
</div>

          <!-- 核心图表卡片 -->
          <div class="chart-mega-card">
            <div class="chart-card-inner">
              
              <div class="chart-meta-row">
                <span class="chart-spec-tag">测试规格：1080P · 16:9 · 5 秒文生视频</span>
                <span class="chart-model-tag">使用模型：Seedance 2.5 </span>
              </div>

              <!-- 纯 CSS 科技风对比柱状图 -->
              <div class="chart-visual-wrapper">
                <div class="y-axis-labels">
                  <span>30</span>
                  <span>25</span>
                  <span>20</span>
                  <span>15</span>
                  <span>10</span>
                  <span>5</span>
                  <span>0</span>
                </div>

                <div class="bars-canvas">
                  <!-- 刻度参考虚线 -->
                  <div class="grid-line line-30"></div>
                  <div class="grid-line line-25"></div>
                  <div class="grid-line line-20"></div>
                  <div class="grid-line line-15"></div>
                  <div class="grid-line line-10"></div>
                  <div class="grid-line line-5"></div>
                  <div class="grid-line line-0"></div>

                  <!-- 柱子 1：我方平台 -->
                  <div class="bar-column">
                    <div class="bar-value-label self-highlight">
                      <span class="price-val">¥18.71</span>
                      <span class="cost-adv-tag">核心成本优势</span>
                    </div>
                    <div class="bar-track">
                      <!-- 18.71 / 30 ≈ 62.3% -->
                      <div class="bar-fill self-bar" style="height: 62.3%;">
                        <div class="bar-top-glow"></div>
                      </div>
                    </div>
                    <div class="bar-x-label active-platform">
                      <strong>我方平台</strong>
                      <small>(使用API)</small>
                    </div>
                  </div>

                  <!-- 柱子 2：行业主流大平台 A -->
                  <div class="bar-column">
                    <div class="bar-value-label">
                      <span class="price-val">¥25.92</span>
                      <span class="diff-tag">+¥7.21 / 贵 27.8%</span>
                    </div>
                    <div class="bar-track">
                      <!-- 25.92 / 30 = 86.4% -->
                      <div class="bar-fill competitor-bar-a" style="height: 86.4%;"></div>
                    </div>
                    <div class="bar-x-label">
                      <span>行业主流大平台 A</span>
                      <small>(最高档会员折算)</small>
                    </div>
                  </div>

                  <!-- 柱子 3：行业主流大平台 B -->
                  <div class="bar-column">
                    <div class="bar-value-label">
                      <span class="price-val">¥26.74</span>
                      <span class="diff-tag">+¥8.03 / 贵 30.0%</span>
                    </div>
                    <div class="bar-track">
                      <!-- 26.74 / 30 = 89.1% -->
                      <div class="bar-fill competitor-bar-b" style="height: 89.1%;"></div>
                    </div>
                    <div class="bar-x-label">
                      <span>行业主流大平台 B</span>
                      <small>(最高档会员折算)</small>
                    </div>
                  </div>

                </div>
              </div>

              <!-- 强制要求的注释说明文字 -->
              <div class="pricing-note-strip">
                <svg class="info-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>注：成本计算未计算暂时的优惠活动，行业主流平台成本计算使用最高档会员下的积分使用折算。</span>
              </div>

              <!-- 底部直达工作台按钮 -->
              <div class="chart-action-bar">
                <button class="pricing-cta-btn" @click="enterWorkspace">
                  即刻体验低成本高质创作
                </button>
              </div>

            </div>
          </div>

        </div>
      </section>

    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import request from '@/utils/request';

const router = useRouter();
const scrollContainerRef = ref<HTMLElement | null>(null);
const aboutSectionRef = ref<HTMLElement | null>(null);
const pricingSectionRef = ref<HTMLElement | null>(null);

const isLoggedIn = ref(false);

onMounted(async () => {
  await checkLoginState();
});

async function checkLoginState() {
  try {
    const res: any = await request.get('/users/me'); // 后端契约 4.10[cite: 7]
    if (res && res.id) {
      isLoggedIn.value = true;
    } else {
      isLoggedIn.value = false;
    }
  } catch (err) {
    isLoggedIn.value = false;
  }
}

function enterWorkspace() {
  router.push('/workspace');
}

function scrollToAbout() {
  aboutSectionRef.value?.scrollIntoView({ behavior: 'smooth' });
}

function scrollToPricing() {
  pricingSectionRef.value?.scrollIntoView({ behavior: 'smooth' });
}

function scrollToTop() {
  scrollContainerRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
}
</script>

<style scoped>
/* 全屏容器 */
.landing-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  background-color: #07090e;
  overflow: hidden;
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif;
  user-select: none;
}

/* 顶部导航 */
.landing-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  height: clamp(60px, 7.5vh, 80px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(24px, 4vw, 56px);
  background: rgba(7, 9, 14, 0.75);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.brand-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 700;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.4);
}
.brand-name {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.nav-right {
  display: flex;
  align-items: center;
  gap: 24px;
}
.nav-btn {
  color: #94a3b8;
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
  cursor: pointer;
}
.nav-btn:hover {
  color: #ffffff;
}
.login-btn {
  padding: 6px 16px;
  border: 1px solid #2e384d;
  border-radius: 6px;
  background-color: #121826;
}
.login-btn:hover {
  background-color: #1a2336;
  border-color: #6366f1;
}

/* 用户头像 SVG 徽章 */
.user-avatar-btn {
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-circle {
  position: relative;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(56, 189, 248, 0.25));
  border: 1px solid rgba(99, 102, 241, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f8fafc;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.3);
}
.user-avatar-svg {
  width: 20px;
  height: 20px;
  color: #e2e8f0;
}
.online-status-dot {
  position: absolute;
  bottom: 1px;
  right: 1px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #10b981;
  border: 2px solid #07090e;
  box-shadow: 0 0 6px #10b981;
}
.avatar-circle:hover {
  transform: translateY(-2px) scale(1.06);
  border-color: #818cf8;
  box-shadow: 0 0 18px rgba(99, 102, 241, 0.6);
}

/* 整屏吸附滚动容器：强制隐藏滚动条 */
.snap-container {
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  overflow-y: scroll;
  overflow-x: hidden;
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
  position: relative;
  z-index: 10;
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
}
.snap-container::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
}

.snap-section {
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  min-height: 100vh;
  scroll-snap-align: start;
  scroll-snap-stop: always;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  box-sizing: border-box;
}

/* ================= 第一屏 Hero ================= */
.hero-screen {
  padding-top: clamp(64px, 8vh, 90px);
  padding-bottom: clamp(20px, 3vh, 36px);
}
.hero-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  width: min(92vw, 1300px);
  margin: auto 0;
}
.badge-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid rgba(99, 102, 241, 0.3);
  padding: 8px 22px;
  border-radius: 30px;
  font-size: 14px;
  color: #cbd5e1;
  margin-bottom: 24px;
  backdrop-filter: blur(8px);
}
.pulse-point {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #38bdf8;
  box-shadow: 0 0 8px #38bdf8;
  animation: pulse 2s infinite;
  flex-shrink: 0;
}
.main-title {
  font-size: clamp(34px, 4.8vw, 68px);
  font-weight: 800;
  line-height: 1.24;
  letter-spacing: -0.5px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 85vw;
}
.gradient-text {
  background: linear-gradient(
    90deg,
    #818cf8 0%,
    #38bdf8 25%,
    #34d399 50%,
    #f472b6 75%,
    #818cf8 100%
  );
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: rainbowFlow 5s linear infinite;
}
@keyframes rainbowFlow {
  0% { background-position: 0% 50%; }
  100% { background-position: 300% 50%; }
}
.sub-title {
  font-size: clamp(15px, 1.3vw, 19px);
  color: #94a3b8;
  max-width: min(90vw, 760px);
  line-height: 1.65;
  margin-bottom: clamp(24px, 4vh, 44px);
}
.cta-wrapper {
  position: relative;
  margin-bottom: clamp(24px, 4vh, 44px);
}
.launch-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #ffffff;
  border: 1px solid #818cf8;
  padding: clamp(14px, 2vh, 20px) clamp(36px, 3.5vw, 56px);
  border-radius: 14px;
  font-size: clamp(16px, 1.25vw, 20px);
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 10px 30px -6px rgba(99, 102, 241, 0.6);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.launch-btn:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 16px 40px -4px rgba(99, 102, 241, 0.8);
  border-color: #a5b4fc;
}
.btn-arrow { width: 22px; height: 22px; transition: transform 0.25s ease; }
.launch-btn:hover .btn-arrow { transform: translateX(5px); }
.btn-glow {
  position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, transparent 60%);
  pointer-events: none; opacity: 0; transition: opacity 0.3s;
}
.launch-btn:hover .btn-glow { opacity: 1; }

.feature-metrics {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(20px, 3vw, 48px);
  background: rgba(18, 24, 38, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 16px clamp(24px, 3.5vw, 44px);
  border-radius: 18px;
  backdrop-filter: blur(12px);
  width: min(92vw, 840px);
}
.metric-item { display: flex; flex-direction: column; gap: 4px; text-align: left; }
.metric-value { font-size: clamp(15px, 1.2vw, 18px); font-weight: 700; color: #f8fafc; }
.metric-desc { font-size: clamp(12px, 0.95vw, 14px); color: #94a3b8; }
.divider { width: 1px; height: 30px; background-color: rgba(255, 255, 255, 0.12); }

.scroll-down-hint {
  position: absolute;
  bottom: clamp(12px, 2.5vh, 28px);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #64748b;
  font-size: 14px;
  transition: color 0.2s;
  animation: floatUpDown 2s infinite ease-in-out;
  z-index: 20;
}
.scroll-down-hint:hover { color: #94a3b8; }
.scroll-arrow { width: 18px; height: 18px; }
@keyframes floatUpDown { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(6px); } }

/* ================= 第二屏：产品介绍 ================= */
.about-screen {
  padding-top: clamp(70px, 8vh, 90px);
  padding-bottom: clamp(24px, 3vh, 36px);
  background: linear-gradient(180deg, rgba(7, 9, 14, 0.4) 0%, rgba(10, 13, 22, 0.95) 100%);
}
.about-container {
  width: min(94vw, 1480px);
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.external-header {
  margin-bottom: clamp(20px, 3.5vh, 38px);
  text-align: center;
}
.platform-main-title {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  font-size: clamp(28px, 3.4vw, 52px);
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.5px;
}
.en-title { font-weight: 800; }
.logo-symbol {
  width: clamp(32px, 3.4vw, 48px);
  height: clamp(32px, 3.4vw, 48px);
  color: #818cf8;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.logo-symbol svg { width: 100%; height: 100%; }
.cn-title { font-weight: 700; color: #f1f5f9; }

.tapnow-card {
  width: 100%;
  background: rgba(12, 16, 26, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 28px;
  padding: clamp(36px, 4vw, 64px);
  backdrop-filter: blur(24px);
  box-shadow: 0 30px 70px -15px rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: clamp(36px, 4vw, 64px);
  box-sizing: border-box;
}
.card-left-content {
  flex: 1.25;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
}
.left-big-heading {
  font-size: clamp(34px, 3.8vw, 54px);
  font-weight: 800;
  line-height: 1.22;
  color: #f8fafc;
  margin-bottom: clamp(16px, 2.2vh, 26px);
  letter-spacing: -0.5px;
}
.left-desc-text {
  font-size: clamp(15px, 1.25vw, 19px);
  line-height: 1.85;
  color: #94a3b8;
  margin-bottom: clamp(28px, 4vh, 44px);
  max-width: 620px;
}
.left-action-btn {
  background-color: #ffffff;
  color: #0b0f19;
  font-size: clamp(15px, 1.2vw, 18px);
  font-weight: 700;
  padding: 16px 44px;
  border-radius: 14px;
  border: none;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 6px 22px rgba(255, 255, 255, 0.18);
}
.left-action-btn:hover {
  transform: translateY(-2px);
  background-color: #f1f5f9;
  box-shadow: 0 10px 28px rgba(255, 255, 255, 0.3);
}

.card-right-preview {
  flex: 1;
  width: 100%;
  max-width: 540px;
}
.brief-preview-box {
  background: #0d121f;
  border: 1px solid #1e2638;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
  text-align: left;
}
.preview-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.preview-title { font-size: 18px; font-weight: 700; color: #f8fafc; }
.preview-version-pill {
  background-color: #1e293b;
  color: #38bdf8;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
}
.preview-status-strip {
  background-color: #111827;
  border: 1px solid #1e293b;
  padding: 10px 14px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.strip-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #cbd5e1;
}
.strip-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #eab308;
  flex-shrink: 0;
}
.strip-confirm-btn {
  background-color: #1e293b;
  color: #38bdf8;
  border: 1px solid #334155;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.preview-fields-container {
  background-color: #101625;
  border: 1px solid #1c2639;
  border-radius: 10px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  scrollbar-width: none;
}
.preview-fields-container::-webkit-scrollbar { display: none; }
.field-block .field-title {
  font-size: 13px;
  color: #94a3b8;
  margin-bottom: 4px;
  font-weight: 500;
}
.field-block .field-desc {
  font-size: 14px;
  color: #e2e8f0;
  line-height: 1.55;
}
.field-block .field-desc strong { color: #f8fafc; }
.prompt-preview-shell {
  background-color: #0b0f19;
  border: 1px solid #1b2436;
  padding: 10px 12px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 13px;
  color: #38bdf8;
}

/* ================= 第三屏：价格优势看板 ================= */
.pricing-screen {
  padding-top: clamp(70px, 8vh, 90px);
  padding-bottom: clamp(24px, 3vh, 36px);
  background: linear-gradient(180deg, rgba(10, 13, 22, 0.95) 0%, rgba(7, 9, 14, 0.98) 100%);
}

.pricing-container {
  width: min(94vw, 1300px);
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* 电脑端标题容器：设为纵向列排布，实现小胶囊严格置于大字正上方 */
.pricing-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: clamp(20px, 3.5vh, 36px);
}

/* 蓝色小胶囊：电脑端居中位于大字上方 */
.pricing-header .section-badge-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.3);
  padding: 4px 16px;
  border-radius: 20px;
  margin-bottom: 14px; /* 与下方大字拉开呼吸感间距 */
  width: fit-content;
}

.pricing-sub-desc {
  font-size: clamp(14px, 1.15vw, 17px);
  color: #94a3b8;
  margin-top: 12px;
}

/* 核心图表卡片主体 */
.chart-mega-card {
  width: 100%;
  background: rgba(14, 19, 31, 0.75);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 28px;
  padding: clamp(28px, 3.5vw, 48px);
  backdrop-filter: blur(24px);
  box-shadow: 0 30px 70px -15px rgba(0, 0, 0, 0.85);
  box-sizing: border-box;
}
.chart-card-inner {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.chart-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #94a3b8;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 12px;
}
.chart-spec-tag {
  color: #cbd5e1;
  font-weight: 600;
}
.chart-model-tag {
  color: #818cf8;
  font-family: monospace;
}

/* 柱状图主布局 */
.chart-visual-wrapper {
  display: flex;
  height: clamp(240px, 32vh, 320px);
  margin-top: 20px;
  position: relative;
}
.y-axis-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding-right: 18px;
  color: #64748b;
  font-size: 13px;
  font-family: monospace;
  text-align: right;
  height: 80%; /* 与柱体区域对齐 */
}
.bars-canvas {
  flex: 1;
  position: relative;
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  border-bottom: 2px solid rgba(255, 255, 255, 0.15);
  padding-bottom: 4px;
}

/* 背景参考虚线 */
.grid-line {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px dashed rgba(255, 255, 255, 0.08);
  pointer-events: none;
}
.line-30 { top: 0%; }
.line-25 { top: 16.6%; }
.line-20 { top: 33.3%; }
.line-15 { top: 50%; }
.line-10 { top: 66.6%; }
.line-5  { top: 83.3%; }
.line-0  { bottom: 0%; border-top: none; }

/* 单个柱子列 */
.bar-column {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: clamp(100px, 16vw, 180px);
  height: 100%;
  justify-content: flex-end;
}
.bar-value-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 12px;
  text-align: center;
}
.bar-value-label .price-val {
  font-size: clamp(16px, 1.4vw, 22px);
  font-weight: 800;
  color: #94a3b8;
}
.bar-value-label .diff-tag {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}
.bar-value-label.self-highlight .price-val {
  color: #6366f1;
  font-size: clamp(20px, 1.8vw, 28px);
  text-shadow: 0 0 16px rgba(99, 102, 241, 0.6);
}
.bar-value-label .cost-adv-tag {
  font-size: 13px;
  font-weight: 700;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
  padding: 2px 8px;
  border-radius: 4px;
  margin-top: 3px;
}

.bar-track {
  width: clamp(48px, 6vw, 76px);
  height: 80%;
  display: flex;
  align-items: flex-end;
}
.bar-fill {
  width: 100%;
  border-radius: 8px 8px 0 0;
  position: relative;
  transition: height 1s cubic-bezier(0.16, 1, 0.3, 1);
  animation: growUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes growUp {
  from { transform: scaleY(0); transform-origin: bottom; }
  to { transform: scaleY(1); transform-origin: bottom; }
}

/* 我方柱体高亮发光 */
.self-bar {
  background: linear-gradient(180deg, #6366f1 0%, #4338ca 100%);
  box-shadow: 0 0 24px rgba(99, 102, 241, 0.5);
  border: 1px solid #818cf8;
  border-bottom: none;
}
.bar-top-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: #a5f3fc;
  box-shadow: 0 0 10px #38bdf8;
}

/* 竞品柱体：低饱和冷灰蓝 */
.competitor-bar-a {
  background: linear-gradient(180deg, #64748b 0%, #334155 100%);
  border: 1px solid #94a3b8;
  border-bottom: none;
  opacity: 0.85;
}
.competitor-bar-b {
  background: linear-gradient(180deg, #94a3b8 0%, #475569 100%);
  border: 1px solid #cbd5e1;
  border-bottom: none;
  opacity: 0.8;
}

.bar-x-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 14px;
  font-size: 14px;
  color: #94a3b8;
  text-align: center;
}
.bar-x-label.active-platform {
  color: #ffffff;
}
.bar-x-label.active-platform strong {
  font-size: 16px;
  color: #818cf8;
}
.bar-x-label small {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

/* 必须包含的注释条 */
.pricing-note-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(18, 24, 38, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 13px;
  color: #94a3b8;
  margin-top: 10px;
}
.info-icon {
  width: 16px;
  height: 16px;
  color: #38bdf8;
  flex-shrink: 0;
}

.chart-action-bar {
  display: flex;
  justify-content: flex-end;
}
.pricing-cta-btn {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #ffffff;
  border: 1px solid #818cf8;
  padding: 12px 32px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 4px 18px rgba(99, 102, 241, 0.4);
}
.pricing-cta-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.6);
  border-color: #a5b4fc;
}

/* ================= 动态背景动效 ================= */
.ambient-glow {
  position: fixed; top: 25%; left: 50%; transform: translate(-50%, -50%);
  width: min(80vw, 700px); height: min(50vh, 400px);
  background: radial-gradient(ellipse at center, rgba(99, 102, 241, 0.15) 0%, rgba(56, 189, 248, 0.05) 50%, transparent 80%);
  pointer-events: none; filter: blur(60px);
}
.lines-layer { position: fixed; inset: 0; pointer-events: none; overflow: hidden; }
.light-line {
  position: absolute; width: 2px; height: 180vh;
  background: linear-gradient(180deg, transparent 0%, rgba(99, 102, 241, 0.6) 50%, transparent 100%);
  transform: rotate(-35deg); opacity: 0.25;
}
.line-1 { left: 15%; animation: moveLine 9s linear infinite; }
.line-2 { left: 38%; opacity: 0.18; animation: moveLine 13s linear infinite 3s; }
.line-3 { left: 65%; opacity: 0.3; animation: moveLine 8s linear infinite 1.5s; }
.line-4 { left: 88%; opacity: 0.15; animation: moveLine 11s linear infinite 5s; }
@keyframes moveLine { 0% { transform: translateY(-60%) rotate(-35deg); } 100% { transform: translateY(60%) rotate(-35deg); } }

.stars-layer { position: fixed; inset: 0; pointer-events: none; }
.star {
  position: absolute; background-color: #ffffff; border-radius: 50%;
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.8); animation: twinkle ease-in-out infinite alternate;
}
@keyframes twinkle { 0% { opacity: 0.1; transform: scale(0.6); } 100% { opacity: 1; transform: scale(1.4); } }
@keyframes pulse { 0% { opacity: 0.5; transform: scale(0.9); } 50% { opacity: 1; transform: scale(1.2); } 100% { opacity: 0.5; transform: scale(0.9); } }

.star-1  { top: 12%; left: 18%; width: 2px; height: 2px; animation-duration: 2.2s; }
.star-2  { top: 22%; left: 75%; width: 3px; height: 3px; animation-duration: 3.1s; animation-delay: 0.5s; }
.star-3  { top: 40%; left: 88%; width: 2px; height: 2px; animation-duration: 1.8s; animation-delay: 1.2s; }
.star-4  { top: 68%; left: 12%; width: 3px; height: 3px; animation-duration: 2.5s; animation-delay: 0.8s; }
.star-5  { top: 82%; left: 30%; width: 2px; height: 2px; animation-duration: 3.5s; }
.star-6  { top: 18%; left: 45%; width: 2px; height: 2px; animation-duration: 2.7s; animation-delay: 1.5s; }
.star-7  { top: 55%; left: 22%; width: 2px; height: 2px; animation-duration: 2.1s; }
.star-8  { top: 75%; left: 82%; width: 3px; height: 3px; animation-duration: 2.9s; animation-delay: 0.3s; }
.star-9  { top: 32%; left: 8%;  width: 2px; height: 2px; animation-duration: 3.8s; }
.star-10 { top: 88%; left: 62%; width: 2px; height: 2px; animation-duration: 2.4s; }
.star-11 { top: 10%; left: 92%; width: 2px; height: 2px; animation-duration: 1.9s; }
.star-12 { top: 50%; left: 95%; width: 2px; height: 2px; animation-duration: 3.2s; }
.star-13 { top: 8%;  left: 35%; width: 3px; height: 3px; animation-duration: 2.8s; }
.star-14 { top: 62%; left: 72%; width: 2px; height: 2px; animation-duration: 2.6s; animation-delay: 1.1s; }
.star-15 { top: 30%; left: 60%; width: 2px; height: 2px; animation-duration: 3.4s; }
.star-16 { top: 85%; left: 15%; width: 2px; height: 2px; animation-duration: 2.3s; }
.star-17 { top: 25%; left: 28%; width: 2px; height: 2px; animation-duration: 1.7s; }
.star-18 { top: 70%; left: 48%; width: 2px; height: 2px; animation-duration: 3.6s; }

/* ================= 移动端适配 (<= 868px) ================= */
@media (max-width: 868px) {
  .nav-link-about,
  .nav-link-pricing,
  .nav-link-api {
    display: none;
  }
  .snap-container {
    scroll-snap-type: none;
  }
  .snap-section {
    scroll-snap-align: none;
    height: auto;
    min-height: 100dvh;
    padding-top: 76px;
    padding-bottom: 40px;
  }
  .hero-container {
    margin: 20px auto 0;
  }
  .main-title {
    font-size: 8.5vw;
    line-height: 1.3;
  }
  .sub-title {
    font-size: 3.8vw;
  }
  .feature-metrics {
    flex-direction: column;
    gap: 12px;
    padding: 16px 20px;
    width: 88vw;
  }
  .divider {
    width: 80%;
    height: 1px;
  }
  .metric-item {
    text-align: center;
    align-items: center;
  }
  .scroll-down-hint {
    display: none;
  }

  /* 第二屏移动端 */
  .about-container { width: 90vw; }
  .platform-main-title { font-size: 6vw; flex-wrap: wrap; gap: 6px; }
  .tapnow-card {
    display: flex;
    flex-direction: column;
    padding: 28px 20px;
    gap: 24px;
  }
  .card-left-content { display: contents; }
  .left-big-heading { order: 1; font-size: 7vw; margin-bottom: 8px; text-align: center; width: 100%; }
  .left-desc-text { order: 1; font-size: 3.8vw; margin-bottom: 8px; text-align: center; width: 100%; }
  .card-right-preview { order: 2; max-width: 100%; width: 100%; }
  .left-action-btn { order: 3; width: 100%; max-width: 320px; margin: 8px auto 0 auto; padding: 14px 0; font-size: 16px; }

.pricing-container { width: 90vw; }
  .chart-mega-card { padding: 20px 14px; }
  .chart-visual-wrapper { height: 260px; }
  .y-axis-labels { display: none; }
  .bar-track { width: 36px; }
  .bar-value-label .price-val { font-size: 15px; }
  .bar-value-label.self-highlight .price-val { font-size: 18px; }
  .bar-value-label .cost-adv-tag { font-size: 10px; }
  .bar-value-label .diff-tag { font-size: 9px; }
  .bar-x-label { font-size: 11px; }
  .bar-x-label small { display: none; }
  .pricing-note-strip { font-size: 11px; }
  .chart-action-bar { justify-content: center; }
  .pricing-cta-btn { width: 100%; }
}
</style>