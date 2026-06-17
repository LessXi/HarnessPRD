import { useState, useRef, useCallback, KeyboardEvent } from "react";

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({
  onSend,
  disabled = false,
  placeholder = "输入消息…",
}: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整高度
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const scrollHeight = el.scrollHeight;
    // 单行 ~28px，最大 6 行 ≈ 168px
    el.style.height = `${Math.min(Math.max(scrollHeight, 28), 168)}px`;
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    // 发送后重置高度
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div className="border-t border-gray-200 bg-white px-4 py-3">
      <div className="flex items-end gap-2 max-w-3xl mx-auto">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            // 用 requestAnimationFrame 确保 DOM 已更新
            requestAnimationFrame(adjustHeight);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className={`flex-1 resize-none rounded-xl border px-3 py-2 text-sm outline-none transition-colors ${
            disabled
              ? "bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed"
              : "bg-white border-gray-300 text-gray-900 focus:border-primary-400 focus:ring-1 focus:ring-primary-400"
          }`}
        />

        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className={`shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            disabled || !value.trim()
              ? "bg-gray-100 text-gray-400 cursor-not-allowed"
              : "bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-700"
          }`}
        >
          发送
        </button>
      </div>
      <p className="text-[11px] text-gray-400 mt-1 text-center">
        Enter 发送 · Shift+Enter 换行
      </p>
    </div>
  );
}
