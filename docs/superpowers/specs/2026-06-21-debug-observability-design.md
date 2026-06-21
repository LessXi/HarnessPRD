---
comet_change: debug-observability
role: technical-design
canonical_spec: openspec
created: 2026-06-21
status: confirmed
---

# Design Doc: AI 可消费的 Debug 可观测性体系

---

## 1. 概述

HarnessPRD 当前仅有启动级 WARNING 日志（Python `logging`），无 LLM 追踪、无请求链路、无结构化日志。当 AI 排查问题时，缺少一条 `correlation_id` 贯穿全链路的数据。

本设计为 HarnessPRD 添加 **AI 优先** 的可观测性体系：
- LangSmith 环境变量零侵入接入，RunnableConfig 补 metadata
- loguru 双 sink（终端彩色 + NDJSON 文件），`contextualize` 协程安全传递 corr_id
- 前端 `debugLogger` 单例批量上报，与 SSE 流式解耦
- 诊断端点为 AI 提供一键聚合查询

### 约束

| 约束 | 影响 |
|------|------|
| 后端无数据库/Redis | Debug 数据仅内存 OrderedDict，FIFO 上限 50 session |
| 不修改 SSE 协议 | SSEMessage 结构不变 |
| LangChain 0.3.x | 原生支持环境变量触发 LangSmith callback |
| React 18 + Zustand | `debugLogger` 单例松耦合，`setSessionId()` 注入 |

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Debug 可观测性架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Browser (前端)                                                      │
│  ┌─────────────┐    ┌──────────────┐                                │
│  │ debugLogger  │───▶│ buffer[100]  │──▶ POST /api/debug/log (5s/50)│
│  │ .setSession  │    │ (RingBuffer) │    └──────────────────────┘    │
│  │ Id(id)       │    └──────────────┘                                │
│  └──────┬───────┘                                                    │
│         │ log() at SSE chunk / state transition / fetch error        │
│         ▼                                                            │
│  ┌─────────────┐                                                     │
│  │ useProject   │───────── session_id ─────────────┐                 │
│  │ Store        │                                  │                 │
│  └─────────────┘                                  │                 │
│                                                    ▼                 │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─     │
│  FastAPI Server                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Middleware Layer                                             │    │
│  │  ┌─────────────────────────┐  ┌──────────────────────────┐  │    │
│  │  │ RequestLogging          │  │ CorrelationMiddleware      │  │    │
│  │  │ method/path/status/ms   │  │ with logger.contextualize │  │    │
│  │  │ → logger.info NDJSON    │  │  (corr_id=uuid4):         │  │    │
│  │  └─────────────────────────┘  │     await call_next()     │  │    │
│  │                               └──────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Service Layer                                               │    │
│  │  conversation_service / document_service / llm_service       │    │
│  │                                                              │    │
│  │  ┌─────────────────────┐  ┌────────────────────────┐        │    │
│  │  │ llm.astream(msgs,   │  │ load_prompt(template,   │        │    │
│  │  │  config={"metadata":│  │  vars) → logger.debug(  │        │    │
│  │  │  {session_id,       │  │  "prompt_rendered",     │        │    │
│  │  │   doc_type}})       │  │  prompt_text[:2000])    │        │    │
│  │  └──────┬──────────────┘  └────────────────────────┘        │    │
│  │         │                                                    │    │
│  │  ┌──────▼──────────────┐  ┌────────────────────────┐        │    │
│  │  │ classify_error(e)   │  │ ErrorCategory enum      │        │    │
│  │  │ → ErrorCategory     │  │ RATE_LIMIT / TIMEOUT   │        │    │
│  │  └─────────────────────┘  │ CONTENT_FILTER / etc.   │        │    │
│  │                           └────────────────────────┘        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Debug API Layer                                             │    │
│  │  POST /api/debug/log          → 前端日志收集                  │    │
│  │  GET  /api/debug/session/{id} → AI 聚合查询 (JSON)           │    │
│  │  POST /api/debug/log-level    → 运行时动态调级                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌──────────┐  ┌──────────────────┐  ┌────────────────────────┐    │
│  │ LangChain│─▶│ LangSmith Cloud  │  │ loguru                  │    │
│  │ Callback │  │ (trace dashboard)│  │ stderr (彩色) + NDJSON   │    │
│  └──────────┘  └──────────────────┘  └────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 详细设计

### 3.1 correlation_id 全链路贯穿

**方案**: `logger.contextualize(corr_id=id)` 包裹 ASGI 请求处理链

```python
# backend/middleware/correlation.py
from loguru import logger
from uuid import uuid4

async def correlation_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID", str(uuid4()))
    with logger.contextualize(corr_id=corr_id):
        request.state.correlation_id = corr_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
```

**关键保证**:
- `logger.contextualize` 底层使用 `ContextVar`，asyncio 协程安全
- 所有 service 函数中 `logger.info(...)` 自动携带 `corr_id`，无需手动 `bind()`
- 响应头返回 `X-Correlation-ID`，前端可缓存作为 `session_id`
- try/finally 确保异常路径也正确退出上下文

### 3.2 LangSmith 追踪

**接入方式**:
1. 环境变量 `LANGCHAIN_TRACING_V2=true` 触发 LangChain 内置 callback 自动注入
2. `pip install 'langsmith<1.0'`（langsmith SDK ≥0.1.0 与 LangChain 0.3 兼容）

**Metadata 注入 (RunnableConfig)**:
```python
# 在 5 个 LLM 调用点各自加 config 参数
stream = await llm.astream(
    messages,
    config={
        "metadata": {
            "session_id": session_id,
            "doc_type": doc_type,     # "chat" | "prd" | "api" | "prompts"
        }
    }
)
```

**调用点清单**（共 5 处）:

| # | 文件 | 函数 | doc_type |
|---|------|------|----------|
| 1 | `conversation_service.py` | `chat_stream()` | `chat` |
| 2 | `conversation_service.py` | `generate_summary()` | `chat` |
| 3 | `document_service.py` | `generate_document_stream()` | 动态 `prd`/`api`/`prompts` |
| 4 | `document_service.py` | `optimize_document_stream()` → Review 调用 | 动态 |
| 5 | `document_service.py` | `optimize_document_stream()` → Rewrite 调用 | 动态 |

**LangSmith 项目名**: `LANGCHAIN_PROJECT` 环境变量控制，默认 `"HarnessPRD"`

### 3.3 loguru 结构化日志

**双 Sink 配置**:

```python
# backend/core/logging.py
from loguru import logger
import sys

def setup_logging():
    logger.remove()  # 清空默认 handler

    # Sink 1: 终端彩色输出 (非 DEBUG 时)
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{extra[corr_id]:15.15}</cyan> | <level>{message}</level>",
        level=config.LOG_LEVEL,
        colorize=True,
    )

    # Sink 2: NDJSON 文件 (始终记录，含所有 extra 字段)
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.ndjson",
        format="{extra[ndjson]}",
        level="DEBUG",
        rotation="00:00",      # 每天午夜轮转
        retention="7 days",     # 保留 7 天
        serialize=True,         # 序列化 extra 为 JSON
        encoding="utf-8",
    )
```

**NDJSON 记录格式**:
```json
{
  "timestamp": "2026-06-21T14:35:22.123456",
  "level": "DEBUG",
  "correlation_id": "abc-123-def",
  "message": "chat started",
  "module": "conversation_service",
  "function": "chat_stream",
  "line": 42,
  "extra": {
    "event": "chat_started",
    "session_id": "abc-123-def",
    "doc_type": "chat"
  }
}
```

**结构化日志规范** — 每条日志的 `extra` 必须含 `event` 字段，取值:

| event 值 | 层级 | 含义 |
|----------|------|------|
| `request_start` | INFO | API 请求开始 |
| `request_complete` | INFO | API 请求完成 |
| `request_failed` | ERROR | API 请求异常 |
| `chat_started` | INFO | 对话流开始 |
| `sse_chunk` | DEBUG | SSE chunk 发送 |
| `sse_done` | INFO | SSE 流结束 |
| `sse_error` | ERROR | SSE 流错误 |
| `prompt_rendered` | DEBUG | Prompt 渲染后内容 |
| `llm_call_start` | INFO | LLM 调用开始 |
| `llm_call_complete` | INFO | LLM 调用完成 |
| `llm_error` | ERROR | LLM 调用异常 (含 error_category) |
| `doc_generation_start` | INFO | 文档生成开始 |
| `doc_generation_complete` | INFO | 文档生成完成 |
| `doc_optimization_round` | INFO | Review→Rewrite 轮次 |
| `frontend_log` | DEBUG | 前端批量上报的日志 |
| `config_change` | WARNING | 运行时配置变更 |
| `startup_check` | WARNING | 启动校验结果 |
| `debug_store_full` | WARNING | 诊断存储满 |

**Python logging → loguru 桥接**:
```python
# 使用 InterceptHandler 将标准库 logging 转发到 loguru
# 确保 uvicorn、langchain 等三方库日志不丢失
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

### 3.4 Prompt 渲染追踪

```python
# backend/services/llm_service.py
from loguru import logger
from backend.core.config import settings

def load_prompt(template_name: str, **variables) -> str:
    # 现有 Jinja2 渲染逻辑
    prompt_text = render_template(template_name, variables)

    # Debug 追踪 (无侵入增量)
    logger.bind(event="prompt_rendered").debug(
        "Prompt rendered: {template}",
        template=template_name,
        prompt_text=prompt_text[:settings.PROMPT_LOG_MAX_LENGTH],
        truncated=len(prompt_text) > settings.PROMPT_LOG_MAX_LENGTH,
    )
    return prompt_text
```

### 3.5 错误分类

```python
# backend/core/error_classifier.py
from enum import Enum

class ErrorCategory(str, Enum):
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_TIMEOUT = "llm_timeout"
    LLM_CONTENT_FILTER = "llm_content_filter"
    LLM_AUTH = "llm_auth"
    LLM_UNKNOWN = "llm_unknown"
    HTTP_CLIENT_ERROR = "http_client_error"
    HTTP_SERVER_ERROR = "http_server_error"
    BUSINESS = "business"
    UNKNOWN = "unknown"

def classify_error(exception: Exception) -> ErrorCategory:
    cls_name = type(exception).__name__
    msg = str(exception).lower()

    # OpenAI / Anthropic / DeepSeek 异常模式匹配
    if "rate" in msg or "429" in msg or "RateLimitError" in cls_name:
        return ErrorCategory.LLM_RATE_LIMIT
    if "timeout" in msg or "timed out" in msg:
        return ErrorCategory.LLM_TIMEOUT
    if "content" in msg and "filter" in msg or "ContentFilterError" in cls_name:
        return ErrorCategory.LLM_CONTENT_FILTER
    if "auth" in msg or "401" in msg or "403" in msg or "key" in msg:
        return ErrorCategory.LLM_AUTH
    # ... 继续细化
    return ErrorCategory.UNKNOWN
```

**使用位置**: 5 个 LLM 调用点的 `try/except` 块中，catch 后 `classify_error(e)` 并将 `error_category` 写入日志 extra。

### 3.6 请求日志中间件

```python
# backend/middleware/request_logging.py
import time
from loguru import logger

async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.bind(event="request_complete").info(
            "{method} {path} → {status} ({duration:.1f}ms)",
            method=request.method, path=request.url.path,
            status=response.status_code, duration=round(duration_ms, 1),
        )
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.bind(event="request_failed").error(
            "{method} {path} → ERROR: {error} ({duration:.1f}ms)",
            method=request.method, path=request.url.path,
            error=str(e), duration=round(duration_ms, 1),
        )
        raise
```

**中间件顺序**: CorrelationMiddleware → RequestLoggingMiddleware → App Router（先种 corr_id，后记录请求）

### 3.7 Debug API 端点

**数据模型**:
```python
# backend/api/debug.py
from collections import OrderedDict

class DebugStore:
    MAX_SESSIONS = 50
    MAX_SESSION_SIZE = 100_000  # bytes

    def __init__(self):
        self._store: OrderedDict[str, dict] = OrderedDict()

    def add_log(self, session_id: str, log_entry: dict):
        if session_id not in self._store:
            if len(self._store) >= self.MAX_SESSIONS:
                self._store.popitem(last=False)  # FIFO
            self._store[session_id] = {"logs": [], "total_size": 0}
        session = self._store[session_id]
        session["logs"].append(log_entry)
        # 超出大小截断
        if session["total_size"] > self.MAX_SESSION_SIZE:
            session["logs"] = session["logs"][-50:]  # 保留最近 50 条
```

**端点**:
| 端点 | 输入 | 输出 | 安全 |
|------|------|------|------|
| `POST /api/debug/log` | `[{timestamp, level, source, data, session_id}]` | `{"received": N}` | 仅 DEV 环境 (可配置) |
| `GET /api/debug/session/{session_id}` | path param | `{session_id, logs: [...], count}` | 仅 DEV 环境 |
| `POST /api/debug/log-level` | `{"level": "DEBUG"}` | `{"previous": "INFO", "current": "DEBUG"}` | 仅 DEV 环境 |

**动态调级实现**:
```python
# 修改 loguru handler 的 level
for handler_id in logger._core.handlers:
    if handler_id != 0:  # skip stderr
        logger._core.handlers[handler_id]._levelno = new_level_int
```

### 3.8 前端 debugLogger

```typescript
// frontend/src/utils/debugLogger.ts

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: number;
  level: LogLevel;
  source: string;     // e.g. "sse:readStream", "state:transition"
  data: Record<string, unknown>;
}

class DebugLogger {
  private sessionId: string = '';
  private buffer: LogEntry[] = [];
  private enabled: boolean = (import.meta as any).env.DEV;
  private flushTimer: number | null = null;

  setSessionId(id: string) { this.sessionId = id; }

  log(level: LogLevel, source: string, data: Record<string, unknown>) {
    if (!this.enabled) return;
    this.buffer.push({ timestamp: Date.now(), level, source, data });
    if (this.buffer.length >= 50) this.flush();
    this.scheduleFlush();
  }

  private scheduleFlush() {
    if (this.flushTimer) return;
    this.flushTimer = window.setTimeout(() => {
      this.flush();
      this.flushTimer = null;
    }, 5000);
  }

  private flush() {
    if (this.buffer.length === 0) return;
    const batch = this.buffer.splice(0);
    const payload = batch.map(e => ({ ...e, session_id: this.sessionId }));

    // 优先 sendBeacon (page unload 可靠)
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon('/api/debug/log', blob);
    } else {
      fetch('/api/debug/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {}); // silent fail
    }
  }
}

export const debugLogger = new DebugLogger();

// Page unload 兜底
window.addEventListener('beforeunload', () => debugLogger.flush());
```

**调用点** (前端):
| 位置 | source | data |
|------|--------|------|
| `api.ts:readStream()` chunk | `sse:chunk` | `{event_type, chunk_index}` |
| `api.ts:readStream()` done | `sse:done` | `{total_chunks}` |
| `api.ts:readStream()` error | `sse:error` | `{error}` |
| `useProjectStore` viewState setter | `state:transition` | `{from, to}` |
| `api.ts` fetch() error | `fetch:error` | `{url, status, message}` |

### 3.9 启动校验

```python
# backend/main.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await validate_debug_config()  # 非阻塞
    yield

async def validate_debug_config():
    from backend.core.config import settings
    from loguru import logger

    # 1. LangSmith 连通性探测
    if settings.LANGCHAIN_TRACING_V2:
        if not settings.LANGCHAIN_API_KEY:
            logger.bind(event="startup_check").warning(
                "LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY not set"
            )
        else:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get("https://api.smith.langchain.com")
                    if resp.status_code < 500:
                        logger.bind(event="startup_check").info("LangSmith API reachable")
                    else:
                        logger.bind(event="startup_check").warning(
                            "LangSmith API returned {status}", status=resp.status_code
                        )
            except Exception as e:
                logger.bind(event="startup_check").warning(
                    "LangSmith API unreachable: {error}", error=str(e)
                )

    # 2. 日志目录可写检查
    log_dir = Path("backend/logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
    except Exception as e:
        logger.bind(event="startup_check").warning(
            "Log directory not writable: {error}", error=str(e)
        )
```

---

## 4. 完整请求链路示例

```
1. Browser → POST /api/chat/stream
   Header: X-Correlation-ID: abc-123

2. CorrelationMiddleware:
   with logger.contextualize(corr_id="abc-123"):    # ← 种子
     request.state.correlation_id = "abc-123"

3. RequestLoggingMiddleware:
   logger.bind(event="request_start").info(...)

4. conversation_service.chat_stream():
   logger.bind(event="chat_started").info(...)       # ← corr_id 自动带

5. llm_service.stream_chat():
   stream = await llm.astream(
     messages,
     config={"metadata": {"session_id": "abc-123", "doc_type": "chat"}}
   )
   async for chunk in stream:
     logger.bind(event="sse_chunk").debug(...)       # ← corr_id 自动带
     yield SSEMessage(...)

6. LangChain callback → LangSmith Cloud:
   trace { metadata: { session_id: "abc-123", doc_type: "chat" } }

7. Frontend readStream():
   debugLogger.log("info", "sse:chunk", { event_type: "chunk", chunk_index: 0 })

8. AI debug 查询:
   GET /api/debug/session/abc-123
   → { session_id: "abc-123", logs: [...], count: 73 }

   $ grep "abc-123" logs/app_2026-06-21.ndjson | jq .
   → 一次性拉取全链路数据
```

---

## 5. 技术决策汇总

| ID | 决策 | 选择 | 理由 |
|----|------|------|------|
| D1 | LangSmith 接入 | 环境变量 `LANGCHAIN_TRACING_V2` + LangChain callback 自动注入 | 零代码侵入 |
| D1a | Metadata 注入 | `llm.astream(messages, config={"metadata": {...}})` RunnableConfig | LangChain 0.3 原生，async generator 安全 |
| D2 | 日志库 | loguru 双 sink（stderr 彩色 + NDJSON daily rotation / 7d retention）| 简洁，用户选 |
| D3 | corr_id 传递 | `logger.contextualize(corr_id=id)` 包裹 ASGI 处理链 | loguru 原生协程安全，零手动传递 |
| D4 | Prompt 追踪 | `load_prompt()` wrapper → `logger.debug()`，截断 2000 字符 | 源头截获 Jinja2 渲染文本 |
| D5 | 错误分类 | `ErrorCategory` enum + `classify_error()` 模式匹配 | LangSmith 关闭后独立可用 |
| D6 | Debug API 存储 | OrderedDict FIFO 50 session 上限，每 session ≤100KB | 无 DB 约束下够用 |
| D7 | 前端 Logger | 单例 `debugLogger`，`setSessionId()` 注入，buffer 100条，5s/50条批量 POST | 松耦合，防请求风暴 |
| D8 | 启动校验 | lifespan 事件非阻塞检查，失败 WARNING | 不 crash |

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LangSmith SDK 与 LangChain 0.3 不兼容 | 低 | trace 不上报 | `pip install 'langsmith<1.0'` 定版本，启动校验探测 |
| `contextualize` 在 async 嵌套中异常 | 极低 | corr_id 丢失 | middleware try/finally |
| uvicorn reload 导致 loguru handler 重复 | 中 | 日志重复输出 | `logger.remove()` 后按 handler_id 去重 |
| 前端 crash 丢 buffer | 低 | 少量日志丢 | `sendBeacon` + `beforeunload` |
| debug_store OOM | 低 | 内存溢出 | 50 session FIFO + 每 session 100KB 上限 |
| LangSmith 关闭后 prompt 追踪仍写磁盘 | — | 无关 | 由 `LOG_LEVEL` 独立控制 |

---

## 7. 测试策略

| 层级 | 方法 | 覆盖目标 |
|------|------|---------|
| **单元** | `classify_error()` 8 种异常类型输入 | 100% ErrorCategory |
| **单元** | `debugLogger` buffer/flush/sendBeacon 路径 | 边界 (空buffer/满buffer/disabled) |
| **单元** | `DebugStore` FIFO/截断/满 | 50 session 上限行为 |
| **集成** | FastAPI TestClient + middleware | corr_id 传递链、request log 格式 |
| **集成** | Mock LLM + LangSmith 环境变量开关 | trace 开/关、metadata 注入 |
| **集成** | TestClient `POST /api/debug/log-level` | 动态调级即时生效 |
| **E2E** | Playwright 完整工作流 | 表单→对话→文档生成→诊断端点查询 |

---

## 8. 实现计划

见 `openspec/changes/debug-observability/tasks.md` — 22 任务，9 组。

| 优先级 | 组 | 任务 | 依赖 |
|--------|-----|------|------|
| P0 | 1. 配置与依赖 | `.env.example`、`requirements.txt`、`config.py` | — |
| P0 | 2. loguru 日志系统 | `core/logging.py`、`InterceptHandler` | 1 |
| P0 | 3. correlation_id 贯穿 | `middleware/correlation.py`、`middleware/request_logging.py` | 2 |
| P0 | 4. LLM 可观测性 | LangSmith metadata 注入 (5 处)、Prompt 追踪、错误分类 | 3 |
| **P0 门** | **基础可观测体系可用** | | 4 |
| P1 | 5. Debug API 端点 | `api/debug.py`、`debug_store`、动态调级 | 3 |
| P1 | 6. 前端上报 | `debugLogger` 单例、SSE 日志点、状态转换日志 | 4 |
| P1 | 7. 启动配置校验 | `main.py` lifespan | 1 |
| P1 | 8. 前端集成 | `useProjectStore` 集成 `setSessionId()`、注入日志点 | 6 |
| **P1 门** | **AI 可消费的全链路数据就绪** | | 8 |
| P2 | 9. 端到端验证 | Playwright 测试脚本 | 8 |
