# HarnessPRD API 端点清单

> 版本 2.0 · 2026-06-16
>
> 基于代码实际路由校对，与 `backend/api/` 下路由定义保持一致
>
> **SSE 事件格式**（所有 SSE 端点统一）：
> ```
> data: {"event":"chunk","content":"<逐 token 文本>"}
> data: {"event":"done"}
> data: {"event":"error","content":"<错误信息>"}
> ```

**基础路径**：`/api`

---

## 模块 1：会话管理

| # | 方法 | 路径 | 状态转换 | 说明 |
|---|------|------|---------|------|
| 1 | `POST` | `/api/sessions` | `form_editing → ai_dialogue` | 提交表单 → 创建 Session |
| 2 | `GET` | `/api/sessions` | — | 获取最近会话列表 |
| 3 | `GET` | `/api/sessions/{id}` | — | 获取完整 SessionData（刷新恢复用） |
| 4 | `GET` | `/api/sessions/questions` | — | 返回表单配置（步骤一动态渲染用） |

## 模块 2：AI 对话

| # | 方法 | 路径 | 状态转换 | 说明 |
|---|------|------|---------|------|
| 5 | `POST` | `/api/sessions/{id}/messages` | 自环（`ai_dialogue`） | 发送用户消息 |
| 6 | `POST` | `/api/sessions/{id}/start-stream` | 自环 | SSE 端点：AI 主动破冰问候 |
| 7 | `POST` | `/api/sessions/{id}/continue-stream` | 自环 | SSE 端点：AI 接续回复 |
| 8 | `GET` | `/api/sessions/{id}/messages` | — | 获取对话历史 |
| 9 | `POST` | `/api/sessions/{id}/summary/generate` | 自环 | 触发需求摘要生成 |
| 10 | `POST` | `/api/sessions/{id}/summary/confirm` | `ai_dialogue → generating_prd` | 确认摘要 + 进入生成 |
| 11 | `POST` | `/api/sessions/{id}/summary/reject` | 自环 | 拒绝摘要 + 继续补充 |
| 12 | `POST` | `/api/sessions/{id}/dialogues/skip` | `ai_dialogue → generating_prd` | 跳过对话兜底分支 |

## 模块 3：文档生成

### 3a. PRD

| # | 方法 | 路径 | 状态转换 | 说明 |
|---|------|------|---------|------|
| 13 | `POST` | `/api/sessions/{id}/documents/prd/generate` | → `generating_prd` | 启动 PRD 生成 |
| 14 | `GET` | `/api/sessions/{id}/documents/prd/stream` | `generating_prd → reviewing_prd` | SSE 端点 |
| 15 | `GET` | `/api/sessions/{id}/documents/prd` | — | 获取 PRD 内容 |
| 16 | `GET` | `/api/sessions/{id}/documents/prd/review-rounds` | — | 审核轮次历史 |
| 17 | `PUT` | `/api/sessions/{id}/documents/prd/content` | 自环 | 保存用户编辑 |
| 18 | `GET` | `/api/sessions/{id}/documents/prd/download` | — | 下载 `.md` |
| 19 | `POST` | `/api/sessions/{id}/documents/prd/confirm` | `reviewing_prd → generating_api` | 确认 PRD 完成 |

### 3b. 接口文档

| # | 方法 | 路径 | 状态转换 | 说明 |
|---|------|------|---------|------|
| 20 | `POST` | `/api/sessions/{id}/documents/api/generate` | → `generating_api` | 启动接口文档生成 |
| 21 | `GET` | `/api/sessions/{id}/documents/api/stream` | `generating_api → reviewing_api` | SSE 端点 |
| 22 | `GET` | `/api/sessions/{id}/documents/api` | — | 获取接口文档内容 |
| 23 | `GET` | `/api/sessions/{id}/documents/api/review-rounds` | — | 审核轮次历史 |
| 24 | `PUT` | `/api/sessions/{id}/documents/api/content` | 自环 | 保存用户编辑 |
| 25 | `GET` | `/api/sessions/{id}/documents/api/download` | — | 下载 `.md` |
| 26 | `POST` | `/api/sessions/{id}/documents/api/confirm` | `reviewing_api → generating_prompts` | 确认接口文档完成 |

### 3c. 提示词套件

| # | 方法 | 路径 | 状态转换 | 说明 |
|---|------|------|---------|------|
| 27 | `POST` | `/api/sessions/{id}/documents/prompts/generate` | → `generating_prompts` | 启动提示词套件生成 |
| 28 | `GET` | `/api/sessions/{id}/documents/prompts/stream` | `generating_prompts → reviewing_prompts` | SSE 端点 |
| 29 | `GET` | `/api/sessions/{id}/documents/prompts` | — | 获取提示词套件 |
| 30 | `GET` | `/api/sessions/{id}/documents/prompts/review-rounds` | — | 审核轮次历史 |
| 31 | `PUT` | `/api/sessions/{id}/documents/prompts/content` | 自环 | 保存用户编辑 |
| 32 | `GET` | `/api/sessions/{id}/documents/prompts/download` | — | 下载 `.md` |
| 33 | `POST` | `/api/sessions/{id}/documents/prompts/confirm` | `reviewing_prompts → completed` | 确认全部完成 |

---

## 统计

| 维度 | 数值 |
|------|------|
| 总接口 | 33 个 |
| HTTP 端点 | 30 个 |
| SSE 端点 | 5 个 |
| 触发状态转换 | 9 个 |
| 只读查询 | 14 个 |
