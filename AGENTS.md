# HarnessPRD

AI 驱动的对话式需求工作台。引导产品经理完成三个步骤：填写产品信息表单 → AI 对话澄清（SSE 流式）→ 文档生成（PRD、接口文档、提示词套件 — 每项都经历 Write→Review→Rewrite 循环）。

**状态：预实现阶段。** 仅有依赖清单和规格文档，尚未编写任何源码。

## 项目结构

| 层 | 技术栈 | 入口 |
|-------|-------|-------|
| **前端** | React 18 + Vite 5 + TypeScript + Tailwind 3 + shadcn/ui | `frontend/`（尚无 src）|
| **后端** | Python 3.11 + FastAPI + LangChain 0.3 + SSE | `backend/`（尚无 src）|
| **LLM** | OpenAI / Anthropic / DeepSeek（通过 LangChain Provider） | — |

**关键设计决策（无数据库、无认证、无 Redis、开发阶段无 Docker）：** 详见 `docs/tech-stack.md`。

## 命令

```bash
# 后端
cd backend && pip install -r requirements.txt  # 安装依赖
cd backend && uvicorn main:app --reload          # 开发服务器 :8000

# 前端
cd frontend && npm install    # 安装依赖
cd frontend && npm run dev    # Vite 开发服务器（代理 /api → 后端）
cd frontend && npm run build  # 生产构建
cd frontend && npm run preview
```

## 架构

### 无状态后端

后端为纯计算层，不存储任何会话数据。所有 API 端点是无状态的——每次请求携带完整上下文（`form_data`、`history`、文档内容等）。

**仅 8 个 API 端点**：
1. `GET /api/questions` — 表单配置
2. `POST /api/chat/stream` — SSE 聊天流式
3. `POST /api/summary/generate` — 需求摘要生成
4. `POST /api/documents/{type}/stream` — SSE 文档生成（PRD/API/Prompts）
5. `POST /api/documents/{type}/optimize` — SSE 审阅→改写
6. `POST /api/documents/{type}/download` — 下载 `.md` 文件
7. `GET /` — API 根路径
8. `GET /health` — 健康检查

### 前端全量状态

前端拥有全部状态，通过 `localStorage` 单键 `harnessprd:project` 持久化：

```typescript
interface ProjectState {
  session_id: string          // 前端生成：crypto.randomUUID()
  viewState: ViewState        // 前端管理的 10 个视图状态
  form_data: Record<string, any>
  messages: ChatMessage[]
  requirements_summary: string
  prd: DocumentState          // { content, user_edits, confirmed }
  api: DocumentState
  prompts: DocumentState
}
```

### 流程步骤

1. **步骤一 — 产品信息表单**（`/form` 路由）。共 17 个字段（11 个必填基础字段，6 个选填高级字段）。`mvp_features` 是唯一的 `string[]` 字段（至少 3 项）。表单数据本地存储，提交时发送至后端 API。

2. **步骤二 — AI 对话澄清**（`/chat` 路由，携带 `viewState` 参数）。前端携带完整 `form_data` 和 `history` 调用 `POST /api/chat/stream`（SSE 流式）。对话结束后调用 `POST /api/summary/generate` 生成需求摘要，用户确认后进入生成阶段。

3. **步骤三 — 文档生成**：
   - 前端调用 `POST /api/documents/{type}/stream`（SSE 流式）生成初稿
   - 完成后自动调用 `POST /api/documents/{type}/optimize`（SSE 流式）进行审阅→改写
   - 最多 3 轮 Review→Rewrite 循环，由前端控制轮次计数
   - 文档类型：`prd`（PRD）、`api`（接口文档）、`prompts`（提示词套件）

4. **会话 ID** — 前端使用 `crypto.randomUUID()` 生成，`session_id` 仅用于后端日志追踪，无实际存储语义。

5. **SSE 流式传输** — 服务端推送事件用于 LLM token 流式输出。不使用 WebSocket。后端使用 `sse-starlette`，前端使用 `EventSource` 或 `fetch` 流式读取。

## 约定

- **尚无源码** — 所有实现从零开始。
- **前端路由**：`/form`、`/chat`、`/generate`、`/completed`（不再使用 `<session_id>` 路径参数，所有数据在 localStorage 中）。
- **表单数据模型** 定义在 `docs/form-data-structure.md` 中 — 直接使用其中所示的 Pydantic 模型。
- **优先级标记** 定义在 `docs/features.md` 中：P0（必须有）、P1（重要）、P2（锦上添花）。
- **shadcn/ui** 组件复制到仓库内（非 npm 依赖），基于 Radix UI 原语。
- **语言**：API 和代码标识符用英文；UI 标签可用中文或英文。
- **类型**：前端 TypeScript 类型应与 Pydantic 模型字段名保持一致。
- **dotenv 不入库** — `.env` 已在 `.gitignore` 中；使用 `.env.example` 作为文档。

## 备注

（项目特定备注可在此处添加。）

## Notes

- 当网络不通畅时，尝试29290端口
- 关于安装 Puppeteer：只需在 launchOptions 中传入 executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" 即可使用已有Chrome无需额外安装。已验证可用。
- 用中文做思维链输出
- 用中文做思维链推理显示

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
