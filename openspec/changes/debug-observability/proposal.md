## Why

HarnessPRD 当前缺少可观测性体系：LLM 调用无追踪、日志零散、无请求链路关联。AI debug 时需在多处 grep 猜测因果链，排查效率低。项目已过 v1 原型阶段（10 个 viewState、Review→Rewrite 循环、多文档生成），流程复杂度需要配套的 AI 可消费 debug 基础设施。

## What Changes

- **新增 LangSmith 集成**：所有 LLM 调用自动上报 trace（prompt/response/token/latency），metadata 携带 session_id 和 doc_type
- **新增 loguru 结构化日志**：替换 Python logging，终端彩色输出 + NDJSON 文件（按天轮转），correlation_id 贯穿全链路
- **新增请求拦截中间件**：FastAPI middleware 记录所有 API 请求的 method/path/耗时/状态码
- **新增 Prompt 渲染追踪**：Jinja2 渲染后的实际 prompt 写入日志（可配置截断长度）
- **新增错误分级与分类**：LLM 错误（rate_limit/timeout/content_filter）/ HTTP 错误 / 业务错误自动分类
- **新增 Debug 诊断端点**：`GET /api/debug/session/{id}` 返回 session 完整诊断数据
- **新增动态日志级别**：`POST /api/debug/log-level` 运行时调整
- **新增启动配置校验**：LangSmith 连通性/API key 有效性/日志目录可写自检
- **新增前端日志上报**：SSE 事件 + viewState 转换自动 POST 到 `/api/debug/log`
- **新增 `.env` 配置项**：`LANGCHAIN_TRACING_V2`、`LANGCHAIN_API_KEY`、`LANGCHAIN_PROJECT`、`LOG_LEVEL`，全部可控关闭

## Capabilities

### New Capabilities

- `llm-observability`: LangSmith 追踪所有 LLM 调用，Prompt 渲染内容追踪，trace metadata 携带 session_id/doc_type
- `structured-logging`: loguru 结构化日志（终端彩色 + NDJSON 文件），请求拦截中间件，错误分级分类，correlation_id 全链路关联
- `debug-api`: GET /api/debug/session/{id} 诊断端点、POST /api/debug/log-level 动态调级、启动配置校验与自检
- `frontend-debug-logging`: 前端 SSE 事件日志、viewState 转换日志、批量 POST 到后端 debug 端点

### Modified Capabilities

<!-- 无现有 capability 被修改 — 全部为新增 -->

## Impact

- **依赖新增**: `langsmith`、`loguru` 加入 `backend/requirements.txt`
- **配置变更**: `backend/.env.example` 新增 4 个配置项
- **后端新增文件**: `core/logging_config.py`、`core/middleware.py`、`core/error_classifier.py`、`api/debug.py`
- **后端修改文件**: `config.py`、`main.py`、`llm_service.py`、`conversation_service.py`、`document_service.py`
- **前端新增文件**: `utils/debugLogger.ts`
- **前端修改文件**: `utils/api.ts`、`store/useProjectStore.ts`
- **非目标**: 不修改现有业务逻辑、不改变 SSE 协议、不引入新数据库/缓存依赖
