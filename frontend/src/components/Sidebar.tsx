import React from "react";
import { ViewState, ProjectState, STEPS, STEP_INDEX_MAP } from "@/types";

export interface PrimaryAction {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
}

export interface SecondaryAction {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  icon?: React.ReactNode;
}

interface SidebarProps {
  current: ViewState;
  project: ProjectState;
  onNavigate: (viewState: ViewState) => void;
  onGoBack: (targetState: ViewState) => void;
  primaryActions?: PrimaryAction[];
  secondaryActions?: SecondaryAction[];
}

const Sidebar = React.memo(function Sidebar({ current, project, onNavigate, onGoBack, primaryActions, secondaryActions }: SidebarProps) {
  const currentIdx = STEP_INDEX_MAP[current] ?? -1;
  
  // 计算前一个和下一个状态
  const getPreviousState = (): ViewState | null => {
    if (currentIdx <= 0) return null;
    const prevStep = STEPS[currentIdx - 1];
    return prevStep ? (prevStep.id as ViewState) : null;
  };
  
  const getNextState = (): ViewState | null => {
    if (currentIdx >= STEPS.length - 1) return null;
    const nextStep = STEPS[currentIdx + 1];
    return nextStep ? (nextStep.id as ViewState) : null;
  };
  
  const previousState = getPreviousState();
  const nextState = getNextState();

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* 进度条 */}
      <div className="p-4 border-b border-gray-100">
        <h3 className="text-sm font-medium text-gray-700 mb-3">项目进度</h3>
        <nav>
          <ol className="space-y-2">
            {STEPS.map((step, idx) => {
              const stepState = idx === currentIdx ? "current" : idx < currentIdx ? "done" : "pending";
              const isCompleted = project.completedSteps.includes(step.id as ViewState);
              const isPendingUpdate = project.pendingUpdates.includes(step.id as ViewState);
              
              return (
                <li key={step.id} className="flex items-center">
                  <button
                    onClick={() => {
                      if (stepState === "done" || isCompleted) {
                        onGoBack(step.id as ViewState);
                      }
                    }}
                    disabled={stepState === "pending" && !isCompleted}
                    className={`flex items-center w-full text-left p-2 rounded-lg transition-colors ${
                      stepState === "current"
                        ? "bg-primary-50 text-primary-700"
                        : stepState === "done" || isCompleted
                        ? "hover:bg-gray-50 text-gray-700 cursor-pointer"
                        : "text-gray-400 cursor-not-allowed"
                    }`}
                  >
                    <span className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium shrink-0 ${
                      stepState === "done" || isCompleted
                        ? "bg-primary-500 text-white"
                        : stepState === "current"
                        ? "bg-primary-100 text-primary-700 ring-2 ring-primary-300"
                        : "bg-gray-100 text-gray-400"
                    }`}>
                      {stepState === "done" || isCompleted ? (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        idx + 1
                      )}
                    </span>
                    <span className="ml-2 text-sm">{step.label}</span>
                    {isPendingUpdate && (
                      <span className="ml-auto text-yellow-500" title="数据可能不一致">⚠</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
      </div>

      {/* 操作按钮区域 */}
      <div className="p-4 flex-1">
        <h3 className="text-sm font-medium text-gray-700 mb-3">操作</h3>
        <div className="space-y-2">
          {/* 导航组 */}
          <div className="flex space-x-2">
            {previousState && (
              <button
                onClick={() => onGoBack(previousState)}
                className="flex-1 px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                ← 上一步
              </button>
            )}
            {nextState && (
              <button
                onClick={() => onNavigate(nextState)}
                className="flex-1 px-3 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
              >
                下一步 →
              </button>
            )}
          </div>
          
          {/* 主要操作按钮 */}
          {primaryActions && primaryActions.length > 0 && (
            <div className="space-y-2">
              {primaryActions.map((action, index) => (
                <button
                  key={index}
                  onClick={action.onClick}
                  disabled={action.disabled}
                  className={`w-full px-3 py-2 text-sm rounded-lg transition-colors ${
                    action.variant === 'primary'
                      ? 'bg-primary-500 text-white hover:bg-primary-600'
                      : action.variant === 'danger'
                      ? 'bg-red-100 text-red-600 hover:bg-red-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  } ${action.disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
          
          {/* 次要操作按钮 */}
          {secondaryActions && secondaryActions.length > 0 && (
            <div className="space-y-2">
              {secondaryActions.map((action, index) => (
                <button
                  key={index}
                  onClick={action.onClick}
                  disabled={action.disabled}
                  className={`w-full px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center gap-2 ${action.disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {action.icon}
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 文档信息 */}
      <div className="p-4 border-t border-gray-100">
        <h3 className="text-sm font-medium text-gray-700 mb-2">文档信息</h3>
        <div className="text-xs text-gray-500 space-y-1">
          <div>PRD: {project.prd.content.length} 字</div>
          <div>接口文档: {project.api.content.length} 字</div>
          <div>提示词: {project.prompts.content.length} 字</div>
        </div>
      </div>


    </aside>
  );
});

export default Sidebar;