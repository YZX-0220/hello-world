import { createRouter, createWebHistory } from 'vue-router';

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
  history: createWebHistory(),
  routes,
});

export default router;