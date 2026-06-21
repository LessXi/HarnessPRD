# Design: Debug 系统接入收尾

## 实现方案

### 1. LangSmith 环境变量（main.py 顶部）

在 `main.py` 最顶部（所有 langchain 相关 import 之前）设置环境变量：

```python
import os
from core.config import settings

if settings.langchain_tracing_v2:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
```

**关键注意**：必须在 `import langchain` 之前执行。当前 main.py 的 import 链（api → services → llm_service → langchain）会在模块加载时触发 langchain import，因此需将此段放在文件最顶部、所有应用模块 import 之前。

### 2. 启动校验 lifespan

将 `app = FastAPI(...)` 改为带 lifespan 的写法：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await validate_debug_config()
    yield

app = FastAPI(..., lifespan=lifespan)
```

`validate_debug_config()` 函数：
- 检查 LangSmith API 可达性（若 tracing 开启且有 key）
- 检查日志目录可写
- 所有失败仅 WARNING，不抛异常

## 风险评估

| 风险 | 缓解 |
|------|------|
| env var 设置晚于 langchain import | 将该段放在 main.py 最顶部，早于所有应用 import |
| lifespan 中 httpx 请求阻塞启动 | 使用 async/await，5s timeout |
