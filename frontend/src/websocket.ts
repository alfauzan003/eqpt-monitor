import type { TelemetryEvent } from './types';

type Handler = (e: TelemetryEvent) => void;
type StatusHandler = (connected: boolean) => void;

export class TelemetryWebSocket {
  private ws: WebSocket | null = null;
  private closed = false;
  private reconnectDelay = 1000;

  constructor(
    private onTelemetry: Handler,
    private onStatus: StatusHandler,
  ) {}

  connect(): void {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws/telemetry`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.onStatus(true);
      this.ws?.send(JSON.stringify({ action: 'subscribe_all' }));
    };

    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'telemetry') {
          this.onTelemetry(msg as TelemetryEvent);
        }
      } catch {
        // ignore
      }
    };

    this.ws.onclose = () => {
      this.onStatus(false);
      if (this.closed) return;
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
  }
}
