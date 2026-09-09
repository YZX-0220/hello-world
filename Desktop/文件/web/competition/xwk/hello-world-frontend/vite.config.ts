import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 代理业务接口到远程服务器
      '/api/v1': {
        target: 'http://47.99.35.159',
        changeOrigin: true,
      },
      '/healthz': {
        target: 'http://47.99.35.159',
        changeOrigin: true,
      },
      '/readyz': {
        target: 'http://47.99.35.159',
        changeOrigin: true,
      }
    }
  }
});