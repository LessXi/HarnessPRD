# Proposal: 接入 Debug 系统 — LangSmith 环境变量 + 启动校验

## 动机

debug-observability 体系的各组（1-4, 6-8）已实现完毕，但 `main.py` 中缺少两处关键接入：

1. **LangSmith 环境变量设置**：LangChain 在首次 import 时读取 `LANGCHAIN_TRACING_V2` 环境变量，当前未在 import 前设置，导致即使 `.env` 中配置了 tracing 也无法生效。
2. **启动校验 lifespan**：`validate_debug_config()` 函数（设计文档 §3.9）未实现，启动时无法校验 LangSmith 连通性和日志目录可写性。

## 目标

在 `main.py` 中补齐上述两处接入，使 debug-observability 体系完整闭环。

## 范围

- 仅修改 `backend/main.py`（1 个文件）
- 不新增 capability（纯接线）
- 不改变架构和接口
