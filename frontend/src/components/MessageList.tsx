import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/types";

interface Props {
  messages: ChatMessage[];
  /** 当前正在流式接收的 AI 回复片段（打字机效果） */
  streamingText?: string;
}

export default function MessageList({ messages, streamingText }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 消息变化时自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  // 空状态
  if (messages.length === 0 && !streamingText) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-sm">开始与 AI 助手对话</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.map((msg, idx) => (
        <div
          key={idx}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-primary-500 text-white rounded-br-sm"
                : "bg-white border border-gray-200 rounded-bl-sm"
            }`}
          >
            {msg.role === "assistant" ? (
              <div className="prose prose-sm max-w-none prose-p:my-1 prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="whitespace-pre-wrap">{msg.content}</div>
            )}
          </div>
        </div>
      ))}

      {/* 流式回复：打字机效果 */}
      {streamingText && (
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-xl rounded-bl-sm bg-white border border-gray-200 px-4 py-2.5 text-sm leading-relaxed">
            <div className="prose prose-sm max-w-none prose-p:my-1 prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {streamingText}
              </ReactMarkdown>
            </div>
            {/* 闪烁光标 */}
            <span className="inline-block w-1.5 h-4 bg-primary-500 animate-pulse ml-0.5 align-text-bottom" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
