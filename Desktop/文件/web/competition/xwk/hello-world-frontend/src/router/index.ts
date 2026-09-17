import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: () => import('@/views/LandingView.vue'), // 首页（公开）
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('@/views/WorkspaceView.vue'),
    meta: { requiresAuth: true }, // 需要登录
  },
  {
    path: '/settings/api',
    name: 'ApiConfig',
    component: () => import('@/views/ApiConfigView.vue'),
    meta: { requiresAuth: true }, // 需要登录
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'), // 登录页（公开）
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 全局路由守卫
router.beforeEach((to, from, next) => {
  // 定义不需要登录即可访问的公开路径白名单
  const publicPages = ['/', '/login'];
  const authRequired = !publicPages.includes(to.path);
  
  // 检查本地是否有登录凭据（例如检查 Cookie 或 Pinia/localStorage 中的登录态）
  // 注：根据您的后端契约，通常通过读取 Cookie 或发送鉴权请求来判断，这里假设用一个简单的判断函数
  const loggedIn = document.cookie.includes('hw_session'); // 或者检查您的登录状态管理

  if (authRequired && !loggedIn) {
    // 如果去需要权限的页面但没登录，才跳转到登录页
    return next('/login');
  }

  // 访问首页或已登录，正常放行
  next();
});

export default router;