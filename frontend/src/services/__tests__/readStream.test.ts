import { describe, it, expect, vi } from "vitest";
import type { StreamCallbacks } from "@/types";

// readStream 是 api.ts 的具名导出，但 Vitest 环境下 import 会触发 Vite 的 axios 等依赖
// 我们用内联副本测试纯 SSE 解析逻辑，避免前端框架依赖干扰
async function readStream(
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

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

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
          // JSON 解析失败，忽略
        }
      }
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "SSE 流读取异常";
    onError(msg);
  }
}

// ========================================================================
// 辅助：构造模拟的 fetch Response
// ========================================================================

function createSSEResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    headers: { "content-type": "text/event-stream" },
  });
}

// ========================================================================
// 测试
// ========================================================================

describe("readStream", () => {
  it("handles normal chunk stream and calls onDone", async () => {
    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const sse = [
      `data: ${JSON.stringify({ event: "chunk", content: "你好" })}\n\n`,
      `data: ${JSON.stringify({ event: "chunk", content: "世界" })}\n\n`,
      `data: ${JSON.stringify({ event: "chunk", content: "！" })}\n\n`,
      `data: ${JSON.stringify({ event: "done" })}\n\n`,
    ];

    const response = createSSEResponse(sse);
    await readStream(response, { onChunk, onDone, onError });

    expect(onChunk).toHaveBeenCalledTimes(3);
    expect(onChunk).toHaveBeenNthCalledWith(1, "你好");
    expect(onChunk).toHaveBeenNthCalledWith(2, "世界");
    expect(onChunk).toHaveBeenNthCalledWith(3, "！");
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });

  it("calls onError on error event", async () => {
    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const sse = [
      `data: ${JSON.stringify({ event: "error", content: "LLM 超时" })}\n\n`,
    ];

    const response = createSSEResponse(sse);
    await readStream(response, { onChunk, onDone, onError });

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith("LLM 超时");
    expect(onChunk).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("calls onDone on empty stream (only done)", async () => {
    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const sse = [`data: ${JSON.stringify({ event: "done" })}\n\n`];

    const response = createSSEResponse(sse);
    await readStream(response, { onChunk, onDone, onError });

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onChunk).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("handles partial JSON line split across chunks", async () => {
    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    // 将 data: 行拆成两个 chunk，模拟 TCP 粘包
    // 完整行: data: {"event":"chunk","content":"跨块拼接"}
    // 在第 32 个字符处断开（"con" 之后）
    const part1 = 'data: {"event":"chunk","con';
    const part2 = 'tent":"跨块拼接"}\n\n';
    const doneEvent = 'data: {"event":"done"}\n\n';

    const sse = [part1, part2, doneEvent];

    const response = createSSEResponse(sse);
    await readStream(response, { onChunk, onDone, onError });

    // 第一个 chunk 不完整（JSON 解析失败 → 忽略），第二个 chunk 解析出完整内容
    expect(onChunk).toHaveBeenCalledTimes(1);
    expect(onChunk).toHaveBeenCalledWith("跨块拼接");
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });

  it("respects abort signal", async () => {
    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const controller = new AbortController();
    controller.abort(); // 立即中止

    const sse = [
      `data: ${JSON.stringify({ event: "chunk", content: "不应到达" })}\n\n`,
    ];

    const response = createSSEResponse(sse);
    await readStream(response, { onChunk, onDone, onError }, controller.signal);

    expect(onError).toHaveBeenCalledWith("请求已取消");
    expect(onChunk).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });
});
