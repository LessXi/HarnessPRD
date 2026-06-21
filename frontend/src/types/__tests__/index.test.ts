import { describe, it, expect } from 'vitest';
import { isValidStateTransition, ViewState } from '../index';

describe('isValidStateTransition', () => {
  // 合法的直接转换
  it('should allow valid direct transitions', () => {
    expect(isValidStateTransition('form_editing', 'ai_dialogue', [])).toBe(true);
    expect(isValidStateTransition('ai_dialogue', 'generating_prd', [])).toBe(true);
    expect(isValidStateTransition('generating_prd', 'reviewing_prd', [])).toBe(true);
    expect(isValidStateTransition('reviewing_prd', 'generating_api', [])).toBe(true);
    expect(isValidStateTransition('generating_api', 'reviewing_api', [])).toBe(true);
    expect(isValidStateTransition('reviewing_api', 'generating_prompts', [])).toBe(true);
    expect(isValidStateTransition('generating_prompts', 'reviewing_prompts', [])).toBe(true);
    expect(isValidStateTransition('reviewing_prompts', 'completed', [])).toBe(true);
    expect(isValidStateTransition('completed', 'form_editing', [])).toBe(true);
  });

  // 合法的回退转换
  it('should allow rollback to completed steps', () => {
    const completedSteps: ViewState[] = ['form_editing', 'ai_dialogue', 'reviewing_prd'];
    expect(isValidStateTransition('reviewing_api', 'ai_dialogue', completedSteps)).toBe(true);
    expect(isValidStateTransition('reviewing_api', 'form_editing', completedSteps)).toBe(true);
    expect(isValidStateTransition('reviewing_api', 'reviewing_prd', completedSteps)).toBe(true);
  });

  // 非法的回退转换（目标步骤未完成）
  it('should not allow rollback to incomplete steps', () => {
    const completedSteps: ViewState[] = ['form_editing', 'ai_dialogue'];
    expect(isValidStateTransition('reviewing_prd', 'reviewing_api', completedSteps)).toBe(false);
  });

  // 非法的向前转换（跳过步骤）
  it('should not allow forward transitions that skip steps', () => {
    expect(isValidStateTransition('form_editing', 'generating_prd', [])).toBe(false);
    expect(isValidStateTransition('ai_dialogue', 'reviewing_prd', [])).toBe(false);
    expect(isValidStateTransition('reviewing_prd', 'reviewing_api', [])).toBe(false);
  });

  // 非法的回退转换（目标步骤在当前步骤之后）
  it('should not allow rollback to steps after current step', () => {
    const completedSteps: ViewState[] = ['form_editing', 'ai_dialogue', 'reviewing_prd', 'reviewing_api'];
    expect(isValidStateTransition('reviewing_prd', 'reviewing_api', completedSteps)).toBe(false);
    expect(isValidStateTransition('ai_dialogue', 'reviewing_prd', completedSteps)).toBe(false);
  });

  // 边界情况：空的已完成步骤列表
  it('should handle empty completedSteps array', () => {
    // reviewing_prd -> ai_dialogue 是合法的直接转换（回退）
    expect(isValidStateTransition('reviewing_prd', 'ai_dialogue', [])).toBe(true);
    // reviewing_api -> form_editing 不是合法的直接转换，也不是回退
    expect(isValidStateTransition('reviewing_api', 'form_editing', [])).toBe(false);
  });

  // 边界情况：相同状态转换
  it('should not allow transition to same state', () => {
    expect(isValidStateTransition('form_editing', 'form_editing', [])).toBe(false);
    expect(isValidStateTransition('ai_dialogue', 'ai_dialogue', [])).toBe(false);
  });

  // 复杂场景：多次回退
  it('should allow multiple rollbacks', () => {
    const completedSteps: ViewState[] = ['form_editing', 'ai_dialogue', 'reviewing_prd', 'reviewing_api', 'reviewing_prompts'];
    
    // 从完成状态回退到对话状态
    expect(isValidStateTransition('completed', 'ai_dialogue', completedSteps)).toBe(true);
    
    // 从对话状态回退到表单编辑状态
    expect(isValidStateTransition('ai_dialogue', 'form_editing', completedSteps)).toBe(true);
  });

  // 验证所有ViewState类型都有定义
  it('should have valid transitions defined for all ViewState types', () => {
    const viewStates: ViewState[] = [
      'form_editing',
      'ai_dialogue',
      'generating_prd',
      'reviewing_prd',
      'generating_api',
      'reviewing_api',
      'generating_prompts',
      'reviewing_prompts',
      'completed'
    ];
    
    viewStates.forEach(state => {
      // 每个状态至少应该有一个合法的转换目标
      const hasValidTransition = viewStates.some(targetState => 
        isValidStateTransition(state, targetState, viewStates)
      );
      expect(hasValidTransition).toBe(true);
    });
  });
});