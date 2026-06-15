# 接口文档模板

> 版本 1.0 · 2026-06-15
>
> 目标读者：后端开发团队
> 文档目标：基于 PRD 自动生成清晰的 API 设计，为后端开发提供依据
> 前置依赖：`docs/prd-template.md` 第 5 章（交互流程与界面设计）、第 6 章（技术约束）

---

## 第 1 章：文档信息

| 字段 | 内容 |
|------|------|
| 文档名称 | `{产品名称}` 接口文档 |
| 版本号 | v1.0 |
| 更新日期 | `{生成日期}` |
| 关联 PRD | `{产品名称}` PRD v1.0 |
| 文档概述 | 本文档定义 `{产品名称}` 的全部服务端 API 接口，包括请求/响应格式、错误码约定和业务逻辑说明。后端开发以此为依据。 |

---

## 第 2 章：项目概述与约定

### 2.1 技术栈简述

| 项 | 值 |
|----|-----|
| 目标平台 | `{platform_type}` |
| 协议 | HTTPS（生产）/ HTTP（开发） |
| 数据格式 | JSON / SSE（`text/event-stream`） |
| 编码 | UTF-8 |
| 鉴权 | `{needs_auth}` |

### 2.2 API 设计原则

| 原则 | 规则 |
|------|------|
| **资源导向** | URL 使用名词复数：`/sessions`、`/messages`、`/documents` |
| **RESTful 方法** | `GET` 查 / `POST` 增 / `PUT` 改 / `DELETE` 删 |
| **嵌套资源** | 子资源表达层级：`/sessions/{id}/messages` |
| **URL 命名** | 小写 + 连字符：`/api/chat-messages`，不用下划线或驼峰 |
| **SSE 流式** | 长响应用 `text/event-stream`，不在接口文档中重复描述 |
| **分页格式** | `GET /api/xxx?page=1&page_size=20`，响应体含 `{ "items": [...], "total": 100 }` |
| **幂等性** | `GET`/`PUT`/`DELETE` 天生幂等；`POST` 创建操作标注是否允许重复 |
| **版本化** | v1 不带版本前缀；如需 API 版本，使用 `/api/v2/xxx` |

### 2.3 通用响应格式

```json
// 成功
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}

// 失败
{
  "code": 40001,
  "data": null,
  "message": "product_name 不能为空"
}
```

- `code = 0` → 成功；`code > 0` → 失败
- `data` 成功时返回具体内容，失败时为 `null`
- `message` 失败时用于前端展示错误提示

### 2.4 错误码约定

| code | HTTP 状态 | 含义 | 使用场景 |
|------|----------|------|---------|
| `0` | 200 | 成功 | — |
| `40001` | 400 | 参数校验失败 | 必填字段缺失、列表长度不足 |
| `40002` | 400 | 非法枚举值 | 参数值不在允许范围内 |
| `40100` | 401 | 未登录 | 需要鉴权的接口但没有 token |
| `40300` | 403 | 无权限 | 试图操作他人的资源 |
| `40400` | 404 | 资源不存在 | Session ID 找不到 |
| `40900` | 409 | 状态冲突 | 当前状态不允许此操作（如在 `form_editing` 下请求生成文档） |
| `50000` | 500 | 服务器内部错误 | 未预料的异常 |
| `50001` | 500 | LLM 调用失败 | AI 服务超时或返回异常 |
| `50002` | 500 | SSE 流中断 | 流式传输异常断开 |

### 2.5 鉴权机制

{% if needs_auth == "yes" %}
- 采用 `Bearer Token` 方案
- 请求头：`Authorization: Bearer <token>`
- 未登录接口返回 `40100`
{% elif needs_auth == "no" %}
- v1 无需鉴权，所有接口公开访问
- Session 通过 UUID 隔离，无需登录
{% elif needs_auth == "unsure" %}
- 建议 v1 无需鉴权，通过 UUID Session 隔离
- 如需鉴权，后续版本可追加 `Bearer Token`
{% endif %}

---

## 第 3 章：接口清单

> 本章根据 PRD 第 5 章「交互流程与界面设计」自动生成。
> 每个 PRD 页面 → 一个业务模块；每个交互步骤 → 一个 API 端点。

### 3.1 模块：`{模块名称}` — 对应 PRD 5.`{N}` `{页面名称}`

#### 接口 3.1.1：`{接口名称}`

| 字段 | 内容 |
|------|------|
| **接口名称** | `{简短描述}` |
| **请求** | `METHOD /api/xxx/{param}` |
| **业务说明** | 对应 PRD 5.N 节中「用户执行操作 A → 系统响应是什么」的步骤 |
| **路径参数** | `param: type` — 说明 |
| **查询参数** | `param: type?` — 说明（默认值） |
| **请求体** | `{ "field1": "value1", ... }` |
| **成功响应** | `200 { "code": 0, "data": { ... }, "message": "ok" }` |
| **错误码** | `40001` — 参数校验失败<br>`40400` — 资源不存在<br>`40900` — 状态冲突 |
| **边界情况** | 重复提交时如何、并发时如何、超时时如何 |

#### 接口 3.1.2：`{接口名称}`

| 字段 | 内容 |
|------|------|
| （同上结构） | |

### 3.2 模块：`{模块名称}` — 对应 PRD 5.`{N}` `{页面名称}`

（同上结构，每个页面为一个模块）

---

## 第 4 章：数据模型

> 本章定义接口中复用的结构体。与 `docs/form-data-structure.md` 和 `docs/session-data-structure.md` 对齐。

### 4.1 `FormData`

```json
{
  "product_name": "string (必填)",
  "one_liner": "string (必填)",
  "problem_statement": "string (必填)",
  "target_users": "string (必填)",
  "mvp_features": ["string (至少3条)"],
  "platform_type": "string (枚举)",
  "needs_auth": "string (枚举)",
  "needs_database": "string (枚举)",
  "page_count": "string (枚举)",
  "visual_style": "string (选填)",
  "competitors": "string (选填)",
  "tech_stack_preference": "string (选填)",
  "feature_priority": "string (选填, 枚举)",
  "doc_depth": "string (选填, 枚举)",
  "ai_temperature": "string (选填, 枚举)",
  "timeline_expectation": "string (选填, 枚举)",
  "additional_context": "string (选填)"
}
```

### 4.2 `SessionData`

```json
{
  "session_id": "string (UUID)",
  "current_state": "string (状态枚举)",
  "form_data": "FormData | null",
  "chat_messages": ["ChatMessage"],
  "requirements_summary": "string | null",
  "prd": "DocumentState",
  "api": "DocumentState",
  "prompts": "DocumentState"
}
```

### 4.3 其他结构体

根据 PRD 推导，在此处补充：

```json
// ChatMessage
{
  "role": "string (\"user\" | \"assistant\")",
  "content": "string",
  "timestamp": "string (ISO 8601)"
}

// DocumentState
{
  "content": "string",
  "streaming": "bool",
  "review_rounds": ["ReviewRound"],
  "current_round": "int",
  "user_edits": "string | null",
  "confirmed": "bool"
}
```

---

## 第 5 章：业务流程对照

> 将 PRD 第 5 章的交互流程映射到第 3 章的接口调用顺序。

### 5.1 表单提交流程

| 步骤 | PRD 描述 | 接口调用 |
|------|---------|---------|
| 1 | 用户打开表单页面 | —（前端路由） |
| 2 | 用户填写字段 | —（前端状态） |
| 3 | 用户点击提交 | `POST /api/sessions` |
| 4 | 系统跳转到对话页 | 前端跳转 `/chat/{session_id}` |

### 5.2 AI 对话流程

| 步骤 | PRD 描述 | 接口调用 |
|------|---------|---------|
| 1 | 进入对话页 | `GET /api/sessions/{id}`（恢复状态） |
| 2 | AI 首轮追问 | `POST /api/sessions/{id}/messages` → SSE |
| 3 | 用户回复 | `POST /api/sessions/{id}/messages` → SSE |
| ... | ... | ... |

### 5.3 文档生成流程

（同上格式，根据 PRD 实际章节填充）

---

## 附录 A：接口生成规则

从 PRD 第 5 章「交互流程与界面设计」自动生成第 3 章的规则：

| PRD 交互步骤 | 转换结果 |
|-------------|---------|
| "用户查看 X 页面" | `GET /api/sessions/{id}/X` |
| "用户执行操作 A → 创建/提交 X" | `POST /api/X` 或 `POST /api/sessions/{id}/X` |
| "用户执行操作 A → 修改 X" | `PUT /api/X/{id}` |
| "用户执行操作 A → 删除 X" | `DELETE /api/X/{id}` |
| "系统推送流式内容" | SSE 端点，不在接口文档中列为独立接口 |
| "用户确认 → 进入下一阶段" | `POST /api/sessions/{id}/X/confirm` |

## 附录 B：字段对照表

| 接口文档章节 | 数据来源 |
|-------------|---------|
| 第 2 章 约定 | `form_data`（`needs_auth`、`platform_type`）+ 项目约定 |
| 第 3 章 接口清单 | PRD 第 5 章：交互流程与界面设计 |
| 第 4 章 数据模型 | `docs/form-data-structure.md` + `docs/session-data-structure.md` |
| 第 5 章 业务对照 | PRD 第 5 章 + 第 3 章推导 |
