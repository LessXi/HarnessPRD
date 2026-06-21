import axios from "axios";
import type {
  QuestionsConfig,
  ChatRequest,
  SummaryRequest,
  DocumentRequest,
  OptimizeRequest,
  StreamCallbacks,
} from "@/types";
import { debugLogger } from "@/utils/debugLogger";

const api = axios.create({
  baseURL: "/api",
});

// ========================================================================
// 常规 API（axios）
// ========================================================================

export async function getQuestions(): Promise<QuestionsConfig> {
  const { data } = await api.get<QuestionsConfig>("/questions");
  return data;
}

export async function generateSummary(
  req: SummaryRequest,
): Promise<{ summary: string }> {
  const { data } = await api.post("/summary/generate", req);
  return data;
}

// ========================================================================
// SSE 流式 API（fetch — 浏览器原生 ReadableStream）
// ========================================================================

const SSE_BASE = api.defaults.baseURL!;

/**
 * 从 fetch Response 中逐行读取 SSE data: 事件。
 *
 * 后端 SSE 格式：
 *   data: {"event":"chunk","content":"..."}
 *   data: {"event":"done","assistant_content":"..."}
 *   data: {"event":"error","content":"..."}
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
  let chunkCount = 0;

  // 解析 buffer 中的完整 SSE 行，返回剩余不完整行
  const processLines = (buf: string): string => {
    const lines = buf.split("\n");
    const remainder = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith("data: ")) continue;

      const jsonStr = trimmed.slice(6);
      if (!jsonStr) continue;

      try {
        const parsed = JSON.parse(jsonStr);
        const event = parsed.event as string;

        switch (event) {
          case "chunk":
            chunkCount++;
            debugLogger.log('info', 'sse:readStream', { event_type: 'chunk', chunk_index: chunkCount });
            onChunk(parsed.content ?? "");
            break;
          case "done":
            debugLogger.log('info', 'sse:readStream', { event_type: 'done', total_chunks: chunkCount });
            onDone(parsed);
            break;
          case "error":
            debugLogger.log('error', 'sse:readStream', { event_type: 'sse_error', error: parsed.content });
            onError(parsed.content ?? "未知 SSE 错误");
            break;
        }
      } catch {
        // JSON 解析失败，忽略这一行
      }
    }
    return remainder;
  };

  try {
    while (true) {
      if (signal?.aborted) {
        onError("请求已取消");
        return;
      }

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      buffer = processLines(buffer);
    }

    // 流结束：刷新解码器并处理缓冲区中残留的最后一行
    // （最后一个 SSE 事件可能没有以 \n 结尾，否则会丢失 done 事件）
    buffer += decoder.decode();
    if (buffer.trim()) {
      processLines(buffer + "\n");
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "SSE 流读取异常";
    debugLogger.log('error', 'sse:readStream', { event_type: 'stream_error', error: msg });
    onError(msg);
  }
}

// ========================================================================
// 对话 SSE
// ========================================================================

/**
 * SSE 流式对话（合并 start/continue）。
 * POST /api/chat/stream
 */
export async function chatStream(
  req: ChatRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`chat/stream 失败 (${response.status}): ${body}`);
      return;
    }
    await readStream(response, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "chat/stream 请求异常";
    callbacks.onError(msg);
  }
}

// ========================================================================
// 文档生成 SSE
// ========================================================================

/**
 * 流式生成文档。
 * POST /api/documents/{docType}/stream
 */
export async function generateDocumentStream(
  docType: "prd" | "api" | "prompts",
  req: DocumentRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/documents/${docType}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`文档生成失败 (${response.status}): ${body}`);
      return;
    }
    await readStream(response, callbacks, signal);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "文档生成请求异常";
    callbacks.onError(msg);
  }
}

/**
 * 流式优化文档（Review→Rewrite）。
 * POST /api/documents/{docType}/optimize
 */
export async function optimizeDocumentStream(
  docType: "prd" | "api" | "prompts",
  req: OptimizeRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/documents/${docType}/optimize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal,
    });
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

// ========================================================================
// 下载
// ========================================================================

/**
 * 下载文档为 .md 文件。
 * POST /api/documents/{docType}/download
 */
export async function downloadDocument(
  docType: "prd" | "api" | "prompts",
  content: string,
): Promise<void> {
  try {
    const response = await fetch(`${SSE_BASE}/documents/${docType}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`下载失败 (${response.status}): ${body}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${docType}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "下载请求异常";
    throw new Error(msg);
  }
}
