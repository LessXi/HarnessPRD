import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Sidebar from '../Sidebar';
import { ViewState, ProjectState, createEmptyProjectState } from '@/types';

describe('Rollback functionality', () => {
  const createProjectWithCompletedSteps = (completedSteps: ViewState[]): ProjectState => {
    const project = createEmptyProjectState();
    project.completedSteps = completedSteps;
    return project;
  };

  it('should call onRollback when clicking a completed step', () => {
    const onRollback = vi.fn();
    const onNavigate = vi.fn();
    const project = createProjectWithCompletedSteps(['form_editing', 'ai_dialogue']);
    
    render(
      <Sidebar
        current="reviewing_prd"
        project={project}
        onNavigate={onNavigate}
        onRollback={onRollback}
      />
    );

    // 点击已完成的步骤（AI 对话）
    const aiDialogueButton = screen.getByText('AI 对话');
    fireEvent.click(aiDialogueButton);

    expect(onRollback).toHaveBeenCalledWith('ai_dialogue');
  });

  it('should not call onRollback when clicking a pending step', () => {
    const onRollback = vi.fn();
    const onNavigate = vi.fn();
    const project = createProjectWithCompletedSteps(['form_editing']);
    
    render(
      <Sidebar
        current="ai_dialogue"
        project={project}
        onNavigate={onNavigate}
        onRollback={onRollback}
      />
    );

    // 点击未完成的步骤（PRD）
    const prdButton = screen.getByText('PRD');
    fireEvent.click(prdButton);

    expect(onRollback).not.toHaveBeenCalled();
  });

  it('should show pending update warning for pending updates', () => {
    const onRollback = vi.fn();
    const onNavigate = vi.fn();
    const project = createProjectWithCompletedSteps(['form_editing', 'ai_dialogue']);
    project.pendingUpdates = ['reviewing_prd'];
    
    render(
      <Sidebar
        current="reviewing_api"
        project={project}
        onNavigate={onNavigate}
        onRollback={onRollback}
      />
    );

    // 检查是否有待更新警告图标
    const warningIcon = screen.getByTitle('数据可能不一致');
    expect(warningIcon).toBeInTheDocument();
  });

  it('should display correct step states', () => {
    const onRollback = vi.fn();
    const onNavigate = vi.fn();
    const project = createProjectWithCompletedSteps(['form_editing', 'ai_dialogue']);
    
    render(
      <Sidebar
        current="reviewing_prd"
        project={project}
        onNavigate={onNavigate}
        onRollback={onRollback}
      />
    );

    // 检查步骤状态显示
    const steps = screen.getAllByRole('button');
    expect(steps.length).toBeGreaterThan(0);
    
    // 验证当前步骤高亮
    const currentStep = screen.getByText('PRD');
    expect(currentStep.closest('button')).toHaveClass('bg-primary-50');
  });
});