import axios, { type AxiosRequestConfig } from 'axios';

// 辅助函数：从 document.cookie 读取 hw_csrf 的值
function getCsrfToken(): string | null {
  const match = document.cookie.match(new RegExp('(^|;\\s*)hw_csrf=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

const service = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true, // 契约规则 1: 必须携带 Cookie
  headers: {
    'Content-Type': 'application/json; charset=utf-8',
  },
});

// 请求拦截器：注入 CSRF Token
service.interceptors.request.use(
  (config) => {
    const method = config.method?.toUpperCase();
    // 契约规则 2: 非查询请求必须携带 X-CSRF-Token
    if (method && ['POST', 'PATCH', 'DELETE'].includes(method)) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：统一拦截 401 并抛出安全化错误
service.interceptors.response.use(
  (response) => {
    // 单个资源直接返回，列表返回分页结构
    return response.data;
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      
      // 契约规则 13: 遇到 401 跳转登录
      if (status === 401) {
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login';
        }
      }
      
      // 提取后端规范化错误对象（包含 code, message, request_id）
      const serverError = data?.error || {
        code: 'UNKNOWN_ERROR',
        message: '网络异常，请稍后重试',
        request_id: error.response.headers['x-request-id'] || ''
      };
      
      return Promise.reject(serverError);
    }
    
    return Promise.reject({
      code: 'NETWORK_ERROR',
      message: '无法连接到服务器',
      request_id: ''
    });
  }
);

export default service;