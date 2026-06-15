# HarnessPRD 技术栈清单

> 版本 1.0 · 更新时间：2026-06-14

---

## 一、后端技术栈

| 类别 | 技术 | 版本范围 | 用途 | 选择理由 |
|------|------|---------|------|---------|
| **语言** | Python | `3.11.x` | 运行时 | 用户指定；3.11 是稳定 LTS，LangChain/FastAPI 均完美支持 |
| **Web 框架** | FastAPI | `>=0.111,<1.0` | HTTP 服务、SSE 流式输出 | 原生异步 + `StreamingResponse`；Pydantic 自动 OpenAPI；社区活跃 |
| **LLM 编排** | LangChain | `>=0.3.0,<0.4` | 消息管理、Chain 编排、Provider 统一 | 用户选择；0.3 是当前稳定主线 |
| **LLM Provider** | langchain-openai | `>=0.2,<1.0` | OpenAI 及兼容格式调用 | LangChain 官方 OpenAI 集成 |
| **LLM Provider** | langchain-anthropic | `>=0.2,<1.0` | Anthropic Claude 调用 | LangChain 官方 Anthropic 集成 |
| **LLM Provider** | langchain-deepseek | `>=0.1,<1.0` | DeepSeek 调用（额外备选） | 国内可用，性价比高，预留接入 |
| **ASGI 服务器** | uvicorn | `>=0.29,<1.0` | 运行 FastAPI | FastAPI 官方推荐，支持 hot-reload 开发 |
| **数据校验** | Pydantic | `>=2.5,<3.0` | 请求/响应/配置模型 | FastAPI 自带，LangChain 也依赖 |
| **配置管理** | pydantic-settings | `>=2.1,<3.0` | `.env` 结构化管理 Agent 配置 | 解决"改 .env 不改代码"需求 |
| **环境变量** | python-dotenv | `>=1.0,<2.0` | 加载 `.env` 文件 | 轻量标准方案 |
| **HTTP 客户端** | httpx | `>=0.27,<1.0` | 非 LangChain 场景的 HTTP 请求 | 异步原生，FastAPI 生态标配 |
| **文档模板** | Jinja2 | `>=3.1,<4.0` | PRD/接口文档/提示词套件渲染 | Python 标准模板引擎，经久考验 |

---

## 二、前端技术栈

| 类别 | 技术 | 版本范围 | 用途 | 选择理由 |
|------|------|---------|------|---------|
| **框架** | React | `^18.3` | UI 框架 | 用户有基础；生态最大，文档资源多 |
| **构建工具** | Vite | `^5.4` | 开发服务器、打包 | 秒级 HMR，零配置，React 官方推荐 |
| **语言** | TypeScript (TSX) | `^5.4` | 前端逻辑 | 与后端 Pydantic model 类型对齐，shadcn/ui 原生支持，减少字段名拼写低级错误 |
| **样式** | Tailwind CSS | `^3.4` | 原子化 CSS | 写 UI 效率极高，不需要切图和 class 命名 |
| **组件库** | shadcn/ui | latest | 按钮/表单/对话框/选择器等 | 复制源码到项目，不引入 npm 依赖；基于 Radix UI 无障碍原语 |
| **图标** | lucide-react | `^0.40` | SVG 图标 | shadcn/ui 默认搭配，2000+ 图标 |
| **Markdown** | react-markdown | `^9.0` | AI 输出 Markdown 渲染 | 轻量，支持 GFM（表格/任务列表） |
| **Markdown 插件** | remark-gfm | `^4.0` | 表格/删除线/任务列表支持 | react-markdown 配套插件 |
| **CSS 工具** | tailwind-merge | `^2.3` | 智能合并 Tailwind class | shadcn/ui 内部使用 |
| **动画** | tailwindcss-animate | `^1.0` | Tailwind 动画预设 | shadcn/ui 组件动画依赖 |

---

## 三、明确不需要的技术

| 不需要 | 原因 |
|--------|------|
| **数据库**（MySQL / PostgreSQL / SQLite / MongoDB） | 数据会话级别，存储在内存 dict 中。如需持久化，JSON 文件即可，不需要数据库。 |
| **ORM**（SQLAlchemy / Django ORM / Prisma） | 没有数据库，ORM 无存在意义。 |
| **Redis** | 不需要共享缓存或分布式锁。单进程内存存储足够了。 |
| **消息队列**（Celery / RabbitMQ / Kafka） | 无异步后台任务。LLM 调用用 FastAPI 异步 + SSE 流式输出天然解决等待问题。 |
| **Docker**（开发阶段） | 1 人开发，`pip install` + `npm install` 更快。部署时再写 Dockerfile（半小时）。 |
| **Nginx**（开发阶段） | Vite 内置代理可直接转发到 FastAPI，开发不需要 Nginx。 |
| **CI/CD**（GitHub Actions / Jenkins） | 1 人开发，本地跑通就推送。有第二个协作者再配置。 |
| **用户认证**（OAuth / JWT / Session） | v1 是单机工具，不需要登录系统。 |
| **微服务 / API 网关** | 单体 FastAPI 应用完全够用。 |
| **WebSocket** | SSE 足够处理服务端→客户端的单向实时流，更简单、更省资源。 |
| **LangSmith / LangFuse**（LLM 可观测性） | v1 不需要，终端日志可审计。等流程复杂了再接入。 |
| **向量数据库**（Pinecone / Chroma / Weaviate） | 不需要 RAG，不需要语义搜索，不需要长期记忆。 |
| **Django / Flask**（替代 FastAPI） | Django 太重（ORM/Admin/Migration 全是负担）；Flask 同步模型做 SSE 体验差。 |
