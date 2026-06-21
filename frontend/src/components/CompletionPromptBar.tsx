import { ViewState } from "@/types";

interface CompletionPromptBarProps {
  currentViewState: ViewState;
  onContinue: () => void;
  onSkip: () => void;
  onBack: () => void;
  onCancel?: () => void;
  isGenerating?: boolean;
}

export default function CompletionPromptBar({
  currentViewState,
  onContinue,
  onSkip,
  onBack,
  onCancel,
  isGenerating = false,
}: CompletionPromptBarProps) {
  // 根据当前阶段确定下一个阶段的标签
  const getNextStageLabel = (): string => {
    switch (currentViewState) {
      case 'reviewing_prd':
        return '接口文档';
      case 'reviewing_api':
        return '提示词套件';
      case 'reviewing_prompts':
        return '完成';
      default:
        return '下一阶段';
    }
  };

  return (
    <div className="fixed bottom-0 left-64 right-0 bg-white border-t border-gray-200 p-4 shadow-lg">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <div className="text-sm text-gray-600">
          是否继续生成{getNextStageLabel()}？
        </div>
        <div className="flex space-x-2">
          {isGenerating && onCancel && (
            <button
              onClick={onCancel}
              className="px-3 py-2 text-sm bg-red-100 text-red-600 rounded-lg hover:bg-red-200 transition-colors"
            >
              取消生成
            </button>
          )}
          <button
            onClick={onBack}
            className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            返回
          </button>
          <button
            onClick={onSkip}
            className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            跳过
          </button>
          <button
            onClick={onContinue}
            className="px-3 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
          >
            继续
          </button>
        </div>
      </div>
    </div>
  );
}