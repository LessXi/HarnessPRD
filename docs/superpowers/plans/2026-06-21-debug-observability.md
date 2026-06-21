---
change: debug-observability
design-doc: docs/superpowers/specs/2026-06-21-debug-observability-design.md
base-ref: 9dbd1e8bad66407ffd8306dba856b89dd1ceffd2
---

# 实现计划：AI 可消费的 Debug 可观测性体系

## 1. 概述

为 HarnessPRD 添加 **AI 优先** 的可观测性体系：LangSmith 零侵入 LLM 追踪、loguru 双 sink 结构化日志（终端彩色 + NDJSON 文件）、correlation_id 全链路贯穿、前端 debugLogger 批量上报、诊断 API 端点。所有 debug 数据仅内存存储（OrderedDict FIFO 50 session），不引入数据库/Redis。

## 2. 架构回顾

### 2.1 核心组件关系

```
┌─────────────────────────────────────────────────────────────────┐
│ Browser (前端)                                                    │
│  debugLogger 单例 ← setSessionId(id)                              │
│   ├─ buffer[100] → 5s/50条批量 POST /api/debug/log               │
│   ├─ beforeunload → sendBeacon() 兜底                             │
│   └─ 注入点: readStream() chunk/done/error, viewState 转换        │
├─────────────────────────────────────────────────────────────────┤
│ FastAPI Server (后端)                                             │
│  ┌─ CorrelationMiddleware (with logger.contextualize)             │
│  ├─ RequestLoggingMiddleware (method/path/status/duration)        │
│  ├─ Service Layer                                                 │
│  │   ├─ llm.astream(config={"metadata": {session_id, doc_type}})  │
│  │   ├─ load_prompt() → logger.debug(prompt_text[:2000])          │
│  │   └─ classify_error(e) → ErrorCategory                         │
│  ├─ Debug API (/api/debug/*)                                      │
│  │   └─ DebugStore: OrderedDict FIFO 50 session                   │
│  ├─ LangChain callback → LangSmith Cloud                          │
│  └─ loguru: stderr彩色 + NDJSON文件 (daily rotation, 7d retention) │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 关键数据流

1. **correlation_id 贯穿**: 前端 session_id → 请求头 X-Correlation-ID → middleware `logger.contextualize()` → 所有 service 日志自动携带
2. **LangSmith trace**: `llm.astream(messages, config={"metadata": {...}})` → LangChain callback 自动上报 → LangSmith dashboard
3. **前端上报**: debugLogger.log() → buffer → POST /api/debug/log → DebugStore → GET /api/debug/session/{id} 聚合查询
4. **诊断查询**: AI 可通过 session_id 一键拉取 NDJSON + Debug API 的全链路数据

## 3. 实现顺序与理由

### 顺序策略

按 **自底向上** 顺序：先基础设施（依赖/配置/日志核心），再横切面（中间件/错误分类），再 LLM 注入，最后前端。每层可独立验证。

| 顺序 | 组 | 名称 | 优先级 | 理由 |
|------|-----|------|--------|------|
| 1 | 组1 | 依赖与配置 | P0 | 所有后续任务的前提 — 新增依赖和配置字段 |
| 2 | 组2 | loguru 日志核心 | P0 | 日志系统是所有 observable 输出的基础管道 |
| 3 | 组3 | 请求中间件与错误分类 | P0 | 横切面 — correlation_id 必须先于所有请求处理注入，错误分类是 LLM 注入的前置依赖 |
| 4 | 组4 | LangSmith 集成与 Prompt 追踪 | P0 | **P0 门** — LLM 可观测性注入，依赖日志和中间件已就位 |
| 5 | 组5 | 启动配置校验 | P1 | 依赖 config 字段就绪（组1），非阻塞验证 |
| 6 | 组6 | Debug API 端点 | P1 | 依赖中间件 corr_id 机制和日志系统（组2/3），为前端上报提供后端 |
| 7 | 组7 | 前端 debugLogger 工具 | P1 | 独立工具类，依赖 Debug API 端点（组6）就绪 |
| 8 | 组8 | 前端日志集成 | P1 | 在 debugLogger 工具就绪后，注入到现有代码路径；**P1 门** — AI 可消费的全链路数据就绪 |
| 9 | 组9 | E2E 验证 | P2 | 全链路端到端回归，依赖所有代码完成 |

## 4. 详细任务分解

---

### 组1：依赖与配置 (P0) — 预计 0.5h

---

#### 任务 1.1 — 添加 langsmith、loguru 到 `backend/requirements.txt`

- **文件**: `backend/requirements.txt`（修改）
- **实现要点**:
  - 新增 `langsmith>=0.1,<1.0` — LangChain 0.3 兼容版本
  - 新增 `loguru>=0.7,<1.0` — 结构化日志库
  - 注意：`langsmith` SDK 与 `langchain` 0.3.x 原生集成，无需额外 langchain callback 包
  - 安装验证：`pip install -r requirements.txt`
- **预估代码行数**: +2 行
- **依赖**: 无

---

#### 任务 1.2 — 在 `backend/.env.example` 中添加可观测性配置项

- **文件**: `backend/.env.example`（修改）
- **实现要点**:
  - 新增 `# ======== 可观测性 ========` 区块
  - `LANGCHAIN_TRACING_V2=false` — LangSmith 追踪开关，默认关闭
  - `LANGCHAIN_API_KEY=` — LangSmith API key（tracing 开启时必填）
  - `LANGCHAIN_PROJECT=HarnessPRD` — LangSmith 项目名
  - `LOG_LEVEL=INFO` — 日志级别（DEBUG/INFO/WARNING/ERROR）
  - `PROMPT_LOG_MAX_LENGTH=2000` — Prompt 渲染日志截断长度
  - 每个字段加中文注释说明用途
- **预估代码行数**: +12 行
- **依赖**: 无

---

#### 任务 1.3 — 在 `Settings` 类中添加可观测性配置字段与校验

- **文件**: `backend/core/config.py`（修改）
- **实现要点**:
  - 新增字段:
    ```python
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "HarnessPRD"
    log_level: str = "INFO"
    prompt_log_max_length: int = 2000
    ```
  - 新增 `@field_validator("log_level")` 校验合法值：`{"DEBUG", "INFO", "WARNING", "ERROR"}`
  - 新增 `@model_validator(mode="after")` 方法 `check_langsmith_config`：
    - 若 `langchain_tracing_v2=true` 且 `langchain_api_key` 为空 → `logging.warning(...)`（复用现有 warning 风格，不抛异常）
  - **注意**：config.py 现有 `import logging`，需在新 validator 中继续使用（尚未切换到 loguru），等组2完成后再考虑统一由 InterceptHandler 桥接
- **预估代码行数**: +25 行
- **依赖**: 无

---

### 组2：loguru 日志核心 (P0) — 预计 1h

---

#### 任务 2.1 — 创建 `backend/core/logging_config.py`：loguru 双 sink + InterceptHandler

- **文件**: `backend/core/logging_config.py`（新建）
- **实现要点**:
  - `setup_logging()` 函数:
    1. `logger.remove()` 清空默认 handler
    2. **Sink 1 — 终端彩色输出**:
       ```python
       logger.add(
           sys.stderr,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
                  "<cyan>{extra[corr_id]:15.15}</cyan> | <level>{message}</level>",
           level=config.log_level.upper(),
           colorize=True,
       )
       ```
    3. **Sink 2 — NDJSON 文件**:
       ```python
       logger.add(
           "logs/app_{time:YYYY-MM-DD}.ndjson",
           format="{extra[ndjson]}",
           level="DEBUG",
           rotation="00:00",
           retention="7 days",
           serialize=True,
           encoding="utf-8",
       )
       ```
    4. **注意**：NDJSON 文件路径是相对于当前工作目录（即项目根目录），需要在 `main.py` 启动前确保 `backend/logs/` 路径正确。使用 `Path(__file__).resolve().parent.parent / "logs"` 构造绝对路径。
  - `InterceptHandler` 类：继承 `logging.Handler`，`emit()` 方法将标准库 logging 记录转发到 loguru
  - `get_logger(name: str)` 工厂函数：返回 `logger.bind(module=name)` 的 loguru logger
- **预估代码行数**: ~60 行
- **依赖**: 任务 1.3（Config 字段就绪）
- **Gotcha**: uvicorn 的 reload 模式可能导致 logger handler 重复（每次 reload 都调用 `setup_logging()`）。缓解：`setup_logging()` 开头 `logger.remove()` 后按 handler_id 去重，或仅在首次调用时执行。

---

#### 任务 2.2 — 在 `main.py` 中集成 loguru，替换 uvicorn 默认 logging

- **文件**: `backend/main.py`（修改）
- **实现要点**:
  - 在 `app = FastAPI(...)` 之后、注册 middleware 之前调用 `setup_logging()`
  - 在文件顶部添加 `import logging; from core.logging_config import setup_logging, InterceptHandler`
  - `logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)` — 桥接标准 logging
  - 替换现有 `logging.warning(...)` 为 `logger.warning(...)`（config.py 的启动提示）
  - 启动时输出初始化日志：
    ```python
    logger.bind(event="startup").info("Logging initialized — level={level}", level=settings.log_level)
    ```
- **预估代码行数**: +8 行（修改后）
- **依赖**: 任务 2.1

---

#### 任务 2.3 — 实现 `get_logger(name)` 工厂函数

- **文件**: `backend/core/logging_config.py`（修改 — 追加到 2.1）
- **实现要点**:
  - 已包含在任务 2.1 的实现中
  - 函数签名: `def get_logger(name: str) -> loguru.Logger`
  - 返回 `logger.bind(module=name)` — 自动在 extra 中注入模块名
- **预估代码行数**: +3 行（已计入 2.1）
- **依赖**: 任务 2.1

---

### 组3：请求中间件与错误分类 (P0) — 预计 1.5h

---

#### 任务 3.1 — 创建 CorrelationMiddleware 和 RequestLoggingMiddleware

- **文件**:
  - `backend/middleware/__init__.py`（新建）
  - `backend/middleware/correlation.py`（新建）
  - `backend/middleware/request_logging.py`（新建）
- **实现要点**:

  **CorrelationMiddleware** (`backend/middleware/correlation.py`):
  - 纯 ASGI middleware，`async def correlation_middleware(request: Request, call_next)`
  - 从 `request.headers.get("X-Correlation-ID")` 提取，若无则 `str(uuid4())`
  - 使用 `with logger.contextualize(corr_id=corr_id):` 包裹整个请求处理链
  - `request.state.correlation_id = corr_id`（供下游 service 读取）
  - 响应头设置 `X-Correlation-ID: corr_id`
  - try/finally 确保异常路径也正确退出 contextualize 上下文
  - **Gotcha**: `logger.contextualize()` 底层使用 `ContextVar`，asyncio 协程安全，但需确认 loguru ≥0.7 版本

  **RequestLoggingMiddleware** (`backend/middleware/request_logging.py`):
  - 纯 ASGI middleware
  - 记录：`method`、`path`、`status`、`duration_ms`、`corr_id`
  - 使用 `time.perf_counter()` 计毫秒
  - 事件 event 值：
    - 成功：`request_complete` (INFO)
    - 异常：`request_failed` (ERROR)
  - 日志格式示例：`logger.bind(event="request_complete").info("{method} {path} → {status} ({duration:.1f}ms)", ...)`

  **中间件顺序**: CorrelationMiddleware → RequestLoggingMiddleware → App Router（先种 corr_id，后记录请求）

- **关键注意**: 设计文档（§3.1, §3.6）将两者拆分到独立文件。任务文件中两者合并在 `backend/core/middleware.py`。本计划遵循设计文档的分离方案——职责清晰，各自独立测试。若追求简洁可内联为一个文件，但需合并 `@app.middleware` 注册。
- **预估代码行数**: ~70 行（correlation.py ~30, request_logging.py ~40）
- **依赖**: 任务 2.2（loguru 已初始化）

---

#### 任务 3.2 — 在 `main.py` 注册中间件

- **文件**: `backend/main.py`（修改）
- **实现要点**:
  - 在 CORS middleware 之后注册：
    ```python
    from middleware.correlation import correlation_middleware
    from middleware.request_logging import request_logging_middleware
    
    app.middleware("http")(correlation_middleware)
    app.middleware("http")(request_logging_middleware)
    ```
  - **顺序关键**: CORS → Correlation → RequestLogging → Router。CORS 必须在最外层处理 preflight；Correlation 必须在 RequestLogging 之前以确保 corr_id 已存在。
  - **注意**: FastAPI 的 `app.add_middleware()` 是 LIFO（后注册的先执行），但 `app.middleware("http")` 装饰器是 FIFO（先注册的先执行）。使用 `app.middleware("http")` 装饰器顺序一致。
- **预估代码行数**: +5 行
- **依赖**: 任务 3.1

---

#### 任务 3.3 — 创建错误分类器

- **文件**: `backend/core/error_classifier.py`（新建）
- **实现要点**:
  - `ErrorCategory` enum（8 个值）:
    ```python
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
    ```
  - `classify_error(exception: Exception) -> ErrorCategory` 函数:
    - 基于异常类名 (`type(exception).__name__`) 和消息内容 (`str(exception).lower()`) 的模式匹配
    - 覆盖 OpenAI / Anthropic / DeepSeek 的常见异常：
      - `RateLimitError` / `"rate"` / `"429"` → LLM_RATE_LIMIT
      - `APITimeoutError` / `"timeout"` / `"timed out"` → LLM_TIMEOUT
      - `ContentFilterError` / `"content" + "filter"` → LLM_CONTENT_FILTER
      - `AuthenticationError` / `"auth"` / `"401"` / `"403"` / `"key"` → LLM_AUTH
      - `httpx.HTTPStatusError` 4xx → HTTP_CLIENT_ERROR, 5xx → HTTP_SERVER_ERROR
  - **测试优先**: 为 8 种分类各准备至少 1 个 mock 异常输入
- **预估代码行数**: ~50 行
- **依赖**: 无（纯函数，无外部依赖）

---

### 组4：LangSmith 集成与 Prompt 追踪 (P0) — 预计 1.5h

---

#### 任务 4.1 — 在 startup 事件中配置 LangSmith tracing

- **文件**: `backend/main.py`（修改）
- **实现要点**:
  - 在 `app = FastAPI()` 之后、`setup_logging()` 之后：
    ```python
    if settings.langchain_tracing_v2:
        import langsmith
        langsmith.tracing_v2_enabled()  # 等效于设置 LANGCHAIN_TRACING_V2=true
    ```
  - 等效替代：直接设置环境变量 `os.environ["LANGCHAIN_TRACING_V2"] = "true"` — LangChain 0.3 在 import 时读取环境变量，需在 import langchain 之前设置
  - **Gotcha**: LangChain 在首次 `import langchain` 时读取 `LANGCHAIN_TRACING_V2` 环境变量。如果 `main.py` 已经 `import langchain`（通过 service 间接 import），则需在文件最顶部设置环境变量。建议在 `main.py` 最顶部（uvicorn import 之后、app import 之前）设置：
    ```python
    import os
    from core.config import settings
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    ```
- **预估代码行数**: +10 行
- **依赖**: 任务 1.3（config 字段）

---

#### 任务 4.2 — 在 LLM 调用点注入 LangSmith metadata (RunnableConfig)

- **文件**:
  - `backend/services/llm_service.py`（修改 — 2 处）
  - `backend/services/conversation_service.py`（修改 — 2 处）
  - `backend/services/document_service.py`（修改 — 1 处，_call_llm_once）
- **实现要点**:
  
  **5 个注入点**:
  
  | # | 文件 | 函数 | 行号 | 调用方式 | doc_type |
  |---|------|------|------|----------|----------|
  | 1 | `llm_service.py` | `stream_chat()` | L79 | `llm.astream(messages)` | `"chat"` |
  | 2 | `conversation_service.py` | `generate_summary()` | L104 | `llm.ainvoke(...)` | `"chat"` |
  | 3 | `llm_service.py` | `stream_generate()` | L89 | `llm.astream(messages)` | 动态由调用方传入 |
  | 4 | `document_service.py` | `_call_llm_once()` | L182 | `llm.ainvoke(...)` | 动态由调用方传入 |
  | 5 | `llm_service.py` | `stream_generate()` | L89 | 第二处调用 (Rewrite) | 动态 |

  **修改策略**:
  1. **`stream_chat` 和 `stream_generate`** 新增可选参数：
     ```python
     async def stream_chat(
         system_prompt: str, 
         user_message: str,
         *,
         session_id: str = "",
         doc_type: str = "",
     ) -> AsyncGenerator[str, None]:
     ```
     在 `llm.astream(messages)` 调用中添加 `config` 参数：
     ```python
     config = {}
     if session_id:
         config = {"metadata": {"session_id": session_id, "doc_type": doc_type}}
     await llm.astream(messages, config=config)
     ```
  2. **`conversation_service.chat_stream`** (L82) 和 **`conversation_service.generate_summary`** (L104)：传递 session_id 到 `stream_chat`/`get_llm().ainvoke`
  3. **`document_service.generate_document_stream`** 和 **`optimize_document_stream`**：传递 session_id + doc_type 到 `stream_generate`/`_call_llm_once`
  4. **`conversation_service.generate_summary`** 直接调用 `llm.ainvoke()`，需追加 config：
     ```python
     result = await llm.ainvoke(
         [...],
         config={"metadata": {"session_id": session_id, "doc_type": "chat"}}
     )
     ```
  
  **注意**: session_id 目前在各 service 函数签名中未显式传递。需从 `request.state.correlation_id` 获取（通过 middleware 注入），或在 API route handler 中提取并通过参数传入 service 函数。推荐后者（显式参数）保持 service 无状态可测试。
  
  **API route handler 改动**（非计划核心，但需配合）:
  - `api/conversation.py` 的 `chat_stream` endpoint 从 `request.state.correlation_id` 获取
  - `api/sessions.py` 的 `generate_summary` endpoint 同上
  - `api/documents.py` 的生成/优化 endpoint 同上

- **预估代码行数**: ~40 行（分散在各文件中的小改动）
- **依赖**: 任务 3.1（correlation_id 机制），任务 4.1（LangSmith 环境变量）

---

#### 任务 4.3 — Prompt 渲染追踪（load_prompt wrapper）

- **文件**: `backend/services/llm_service.py`（修改）
- **实现要点**:
  - 在现有 `load_prompt()` 函数中，Jinja2 渲染后追加日志：
    ```python
    from loguru import logger
    from core.config import settings
    
    def load_prompt(name: str, **kwargs) -> str:
        template: Template = _jinja_env.get_template(name)
        prompt_text = template.render(**kwargs)
        
        # 仅在 DEBUG 级别记录（条件检查由 loguru level 控制）
        max_len = settings.prompt_log_max_length
        logger.bind(event="prompt_rendered").debug(
            "Prompt rendered: {template} ({len} chars{truncated})",
            template=name,
            prompt_text=prompt_text[:max_len],
            len=len(prompt_text),
            truncated=", truncated" if len(prompt_text) > max_len else "",
        )
        return prompt_text
    ```
  - **注意**: 截断由 `prompt_log_max_length` 控制（默认 2000），NDJSON 文件中存储完整截断内容
  - **性能考量**: `logger.debug()` 在 INFO 级别时几乎零开销（loguru 跳过 DEBUG 消息），仅在 `LOG_LEVEL=DEBUG` 时生效
- **预估代码行数**: +8 行
- **依赖**: 任务 2.1（loguru 初始化），任务 1.3（config 字段）

---

#### 任务 4.4 — 在 service 调用点添加结构化日志 + 错误分类

- **文件**:
  - `backend/services/conversation_service.py`（修改）
  - `backend/services/document_service.py`（修改）
- **实现要点**:
  
  **conversation_service.py**:
  - `chat_stream()` 开头：`logger.bind(event="chat_started").info("Chat stream started")`
  - `chat_stream()` 异常处理（新增 try/except 包裹 LLM 调用）：
    ```python
    try:
        async for chunk in llm.astream(messages, config=...):
            ...
    except Exception as e:
        category = classify_error(e)
        logger.bind(event="llm_error").error(
            "LLM call failed: {error} [{category}]",
            error=str(e), category=category.value,
        )
        raise
    ```
  - `generate_summary()` — 同上模式，event: `llm_call_complete` / `llm_error`
  
  **document_service.py**:
  - `generate_document_stream()` 开头：`logger.bind(event="doc_generation_start").info("Generating {doc_type}", doc_type=doc_type)`
  - 结束时：`logger.bind(event="doc_generation_complete").info("Generated {doc_type} ({len} chars)", doc_type=doc_type, len=...)`
  - `optimize_document_stream()` 每轮：`logger.bind(event="doc_optimization_round").info("Round {round}/{max}", round=round_num+1, max=max_rounds)`
  - Review/Rewrite 异常分类同 conversation_service 模式

  **注意**: 现有代码中 LLM 调用未包裹 try/except（异常直接冒泡到 FastAPI exception handler）。需在 4-5 处 LLM 调用点添加 try/except 块来捕获并分类异常。

- **预估代码行数**: ~60 行（分散在多处 try/except + log 调用）
- **依赖**: 任务 3.3（错误分类器），任务 4.2（LangSmith metadata）

---

**🎯 P0 门：基础可观测体系可用** — 完成组1-4后，后端将具备：correlation_id 贯穿日志、LangSmith LLM 追踪、Prompt 渲染日志、错误自动分类。可通过启动后端并调用一次 API 验证。

---

### 组5：启动配置校验 (P1) — 预计 0.5h

---

#### 任务 5.1 — 实现 lifespan 事件中的 `validate_debug_config()`

- **文件**: `backend/main.py`（修改）
- **实现要点**:
  - 将现有 `app = FastAPI(...)` 改为带 lifespan：
    ```python
    from contextlib import asynccontextmanager
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await validate_debug_config()
        yield
    
    app = FastAPI(..., lifespan=lifespan)
    ```
  - `validate_debug_config()` 异步函数：
    1. 检查 LangSmith：
       - 若 `settings.langchain_tracing_v2` 且 `settings.langchain_api_key` 为空 → `logger.bind(event="startup_check").warning("LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY not set")`
       - 若有 key，用 `httpx.AsyncClient` ping `https://api.smith.langchain.com`（5s timeout），判断可达性
    2. 检查日志目录可写：
       ```python
       log_dir = Path(__file__).parent / "logs"
       log_dir.mkdir(parents=True, exist_ok=True)
       test_file = log_dir / ".write_test"
       test_file.write_text("ok")
       test_file.unlink()
       ```
    3. 所有失败仅 WARNING，不抛异常
  - **注意**: 使用 `httpx`（已在 requirements.txt 中）
- **预估代码行数**: ~40 行
- **依赖**: 任务 1.3（config 字段），任务 2.1（loguru 初始化）

---

#### 任务 5.2 — 失败场景输出 WARNING 日志，不阻塞启动

- **文件**: `backend/main.py`（修改 — 已计入 5.1）
- **实现要点**: 已包含在 5.1 实现中。确认所有异常分支都 `logger.bind(event="startup_check").warning(...)` 且不 re-raise。
- **预估代码行数**: 0（已计入 5.1）
- **依赖**: 任务 5.1

---

### 组6：Debug API 端点 (P1) — 预计 1.5h

---

#### 任务 6.1 — 创建 `POST /api/debug/log` 端点 + DebugStore

- **文件**: `backend/api/debug.py`（新建）
- **实现要点**:

  **数据模型** (Pydantic):
  ```python
  from pydantic import BaseModel
  
  class LogEntry(BaseModel):
      timestamp: float          # Date.now() 毫秒时间戳
      level: str                # debug | info | warn | error
      source: str               # e.g. "sse:readStream", "state:transition"
      data: dict[str, Any]
  
  class BatchLogRequest(BaseModel):
      session_id: str
      logs: list[LogEntry]
  ```

  **DebugStore**:
  ```python
  from collections import OrderedDict
  
  class DebugStore:
      MAX_SESSIONS = 50
      MAX_SESSION_SIZE = 100_000  # bytes
  
      def __init__(self):
          self._store: OrderedDict[str, dict] = OrderedDict()
  
      def add_log(self, session_id: str, log_entry: dict):
          ...
  
      def get_session(self, session_id: str) -> dict | None:
          ...
  ```
  - FIFO 淘汰: `_store.popitem(last=False)` 删除最旧 session
  - 大小截断: 每 session 保留最近 50 条日志

  **端点**:
  ```python
  router = APIRouter(prefix="/debug", tags=["debug"])
  
  @router.post("/log")
  async def receive_logs(payload: BatchLogRequest):
      for log in payload.logs:
          debug_store.add_log(payload.session_id, log.model_dump())
      return {"received": len(payload.logs)}
  ```
  - **安全**: 仅 DEV 环境下启用。检查 `settings.debug` 标志，非 DEV 返回 404 或空实现
- **预估代码行数**: ~80 行
- **依赖**: 任务 2.1（loguru 就绪以记录 `debug_store_full` 事件）

---

#### 任务 6.2 — 实现 `GET /api/debug/session/{session_id}` 聚合查询

- **文件**: `backend/api/debug.py`（修改 — 追加到 6.1）
- **实现要点**:
  - 端点: `@router.get("/debug/session/{session_id}")`
  - 返回格式:
    ```json
    {
      "session_id": "abc-123",
      "logs": [...],
      "count": 73,
      "aggregations": {
        "llm_calls": 5,
        "sse_events": 47,
        "errors": 2,
        "state_transitions": 3
      }
    }
    ```
  - aggregation 通过遍历 `logs` 按 `source` 前缀聚合
  - 若 session 不存在 → 404 `{"error": "session not found"}`
  - **安全**: 同上，仅 DEV 环境
- **预估代码行数**: ~30 行
- **依赖**: 任务 6.1

---

#### 任务 6.3 — 实现 `POST /api/debug/log-level` 动态调级

- **文件**: `backend/api/debug.py`（修改 — 追加）
- **实现要点**:
  - 请求模型: `class LogLevelRequest(BaseModel): level: str`
  - 校验 level ∈ `{"DEBUG", "INFO", "WARNING", "ERROR"}`
  - 动态调级实现:
    ```python
    from loguru import logger
    
    @router.post("/debug/log-level")
    async def set_log_level(req: LogLevelRequest):
        previous = settings.log_level
        new_level = req.level.upper()
        # 修改 loguru handler 级别
        logger.remove()
        # 重新 add 两个 sink（复用 setup_logging 逻辑）
        # 简单方案：直接修改 handler 的 _levelno
        for handler_id in logger._core.handlers:
            if handler_id != 0:
                logger._core.handlers[handler_id]._levelno = getattr(logger.level(new_level), "no", 20)
        settings.log_level = new_level
        logger.bind(event="config_change").warning(
            "Log level changed: {previous} → {current}",
            previous=previous, current=new_level,
        )
        return {"previous": previous, "current": new_level}
    ```
  - **安全**: 仅 DEV 环境
  - **Gotcha**: `logger._core.handlers` 是内部 API，loguru 版本升级可能变化。备选方案：`logger.remove()` + 重新调用 `setup_logging()` 的简化版。
- **预估代码行数**: ~25 行
- **依赖**: 任务 2.1（loguru handler 结构）

---

#### 任务 6.4 — 注册 debug_router 到 FastAPI app

- **文件**: `backend/main.py`（修改），`backend/api/__init__.py`（可选修改）
- **实现要点**:
  - `from api.debug import router as debug_router`
  - `app.include_router(debug_router)`
  - 挂载路径：`/api/debug`（router 前缀已为 `/debug`，include 不加额外 prefix）
- **预估代码行数**: +2 行
- **依赖**: 任务 6.1-6.3

---

### 组7：前端 debugLogger 工具 (P1) — 预计 1h

---

#### 任务 7.1 — 创建 `debugLogger` 单例（buffer + 批量 POST）

- **文件**: `frontend/src/utils/debugLogger.ts`（新建）
- **实现要点**:
  
  ```typescript
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
    private enabled: boolean = import.meta.env.DEV;
    private flushTimer: number | null = null;
    private readonly MAX_BUFFER = 100;
    private readonly BATCH_SIZE = 50;
    private readonly FLUSH_INTERVAL = 5000;
  
    setSessionId(id: string): void { this.sessionId = id; }
  
    log(level: LogLevel, source: string, data: Record<string, unknown>): void {
      if (!this.enabled) return;
      this.buffer.push({ timestamp: Date.now(), level, source, data });
      if (this.buffer.length >= this.BATCH_SIZE) this.flush();
      this.scheduleFlush();
    }
  
    private scheduleFlush(): void {
      if (this.flushTimer) return;
      this.flushTimer = window.setTimeout(() => {
        this.flush();
        this.flushTimer = null;
      }, this.FLUSH_INTERVAL);
    }
  
    private flush(): void {
      if (this.buffer.length === 0) return;
      const batch = this.buffer.splice(0);
      const payload = {
        session_id: this.sessionId,
        logs: batch,
      };
      // 优先 sendBeacon
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
  ```
  - **注意**: Vite 环境变量 `import.meta.env.DEV` 在 `npm run dev` 时为 true，`npm run build` 时自动 tree-shake（所有 `debugLogger.log()` 调用被移除）
  - **Gotcha**: `fetch()` + `keepalive: true` 在某些浏览器限制 payload 大小（64KB）。sendBeacon 也有限制。单次 50 条日志通常 < 10KB，安全。
- **预估代码行数**: ~70 行
- **依赖**: 无（独立工具类，后端 Debug API 可稍后就绪）

---

#### 任务 7.2 — 实现 pagehide/beforeunload 事件监听

- **文件**: `frontend/src/utils/debugLogger.ts`（修改 — 追加到 7.1）
- **实现要点**:
  - 在类底部（export 之前）或模块顶层注册：
    ```typescript
    // Page unload 兜底
    window.addEventListener('beforeunload', () => {
      debugLogger.flush();
    });
    // pagehide 更可靠（移动端 + bfcache）
    window.addEventListener('pagehide', () => {
      debugLogger.flush();
    });
    ```
  - `flush()` 方法需处理空 buffer 的快速返回（已在 7.1 实现）
- **预估代码行数**: +6 行
- **依赖**: 任务 7.1

---

#### 任务 7.3 — 实现 `isEnabled()` 检查（localStorage 或 env var 开关）

- **文件**: `frontend/src/utils/debugLogger.ts`（修改 — 追加）
- **实现要点**:
  - `enabled` 字段初始化逻辑：
    ```typescript
    private enabled: boolean = (() => {
      // 1. 生产构建始终关闭（tree-shake 保证）
      if (!import.meta.env.DEV) return false;
      // 2. localStorage 覆盖（运行时开关）
      try {
        const stored = localStorage.getItem('harnessprd:debug');
        if (stored !== null) return stored === 'true';
      } catch {}
      // 3. 环境变量覆盖（VITE_DEBUG_ENABLED）
      return import.meta.env.VITE_DEBUG_ENABLED !== 'false';
    })();
    ```
  - 导出 `isEnabled()` 方法供外部检查
  - **注意**: 关闭时 `log()` 为 no-op，zero overhead
- **预估代码行数**: +15 行
- **依赖**: 任务 7.1

---

### 组8：前端日志集成 (P1) — 预计 0.5h

---

#### 任务 8.1 — 在 `readStream()` 中注入 SSE 事件日志

- **文件**: `frontend/src/services/api.ts`（修改）
- **实现要点**:
  - 在文件顶部 `import { debugLogger } from "@/utils/debugLogger";`
  - 在 `readStream()` 函数中：
    - chunk 事件处理（L78）：`debugLogger.log('info', 'sse:readStream', { event_type: 'chunk', chunk_index: chunkCount })`
      - 需添加 `let chunkCount = 0` 计数器，每 chunk 递增
    - done 事件处理（L81）：`debugLogger.log('info', 'sse:readStream', { event_type: 'done', total_chunks: chunkCount })`
    - error 事件处理（L84）：`debugLogger.log('error', 'sse:readStream', { event_type: 'sse_error', error: parsed.content })`
    - 流读取异常（catch block L114）：`debugLogger.log('error', 'sse:readStream', { event_type: 'stream_error', error: msg })`
  - **注意**: `api.ts` 是高频路径（SSE token 流式），每次 chunk 触发一次 `debugLogger.log()`（47+ 次/session）。批量机制（buffer 100，5s flush）确保不会造成请求风暴。
- **预估代码行数**: +12 行
- **依赖**: 任务 7.1（debugLogger 工具）

---

#### 任务 8.2 — 在 ViewState 转换处注入状态日志

- **文件**: `frontend/src/App.tsx`（修改）
- **实现要点**:
  - 在文件顶部 `import { debugLogger } from "@/utils/debugLogger";`
  - **关键发现**: 项目未使用 Zustand — 状态管理在 `App.tsx` 的 `useState` 中。`switchView` 函数（L194）是唯一的 viewState 变更入口。
  - 在 `switchView` 函数中注入日志：
    ```typescript
    const switchView = useCallback((viewState: ViewState) => {
      updateProject((prev) => {
        debugLogger.log('info', 'state:transition', {
          from: prev.viewState,
          to: viewState,
          trigger: 'user_action',
        });
        return { ...prev, viewState };
      });
    }, [updateProject]);
    ```
  - 在 `handleRollback`（L678）中也注入（使用 `state:transition` source）：
    ```typescript
    debugLogger.log('info', 'state:transition', {
      from: project.viewState,
      to: targetStep,
      trigger: 'rollback',
    });
    ```
  - **注意**: 表单提交后自动跳转 `ai_dialogue`（L211）也经过 `switchView`，已自动覆盖。
  - 确保 `setSessionId()` 在 session_id 生成/加载后调用：
    ```typescript
    // 在 project 初始化后
    useEffect(() => {
      if (project.session_id) {
        debugLogger.setSessionId(project.session_id);
      }
    }, [project.session_id]);
    ```
- **预估代码行数**: +15 行
- **依赖**: 任务 7.1（debugLogger），任务 8.1（同组无依赖）

---

**🎯 P1 门：AI 可消费的全链路数据就绪** — 完成组5-8后，AI 可通过 `GET /api/debug/session/{id}` 一键获取 session 的完整诊断数据（请求日志 + LLM 调用 + SSE 事件 + 前端日志 + 错误分类 + 状态转换链路）。

---

### 组9：E2E 验证 (P2) — 预计 1h

---

#### 任务 9.1 — 验证 LangSmith trace

- **验证步骤**:
  1. 设置 `.env` 中 `LANGCHAIN_TRACING_V2=true`，填写有效 `LANGCHAIN_API_KEY`
  2. 启动后端 `uvicorn main:app --reload`
  3. 检查启动日志：`startup_check` 事件输出 LangSmith API reachable
  4. 调用 `POST /api/chat/stream`（可用 curl 或 httpie）
  5. 登录 LangSmith Dashboard → Projects → HarnessPRD → 确认出现新 trace
  6. 点击 trace 查看 metadata → 确认含 `session_id` 和 `doc_type: "chat"`
  7. 验证关闭：`LANGCHAIN_TRACING_V2=false` → 重启 → 调用 API → LangSmith 无新 trace，LLM 调用正常
- **依赖**: 组4（LangSmith 集成）

---

#### 任务 9.2 — 验证 NDJSON 日志文件

- **验证步骤**:
  1. 启动后端后检查 `backend/logs/` 目录自动创建
  2. 调用一次 `/api/chat/stream` 和 `/api/documents/prd/stream`
  3. 检查 `backend/logs/app_{date}.ndjson` 存在
  4. 使用 `rg "corr_id" logs/app_{date}.ndjson` 验证 corr_id 存在
  5. 验证事件类型：grep `request_start`、`chat_started`、`sse_chunk`、`request_complete`
  6. 验证错误日志：触发一次错误（如错误的 API key），检查 `llm_error` 事件含 `error_category`
  7. 验证 Prompt 追踪：`LOG_LEVEL=DEBUG` → 调用 → 检查 `prompt_rendered` 事件含截断文本
- **依赖**: 组2（loguru），组3（中间件），组4（LLM 注入）

---

#### 任务 9.3 — 验证前端上报 → 诊断端点查询

- **验证步骤**:
  1. 启动前后端，打开浏览器 `http://localhost:5173`
  2. 确保 `VITE_DEBUG_ENABLED` 未显式设为 `false`（`import.meta.env.DEV` = true）
  3. 完整走通工作流：表单 → 对话 → 生成 PRD → 优化 → 生成 API → 优化 → 生成提示词 → 优化
  4. 期间打开 DevTools Network 面板，观察定期 POST `/api/debug/log` 请求（5s 间隔或 50 条触发）
  5. 完成后调用 `GET http://localhost:8000/api/debug/session/{session_id}`
  6. 验证返回包含：
     - `logs` 数组非空
     - `count` ＞ 50（完整的 SSE 流会产生大量 chunk 事件）
     - `aggregations.llm_calls` ≈ 7-9（chat + summary + prd gen + review × N + rewrite × N + api gen + ...）
     - `aggregations.state_transitions` ≥ 7（每个步骤转换至少一次）
  7. 触发 page unload（刷新或关闭 tab），在 Network 中看到 `sendBeacon` 调用
- **依赖**: 组6（Debug API），组7（debugLogger），组8（前端集成）

---

#### 任务 9.4 — 验证动态调级

- **验证步骤**:
  1. 启动后端（默认 LOG_LEVEL=INFO），观察终端日志无 DEBUG 消息
  2. `curl -X POST http://localhost:8000/api/debug/log-level -H "Content-Type: application/json" -d '{"level":"DEBUG"}'`
  3. 验证返回：`{"previous": "INFO", "current": "DEBUG"}`
  4. 调用一次 API，观察终端出现 DEBUG 级别日志（如 `sse_chunk`）
  5. `curl -X POST http://localhost:8000/api/debug/log-level -H "Content-Type: application/json" -d '{"level":"INFO"}'`
  6. 调用 API，确认 DEBUG 日志消失
  7. 验证无效 level：`{"level":"TRACE"}` → 400 错误
- **依赖**: 组6.3（动态调级端点）

---

#### 任务 9.5 — 验证 LangSmith 关闭场景

- **验证步骤**:
  1. 设置 `.env`：`LANGCHAIN_TRACING_V2=false`
  2. 重启后端，检查启动日志无 LangSmith 相关 WARNING（若 api_key 为空也不报警，因为 tracing 已关闭）
  3. 调用 `POST /api/chat/stream` 和文档生成 API — 确认 LLM 调用正常
  4. 检查 LangSmith Dashboard — 确认无新 trace
  5. 检查 NDJSON 日志 — 确认 LLM 调用日志正常（不受 LangSmith 开关影响）
  6. 验证后端无报错（无 `ModuleNotFoundError: langsmith` 等）
- **依赖**: 组4（LangSmith 集成），组5（启动校验）

---

## 5. 风险缓解

| 风险 | 概率 | 缓解措施 | 对应任务 |
|------|------|----------|----------|
| **LangSmith SDK 与 LangChain 0.3 不兼容** | 低 | `pip install 'langsmith<1.0'` 锁定版本；启动校验探测 API 可达性 | 1.1, 5.1 |
| **`contextualize` 在 async 嵌套中丢失 corr_id** | 极低 | loguru `ContextVar` 协程安全；middleware try/finally 确保退出；测试验证 | 3.1, 9.2 |
| **uvicorn reload 导致 loguru handler 重复** | 中 | `setup_logging()` 中 `logger.remove()` 清空后再 add；按 handler_id 去重 | 2.1 |
| **前端 crash 丢失 buffer** | 低 | `sendBeacon` + `beforeunload` 兜底；buffer 上限 100 限制损失 | 7.1, 7.2 |
| **debug_store OOM** | 低 | 50 session FIFO + 每 session ≤100KB 截断；触发时 log `debug_store_full` 警告 | 6.1 |
| **Prompt 追踪与 LangSmith 均关闭后 LLM 日志丢失** | — | loguru NDJSON 独立于 LangSmith，由 `LOG_LEVEL` 控制；LLM 调用日志始终写入 NDJSON | 2.1, 4.4 |
| **`frontend/src/utils/api.ts` 路径不存在** | 确定 | 实际路径为 `frontend/src/services/api.ts`，本计划已纠正 | 8.1 |
| **`useProjectStore` (Zustand) 不存在** | 确定 | 状态管理在 `App.tsx` 的 `useState` 中，`switchView` 函数为注入点 | 8.2 |

## 6. 验证清单

| # | 验证项 | 方法 | 通过标准 |
|---|--------|------|----------|
| V1 | 依赖安装 | `pip install -r requirements.txt` 无报错 | import langsmith, loguru 成功 |
| V2 | 配置字段 | 启动后端，检查 `settings.langchain_tracing_v2` 等字段值 | 值与 .env 一致 |
| V3 | 终端日志彩色 | 启动后端，观察 stderr 输出 | 绿色时间戳 + 青色 corr_id + 彩色 level |
| V4 | NDJSON 文件创建 | 启动后端，检查 `backend/logs/` | `app_{date}.ndjson` 存在且含有效 JSON 行 |
| V5 | correlation_id 传递 | 调用 API，检查响应头 | `X-Correlation-ID` 返回 UUID4 |
| V6 | 请求日志 | 调用 API，rg NDJSON 文件 | 含 `request_start`/`request_complete` 事件，带 method/path/status/duration |
| V7 | 错误分类 | 用错误 API key 调用 LLM | 日志 `llm_error` 事件含 `error_category: "llm_auth"` |
| V8 | Prompt 追踪 | LOG_LEVEL=DEBUG 调用 | NDJSON 含 `prompt_rendered` 事件，prompt_text 非空 |
| V9 | LangSmith trace | 开启 tracing 调用 API | Dashboard 出现新 trace，metadata 含 session_id |
| V10 | Debug API log | 浏览器走完整流程 | Network 面板见定期 POST /api/debug/log |
| V11 | Debug API session | `GET /api/debug/session/{id}` | 返回 logs 数组，count > 0 |
| V12 | 动态调级 | `POST /api/debug/log-level` | 终端日志级别即时变化 |
| V13 | LangSmith 关闭 | LANGCHAIN_TRACING_V2=false 重启 | LLM 调用正常，无 LangSmith 报错 |
| V14 | 启动校验 | 错误配置下启动 | WARNING 日志输出，不崩溃 |
