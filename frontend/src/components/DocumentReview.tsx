import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface DocumentReviewProps {
  /** 文档标题，如 "PRD" / "接口文档" / "提示词套件" */
  title: string;
  /** 已生成的完整文档内容 */
  content: string;
  /** 流式生成中的 token 内容。非 undefined 时表示正在生成，组件只读 */
  streamingText?: string;
  /** AI 优化中（流式覆盖） */
  optimizing?: boolean;
  /** 点击 AI 优化 */
  onOptimize?: () => void;
  /** 底部确认按钮 */
  onConfirm?: () => void;
  /** 确认按钮文字，默认 "确认并继续" */
  confirmLabel?: string;
}

export default function DocumentReview({
  title,
  content,
  streamingText,
  optimizing = false,
  onOptimize,
  onConfirm,
  confirmLabel = "确认并继续",
}: DocumentReviewProps) {
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  const isStreaming = streamingText !== undefined || optimizing;
  const displayContent = isStreaming ? streamingText ?? content : content;

  // 自动滚动到底部
  useEffect(() => {
    contentRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [displayContent]);

  // 编辑模式下自适应 textarea 高度
  useEffect(() => {
    const el = textareaRef.current;
    if (!el || !editing) return;
    el.style.height = "auto";
    el.style.height = Math.max(el.scrollHeight, 400) + "px";
  }, [content, editing]);

  // 复制
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 降级方案
      const ta = document.createElement("textarea");
      ta.value = content;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [content]);

  return (
    <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white shrink-0">
        <h2 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <span className="text-primary-500">📄</span>
          {title}
          {isStreaming && (
            <span className="text-xs font-normal text-primary-500 animate-pulse">
              生成中…
            </span>
          )}
        </h2>

        <div className="flex items-center gap-2">
          {/* 编辑 / 预览切换 */}
          <button
            onClick={() => setEditing(!editing)}
            disabled={isStreaming}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              isStreaming
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : editing
                ? "bg-primary-100 text-primary-700 hover:bg-primary-200"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {editing ? "预览" : "编辑"}
          </button>

          {/* 复制 */}
          <button
            onClick={handleCopy}
            disabled={isStreaming || !content}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              isStreaming || !content
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : copied
                ? "bg-green-100 text-green-700"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {copied ? "已复制" : "复制"}
          </button>

          {/* AI 优化 */}
          {onOptimize && (
            <button
              onClick={onOptimize}
              disabled={isStreaming || editing}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                isStreaming || editing
                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                  : "bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-700"
              }`}
            >
              ✨ AI 优化
            </button>
          )}
        </div>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {editing && !isStreaming ? (
          <textarea
            ref={textareaRef}
            className="w-full min-h-[400px] rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 leading-relaxed outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-200 resize-y font-mono"
            value={content}
            readOnly
          />
        ) : (
          <div className="rounded-xl border border-gray-200 bg-white px-6 py-5">
            <div className="prose prose-sm max-w-none prose-headings:text-gray-800 prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-p:text-sm prose-p:leading-relaxed prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-table:text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {displayContent}
              </ReactMarkdown>
            </div>

            {/* 流式光标 */}
            {isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-primary-500 animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        )}
      </div>

      {/* 底部确认按钮 */}
      {onConfirm && (
        <div className="border-t border-gray-100 bg-white px-4 py-3 shrink-0">
          <button
            onClick={onConfirm}
            disabled={isStreaming}
            className={`w-full rounded-xl font-semibold py-3 px-6 transition-colors text-sm ${
              isStreaming
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-700 shadow-sm"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      )}

      <div ref={contentRef} />
    </div>
  );
}
