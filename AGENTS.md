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

1. **步骤一 — 产品信息表单**（`/form` 路由）。共 17 个字段（11 个必填基础字段，6 个选填高级字段）。`mvp_features` 是唯一的 `string[]` 字段（至少 3 项）。表单数据以 JSON 提交至后端，后端以 UUID 会话为键存储在内存 dict 中。

2. **步骤二 — AI 对话澄清**（`/chat/<session_id>`）。LLM 通过 SSE 流式提出追问。上下文保存在 `messages[]` 中。结束时 AI 生成结构化的 JSON 需求摘要，用户需确认后方可继续。

3. **步骤三 — 文档生成**（三个并行子步骤，各有独立路由）：
   - `/generate/prd/<session_id>` — PRD 文档
   - `/generate/api/<session_id>` — 接口文档
   - `/generate/prompts/<session_id>` — 提示词套件
   - 每个子步骤：Write 阶段（SSE 流式）→ Review 阶段（审核 Agent）→ Rewrite 阶段 → 循环（最多 3 轮）。

4. **会话管理器** — 内存中的 `dict[str, Session]`；无需数据库。JSON 文件持久化仅为备用方案。

5. **SSE 流式传输** — 服务端推送事件用于 LLM token 流式输出。不使用 WebSocket。后端使用 `sse-starlette`，前端使用 `EventSource` 或类似方案。

## 约定

- **尚无源码** — 所有实现从零开始。
- **路由结构** 必须遵循 `/form`、`/chat/<id>`、`/generate/{prd,api,prompts}/<id>` 模式。
- **表单数据模型** 定义在 `docs/form-data-structure.md` 中 — 直接使用其中所示的 Pydantic 模型。
- **优先级标记** 定义在 `docs/features.md` 中：P0（必须有）、P1（重要）、P2（锦上添花）。
- **shadcn/ui** 组件复制到仓库内（非 npm 依赖），基于 Radix UI 原语。
- **语言**：API 和代码标识符用英文；UI 标签可用中文或英文。
- **类型**：前端 TypeScript 类型应与 Pydantic 模型字段名保持一致。
- **dotenv 不入库** — `.env` 已在 `.gitignore` 中；使用 `.env.example` 作为文档。

## 备注

（项目特定备注可在此处添加。）
