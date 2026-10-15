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
  path: '/tv',
  name: 'TV',
    component: () => import('@/views/Tv.vue'),
},
{
  path: '/tv/admin',
  name: 'TVAdmin',
  component: () => import('@/views/TVAdmin.vue'),
  meta: {
    title: 'TV 素材库管理控制台'
  }
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
