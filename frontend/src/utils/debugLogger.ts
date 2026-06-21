type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: number;
  level: LogLevel;
  source: string;
  data: Record<string, unknown>;
}

class DebugLogger {
  private sessionId: string = '';
  private buffer: LogEntry[] = [];
  private enabled: boolean;
  private flushTimer: number | null = null;
  private readonly MAX_BUFFER = 100;
  private readonly BATCH_SIZE = 50;
  private readonly FLUSH_INTERVAL = 5000;

  constructor() {
    // 启用条件: Vite DEV 模式 + 环境变量/存储未显式关闭
    this.enabled = (() => {
      if (!import.meta.env.DEV) return false;
      try {
        const stored = localStorage.getItem('harnessprd:debug');
        if (stored !== null) return stored === 'true';
      } catch {}
      return import.meta.env.VITE_DEBUG_ENABLED !== 'false';
    })();
  }

  setSessionId(id: string): void { this.sessionId = id; }

  log(level: LogLevel, source: string, data: Record<string, unknown>): void {
    if (!this.enabled) return;
    this.buffer.push({ timestamp: Date.now(), level, source, data });
    if (this.buffer.length >= this.BATCH_SIZE) this.flush();
    this.scheduleFlush();
  }

  isEnabled(): boolean { return this.enabled; }

  private scheduleFlush(): void {
    if (this.flushTimer) return;
    this.flushTimer = window.setTimeout(() => {
      this.flush();
      this.flushTimer = null;
    }, this.FLUSH_INTERVAL);
  }

  flush(): void {
    if (this.buffer.length === 0) return;
    const batch = this.buffer.splice(0);
    const payload = { session_id: this.sessionId, logs: batch };
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon('/api/debug/log', blob);
    } else {
      fetch('/api/debug/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {});
    }
    // 防止 buffer 无限增长（极端情况：后端不可达）
    if (this.buffer.length > this.MAX_BUFFER) {
      this.buffer = this.buffer.slice(-this.BATCH_SIZE);
    }
  }
}

export const debugLogger = new DebugLogger();

// Page unload 兜底：确保页面关闭前 flush 剩余日志
window.addEventListener('beforeunload', () => { debugLogger.flush(); });
window.addEventListener('pagehide', () => { debugLogger.flush(); });
