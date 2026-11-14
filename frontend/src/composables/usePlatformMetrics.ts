import { computed, onMounted, reactive } from 'vue';
import request from '@/utils/request';
import { platformStats } from '@/config/platformStats';

interface PageLike<T> {
  items?: T[];
  next_cursor?: string | null;
}

export interface TrafficSummary {
  total_visits?: number;
  total_tokens?: number;
  total_creations?: number;
  creations_breakdown?: { videos?: number; images?: number };
  total_users?: number;
  published_works?: number;
  daily_tokens_14d?: Array<{ date: string; tokens: number }>;
}

async function safeGet<T>(url: string, config?: Record<string, unknown>): Promise<T | null> {
  try {
    return (await request.get(url, config)) as T;
  } catch {
    return null;
  }
}

function countOf(value: unknown): { count: number | null; capped: boolean } {
  if (Array.isArray(value)) return { count: value.length, capped: false };
  if (value && typeof value === 'object') {
    const page = value as PageLike<unknown>;
    if (Array.isArray(page.items)) {
      return { count: page.items.length, capped: Boolean(page.next_cursor) };
    }
  }
  return { count: null, capped: false };
}

/** 千分位；null 统一显示为占位符 */
export function formatCount(value: number | null): string {
  if (value === null) return '—';
  return new Intl.NumberFormat('zh-CN').format(value);
}

export interface DailyBar {
  label: string;
  date: string;
  height: number;
  tokens: number;
}

export function usePlatformMetrics() {
  const state = reactive({
    visits: null as number | null,
    works: null as number | null,
    worksCapped: false,
    tokens: null as number | null,
    creations: null as number | null,
    videos: null as number | null,
    images: null as number | null,
    users: null as number | null,
    daily: [] as Array<{ day: string; tokens: number }>,
    updatedAt: '' as string,
    loading: true,
  });

  /** Token 优先取后端汇总，其次退回本地配置注入 */
  const tokenTotal = computed(() => state.tokens ?? platformStats.tokenTotal);
  const hasToken = computed(() => tokenTotal.value !== null);
  const hasCreations = computed(() => state.creations !== null);

  const formattedTokens = computed(() => formatCount(tokenTotal.value));
  const formattedVisits = computed(() => formatCount(state.visits));
  const formattedCreations = computed(() => formatCount(state.creations));
  const formattedVideos = computed(() => formatCount(state.videos));
  const formattedImages = computed(() => formatCount(state.images));
  const formattedUsers = computed(() => formatCount(state.users));
  const formattedWorks = computed(() =>
    state.works === null ? '—' : `${formatCount(state.works)}${state.worksCapped ? '+' : ''}`,
  );

  const dailyBars = computed<DailyBar[]>(() => {
    const points = state.daily.length ? state.daily : platformStats.dailyTokens;
    if (!points.length) return [];
    const max = Math.max(...points.map((p) => p.tokens), 1);
    return points.slice(-14).map((p) => ({
      date: p.day,
      label: p.day.slice(5).replace('-', '/'),
      tokens: p.tokens,
      height: Math.max(6, Math.round((p.tokens / max) * 100)),
    }));
  });

  const hasDaily = computed(() => dailyBars.value.length > 0);

  async function load() {
    state.loading = true;
    const [traffic, library] = await Promise.all([
      safeGet<TrafficSummary>('/site-traffic/summary'),
      safeGet<unknown>('/material-library', { params: { limit: 50 } }),
    ]);

    const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

    state.visits = num(traffic?.total_visits);
    state.tokens = num(traffic?.total_tokens);
    state.creations = num(traffic?.total_creations);
    state.videos = num(traffic?.creations_breakdown?.videos);
    state.images = num(traffic?.creations_breakdown?.images);
    state.users = num(traffic?.total_users);
    state.daily = Array.isArray(traffic?.daily_tokens_14d)
      ? traffic!.daily_tokens_14d!
          .filter((d) => typeof d?.date === 'string' && typeof d?.tokens === 'number')
          .map((d) => ({ day: d.date, tokens: d.tokens }))
      : [];

    if (typeof traffic?.published_works === 'number') {
      state.works = traffic.published_works;
      state.worksCapped = false;
    } else {
      const libraryCount = countOf(library);
      state.works = libraryCount.count;
      state.worksCapped = libraryCount.capped;
    }

    state.updatedAt = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    state.loading = false;
  }

  onMounted(load);

  return {
    state,
    tokenTotal,
    hasToken,
    hasCreations,
    hasDaily,
    dailyBars,
    formattedTokens,
    formattedVisits,
    formattedCreations,
    formattedVideos,
    formattedImages,
    formattedUsers,
    formattedWorks,
  };
}
