# HarnessPRD 状态机定义

> 版本 1.0 · 2026-06-15
>
> 定义产品工作流的全部状态、用户操作边界和允许的状态转换。

---

## 一、状态一览

| 状态ID | 名称 | 含义 | 对应路由 |
|--------|------|------|---------|
| `form_editing` | 表单编辑中 | 用户填写/编辑产品信息表单，尚未提交 | `/form` |
| `ai_dialogue` | AI 对话澄清中 | 用户与 AI 进行多轮对话。内部含 5 个 LLM 子阶段（破冰→功能深挖→竞争定位→技术决策→摘要确认），由 LLM Prompt 控制阶段路由 | `/chat/<session_id>` |
| `generating_prd` | 生成 PRD 中 | AI 正在生成 PRD 初稿，SSE 流式输出到前端 | `/generate/prd/<session_id>` |
| `reviewing_prd` | 审阅 PRD 中 | 系统先自动执行 Review→Rewrite 循环（最多 3 轮），循环结束后用户审阅最终文档、可手动编辑确认。循环期间用户只读等待 | `/generate/prd/<session_id>` |
| `generating_api` | 生成接口文档中 | AI 基于需求摘要 + 最终 PRD 生成接口文档初稿，SSE 流式输出 | `/generate/api/<session_id>` |
| `reviewing_api` | 审阅接口文档中 | 系统先自动执行 Review→Rewrite 循环（最多 3 轮），循环结束后用户审阅最终文档、可手动编辑确认。循环期间用户只读等待 | `/generate/api/<session_id>` |
| `generating_prompts` | 生成提示词套件中 | AI 基于需求摘要 + PRD + 接口文档生成提示词套件初稿，SSE 流式输出 | `/generate/prompts/<session_id>` |
| `reviewing_prompts` | 审阅提示词套件中 | 系统先自动执行 Review→Rewrite 循环（最多 3 轮），循环结束后用户审阅最终文档、可手动编辑确认。循环期间用户只读等待 | `/generate/prompts/<session_id>` |
| `completed` | 已完成 | 全部文档生成完毕，展示汇总页，支持复制/下载 | `/completed/<session_id>` |

## 二、状态内用户操作

| 状态ID | 用户可以做什么 |
|--------|--------------|
| `form_editing` | 填写 17 个字段（11 必填 + 6 选填）；增删 `mvp_features` 列表项（至少 3 条）；提交表单（触发后端校验） |
| `ai_dialogue` | 输入框发送消息（回车/按钮）；阅读 AI 流式回复（打字机效果）；查看完整对话历史；点"确认摘要"或"继续补充"；点"进入生成" |
| `generating_prd` | 只读阅读 SSE 流式输出的 PRD 初稿（不可中断） |
| `reviewing_prd` | 系统循环期间：只读等待。<br>循环结束后：阅读最终文档；手动编辑 Markdown 内容；复制全文；下载 `.md`；点"确认完成" |
| `generating_api` | 只读阅读 SSE 流式输出的接口文档初稿 |
| `reviewing_api` | 系统循环期间：只读等待。<br>循环结束后：阅读最终文档；手动编辑；复制；下载；点"确认完成" |
| `generating_prompts` | 只读阅读 SSE 流式输出的提示词套件初稿 |
| `reviewing_prompts` | 系统循环期间：只读等待。<br>循环结束后：阅读最终文档；手动编辑；复制；下载；点"确认完成" |
| `completed` | 查看三份文档汇总；逐一复制/下载全文；返回首页开始新项目 |

---

## 三、状态转换规则

| 当前状态 | 可转换到 | 触发条件 | 触发方 | 单向？ |
|---------|---------|---------|-------|-------|
| `form_editing` | `ai_dialogue` | 用户提交表单并通过后端校验 | 用户 | 是 |
| `ai_dialogue` | `ai_dialogue` (自环) | 用户发送消息继续对话，或点"继续补充" | 用户 | 否 |
| `ai_dialogue` | `generating_prd` | 用户确认需求摘要后点"进入生成"，或选择跳过对话 | 用户 | 是 |
| `generating_prd` | `reviewing_prd` | SSE 流式写入完成 | 系统 | 是 |
| `reviewing_prd` | `generating_prd` (循环) | 系统审核发现问题 && 轮次 < 3，自动触发 Rewrite | 系统 | 否（上限 3 轮） |
| `reviewing_prd` | `generating_api` | 用户点"确认完成" \|\| 已达 3 轮上限 | 用户/系统 | 是 |
| `generating_api` | `reviewing_api` | SSE 流式写入完成 | 系统 | 是 |
| `reviewing_api` | `generating_api` (循环) | 系统审核发现问题 && 轮次 < 3，自动触发 Rewrite | 系统 | 否（上限 3 轮） |
| `reviewing_api` | `generating_prompts` | 用户点"确认完成" \|\| 已达 3 轮上限 | 用户/系统 | 是 |
| `generating_prompts` | `reviewing_prompts` | SSE 流式写入完成 | 系统 | 是 |
| `reviewing_prompts` | `generating_prompts` (循环) | 系统审核发现问题 && 轮次 < 3，自动触发 Rewrite | 系统 | 否（上限 3 轮） |
| `reviewing_prompts` | `completed` | 用户点"确认完成" \|\| 已达 3 轮上限 | 用户/系统 | 是 |
| `completed` | — | 终点，无后续转换 | — | — |

## 四、转换图

```
form_editing ──[用户提交表单]──→ ai_dialogue

ai_dialogue ──[用户确认摘要]──→ generating_prd
ai_dialogue ──[用户选择跳过对话]──→ generating_prd
ai_dialogue ──[用户继续补充]──→ ai_dialogue（自环）

generating_prd ──[SSE 完成]──→ reviewing_prd

reviewing_prd ──[系统审核发现问题 && 轮次<3]──→ generating_prd（自动循环）
reviewing_prd ──[用户确认完成 || 轮次≥3]──→ generating_api

generating_api ──[SSE 完成]──→ reviewing_api

reviewing_api ──[系统审核发现问题 && 轮次<3]──→ generating_api（自动循环）
reviewing_api ──[用户确认完成 || 轮次≥3]──→ generating_prompts

generating_prompts ──[SSE 完成]──→ reviewing_prompts

reviewing_prompts ──[系统审核发现问题 && 轮次<3]──→ generating_prompts（自动循环）
reviewing_prompts ──[用户确认完成 || 轮次≥3]──→ completed

completed ──→（终点）
```

## 五、关键原则

1. **整体单向流水线**：`form_editing → ai_dialogue → PRD 阶段 → API 阶段 → 提示词阶段 → completed`，不存在跨阶段回退。用户想重来只能新建 session。

2. **Review→Rewrite 循环是系统自动的**：用户不需要手动触发审核或改写。系统审核发现问题且在 3 轮以内，自动触发 Rewrite（重新进入 `generating_X` 状态流式输出修改稿）。

3. **Review→Rewrite 上限 3 轮**：超过 3 轮即使仍有问题也强制进入下一步，防止死循环。

4. **用户操作集中在两处**：
   - `ai_dialogue`：发送消息、确认摘要、进入生成
   - `reviewing_X`：阅读优化后的文档、手动编辑、复制、下载、确认完成

5. **SSE 流式状态自动转换**：`generating_X` → `reviewing_X` 由 SSE 流式传输完成自动触发，无需用户操作。

6. **用户编辑不跨 Rewrite 循环**：用户在 `reviewing_X` 中的手动编辑（`user_edits`）仅作用于循环结束后的最终展示版本。系统触发 Rewrite 循环时自动清空 `user_edits`，用户需在循环完成后重新编辑。
