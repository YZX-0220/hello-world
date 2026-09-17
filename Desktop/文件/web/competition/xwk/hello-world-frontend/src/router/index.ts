import { createRouter, createWebHashHistory } from 'vue-router'; // 1. 修改这里

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: () => import('@/views/LandingView.vue'), // 首页
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('@/views/WorkspaceView.vue'),
  },
  {
    path: '/settings/api',
    name: 'ApiConfig',
    component: () => import('@/views/ApiConfigView.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
  }
];

const router = createRouter({
  history: createWebHashHistory(), // 2. 修改这里（使用 Hash 模式）
  routes,
});

export default router;