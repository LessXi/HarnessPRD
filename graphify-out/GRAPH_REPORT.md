# Graph Report - debug-observability  (2026-06-21)

## Corpus Check
- 83 files · ~29,702 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 95 nodes · 146 edges · 11 communities (10 shown, 1 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f344e16a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]

## God Nodes (most connected - your core abstractions)
1. `classify_error()` - 26 edges
2. `Exception` - 16 edges
3. `Settings` - 15 edges
4. `ErrorCategory` - 8 edges
5. `mock_response()` - 6 edges
6. `RateLimitError` - 5 edges
7. `APITimeoutError` - 5 edges
8. `ContentFilterError` - 5 edges
9. `AuthenticationError` - 5 edges
10. `test_classify_by_class_name_rate_limit()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Response` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `APITimeoutError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `AuthenticationError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `ContentFilterError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py
- `RateLimitError` --uses--> `ErrorCategory`  [INFERRED]
  backend/tests/test_error_classifier.py → backend/core/error_classifier.py

## Import Cycles
- None detected.

## Communities (11 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.11
Nodes (11): BaseSettings, 应用配置，基于 pydantic-settings 从 .env 读取。  工作方式： 1. 自动从 backend/.env 读取环境变量（如果该文件存, 校验所选 provider 的 API key 是否已配置。缺失时只给 warning，不阻塞启动, 全局配置类。      每个字段对应一个 .env key（不区分大小写）。     字段的默认值写在类型注解后面——当 .env 或系统环境变量都没有提, Settings, 测试 core.config 的可观测性字段验证。, 验证合法值：INFO→INFO, debug→DEBUG, tracing=true + api_key="" → 输出 warning (+3 more)

### Community 1 - "Community 1"
Cohesion: 0.20
Nodes (9): 1. 依赖与配置 (P0), 2. loguru 日志核心 (P0), 3. 请求中间件与错误分类 (P0), 4. LangSmith 集成与 Prompt 追踪 (P0), 5. 启动配置校验 (P1), 6. Debug API 端点 (P1), 7. 前端 debugLogger 工具 (P1), 8. 前端日志集成 (P1) (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.50
Nodes (3): Change: debug-observability, Mode: review_mode=standard, tdd_mode=tdd, Subagent-Driven Development Progress Ledger

### Community 5 - "Community 5"
Cohesion: 0.31
Nodes (9): classify_error(), ErrorCategory, _message_indicates_auth(), _message_indicates_content_filter(), _message_indicates_rate_limit(), _message_indicates_timeout(), 错误分类器 —— 根据异常类型和消息内容返回结构化分类。, 根据异常类型和消息内容返回 ErrorCategory。      匹配顺序：     1. 异常类名     2. 异常消息关键词     3. httpx. (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (9): Response, mock_response(), HTTPStatusError 4xx → HTTP_CLIENT_ERROR, HTTPStatusError 5xx → HTTP_SERVER_ERROR, HTTPStatusError 4xx 但消息含 'rate' → LLM_RATE_LIMIT (消息优先), 创建 mock httpx.Response, test_classify_http_4xx(), test_classify_http_5xx() (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (19): Exception, 测试 error_classifier 模块, 消息含 'rate' → LLM_RATE_LIMIT, 消息含 '429' → LLM_RATE_LIMIT, 消息含 'timeout' → LLM_TIMEOUT, 消息含 'timed out' → LLM_TIMEOUT, 消息同时含 'content' 和 'filter' → LLM_CONTENT_FILTER, 消息含 'auth' → LLM_AUTH (+11 more)

### Community 8 - "Community 8"
Cohesion: 0.50
Nodes (4): APITimeoutError, 模仿 LangChain/OpenAI 的 APITimeoutError, 类名 APITimeoutError → LLM_TIMEOUT, test_classify_by_class_name_timeout()

### Community 9 - "Community 9"
Cohesion: 0.50
Nodes (4): AuthenticationError, 模仿 LangChain/OpenAI 的 AuthenticationError, 类名 AuthenticationError → LLM_AUTH, test_classify_by_class_name_auth()

### Community 10 - "Community 10"
Cohesion: 0.50
Nodes (4): ContentFilterError, 模仿 LangChain/OpenAI 的 ContentFilterError, 类名 ContentFilterError → LLM_CONTENT_FILTER, test_classify_by_class_name_content_filter()

### Community 11 - "Community 11"
Cohesion: 0.50
Nodes (4): RateLimitError, 模仿 LangChain/OpenAI 的 RateLimitError, 类名 RateLimitError → LLM_RATE_LIMIT, test_classify_by_class_name_rate_limit()

## Knowledge Gaps
- **12 isolated node(s):** `Change: debug-observability`, `Mode: review_mode=standard, tdd_mode=tdd`, `Current Task`, `1. 依赖与配置 (P0)`, `2. loguru 日志核心 (P0)` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `classify_error()` connect `Community 5` to `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `Exception` connect `Community 7` to `Community 5`, `Community 8`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Settings` (e.g. with `TestLangSmithTracing` and `TestLogLevel`) actually correct?**
  _`Settings` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `ErrorCategory` (e.g. with `Response` and `APITimeoutError`) actually correct?**
  _`ErrorCategory` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Change: debug-observability`, `Mode: review_mode=standard, tdd_mode=tdd`, `Current Task` to the rest of the system?**
  _40 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.11067193675889328 - nodes in this community are weakly interconnected._