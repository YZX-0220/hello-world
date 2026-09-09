<template>
  <div class="landing-page">
    <!-- 1. 动态科技背景层：流光斜线 + 闪烁星光 -->
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

    <!-- 2. 顶部微导航 -->
    <header class="landing-nav">
      <div class="brand">
        <div class="brand-avatar">H</div>
        <span class="brand-name">Hello World</span>
      </div>
      <div class="nav-right">
        <router-link to="/settings/api" class="nav-btn">API 配置中心</router-link>
        <router-link to="/login" class="nav-btn login-btn">登录 / 注册</router-link>
      </div>
    </header>

    <!-- 3. 中央主视觉与行动召唤 (Hero Section) -->
    <main class="hero-container">
      <div class="badge-tag">
        <span class="pulse-point"></span>
        国际传播特化 · 新一代 AI 视频叙事创作引擎
      </div>

      <h1 class="main-title">
        让每一种文化声量，<br />
        <span class="gradient-text">被世界清晰看见。</span>
      </h1>

      <p class="sub-title">
        破除跨文化叙事壁垒 · 自由调度主流底层模型 (BYOK) · 零门槛视听语言构建
      </p>

      <!-- 核心大按钮 -->
      <div class="cta-wrapper">
        <button class="launch-btn" @click="enterWorkspace">
          <span class="btn-text">立即进入创作工作台</span>
          <svg class="btn-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          <div class="btn-glow"></div>
        </button>
      </div>

      <!-- 底部科技指标微章 -->
      <div class="feature-metrics">
        <div class="metric-item">
          <span class="metric-value">BYOK</span>
          <span class="metric-desc">多模型自备 Key 自由调度</span>
        </div>
        <div class="divider"></div>
        <div class="metric-item">
          <span class="metric-value">Agent</span>
          <span class="metric-desc">跨文化分镜精准转译</span>
        </div>
        <div class="divider"></div>
        <div class="metric-item">
          <span class="metric-value">4K HDR</span>
          <span class="metric-desc">电影级画质与运镜设计</span>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();

function enterWorkspace() {
  router.push('/workspace');
}
</script>

<style scoped>
/* 全屏容器 */
.landing-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  background-color: #07090e;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif;
  user-select: none;
}

/* 顶部导航 */
.landing-nav {
  position: relative;
  z-index: 10;
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-avatar {
  width: 34px;
  height: 34px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 700;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  box-shadow: 0 0 16px rgba(99, 102, 241, 0.4);
}
.brand-name {
  font-size: 18px;
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

/* 中央主视觉 (Hero) */
.hero-container {
  position: relative;
  z-index: 10;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 0 20px;
  margin-top: -30px;
}
.badge-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid rgba(99, 102, 241, 0.3);
  padding: 6px 18px;
  border-radius: 30px;
  font-size: 13px;
  color: #cbd5e1;
  margin-bottom: 28px;
  backdrop-filter: blur(8px);
}
.pulse-point {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #38bdf8;
  box-shadow: 0 0 8px #38bdf8;
  animation: pulse 2s infinite;
}
.main-title {
  font-size: 5vw;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.5px;
  margin-bottom: 20px;
  max-width: 80vw;
}
/* 循环流光渐变文字 */
.gradient-text {
  /* 1. 多色环形渐变色板：包含紫蓝、天蓝、翡翠绿、洋红，形成闭环回到起始色 */
  background: linear-gradient(
    90deg,
    #818cf8 0%,
    #38bdf8 25%,
    #34d399 50%,
    #f472b6 75%,
    #818cf8 100%
  );
  /* 2. 背景拉伸为 300%，预留足够的平移流动空间 */
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  
  /* 3. 启用平滑循环滚动动画 (5秒一轮，线性平滑无卡顿) */
  animation: rainbowFlow 5s linear infinite;
}

/* 背景平移动画 */
@keyframes rainbowFlow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 300% 50%;
  }
}
.sub-title {
  font-size: 18px;
  color: #94a3b8;
  max-width: 680px;
  line-height: 1.6;
  margin-bottom: 44px;
}

/* 核心行动召唤大按钮 */
.cta-wrapper {
  position: relative;
  margin-bottom: 60px;
}
.launch-btn {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #ffffff;
  border: 1px solid #818cf8;
  padding: 18px 48px;
  border-radius: 12px;
  font-size: 18px;
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
.launch-btn:active {
  transform: translateY(1px) scale(0.99);
}
.btn-arrow {
  width: 20px;
  height: 20px;
  transition: transform 0.25s ease;
}
.launch-btn:hover .btn-arrow {
  transform: translateX(5px);
}
.btn-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, transparent 60%);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
}
.launch-btn:hover .btn-glow {
  opacity: 1;
}

/* 底部指标微章 */
.feature-metrics {
  display: flex;
  align-items: center;
  gap: 36px;
  background: rgba(18, 24, 38, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
  padding: 16px 36px;
  border-radius: 16px;
  backdrop-filter: blur(12px);
}
.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}
.metric-value {
  font-size: 17px;
  font-weight: 700;
  color: #f8fafc;
}
.metric-desc {
  font-size: 12px;
  color: #64748b;
}
.divider {
  width: 1px;
  height: 26px;
  background-color: rgba(255, 255, 255, 0.1);
}

/* ================= 动态背景动效 ================= */

/* 1. 环境柔光晕 */
.ambient-glow {
  position: absolute;
  top: 30%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 700px;
  height: 400px;
  background: radial-gradient(ellipse at center, rgba(99, 102, 241, 0.15) 0%, rgba(56, 189, 248, 0.05) 50%, transparent 80%);
  pointer-events: none;
  filter: blur(60px);
}

/* 2. 移动的斜线 (Cyber Lines) */
.lines-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.light-line {
  position: absolute;
  width: 2px;
  height: 180vh;
  background: linear-gradient(180deg, transparent 0%, rgba(99, 102, 241, 0.6) 50%, transparent 100%);
  transform: rotate(-35deg);
  opacity: 0.25;
}
.line-1 {
  left: 15%;
  animation: moveLine 9s linear infinite;
}
.line-2 {
  left: 38%;
  opacity: 0.18;
  animation: moveLine 13s linear infinite 3s;
}
.line-3 {
  left: 65%;
  opacity: 0.3;
  animation: moveLine 8s linear infinite 1.5s;
}
.line-4 {
  left: 88%;
  opacity: 0.15;
  animation: moveLine 11s linear infinite 5s;
}
@keyframes moveLine {
  0% { transform: translateY(-60%) rotate(-35deg); }
  100% { transform: translateY(60%) rotate(-35deg); }
}

/* 3. 一闪一闪的星星 (Twinkling Stars) */
.stars-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.star {
  position: absolute;
  background-color: #ffffff;
  border-radius: 50%;
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.8);
  animation: twinkle ease-in-out infinite alternate;
}
@keyframes twinkle {
  0% { opacity: 0.1; transform: scale(0.6); }
  100% { opacity: 1; transform: scale(1.4); }
}
@keyframes pulse {
  0% { opacity: 0.5; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.2); }
  100% { opacity: 0.5; transform: scale(0.9); }
}

/* 各星星随机分布与闪烁周期 */
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
</style>