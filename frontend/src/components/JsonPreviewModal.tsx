import { useEffect, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { debugLogger } from "@/utils/debugLogger";

// 运行时 monaco 实例引用（用于 Range 构造）
let _monaco: typeof import("monaco-editor") | null = null;

interface Props {
  formData: Record<string, any>;
  /** 可选的 JSON schema 对象（仅用于文档） */
  schema?: object;
  errors: { path: string; message: string }[];
  /** 是否打开（由父组件条件渲染控制时可选） */
  open?: boolean;
  onClose: () => void;
}

/**
 * 将 ajv errors 转换为 Monaco decorations
 */
function errorsToDecorations(
  errors: Props["errors"],
  model: editor.ITextModel
): editor.IModelDeltaDecoration[] {
  if (errors.length === 0) return [];

  const text = model.getValue();
  const lines = text.split("\n");

  return errors.map((e) => {
    let lineNumber = 1;
    // 根据 path 中的字段名定位行号
    const fieldName = e.path.replace(/^\//, "");
    if (fieldName) {
      for (let i = 0; i < lines.length; i++) {
        // 匹配 "fieldName": 模式，避免匹配到值中的内容
        if (lines[i].includes(`"${fieldName}"`) || lines[i].includes(`"${fieldName}":`)) {
          lineNumber = i + 1;
          break;
        }
      }
    }

    const Range = _monaco?.Range;
    const range = Range
      ? new Range(lineNumber, 1, lineNumber, 1)
      : { startLineNumber: lineNumber, startColumn: 1, endLineNumber: lineNumber, endColumn: 1 };

    return {
      range,
      options: {
        isWholeLine: true,
        className: "validation-error-line",
        glyphMarginClassName: "validation-error-glyph",
        hoverMessage: { value: `⚠ ${e.message}` },
      },
    };
  });
}

export default function JsonPreviewModal({ formData, errors, onClose }: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<string[]>([]);

  const jsonText = JSON.stringify(formData, null, 2);
  const errorCount = errors.length;

  useEffect(() => {
    debugLogger.log("info", "preview:modal", {
      action: "open",
      fieldCount: Object.keys(formData).length,
      errorCount,
    });
    return () => {
      debugLogger.log("info", "preview:modal", { action: "close" });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    _monaco = monaco as unknown as typeof import("monaco-editor");

    // 应用错误 decorations
    if (errors.length > 0 && editor.getModel()) {
      const decorations = errorsToDecorations(errors, editor.getModel()!);
      decorationsRef.current = editor.deltaDecorations(decorationsRef.current, decorations);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">JSON 预览</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1"
            aria-label="关闭"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Monaco Editor */}
        <div className="flex-1 min-h-[400px] p-4">
          <Editor
            height="100%"
            defaultLanguage="json"
            value={jsonText}
            onMount={handleEditorMount}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
              automaticLayout: true,
            }}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 text-sm text-gray-500">
          <span>
            {errorCount > 0
              ? `${errorCount} 个校验错误`
              : "✅ 校验通过"}
          </span>
          <div className="flex items-center gap-4">
            <span className="text-xs text-gray-400">
              字段数: {Object.keys(formData).length} | 错误: {errorCount}
            </span>
            <button
              onClick={onClose}
              className="rounded-lg bg-primary-500 hover:bg-primary-600 text-white px-4 py-1.5 text-sm font-medium transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
