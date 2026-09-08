import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    redirect: '/workspace',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
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
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;