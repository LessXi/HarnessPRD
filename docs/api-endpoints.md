# HarnessPRD API 端点清单

> 版本 3.0 · 2026-06-20
>
> 基于 stateless 后端架构，共 8 个端点。
>
> **SSE 事件格式**（所有 SSE 端点统一）：
> ```
> data: {"event":"chunk","content":"<逐 token 文本>"}
> data: {"event":"done","assistant_content":"<完整回复>"}   // 聊天端点含 assistant_content
> data: {"event":"done"}                                     // 文档端点无 assistant_content
> data: {"event":"error","content":"<错误信息>"}
> ```

**基础路径**：`/api`

---

## 端点列表

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 1 | `GET` | `/api/questions` | 返回表单配置（步骤一动态渲染用） |
| 2 | `POST` | `/api/chat/stream` | SSE 聊天流式端点。Body: `{session_id, form_data, history}` |
| 3 | `POST` | `/api/summary/generate` | 生成结构化需求摘要。Body: `{session_id, form_data, history}` |
| 4 | `POST` | `/api/documents/{type}/stream` | SSE 文档生成端点。`type`: `prd` / `api` / `prompts`。Body: `{session_id, form_data, requirements_summary, previous_content?, prd_content?, api_content?}` |
| 5 | `POST` | `/api/documents/{type}/optimize` | SSE 审阅→改写端点。Body: `{session_id, content, form_data, requirements_summary, prd_content?, api_content?}` |
| 6 | `POST` | `/api/documents/{type}/download` | 下载 `.md` 文件。Body: `{content}` |
| 7 | `GET` | `/` | 根路径，返回 API 基础信息 |
| 8 | `GET` | `/health` | 健康检查 |

---

## 端点详述

### 1. `GET /api/questions`

返回表单配置，供步骤一动态渲染。无参数。

**响应示例**：
```json
{
  "fields": [
    {
      "key": "product_name",
      "label": "产品名称",
      "type": "text",
      "required": true,
      "max_length": 100
    }
  ]
}
```

### 2. `POST /api/chat/stream`

SSE 流式聊天。前端发送完整上下文，后端无状态回复。

**Request Body**：
```json
{
  "session_id": "uuid-v4",
  "form_data": { "product_name": "..." },
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**SSE 事件**：
- `chunk`：逐 token 输出 AI 回复
- `done`：回复完成。`assistant_content` 包含完整回复文本
- `error`：出错时推送

### 3. `POST /api/summary/generate`

非流式端点。基于对话历史生成结构化需求摘要。

**Request Body**：
```json
{
  "session_id": "uuid-v4",
  "form_data": { "product_name": "..." },
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**Response**：
```json
{
  "summary": "## 需求摘要\n\n### 目标用户\n..."
}
```

### 4. `POST /api/documents/{type}/stream`

SSE 流式文档生成。`type` 为 `prd` / `api` / `prompts`。

**Request Body**：
```json
{
  "session_id": "uuid-v4",
  "form_data": { "product_name": "..." },
  "requirements_summary": "## 需求摘要...",
  "previous_content": "",
  "prd_content": "...",
  "api_content": "..."
}
```

| 字段 | 适用场景 |
|------|---------|
| `previous_content` | 恢复已生成内容（用于刷新恢复或 Rewrite 续写） |
| `prd_content` | 生成 `api` / `prompts` 时传入已确认的 PRD |
| `api_content` | 生成 `prompts` 时传入已确认的接口文档 |

**SSE 事件**：
- `chunk`：逐 token 输出文档内容
- `done`：生成完成（无 `assistant_content`）
- `error`：出错时推送

### 5. `POST /api/documents/{type}/optimize`

SSE 流式审阅→改写。系统自动执行 Review→Rewrite 循环。

**Request Body**：
```json
{
  "session_id": "uuid-v4",
  "content": "当前文档全文...",
  "form_data": { "product_name": "..." },
  "requirements_summary": "## 需求摘要...",
  "prd_content": "...",
  "api_content": "..."
}
```

**SSE 事件**：
- `chunk`：逐 token 输出审核或改写结果
- `done`：优化完成（无 `assistant_content`）
- `error`：出错时推送

### 6. `POST /api/documents/{type}/download`

下载 `.md` 文件。`type` 为 `prd` / `api` / `prompts`。

**Request Body**：
```json
{
  "content": "# 文档全文..."
}
```

**Response**：`Content-Type: text/markdown`，返回 `.md` 文件流。

### 7. `GET /`

**Response**：
```json
{
  "name": "HarnessPRD API",
  "version": "3.0",
  "endpoints": [
    "/api/questions",
    "/api/chat/stream",
    "/api/summary/generate",
    "/api/documents/{type}/stream",
    "/api/documents/{type}/optimize",
    "/api/documents/{type}/download",
    "/health"
  ]
}
```

### 8. `GET /health`

**Response**：
```json
{
  "status": "ok"
}
```

---

## 统计

| 维度 | 数值 |
|------|------|
| 总端点 | 8 个 |
| HTTP 端点 | 5 个 |
| SSE 端点 | 3 个（chat/stream, documents/stream, documents/optimize） |
| 无状态 | 全部：每次请求携带完整上下文 |
