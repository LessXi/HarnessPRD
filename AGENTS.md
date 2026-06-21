# HarnessPRD

AI 驱动的对话式需求工作台。引导产品经理完成三个步骤：填写产品信息表单 → AI 对话澄清（SSE 流式）→ 文档生成（PRD、接口文档、提示词套件 — 每项都经历 Write→Review→Rewrite 循环）。

**状态：Skill Engine 阶段。** 后端已实现 Skill Engine（声明式技能引擎）+ API 服务层。前端正在开发中。

## 项目结构

| 层 | 技术栈 | 入口 |
|-------|-------|-------|
| **前端** | React 18 + Vite 5 + TypeScript + Tailwind 3 + shadcn/ui | `frontend/src/` |
| **后端 — API** | Python 3.11 + FastAPI + LangChain 0.3 + SSE | `backend/api/` |
| **后端 — 核心** | Python 3.11 + 声明式 Skill Engine | `backend/skill_engine/` — 引擎框架（engine、loader、parser、models） |
| **后端 — 技能** | Markdown 声明文件（.md） | `backend/skills/` — 文档生成技能定义（prd/api/prompts） |
| **后端 — 服务** | Python 3.11 + LangChain | `backend/services/` — 聊天、摘要、下载 |
| **后端 — 中间件** | Python 3.11 + SSE | `backend/middleware/` — SSE 流式传输 |
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

**API 端点概览**（所有 `/api` 路径为前端约定反向代理，后端实际路由前缀不同）：
1. `GET /api/questions` — 表单配置（`sessions` 路由）
2. `POST /api/chat/stream` — SSE 聊天流式（`conversation` 路由）
3. `POST /api/summary/generate` — 需求摘要生成（`conversation` 路由）
4. `POST /{doc_type}/stream` — SSE 文档生成，由 Skill Engine 驱动（`documents` 路由）
5. `POST /{doc_type}/optimize` — SSE 审阅→改写，由 Skill Engine 驱动（`documents` 路由）
6. `POST /{doc_type}/download` — 下载 `.md` 文件（`documents` 路由）
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

3. **步骤三 — 文档生成（Skill Engine 驱动）**：
   - 后端 Skill Engine 加载 `backend/skills/*.md` 声明文件，解析为 `SkillSchema`（含多步骤定义）
   - 前端调用 `POST /{doc_type}/stream`（SSE 流式），后端根据 `doc_type` 匹配对应 skill（prd-generate / api-generate / prompts-generate）
   - Skill Engine 按步骤顺序执行：generate → review → rewrite（循环，默认最多 3 轮）
   - 每步输出通过 SSE 流式推送到前端
   - max_iterations 在 skill `.md` 文件中定义，后端 engine.py 控制迭代终止

4. **会话 ID** — 前端使用 `crypto.randomUUID()` 生成，`session_id` 仅用于后端日志追踪，无实际存储语义。

5. **SSE 流式传输** — 服务端推送事件用于 LLM token 流式输出。不使用 WebSocket。后端使用 `sse-starlette`，前端使用 `EventSource` 或 `fetch` 流式读取。

## 约定

- **Skill Engine** — 后端 `backend/skill_engine/` 为声明式 prompt 技能引擎。engine.py 负责编排 generate→review→rewrite 循环，loader.py 负责加载技能文件，parser.py 解析 Markdown 声明，models.py 定义 Pydantic 模型。`backend/skills/` 为 .md 声明文件（prd-generate.md / api-generate.md / prompts-generate.md），每个 skill 包含名称、描述、最大迭代次数和步骤列表。
- **Prompts 文件** — `backend/prompts/` 仅保留 chat 相关文件：`chat_system.jinja2`、`chat_summary.jinja2`、`chat-prompts.md`。文档生成已迁移至 Skill Engine，不再使用 Jinja2 模板。
- **前端路由**：`/form`、`/chat`、`/generate`、`/completed`（不再使用 `<session_id>` 路径参数，所有数据在 localStorage 中）。
- **表单数据模型** 定义在 `docs/form-data-structure.md` 中 — 直接使用其中所示的 Pydantic 模型。
- **优先级标记** 定义在 `docs/features.md` 中：P0（必须有）、P1（重要）、P2（锦上添花）。
- **shadcn/ui** 组件复制到仓库内（非 npm 依赖），基于 Radix UI 原语。
- **语言**：API 和代码标识符用英文；UI 标签可用中文或英文。
- **类型**：前端 TypeScript 类型应与 Pydantic 模型字段名保持一致。
- **dotenv 不入库** — `.env` 已在 `.gitignore` 中；使用 `.env.example` 作为文档。

## 备注

（项目特定备注可在此处添加。）

## E2E 浏览器验证 playbook

用 Playwright MCP 工具做端到端验证时遵循以下做法，避免低效等待和上下文浪费。

### 1. 服务启动检查

开始前确认前后端在跑（PowerShell）：

```powershell
# 后端
try { Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction Stop | Select-Object -ExpandProperty Content } catch { "后端未运行" }
# 前端
try { Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -ErrorAction Stop | Select-Object -ExpandProperty Content } catch { "前端未运行" }
```

未运行则启动：`cd backend; uvicorn main:app --reload` 和 `cd frontend; npm run dev`。

### 2. Mock 数据注入跳步

测试特定步骤时，注入 mock localStorage 跳过前置流程，省 10+ 分钟。

- localStorage key：`harnessprd:project`
- 值为 `ProjectState` JSON（结构见 `frontend/src/types/index.ts`）
- 用 `playwright_browser_evaluate` 注入后 `playwright_browser_navigate` 重载

**viewState 值表**（跳到对应步骤设此字段）：

| viewState | 步骤 | 前置 completedSteps |
|-----------|------|---------------------|
| `form_editing` | 表单 | `[]` |
| `ai_dialogue` | AI 对话 | `["form_editing"]` |
| `reviewing_prd` | PRD 审阅 | `["form_editing","ai_dialogue"]` |
| `reviewing_api` | 接口文档审阅 | `["form_editing","ai_dialogue","reviewing_prd"]` |
| `reviewing_prompts` | 提示词审阅 | `["form_editing","ai_dialogue","reviewing_prd","reviewing_api"]` |
| `completed` | 完成 | 全部 5 步 |

**跳到提示词生成**示例：设 `viewState="reviewing_api"`，`prd`/`api` 填 mock content，`completedSteps` 含前 4 步，点"确认接口文档"→"继续"即开始生成提示词。

注入模板：

```javascript
() => {
  const mock = {
    session_id: "mock-test-001",
    viewState: "reviewing_api",  // 改这里跳步
    form_data: { product_name:"记账小助手", one_liner:"...", problem:"...", target_users:"...", mvp_features:["...","...","..."], platform:"Web 应用", needs_auth:"需要", needs_storage:"需要", page_count:"1-3 页" },
    messages: [{role:"assistant",content:"...",timestamp:"..."},{role:"user",content:"...",timestamp:"..."}],
    requirements_summary: "...",
    prd: { content:"# PRD mock", user_edits:"", confirmed:true },
    api: { content:"# API mock", user_edits:"", confirmed:false },
    prompts: { content:"", user_edits:"", confirmed:false },
    completedSteps: ["form_editing","ai_dialogue","reviewing_prd","reviewing_api"],
    autoAdvance: false,
    pendingUpdates: [],
  };
  localStorage.setItem("harnessprd:project", JSON.stringify(mock));
  return "injected";
}
```

### 3. SSE 流式验证高效做法

**不要**固定 `wait_for(60)` 后全量 `read` 快照 YAML（长文档快照 1400+ 行，浪费上下文）。

**做法**：
- `wait_for` 等文本变化：`textGone:"生成中…"` 或 `text:"确认"` / `text:"完成"` 出现，而非固定秒数
- 读快照用 `grep` 找关键行（标题/字数/按钮状态），非全量 `read`
- 判断生成完成：标题无"生成中…"后缀 + 文档信息字数停止增长 + 操作区出现"确认/AI优化/编辑"按钮
- SSE 流长（提示词 2 万+字）时单次等待不够，分段等待并 grep 检查进度

**已知 gotcha**：`readStream`（api.ts）流末尾缓冲区残行需处理，否则 `done` 事件丢失导致标题残留"生成中…"。已修复，回归测试时关注此点。

## Notes

- 当网络不通畅时，尝试29290端口
- 关于安装 Puppeteer：只需在 launchOptions 中传入 executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" 即可使用已有Chrome无需额外安装。已验证可用。
- 用中文做思维链输出
- 用中文做思维链推理显示
## Project Activity (auto-generated by open-mem)

### ./
| ID | Type | Title | Date |
|----|------|-------|------|
| 4f7610de-9672-424a-b8ad-05d4a7fb7bed | 🔵 discovery | frontend目录：Vite+React+TypeScript+Tailwind项目结构 | 2026-06-20 |

**Key concepts:** how-it-works, pattern

### frontend/
| ID | Type | Title | Date |
|----|------|-------|------|
| 4af9f1bd-0dfc-4463-bcb0-28e43fdfffb8 | 🔵 discovery | 前端package.json：无JSZip依赖（待添加用于ZIP打包） | 2026-06-20 |
| ec895c72-bc73-4cb0-a4ec-ba8b61ca9593 | 🔵 discovery | Tailwind配置：primary色板+sidebar宽度+响应式断点 | 2026-06-20 |
| ce5b9b4b-725d-4fb7-ba31-181dba349a2f | 🔵 discovery | Tailwind配置：primary色板+sidebar宽度+响应式断点 | 2026-06-20 |
| 238ddf19-3973-4a75-a989-48e933100d03 | 🔵 discovery | frontend/src目录：标准React项目源码结构 | 2026-06-20 |

**Key concepts:** how-it-works, gotcha, pattern

### frontend\src/
| ID | Type | Title | Date |
|----|------|-------|------|
| d9f9b54b-6a91-4970-b494-8f4d58452dbc | 🔵 discovery | handleDownloadAll：TODO未实现ZIP打包下载 | 2026-06-20 |
| 6df2f478-a7b3-4479-9835-1d0063598a9c | 🔵 discovery | handleDownloadAll仍为TODO占位（待JSZip实现ZIP打包） | 2026-06-20 |
| 4939ae3b-d97e-4553-896d-9bb38f655aaa | 🔵 discovery | App.tsx新增导入：CompletionSummary和PreviewModal | 2026-06-20 |
| 1a31264d-bccf-4852-8036-15fe2779ce9e | 🔵 discovery | CompletionPromptBar已渲染：showCompletionPrompt条件控制 | 2026-06-20 |
| 8920194e-e53a-4f94-9cc1-b6d905ff9db9 | 🔵 discovery | App.tsx render部分：侧边栏+内容区双栏布局 | 2026-06-20 |
| f1f433a9-e2a5-4df8-8774-1596cc6555de | 🔵 discovery | App.tsx：handlePreview仅console.log，handleDownload实现Blob下载 | 2026-06-20 |
| 1b2f0240-0dbb-4a24-b501-294fdc64a763 | 🔵 discovery | handleDownload实现：Blob下载+URL.createObjectURL | 2026-06-20 |
| 369a2fcd-113c-4332-8f6b-19d805b12b75 | 🔵 discovery | App.tsx状态声明：9个useState + streamingContentRef（872行） | 2026-06-20 |
| c1adb8c7-6355-470b-8ace-46a78deb7e0e | 🔵 discovery | App组件状态：9个useState+1个useRef | 2026-06-20 |
| 11d44113-c2c0-4420-9bab-cebbbce31f89 | 🔵 discovery | App.tsx导入：6个组件+4个React钩子+API服务 | 2026-06-20 |

**Key concepts:** how-it-works, gotcha, what-changed, pattern

### frontend\src\components/
| ID | Type | Title | Date |
|----|------|-------|------|
| e06d24d7-254c-499f-b63a-6243d6c22efa | 🔵 discovery | CompletionPromptBar组件已集成到App.tsx | 2026-06-20 |
| e318de50-71c0-471f-81b6-edfd9b97d558 | 🔵 discovery | CompletionPromptBar已实现但未在App.tsx中渲染 | 2026-06-20 |
| 16a49f7b-e250-49f1-863d-57cabaacd4d0 | 🔵 discovery | Sidebar组件完整实现：进度导航+操作按钮+文档信息 | 2026-06-20 |
| da669392-f4be-4700-8452-eab56dd1eb10 | 🔵 discovery | CompletionPromptBar组件：文档审阅后操作栏 | 2026-06-20 |
| 361fabdf-6439-444e-b991-cde4dfc333b4 | 🔵 discovery | Sidebar组件完整实现：进度导航+操作按钮+文档信息 | 2026-06-20 |

**Key concepts:** pattern, how-it-works, gotcha, what-changed

### frontend\src\services\__tests__/
| ID | Type | Title | Date |
|----|------|-------|------|
| b20025c1-31d2-4cce-9a49-566674db960d | 🔵 discovery | 测试文件发现：readStream.test.ts已存在 | 2026-06-20 |

**Key concepts:** how-it-works, pattern

### frontend\src\types/
| ID | Type | Title | Date |
|----|------|-------|------|
| dc4e6088-e112-44c8-89aa-5d22c02cd14a | 🔵 discovery | types/index.ts已实现ViewState扩展和状态验证 | 2026-06-20 |

**Key concepts:** how-it-works, what-changed, pattern

### openspec\changes\ux-optimization-flow-closure/
| ID | Type | Title | Date |
|----|------|-------|------|
| 0a34fe75-2708-4cb3-9255-7200acb901de | 🔵 discovery | UX优化设计文档：6个关键决策+4个风险缓解 | 2026-06-20 |
| 26dd798e-bde6-479d-bac6-a208c2110c96 | 🔵 discovery | UX优化提案：解决按钮分散和流程引导问题 | 2026-06-20 |
| e53e0c89-fdb8-4f86-87fd-a9b3a157c4ce | 🔵 discovery | UX优化任务进度：前4组完成，后5组待做 | 2026-06-20 |

**Key concepts:** trade-off, pattern, how-it-works, why-it-exists, what-changed

### openspec\changes\ux-optimization-flow-closure\specs\auto-advance/
| ID | Type | Title | Date |
|----|------|-------|------|
| 51a9549a-bc5d-446f-8efe-1469d2b4f0d6 | 🔵 discovery | auto-advance规格：半自动推进4个核心需求 | 2026-06-20 |

**Key concepts:** how-it-works, pattern

### openspec\changes\ux-optimization-flow-closure\specs\completion-summary/
| ID | Type | Title | Date |
|----|------|-------|------|
| 1994defe-609f-4e40-b3da-06f6c788fc26 | 🔵 discovery | completion-summary规格：成果汇总页6个SHALL需求 | 2026-06-20 |

**Key concepts:** how-it-works, pattern

### openspec\changes\ux-optimization-flow-closure\specs\view-state/
| ID | Type | Title | Date |
|----|------|-------|------|
| 09d3ba2e-c419-4bc4-9b4e-a4525f0df4bb | 🔵 discovery | view-state规格：ViewState扩展和数据迁移兼容 | 2026-06-20 |

**Key concepts:** how-it-works, pattern, gotcha

💡 *Use `mem-find` to search full details. Use `mem-create` to save important decisions.*
<!-- /open-mem-context -->
