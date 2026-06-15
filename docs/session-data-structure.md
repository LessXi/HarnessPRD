# HarnessPRD 状态机数据结构

> 版本 1.0 · 2026-06-15
>
> 定义状态机所需的统一数据接口、各状态读写字段和持久化策略。

---

## 一、统一数据接口（SessionData）

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime


class StateEnum(str, Enum):
    FORM_EDITING = "form_editing"
    AI_DIALOGUE = "ai_dialogue"
    GENERATING_PRD = "generating_prd"
    REVIEWING_PRD = "reviewing_prd"
    GENERATING_API = "generating_api"
    REVIEWING_API = "reviewing_api"
    GENERATING_PROMPTS = "generating_prompts"
    REVIEWING_PROMPTS = "reviewing_prompts"
    COMPLETED = "completed"


class ChatMessage(BaseModel):
    role: str                        # "user" | "assistant"
    content: str
    timestamp: datetime


class ReviewRound(BaseModel):
    round_number: int                # 1, 2, 3
    review_content: str | None       # 审核 Agent 的输出
    rewrite_content: str | None      # Rewrite 后的全文


class DocumentState(BaseModel):
    content: str                     # 当前最新文档全文（含 SSE 累加中的内容）
    streaming: bool                  # SSE 是否正在流式传输中
    last_chunk_at: datetime | None   # 上次收到 SSE chunk 的时间，用于超时检测
    review_rounds: list[ReviewRound] # 已完成的历史审核轮次
    current_round: int               # 当前已完成的轮次数 (0, 1, 2, 3)
    user_edits: str | None           # 用户手动编辑后的内容（可选）
    confirmed: bool                  # 用户是否已确认完成


class SessionData(BaseModel):
    # ========== 基础字段 ==========
    session_id: str                  # UUID
    current_state: StateEnum         # 当前状态
    created_at: datetime

    # ========== 步骤一：表单数据 ==========
    form_data: FormData | None       # 17 个字段，详见 docs/form-data-structure.md

    # ========== 步骤二：AI 对话 ==========
    chat_messages: list[ChatMessage] # 完整对话历史
    requirements_summary: str | None # AI 生成的需求摘要 JSON
    summary_confirmed: bool          # 用户是否已确认摘要
    skip_dialogue: bool              # 是否跳过对话

    # ========== 步骤三：三份文档 ==========
    prd: DocumentState               # PRD 文档
    api: DocumentState               # 接口文档
    prompts: DocumentState           # 提示词套件
```

### 默认值说明

- `DocumentState()` 默认：`content=""`, `streaming=False`, `last_chunk_at=None`, `review_rounds=[]`, `current_round=0`, `user_edits=None`, `confirmed=False`
- `summary_confirmed` / `skip_dialogue` 默认 `False`

---

## 二、每个状态读写哪些字段

| 状态 | 读取字段 | 写入字段 |
|------|---------|---------|
| `form_editing` | `form_data`（回显已填内容） | `form_data`（保存表单） |
| `ai_dialogue` | `form_data`, `chat_messages` | `chat_messages`（追加消息）, `requirements_summary`, `summary_confirmed`, `skip_dialogue` |
| `generating_prd` | `form_data`, `requirements_summary` | `prd.content`（SSE 累加写入）, `prd.streaming` |
| `reviewing_prd` | `prd.*` | `prd.review_rounds[]`, `prd.current_round`, `prd.streaming`, `prd.user_edits`, `prd.confirmed` |
| `generating_api` | `form_data`, `requirements_summary`, `prd.content` | `api.content`（SSE 累加）, `api.streaming` |
| `reviewing_api` | `api.*` | `api.review_rounds[]`, `api.current_round`, `api.streaming`, `api.user_edits`, `api.confirmed` |
| `generating_prompts` | `form_data`, `requirements_summary`, `prd.content`, `api.content` | `prompts.content`（SSE 累加）, `prompts.streaming` |
| `reviewing_prompts` | `prompts.*` | `prompts.review_rounds[]`, `prompts.current_round`, `prompts.streaming`, `prompts.user_edits`, `prompts.confirmed` |
| `completed` | 全部字段（展示三份文档） | —（终点，不再写入） |

---

## 三、持久化方案（刷新恢复）

> 用户可能在填写表单、AI 对话或文档生成过程中刷新页面。本方案确保刷新后数据不丢失、状态可恢复。

### 3.1 存储选型

| 存储 | 用途 | 理由 |
|------|------|------|
| **localStorage**（前端） | 表单草稿、会话导航索引 | 跨刷新、跨标签页关闭后仍可恢复；5MB 足够 |
| **sessionStorage**（前端） | 聊天输入框草稿（未发送的文本） | 仅当前标签页需要，关闭即丢弃 |
| **内存 dict + JSON 文件**（后端） | 已提交的 `SessionData` | 已有设计；session 创建后所有数据走服务端 |
| 不引入 IndexedDB | — | 复杂度高，单用户场景不需要 |

### 3.2 数据结构（带版本号）

所有持久化数据均包含 `version` 字段，便于后续兼容升级。

#### 3.2.1 表单草稿（localStorage）

```typescript
// key: harnessprd:form-draft
interface FormDraft {
  version: 1;                    // 数据结构版本，升级时做迁移
  updatedAt: string;             // ISO 8601 时间戳
  data: Partial<FormData>;       // 17 个字段，与 Pydantic 模型对齐
}
```

- 用户填写表单时实时保存（debounce 500ms）
- 用户提交表单后立即清除
- 版本不兼容时丢弃草稿，不报错

#### 3.2.2 聊天输入草稿（sessionStorage）

```typescript
// key: harnessprd:chat-input:<session_id>
interface ChatInputDraft {
  version: 1;
  updatedAt: string;
  data: {
    sessionId: string;
    inputText: string;           // 输入框中的文本
  };
}
```

- 用户输入时实时保存
- 消息发送成功后清除
- 使用 sessionStorage，关闭标签页即丢弃

#### 3.2.3 会话导航索引（localStorage）

```typescript
// key: harnessprd:session-index
interface SessionIndex {
  version: 1;
  sessions: Array<{
    sessionId: string;
    productName: string;         // 产品名称，便于识别
    lastState: StateEnum;        // 最后所处的状态
    updatedAt: string;           // 最后更新时间
  }>;
}
```

- 每次 session 创建或状态转换时更新
- 保留最近 10 条记录
- 可用于首页展示"继续未完成的会话"

### 3.3 各状态刷新恢复流程

| 刷新时的状态 | 恢复流程 |
|-------------|---------|
| **`form_editing`** | ① 读取 localStorage `harnessprd:form-draft`<br>② 校验 `version` 是否兼容（不兼容则丢弃）<br>③ 恢复所有已填字段到表单<br>④ 显示提示"已恢复未提交的草稿" |
| **`ai_dialogue`** | ① 从 URL 取 `session_id`<br>② `GET /api/session/{id}` 获取服务端 `SessionData`<br>③ 恢复 `chat_messages` 到对话列表<br>④ 恢复 `requirements_summary` 和 `summary_confirmed` 状态<br>⑤ 从 sessionStorage 恢复输入框草稿（如有） |
| **`generating_prd` / `generating_api` / `generating_prompts`** | ① 从 URL 取 `session_id`<br>② `GET /api/session/{id}` 获取 `SessionData`<br>③ 渲染已累积的 `DocumentState.content`<br>④ 若 `streaming=true`，检查 `last_chunk_at`：超过 60 秒未更新 → 判定断连，自动重新调用 LLM 生成（保留已累积内容）<br>⑤ 若 `streaming=false`，正常展示完整文档 |
| **`reviewing_prd` / `reviewing_api` / `reviewing_prompts`** | ① 从 URL 取 `session_id`<br>② `GET /api/session/{id}` 获取 `SessionData`<br>③ 渲染最终文档 + 审核轮次记录<br>④ 恢复 `user_edits`（用户之前的手动编辑） |
| **`completed`** | ① 从 URL 取 `session_id`<br>② `GET /api/session/{id}` 获取完整 `SessionData`<br>③ 展示三份文档汇总 |

### 3.4 后端 API（用于刷新恢复）

```python
# 获取完整会话状态
GET /api/session/{session_id}
→ 200: SessionData (包含 form_data, chat_messages, prd, api, prompts)
→ 404: { "detail": "Session not found" }

# 判断会话是否存在
HEAD /api/session/{session_id}
→ 200: 存在
→ 404: 不存在或已过期

# 获取会话概览（用于首页会话索引同步）
GET /api/sessions
→ 200: list[{ session_id, product_name, current_state, updated_at }]
```

### 3.5 关键结论

- **服务端**：`SessionData` 整体是持久化粒度，刷新后只需 `session_id` 即可全量恢复
- **客户端**：只有**未提交的表单草稿**和**未发送的输入框文本**需要前端持久化——其余数据都从服务端恢复
- **版本号**：所有 localStorage/sessionStorage 数据带 `version` 字段，未来字段变更时可做迁移或丢弃

### 3.6 降级兜底机制

> 刷新后恢复数据时，如果 `current_state` 所需的前置依赖数据不完整（服务器重启、JSON 丢失等），不应直接报错，而应自动回退到上一个数据完整的状态。

#### 3.6.1 各状态前置依赖链

每个状态向前推进时，会累积更多数据。越靠前的状态依赖越少，恢复成功率越高。

```
状态                前置依赖（累加）
────────────────────────────────────────────────────
form_editing      → 无
ai_dialogue       → form_data ≠ None
generating_prd    → ↑ + requirements_summary ≠ None + summary_confirmed = True
                     若 streaming=true 且 last_chunk_at 超过 60s 未更新则视为不满足
reviewing_prd     → ↑ + prd.content ≠ "" + prd.streaming = False
generating_api    → ↑ + prd.confirmed = True
                     若 streaming=true 且 last_chunk_at 超过 60s 未更新则视为不满足
reviewing_api     → ↑ + api.content ≠ "" + api.streaming = False
generating_prompts→ ↑ + api.confirmed = True
                     若 streaming=true 且 last_chunk_at 超过 60s 未更新则视为不满足
reviewing_prompts → ↑ + prompts.content ≠ "" + prompts.streaming = False
completed         → ↑ + prompts.confirmed = True
```

#### 3.6.2 降级算法

```
输入: session_id
输出: (恢复后的状态, 是否降级)

1. 从内存/JSON 加载 SessionData
2. 若 SessionData 不存在 → 返回 (form_editing, 降级=true)  // 全新开始
3. target_state = SessionData.current_state
4. loop:
     检查 target_state 的前置依赖是否齐全
     if 齐全 → 更新 SessionData.current_state = target_state
               存储，返回 (target_state, 是否降级)
     else → target_state = 前一个状态  // 沿依赖链回退
            if target_state 不存在 → 返回 (form_editing, 降级=true)
            continue loop
```

#### 3.6.3 降级场景示例

| 恢复失败场景 | 降级到 | 用户提示 |
|-------------|--------|---------|
| `generating_prd` 但 `requirements_summary` 为空 | `ai_dialogue` | "需求摘要数据缺失，已回退到对话阶段，请重新确认需求" |
| `reviewing_prd` 但 `prd.content` 为空 | `generating_prd` | "PRD 内容缺失，已回退重新生成" |
| `reviewing_prd` 但 `prd.streaming = true`（上次生成未完成） | `generating_prd` | "上次 PRD 生成未完成，已回退重新生成" |
| `generating_prd` / `generating_api` / `generating_prompts` 且 `streaming=true` 且超过 60 秒无新 chunk | 同状态（重新触发生成） | "生成连接超时，已重新开始生成，保留已生成内容" |
| `reviewing_api` 但 `api.content` 为空 | `generating_api` | "接口文档内容缺失，已回退重新生成" |
| `completed` 但 `prompts.confirmed = false` | `reviewing_prompts` | "最终确认状态丢失，请重新确认提示词套件" |
| 所有数据全部丢失 | `form_editing` | "会话数据未找到，已创建新的空白会话" |

#### 3.6.4 设计原则

- **宁可降级，不要报错**：用户不应看到白屏或 500 错误页
- **降级必须告知用户**：前端收到降级结果后，显示黄色提示条说明降级原因和当前阶段
- **降级不删除已有数据**：即使降级到 `ai_dialogue`，后面的 `prd`、`api`、`prompts` 数据如果存在也保留在 SessionData 中——用户重新推进时直接复用
- **降级链是最坏情况兜底**：正常情况下（服务器无重启、JSON 完整）不会触发降级
