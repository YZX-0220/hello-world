import assert from 'node:assert/strict';
import { test } from 'node:test';
import { SiteTrafficTracker, trafficReferrerOrigin, type TrafficSummary, type VisitEvent } from '../src/services/siteTraffic.ts';

const summary = (value: number): TrafficSummary => ({
  total_visits: value, started_at: '2026-10-19T12:00:00', session_timeout_minutes: 30,
});

test('direct workspace entry initializes identity before reporting and strips referrer secrets', async () => {
  const calls: string[] = [], events: VisitEvent[] = [], totals: number[] = [];
  const tracker = new SiteTrafficTracker({
    transport: {
      summary: async () => { calls.push('bootstrap'); return summary(12); },
      track: async event => { calls.push('track'); events.push(event); return summary(13); },
    },
    eventId: () => 'first', referrer: () => 'https://search.example/find?secret=private#token',
    onSummary: value => { totals.push(value.total_visits); },
    onUnavailable: () => assert.fail('unexpected failure'),
  });
  await tracker.visit('/workspace');
  assert.deepEqual(calls, ['bootstrap', 'track']);
  assert.deepEqual(totals, [12, 13]);
  assert.deepEqual(events, [{ event_id: 'first', path: '/workspace', referrer_origin: 'https://search.example' }]);
});

test('network retry preserves the event id after a potentially committed request', async () => {
  const events: VisitEvent[] = [];
  let ids = 0, bootstraps = 0;
  const tracker = new SiteTrafficTracker({
    transport: {
      summary: async () => { bootstraps++; return summary(1); },
      track: async event => {
        events.push({ ...event });
        if (events.length === 1) throw new Error('connection lost after commit');
        return summary(1);
      },
    },
    eventId: () => String(++ids), referrer: () => '',
    onSummary: () => {}, onUnavailable: () => assert.fail('retry should recover'),
  });
  await tracker.visit('/');
  assert.equal(ids, 1);
  assert.equal(bootstraps, 2);
  assert.deepEqual(events[0], events[1]);
});

test('rapid navigation is serialized; admin, unknown and API paths are not tracked', async () => {
  const calls: string[] = [];
  let id = 0;
  const tracker = new SiteTrafficTracker({
    transport: {
      summary: async () => { calls.push('bootstrap'); return summary(3); },
      track: async event => { calls.push(event.path); return summary(3); },
    },
    eventId: () => String(++id), referrer: () => '',
    onSummary: () => {}, onUnavailable: () => assert.fail(),
  });
  await Promise.all(['/', '/login', '/tv', '/tv/admin', '/api/v1/video-jobs', '/unknown'].map(path => tracker.visit(path)));
  assert.deepEqual(calls, ['bootstrap', '/', 'bootstrap', '/login', 'bootstrap', '/tv']);
  assert.equal(id, 3);
});

test('a denied request is not retried and does not poison subsequent navigation', async () => {
  let calls = 0, unavailable = 0;
  const counts: number[] = [];
  const tracker = new SiteTrafficTracker({
    transport: {
      summary: async () => summary(7),
      track: async () => {
        calls++;
        if (calls === 1) throw Object.assign(new Error('rate limited'), { status: 429 });
        return summary(8);
      },
    },
    eventId: () => String(calls), referrer: () => '',
    onSummary: value => { counts.push(value.total_visits); },
    onUnavailable: () => { unavailable++; },
  });
  await tracker.visit('/');
  await tracker.visit('/tv');
  assert.equal(calls, 2);
  assert.equal(unavailable, 1);
  assert.deepEqual(counts, [7, 7, 8]);
});

test('an unavailable or malformed service never publishes a made-up zero', async () => {
  for (const bad of [null, -1, 1.5, NaN]) {
    const counts: number[] = [];
    let failures = 0, writes = 0;
    const tracker = new SiteTrafficTracker({
      transport: {
        summary: async () => {
          if (bad === null) throw new Error('offline');
          return summary(bad);
        },
        track: async () => { writes++; return summary(0); },
      },
      eventId: () => 'event', referrer: () => '',
      onSummary: value => { counts.push(value.total_visits); },
      onUnavailable: () => { failures++; },
    });
    await tracker.visit('/');
    assert.deepEqual(counts, []);
    assert.equal(failures, 1);
    assert.equal(writes, 0);
  }
});

test('browser lock wraps bootstrap and report; unsupported referrer protocols are discarded', async () => {
  const calls: string[] = [];
  const tracker = new SiteTrafficTracker({
    transport: {
      summary: async () => { calls.push('bootstrap'); return summary(0); },
      track: async () => { calls.push('track'); return summary(1); },
    },
    eventId: () => 'event', referrer: () => 'javascript:alert(1)',
    onSummary: () => {}, onUnavailable: () => assert.fail(),
    withLock: async run => { calls.push('locked'); await run(); calls.push('unlocked'); },
  });
  await tracker.visit('/');
  assert.deepEqual(calls, ['locked', 'bootstrap', 'track', 'unlocked']);
  assert.equal(trafficReferrerOrigin('javascript:alert(1)'), null);
  assert.equal(trafficReferrerOrigin(''), null);
  assert.equal(trafficReferrerOrigin('https://user:pass@example.com/path?key=private'), 'https://example.com');
});
