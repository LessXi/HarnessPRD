import React, { useState, useRef, useEffect } from "react";
import { ProjectState } from "@/types";
import { assessComplexity } from "@/utils/complexity";

interface CompletionSummaryProps {
  project: ProjectState;
  onPreview: (docType: "prd" | "api" | "prompts") => void;
  onDownload: (docType: "prd" | "api" | "prompts") => void;
  onCopy: (docType: "prd" | "api" | "prompts") => void;
  onDownloadAll: () => void;
  onDownloadAllSeparately: () => void;
  onNewProject: () => void;
}
const CompletionSummary = React.memo(function CompletionSummary({
  project,
  onPreview,
  onDownload,
  onCopy,
  onDownloadAll,
  onDownloadAllSeparately,
  onNewProject,
}: CompletionSummaryProps) {
  const [downloadMenuOpen, setDownloadMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭下拉菜单
  useEffect(() => {
    if (!downloadMenuOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setDownloadMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [downloadMenuOpen]);
  const documents = [
    {
      type: "prd" as const,
      title: "PRD",
      description: "产品需求文档",
      content: project.prd.content,
    },
    {
      type: "api" as const,
      title: "接口文档",
      description: "API 接口文档",
      content: project.api.content,
    },
    {
      type: "prompts" as const,
      title: "提示词套件",
      description: "AI 提示词集合",
      content: project.prompts.content,
    },
  ];

  const handleCopy = async (docType: "prd" | "api" | "prompts", content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      onCopy(docType);
    } catch (err) {
      console.error("复制失败:", err);
    }
  };

  return (
    <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-6">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">项目完成！</h1>
        <p className="text-gray-600">所有文档已生成完毕，您可以预览、下载或复制文档内容。</p>
      </div>

      <div className="grid gap-6 md:grid-cols-3 mb-8">
        {documents.map((doc) => (
          <div key={doc.type} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="mb-4">
              <h3 className="font-medium text-gray-900">{doc.title}</h3>
              <p className="text-sm text-gray-500">{doc.description}</p>
            </div>
            
            <div className="text-sm text-gray-600 mb-4">
              <div>字数: {doc.content.length}</div>
              <div>大小: {new Blob([doc.content]).size} 字节</div>
              <div>复杂度: {assessComplexity(doc.content).level}</div>
            </div>

            <div className="flex space-x-2">
              <button
                onClick={() => onPreview(doc.type)}
                className="flex-1 px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                预览
              </button>
              <button
                onClick={() => onDownload(doc.type)}
                className="flex-1 px-3 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
              >
                下载
              </button>
              <button
                onClick={() => handleCopy(doc.type, doc.content)}
                className="flex-1 px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                复制
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-center space-x-4">
        {/* 一键下载全部 — 下拉菜单 */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setDownloadMenuOpen(!downloadMenuOpen)}
            className="px-6 py-3 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors inline-flex items-center gap-2"
          >
            一键下载全部
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {downloadMenuOpen && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-10">
              <button
                onClick={() => { onDownloadAll(); setDownloadMenuOpen(false); }}
                className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-t-lg transition-colors"
              >
                打包为 ZIP 下载
              </button>
              <button
                onClick={() => { onDownloadAllSeparately(); setDownloadMenuOpen(false); }}
                className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 rounded-b-lg transition-colors"
              >
                逐个下载
              </button>
            </div>
          )}
        </div>
        <button
          onClick={onNewProject}
          className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
        >
          开始新项目
        </button>
      </div>
    </div>
  );
});

export default CompletionSummary;