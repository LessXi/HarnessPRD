import axios from "axios";
import type { QuestionsConfig, StreamCallbacks } from "@/types";

const api = axios.create({
  baseURL: "/api",
});

// ========================================================================
// 常规 API（axios）
// ========================================================================

export async function getQuestions(): Promise<QuestionsConfig> {
  const { data } = await api.get<QuestionsConfig>("/sessions/questions");
  return data;
}

export async function createSession(
  formData: Record<string, any>
): Promise<{ session_id: string; current_state: string }> {
  const { data } = await api.post("/sessions", formData);
  return data;
}

/** 发送用户消息（非流式，追加到对话历史） */
export async function sendMessage(
  sessionId: string,
  content: string
): Promise<void> {
  await api.post(`/sessions/${sessionId}/messages`, { content });
}

/** 获取对话历史 */
export async function getMessages(sessionId: string): Promise<any[]> {
  const { data } = await api.get(`/sessions/${sessionId}/messages`);
  return data;
}

// ========================================================================
// SSE 流式 API（fetch — 浏览器原生 ReadableStream）
// ========================================================================

/** 与 axios 实例共享 base URL，一处修改两处生效 */
const SSE_BASE = api.defaults.baseURL!;

/**
 * 从 fetch Response 中逐行读取 SSE data: 事件。
 *
 * 后端 SSE 格式：
 *   data: {"event":"chunk","content":"..."}
 *   data: {"event":"done"}
 *   data: {"event":"error","content":"..."}
 *
 * 解析后分别回调 onChunk / onDone / onError。
 *
 * @param response  fetch 返回的 Response 对象
 * @param callbacks  onChunk / onDone / onError 回调
 * @param signal     可选的 AbortSignal，用于中断读取
 */
export async function readStream(
  response: Response,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const { onChunk, onDone, onError } = callbacks;
  const reader = response.body?.getReader();
  if (!reader) {
    onError("响应体不可读");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        onError("请求已取消");
        return;
      }

      const { done, value } = await reader.read();
      if (done) break;

      // 解码二进制块并追加到缓冲区
      buffer += decoder.decode(value, { stream: true });

      // 按行分割处理
      const lines = buffer.split("\n");
      // 最后一个元素可能是不完整的行，保留到下次
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data: ")) continue;

        // 提取 data: 后的 JSON
        const jsonStr = trimmed.slice(6);
        if (!jsonStr) continue;

        try {
          const parsed = JSON.parse(jsonStr);
          const event = parsed.event as string;

          switch (event) {
            case "chunk":
              onChunk(parsed.content ?? "");
              break;
            case "done":
              onDone();
              break;
            case "error":
              onError(parsed.content ?? "未知 SSE 错误");
              break;
          }
        } catch {
          // JSON 解析失败，忽略这一行
        }
      }
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "SSE 流读取异常";
    onError(msg);
  }
}

/**
 * SSE 流式发起对话：AI 主动破冰问候。
 * POST /api/sessions/{id}/start-stream
 *
 * @param sessionId  会话 ID
 * @param callbacks  onChunk / onDone / onError
 * @param signal     可选 AbortSignal
 */
export async function startConversationStream(
  sessionId: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/sessions/${sessionId}/start-stream`, {
      method: "POST",
      signal,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`start-stream 失败 (${response.status}): ${body}`);
      return;
    }
    await readStream(response, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "start-stream 请求异常";
    callbacks.onError(msg);
  }
}

/**
 * SSE 流式接续对话：AI 回复用户消息。
 * POST /api/sessions/{id}/continue-stream
 *
 * @param sessionId  会话 ID
 * @param content    用户消息内容
 * @param callbacks  onChunk / onDone / onError
 * @param signal     可选 AbortSignal
 */
export async function continueConversationStream(
  sessionId: string,
  content: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/sessions/${sessionId}/continue-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
      signal,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`continue-stream 失败 (${response.status}): ${body}`);
      return;
    }
    await readStream(response, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "continue-stream 请求异常";
    callbacks.onError(msg);
  }
}

// ========================================================================
// 文档生成 SSE（两步：POST 触发 → GET 流式）
// ========================================================================

/**
 * 流式生成 PRD 文档。
 *
 * 1. POST /api/sessions/{id}/documents/prd/generate  触发状态迁移
 * 2. GET  /api/sessions/{id}/documents/prd/stream     SSE 流式接收
 */
export async function generatePrdStream(
  sessionId: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    // 触发生成
    const triggerRes = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/prd/generate`,
      { method: "POST", signal },
    );
    if (!triggerRes.ok) {
      const body = await triggerRes.text().catch(() => "");
      callbacks.onError(`PRD 生成失败 (${triggerRes.status}): ${body}`);
      return;
    }

    // SSE 流
    const streamRes = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/prd/stream`,
      { signal },
    );
    if (!streamRes.ok) {
      const body = await streamRes.text().catch(() => "");
      callbacks.onError(`PRD 流失败 (${streamRes.status}): ${body}`);
      return;
    }
    await readStream(streamRes, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "PRD 生成请求异常";
    callbacks.onError(msg);
  }
}

/**
 * 流式生成接口文档。
 *
 * 1. POST /api/sessions/{id}/documents/api/generate
 * 2. GET  /api/sessions/{id}/documents/api/stream
 */
export async function generateApiDocsStream(
  sessionId: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const triggerRes = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/api/generate`,
      { method: "POST", signal },
    );
    if (!triggerRes.ok) {
      const body = await triggerRes.text().catch(() => "");
      callbacks.onError(`接口文档生成失败 (${triggerRes.status}): ${body}`);
      return;
    }

    const streamRes = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/api/stream`,
      { signal },
    );
    if (!streamRes.ok) {
      const body = await streamRes.text().catch(() => "");
      callbacks.onError(`接口文档流失败 (${streamRes.status}): ${body}`);
      return;
    }
    await readStream(streamRes, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "接口文档生成请求异常";
    callbacks.onError(msg);
  }
}

/**
 * 流式生成提示词套件。
 *
 * 1. POST /api/sessions/{id}/documents/prompts/generate
 * 2. GET  /api/sessions/{id}/documents/prompts/stream
 */
export async function generatePromptsStream(
  sessionId: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const triggerRes = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/prompts/generate`,
      { method: "POST", signal },
    );
    if (!triggerRes.ok) {
      const body = await triggerRes.text().catch(() => "");
      callbacks.onError(`提示词套件生成失败 (${triggerRes.status}): ${body}`);
      return;
    }

    const streamRes = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/prompts/stream`,
      { signal },
    );
    if (!streamRes.ok) {
      const body = await streamRes.text().catch(() => "");
      callbacks.onError(`提示词套件流失败 (${streamRes.status}): ${body}`);
      return;
    }
    await readStream(streamRes, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "提示词套件生成请求异常";
    callbacks.onError(msg);
  }
}

/**
 * 流式优化文档（Review→Rewrite）。
 *
 * POST /api/sessions/{id}/documents/{docType}/optimize-stream
 * （单步 POST，直接返回 SSE 流）
 */
export async function optimizeDocumentStream(
  sessionId: string,
  docType: "prd" | "api" | "prompts",
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(
      `${SSE_BASE}/sessions/${sessionId}/documents/${docType}/optimize-stream`,
      { method: "POST", signal },
    );
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`文档优化失败 (${response.status}): ${body}`);
      return;
    }
    await readStream(response, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "文档优化请求异常";
    callbacks.onError(msg);
  }
}
