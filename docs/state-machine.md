# HarnessPRD 前端视图状态管理

> 版本 2.0 · 2026-06-20
>
> 状态机已从后端迁移至前端。后端为无状态架构，仅提供 API 计算能力。
> 前端通过 `viewState` 管理 UI 阶段，所有数据存储在 `localStorage` 单键 `harnessprd:project` 中。

---

## 一、ViewState 一览

| viewState | 含义 | 对应前端路由 |
|-----------|------|-------------|
| `form_editing` | 表单编辑中：用户填写/编辑产品信息表单，尚未提交 | `/form` |
| `ai_dialogue` | AI 对话澄清中：用户与 AI 多轮对话，SSE 流式回复 | `/chat` |
| `summary_review` | 需求摘要预览：AI 生成的结构化摘要，用户确认或拒绝 | `/chat` |
| `generating_prd` | 生成 PRD 中：SSE 流式输出 PRD 初稿 | `/generate` |
| `reviewing_prd` | 审阅 PRD 中：Review→Rewrite 自动循环（最多 3 轮），结束后用户编辑确认 | `/generate` |
| `generating_api` | 生成接口文档中：SSE 流式输出接口文档初稿 | `/generate` |
| `reviewing_api` | 审阅接口文档中：Review→Rewrite 自动循环，结束后用户编辑确认 | `/generate` |
| `generating_prompts` | 生成提示词套件中：SSE 流式输出提示词套件初稿 | `/generate` |
| `reviewing_prompts` | 审阅提示词套件中：Review→Rewrite 自动循环，结束后用户编辑确认 | `/generate` |
| `completed` | 已完成：展示三份文档汇总，支持复制/下载 | `/completed` |

> 与旧版相比新增 `summary_review`（将摘要确认从 `ai_dialogue` 中拆出为独立阶段），其余 9 个状态与旧版 9 个 `StateEnum` 一一对应。

---

## 二、视图内用户操作

| viewState | 用户可以做什么 |
|-----------|--------------|
| `form_editing` | 填写 17 个字段（11 必填 + 6 选填）；增删 `mvp_features` 列表项（至少 3 条）；提交表单 |
| `ai_dialogue` | 输入框发送消息（回车/按钮）；阅读 AI 流式回复（打字机效果）；查看完整对话历史；点"生成摘要" |
| `summary_review` | 阅读 AI 生成的结构化需求摘要；点"确认摘要"进入生成阶段；点"继续补充"返回对话 |
| `generating_prd` | 只读阅读 SSE 流式输出的 PRD 初稿（不可中断） |
| `reviewing_prd` | 系统循环期间：只读等待。<br>循环结束后：阅读最终文档；手动编辑 Markdown 内容；复制全文；下载 `.md`；点"确认完成" |
| `generating_api` | 只读阅读 SSE 流式输出的接口文档初稿 |
| `reviewing_api` | 系统循环期间：只读等待。<br>循环结束后：阅读最终文档；手动编辑；复制；下载；点"确认完成" |
| `generating_prompts` | 只读阅读 SSE 流式输出的提示词套件初稿 |
| `reviewing_prompts` | 系统循环期间：只读等待。<br>循环结束后：阅读最终文档；手动编辑；复制；下载；点"确认完成" |
| `completed` | 查看三份文档汇总；逐一复制/下载全文；返回首页开始新项目 |

---

## 三、视图转换规则

| 当前 viewState | 可转换到 | 触发条件 | 触发方 |
|---------------|---------|---------|-------|
| `form_editing` | `ai_dialogue` | 用户提交表单并通过前端校验 | 用户 |
| `ai_dialogue` | `ai_dialogue` (自环) | 用户发送消息继续对话 | 用户 |
| `ai_dialogue` | `summary_review` | 用户点"生成摘要"，调用 `POST /api/summary/generate` 成功 | 用户 |
| `summary_review` | `ai_dialogue` | 用户点"继续补充" | 用户 |
| `summary_review` | `generating_prd` | 用户点"确认摘要"，调用 `POST /api/documents/prd/stream` | 用户 |
| `generating_prd` | `reviewing_prd` | SSE `done` 事件收到，文档流式写入完成 | 系统 |
| `reviewing_prd` | `generating_prd` (循环) | 系统审核发现问题 && 轮次 < 3，自动调用 `POST /api/documents/prd/optimize` | 系统 |
| `reviewing_prd` | `generating_api` | 用户点"确认完成" \|\| 已达 3 轮上限 | 用户/系统 |
| `generating_api` | `reviewing_api` | SSE `done` 事件收到 | 系统 |
| `reviewing_api` | `generating_api` (循环) | 系统审核发现问题 && 轮次 < 3，自动调用 `POST /api/documents/api/optimize` | 系统 |
| `reviewing_api` | `generating_prompts` | 用户点"确认完成" \|\| 已达 3 轮上限 | 用户/系统 |
| `generating_prompts` | `reviewing_prompts` | SSE `done` 事件收到 | 系统 |
| `reviewing_prompts` | `generating_prompts` (循环) | 系统审核发现问题 && 轮次 < 3，自动调用 `POST /api/documents/prompts/optimize` | 系统 |
| `reviewing_prompts` | `completed` | 用户点"确认完成" \|\| 已达 3 轮上限 | 用户/系统 |
| `completed` | — | 终点，无后续转换 | — |

---

## 四、转换图

```
form_editing ──[用户提交表单]──→ ai_dialogue

ai_dialogue ──[用户点"生成摘要"]──→ summary_review
ai_dialogue ──[用户继续补充]──→ ai_dialogue（自环）

summary_review ──[用户确认摘要]──→ generating_prd
summary_review ──[用户继续补充]──→ ai_dialogue

generating_prd ──[SSE done]──→ reviewing_prd

reviewing_prd ──[系统审核发现问题 && 轮次<3]──→ generating_prd（自动循环）
reviewing_prd ──[用户确认完成 || 轮次≥3]──→ generating_api

generating_api ──[SSE done]──→ reviewing_api

reviewing_api ──[系统审核发现问题 && 轮次<3]──→ generating_api（自动循环）
reviewing_api ──[用户确认完成 || 轮次≥3]──→ generating_prompts

generating_prompts ──[SSE done]──→ reviewing_prompts

reviewing_prompts ──[系统审核发现问题 && 轮次<3]──→ generating_prompts（自动循环）
reviewing_prompts ──[用户确认完成 || 轮次≥3]──→ completed

completed ──→（终点）
```

---

## 五、关键原则

1. **前端驱动的视图管理**：`viewState` 存储在前端 `localStorage` 的 `harnessprd:project` 中，后端不感知状态。每次 API 请求携带完整上下文，后端纯计算。

2. **整体单向流水线**：`form_editing → ai_dialogue → summary_review → PRD 阶段 → API 阶段 → 提示词阶段 → completed`，不存在跨阶段回退。用户想重来只能新建 session。

3. **Review→Rewrite 循环是系统自动的**：用户不需要手动触发审核或改写。前端在收到 SSE `done` 后自动调用 `POST /api/documents/{type}/optimize`。系统审核发现问题且在 3 轮以内，自动再次调用 `stream` 流式输出修改稿。

4. **Review→Rewrite 上限 3 轮**：超过 3 轮即使仍有问题也强制进入下一步，防止死循环。

5. **用户操作集中在三处**：
   - `ai_dialogue`：发送消息、生成摘要
   - `summary_review`：确认/拒绝摘要
   - `reviewing_X`：阅读优化后的文档、手动编辑、复制、下载、确认完成

6. **SSE 流式状态自动转换**：`generating_X` → `reviewing_X` 由 SSE `done` 事件自动触发，无需用户操作。

7. **用户编辑不跨 Rewrite 循环**：用户在 `reviewing_X` 中的手动编辑（`user_edits`）仅作用于循环结束后的最终展示版本。系统触发 Rewrite 循环时自动清空 `user_edits`，用户需在循环完成后重新编辑。

8. **刷新恢复**：刷新页面后，前端从 `localStorage` 读取 `harnessprd:project`，根据 `viewState` 恢复对应 UI。`session_id` 保持不变，所有上下文数据（`form_data`、`messages`、`requirements_summary`、文档内容）均在本地，无需后端恢复。
