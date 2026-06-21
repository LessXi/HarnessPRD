import { describe, it, expect } from 'vitest';
import { validateFormData } from '../validation';

const VALID_DATA: Record<string, unknown> = {
  product_name: '测试产品',
  one_liner: '一句话概括',
  problem_statement: '解决痛点',
  target_users: '目标用户群',
  mvp_features: ['功能A', '功能B', '功能C'],
  platform_type: 'web',
  needs_auth: 'yes',
  needs_database: 'yes',
  page_count: '1-3',
};

describe('validateFormData', () => {
  it('should pass for valid complete data', () => {
    const result = validateFormData(VALID_DATA);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('should fail when required field is missing', () => {
    const { product_name, ...rest } = VALID_DATA;
    const result = validateFormData(rest);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.path.includes('product_name') || e.message.includes('required'))).toBe(true);
  });

  it('should fail when mvp_features has fewer than 3 items', () => {
    const data = { ...VALID_DATA, mvp_features: ['仅一项'] };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('minItems') || e.path.includes('mvp_features'))).toBe(true);
  });

  it('should fail when mvp_features is empty array', () => {
    const data = { ...VALID_DATA, mvp_features: [] };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
  });

  it('should fail when platform_type is invalid enum', () => {
    const data = { ...VALID_DATA, platform_type: 'quantum_computer' };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('allowed values'))).toBe(true);
  });

  it('should fail when needs_auth is invalid enum', () => {
    const data = { ...VALID_DATA, needs_auth: 'maybe' };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
  });

  it('should pass with all optional fields set', () => {
    const data = {
      ...VALID_DATA,
      visual_style: 'creative',
      competitors: '竞品A',
      tech_stack_preference: 'React',
      feature_priority: 'user_defined',
      doc_depth: 'detailed',
      ai_temperature: 'creative',
      timeline_expectation: '1-2_months',
      additional_context: '补充说明',
    };
    const result = validateFormData(data);
    expect(result.valid).toBe(true);
  });

  it('should fail when product_name is empty string', () => {
    const data = { ...VALID_DATA, product_name: '' };
    const result = validateFormData(data);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.message.includes('fewer than'))).toBe(true);
  });

  it('should return errors with path and message', () => {
    const result = validateFormData({ product_name: '' });
    expect(result.valid).toBe(false);
    for (const err of result.errors) {
      expect(err).toHaveProperty('path');
      expect(err).toHaveProperty('message');
      expect(typeof err.path).toBe('string');
      expect(typeof err.message).toBe('string');
    }
  });

  it('should have 9 required fields', () => {
    const result = validateFormData({});
    expect(result.valid).toBe(false);
    const requiredErrors = result.errors.filter((e) => e.message.includes('required'));
    expect(requiredErrors.length).toBeGreaterThanOrEqual(9);
  });
});
