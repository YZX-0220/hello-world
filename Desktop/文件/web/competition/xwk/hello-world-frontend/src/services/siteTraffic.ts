/** Anonymous visit reports; retries preserve the event id and never block navigation. */
export interface TrafficSummary {
  total_visits: number;
  started_at: string | null;
  session_timeout_minutes: number;
}

export interface VisitEvent {
  event_id: string;
  path: string;
  referrer_origin: string | null;
}

export interface TrafficTransport {
  summary(): Promise<TrafficSummary>;
  track(event: VisitEvent): Promise<TrafficSummary>;
}

const trackedPaths = new Set(['/', '/login', '/workspace', '/tv', '/settings/api']);

export function trafficReferrerOrigin(referrer: string): string | null {
  try {
    const url = new URL(referrer);
    return ['http:', 'https:'].includes(url.protocol) ? url.origin : null;
  } catch { return null; }
}

export class SiteTrafficTracker {
  private queue: Promise<void> = Promise.resolve();
  private options: {
    transport: TrafficTransport;
    eventId: () => string;
    referrer: () => string;
    onSummary: (summary: TrafficSummary) => void;
    onUnavailable: () => void;
    withLock?: (run: () => Promise<void>) => Promise<void>;
  };

  constructor(options: {
    transport: TrafficTransport;
    eventId: () => string;
    referrer: () => string;
    onSummary: (summary: TrafficSummary) => void;
    onUnavailable: () => void;
    withLock?: (run: () => Promise<void>) => Promise<void>;
  }) { this.options = options; }

  private publish(summary: TrafficSummary) {
    if (!Number.isSafeInteger(summary.total_visits) || summary.total_visits < 0)
      throw new Error('Invalid traffic total');
    this.options.onSummary(summary);
  }

  visit(path: string): Promise<void> {
    if (!trackedPaths.has(path)) return Promise.resolve();
    const event: VisitEvent = {
      event_id: this.options.eventId(), path,
      referrer_origin: trafficReferrerOrigin(this.options.referrer()),
    };
    const run = async () => {
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          // Establish the HttpOnly visitor cookie BEFORE a write. A lost write response
          // can then be retried with the same identity and durable event id.
          this.publish(await this.options.transport.summary());
          this.publish(await this.options.transport.track(event));
          return;
        } catch (error) {
          const status = (error as { status?: number })?.status;
          if (attempt === 1 || (status && status < 500 && status !== 422)) {
            this.options.onUnavailable();
            return;
          }
        }
      }
    };
    const job = async () => {
      try {
        if (this.options.withLock) await this.options.withLock(run);
        else await run();
      } catch { this.options.onUnavailable(); }
    };
    this.queue = this.queue.then(job, job);
    return this.queue;
  }
}
