# Graph Report - debug-observability  (2026-06-21)

## Corpus Check
- 89 files · ~30,684 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 152 nodes · 213 edges · 19 communities (15 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `763cf006`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]

## God Nodes (most connected - your core abstractions)
1. `classify_error()` - 26 edges
2. `Exception` - 16 edges
3. `Settings` - 15 edges
4. `_make_health_app()` - 8 edges
5. `ErrorCategory` - 8 edges
6. `TestRequestLoggingMiddleware` - 7 edges
7. `mock_response()` - 6 edges
8. `TestCorrelationMiddleware` - 5 edges
9. `RateLimitError` - 5 edges
10. `APITimeoutError` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Response` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `AuthenticationError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `ContentFilterError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `RateLimitError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `APITimeoutError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py

## Import Cycles
- None detected.

## Communities (19 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (10): BaseSettings, 校验所选 provider 的 API key 是否已配置。缺失时只给 warning，不阻塞启动, 全局配置类。      每个字段对应一个 .env key（不区分大小写）。     字段的默认值写在类型注解后面——当 .env 或系统环境变量都没有提, Settings, 测试 core.config 的可观测性字段验证。, 验证合法值：INFO→INFO, debug→DEBUG, tracing=true + api_key="" → 输出 warning, tracing=true + api_key="sk-xxx" → 无 warning (+2 more)

### Community 1 - "Community 1"
Cohesion: 0.20
Nodes (9): 1. 依赖与配置 (P0), 2. loguru 日志核心 (P0), 3. 请求中间件与错误分类 (P0), 4. LangSmith 集成与 Prompt 追踪 (P0), 5. 启动配置校验 (P1), 6. Debug API 端点 (P1), 7. 前端 debugLogger 工具 (P1), 8. 前端日志集成 (P1) (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.50
Nodes (3): Change: debug-observability, Mode: review_mode=standard, tdd_mode=tdd, Subagent-Driven Development Progress Ledger

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (18): HarnessPRD — FastAPI 应用入口, 应用配置，基于 pydantic-settings 从 .env 读取。  工作方式： 1. 自动从 backend/.env 读取环境变量（如果该文件存, get_logger(), InterceptHandler, Loguru 日志配置：双 sink + InterceptHandler + get_logger 工厂。  用法：     from core.loggin, 创建模块专属的 loguru logger。      用法：         logger = get_logger(__name__)         lo, 配置 loguru 双 sink（终端彩色 + NDJSON 文件）。      调用前会先 ``logger.remove()`` 清空默认 handler，, 将标准 ``logging`` 记录转发到 loguru。      用法示例：         import logging         logging. (+10 more)

### Community 5 - "Community 5"
Cohesion: 0.29
Nodes (9): classify_error(), _message_indicates_auth(), _message_indicates_content_filter(), _message_indicates_rate_limit(), _message_indicates_timeout(), 错误分类器 —— 根据异常类型和消息内容返回结构化分类。, 根据异常类型和消息内容返回 ErrorCategory。      匹配顺序：     1. 异常类名     2. 异常消息关键词     3. httpx., HTTPStatusError 5xx → HTTP_SERVER_ERROR (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.40
Nodes (5): Response, mock_response(), HTTPStatusError 4xx → HTTP_CLIENT_ERROR, 创建 mock httpx.Response, test_classify_http_4xx()

### Community 7 - "Community 7"
Cohesion: 0.19
Nodes (15): Exception, 测试 error_classifier 模块, 消息含 '429' → LLM_RATE_LIMIT, 消息含 'timeout' → LLM_TIMEOUT, 消息同时含 'content' 和 'filter' → LLM_CONTENT_FILTER, 消息含 'auth' → LLM_AUTH, test_classify_by_message_401(), test_classify_by_message_403() (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.33
Nodes (6): ErrorCategory, str, APITimeoutError, 模仿 LangChain/OpenAI 的 APITimeoutError, 类名 APITimeoutError → LLM_TIMEOUT, test_classify_by_class_name_timeout()

### Community 9 - "Community 9"
Cohesion: 0.50
Nodes (4): AuthenticationError, 模仿 LangChain/OpenAI 的 AuthenticationError, 类名 AuthenticationError → LLM_AUTH, test_classify_by_class_name_auth()

### Community 10 - "Community 10"
Cohesion: 0.50
Nodes (4): ContentFilterError, 模仿 LangChain/OpenAI 的 ContentFilterError, 类名 ContentFilterError → LLM_CONTENT_FILTER, test_classify_by_class_name_content_filter()

### Community 11 - "Community 11"
Cohesion: 0.50
Nodes (4): RateLimitError, 模仿 LangChain/OpenAI 的 RateLimitError, 类名 RateLimitError → LLM_RATE_LIMIT, test_classify_by_class_name_rate_limit()

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (14): _make_health_app(), 测试 CorrelationMiddleware 和 RequestLoggingMiddleware。  测试策略： - 用 Starlette 创建小型测试, 断言捕获日志中包含同时包含所有关键字的条目, 成功请求应记录 method/path/status/duration_ms, 500 错误的请求应记录 ERROR 和异常信息, 日志条目应包含 duration_ms 或 'ms' 字样, 创建一个返回 {"status":"ok"} 的小型测试 app。, 验证 correlation_middleware 行为 (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.40
Nodes (4): Request, correlation_middleware(), Correlation ID 中间件。  从 X-Correlation-ID 请求头提取或生成 corr_id， 用 logger.contextualize, 从 X-Correlation-ID 请求头提取或生成 corr_id，注入日志上下文。      1. 提取或生成 corr_id     2. 存入 req

### Community 15 - "Community 15"
Cohesion: 0.40
Nodes (4): Request, 请求日志中间件。  记录所有 API 请求的 method、path、status_code 和处理耗时。 成功和异常路径均有记录。, 记录所有 API 请求的 method/path/status/duration_ms。      成功路径：logger.bind(event="reques, request_logging_middleware()

## Knowledge Gaps
- **15 isolated node(s):** `Request`, `Request`, `LogRecord`, `1. 依赖与配置 (P0)`, `2. loguru 日志核心 (P0)` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 0` to `Community 4`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `classify_error()` connect `Community 5` to `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 13`, `Community 16`, `Community 17`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Settings` (e.g. with `TestLangSmithTracing` and `TestLogLevel`) actually correct?**
  _`Settings` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `ErrorCategory` (e.g. with `Response` and `APITimeoutError`) actually correct?**
  _`ErrorCategory` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Request`, `Correlation ID 中间件。  从 X-Correlation-ID 请求头提取或生成 corr_id， 用 logger.contextualize`, `从 X-Correlation-ID 请求头提取或生成 corr_id，注入日志上下文。      1. 提取或生成 corr_id     2. 存入 req` to the rest of the system?**
  _68 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.11904761904761904 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.09666666666666666 - nodes in this community are weakly interconnected._