# HarnessPRD 前端状态数据结构

> 版本 2.0 · 2026-06-20
>
> 状态管理已从后端迁移至前端。后端无状态，所有数据存储在前端 `localStorage`。
> 后端不再定义 `SessionData`、`StateEnum` 或 `ReviewRound`。

---

## 一、前端 TypeScript 类型定义

```typescript
// ========== 文档状态 ==========

interface DocumentState {
  content: string            // 当前最新文档全文（含 SSE 累加中的内容）
  user_edits: string         // 用户手动编辑后的内容（空字符串表示无编辑）
  confirmed: boolean         // 用户是否已确认完成
}

// ========== 聊天消息 ==========

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

// ========== 项目状态（localStorage 存储） ==========

interface ProjectState {
  session_id: string          // 前端生成：crypto.randomUUID()
  viewState: ViewState        // 前端视图状态（见 state-machine.md）
  form_data: Record<string, any>  // 17 个表单字段，与 Pydantic 模型对齐
  messages: ChatMessage[]     // 完整对话历史
  requirements_summary: string  // AI 生成的需求摘要 JSON 字符串
  prd: DocumentState          // PRD 文档
  api: DocumentState          // 接口文档
  prompts: DocumentState      // 提示词套件
}
```

### 字段默认值

| 字段 | 默认值 |
|------|--------|
| `session_id` | `crypto.randomUUID()` |
| `viewState` | `"form_editing"` |
| `form_data` | `{}` |
| `messages` | `[]` |
| `requirements_summary` | `""` |
| `prd` | `{ content: "", user_edits: "", confirmed: false }` |
| `api` | `{ content: "", user_edits: "", confirmed: false }` |
| `prompts` | `{ content: "", user_edits: "", confirmed: false }` |

---

## 二、localStorage 持久化

### 2.1 存储方案

| 存储 | Key | 用途 |
|------|-----|------|
| **localStorage** | `harnessprd:project` | 存储完整 `ProjectState`（唯一存储键） |
| **localStorage** | `harnessprd:project` | 覆盖全部已有存储键（`form-draft`、`session-index` 等旧键不再使用） |

**设计要点**：
- 单键存储全部项目状态，简化持久化逻辑
- `JSON.stringify` 序列化，`JSON.parse` 反序列化
- 无需 `version` 字段——前端单页应用，升级时自然迁移
- 用户刷新页面后，从 localStorage 读取完整状态恢复

### 2.2 写入时机

| 场景 | 触发条件 |
|------|---------|
| 表单字段变更 | 用户输入时实时保存（debounce 500ms） |
| 对话消息追加 | 每次 SSE `done` 事件收到后 |
| 需求摘要生成 | `POST /api/summary/generate` 成功返回后 |
| 文档内容更新 | 每次 SSE `chunk` 事件累加写入 |
| 文档确认 | 用户点"确认完成"时 |
| 用户编辑 | 用户手动编辑文档内容时 |
| viewState 变更 | 每次视图转换时 |

### 2.3 读取时机

| 场景 | 行为 |
|------|------|
| 页面加载 | 从 localStorage 读取 `harnessprd:project`，若不存在则创建默认 `ProjectState` |
| 表单回显 | 读取 `form_data` 填充表单字段 |
| 对话历史恢复 | 读取 `messages` 渲染对话列表 |
| 文档展示 | 读取 `prd`/`api`/`prompts` 的 `content` 渲染文档 |
| 视图恢复 | 读取 `viewState` 恢复对应 UI 阶段 |
| 会话恢复 | 读取 `session_id` 用于后续 API 请求 |

---

## 三、后端数据模型（仅 API 参数）

后端不再定义持久化数据模型。仅使用请求/响应的 Pydantic 模型：

```python
from pydantic import BaseModel
from typing import Optional


class ChatMessage(BaseModel):
    role: str          # "user" | "assistant"
    content: str


class ChatStreamRequest(BaseModel):
    session_id: str
    form_data: dict
    history: list[ChatMessage]


class SummaryGenerateRequest(BaseModel):
    session_id: str
    form_data: dict
    history: list[ChatMessage]


class DocumentStreamRequest(BaseModel):
    session_id: str
    form_data: dict
    requirements_summary: str
    previous_content: str = ""          # 用于恢复/续写
    prd_content: Optional[str] = None   # 生成 api/prompts 时传入
    api_content: Optional[str] = None   # 生成 prompts 时传入


class DocumentOptimizeRequest(BaseModel):
    session_id: str
    content: str                        # 当前文档全文
    form_data: dict
    requirements_summary: str
    prd_content: Optional[str] = None
    api_content: Optional[str] = None


class DocumentDownloadRequest(BaseModel):
    content: str                        # 文档全文
```

---

## 四、刷新恢复流程

由于所有数据存储在 `localStorage`，刷新恢复流程大幅简化：

### 4.1 恢复步骤

1. 页面加载 → 读取 `localStorage` 中 `harnessprd:project`
2. 若不存在 → 创建默认 `ProjectState`（`session_id` = `crypto.randomUUID()`，`viewState` = `"form_editing"`）
3. 若存在 → 反序列化为 `ProjectState`
4. 根据 `viewState` 渲染对应 UI：
   - 用 `form_data` 回填表单字段
   - 用 `messages` 恢复对话列表
   - 用 `prd.content` / `api.content` / `prompts.content` 展示文档

### 4.2 断连续写

| 场景 | 处理方式 |
|------|---------|
| SSE 流式生成中断 | 前端检测到连接断开，调用 `POST /api/documents/{type}/stream` 并传入 `previous_content` = 已累积的文档内容，后端从断点续写 |
| 用户中途刷新 | 刷新后读取 localStorage，`viewState` 仍为 `generating_X`，前端自动续调 stream 端点（带 `previous_content`） |
| 对话中断 | 刷新后读取 `messages`，恢复对话列表，用户可继续发送消息 |

### 4.3 降级兜底

由于所有数据在本地，降级场景极少：

| 异常场景 | 处理方式 |
|---------|---------|
| localStorage 数据损坏 | 清空 `harnessprd:project`，创建默认 `ProjectState`，显示提示"项目数据异常，已重新开始" |
| `form_data` 为空但 `viewState` 为 `ai_dialogue` | 回退到 `form_editing`，提示"表单数据缺失，请重新填写" |
| 文档内容为空但 `viewState` 为 `reviewing_prd` | 回退到 `generating_prd`，自动重新调用 stream 端点 |

---

## 五、与旧版对比

| 维度 | 旧版（v1.0） | 新版（v2.0） |
|------|-------------|-------------|
| 状态存储 | 后端 `SessionData` 内存 dict + JSON 文件 | 前端 `localStorage` 单键 |
| 状态类型 | `StateEnum`（后端枚举） | `viewState`（前端字符串联合类型） |
| 文档审核记录 | `ReviewRound` 列表 | `user_edits` 字段（仅保留用户编辑） |
| 会话 ID 生成 | 后端 `POST /api/sessions` 返回 | 前端 `crypto.randomUUID()` |
| 刷新恢复 | `GET /api/sessions/{id}` 从后端恢复 | 从 `localStorage` 本地恢复 |
| 降级链 | 复杂后端降级算法 | 极简：数据损坏直接重置 |
| localStorage 键数 | 3 个键（form-draft、session-index、chat-input） | 1 个键（`harnessprd:project`） |
| 存储数据版本 | 带 `version` 字段 | 无版本号（单页应用自然迁移） |
