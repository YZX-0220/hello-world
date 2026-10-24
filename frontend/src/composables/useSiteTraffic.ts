import { computed, ref } from 'vue';
import type { Router } from 'vue-router';
import { SiteTrafficTracker, type TrafficSummary, type VisitEvent } from '../services/siteTraffic';

const totalVisits = ref<number | null>(null);
const unavailable = ref(false);
let started = false;

async function trafficRequest(path: string, event?: VisitEvent): Promise<TrafficSummary> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    // Separate from the authenticated API interceptor: traffic never redirects or logs out.
    const response = await fetch('/api/v1/site-traffic/' + path, {
      method: event ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
      signal: controller.signal,
      ...(event ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event) } : {}),
    });
    if (!response.ok) throw Object.assign(new Error('Traffic request failed'), { status: response.status });
    return await response.json();
  } finally { clearTimeout(timer); }
}

export function startSiteTraffic(router: Router) {
  if (started) return;
  started = true;
  const tracker = new SiteTrafficTracker({
    transport: {
      summary: () => trafficRequest('summary'),
      track: event => trafficRequest('visits', event),
    },
    eventId: () => typeof crypto.randomUUID === 'function' ? crypto.randomUUID()
      : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const n = Math.random() * 16 | 0;
        return (c === 'x' ? n : n & 3 | 8).toString(16);
      }),
    referrer: () => document.referrer,
    onSummary: summary => { totalVisits.value = summary.total_visits; unavailable.value = false; },
    onUnavailable: () => { unavailable.value = true; },
    withLock: run => navigator.locks ? navigator.locks.request('hw-site-traffic', run) : run(),
  });
  router.afterEach((to, _from, failure) => {
    if (!failure && document.visibilityState !== 'hidden') void tracker.visit(to.path);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void tracker.visit(router.currentRoute.value.path);
  });
}

export function useSiteTraffic() {
  const formattedVisits = computed(() => totalVisits.value === null ? null
    : new Intl.NumberFormat('zh-CN').format(totalVisits.value));
  return { formattedVisits, unavailable };
}
