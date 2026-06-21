import Ajv from 'ajv';
import productSchema from '@/schemas/product_schema.json';
import { debugLogger } from './debugLogger';

export interface ValidationResult {
  valid: boolean;
  errors: { path: string; message: string }[];
}

const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(productSchema);

export function validateFormData(data: Record<string, unknown>): ValidationResult {
  const valid = validate(data);
  const errors: { path: string; message: string }[] = (validate.errors || []).map((e) => ({
    path: e.instancePath || (e.params as Record<string, string>)?.missingProperty || '',
    message: e.message || '校验失败',
  }));

  debugLogger.log('info', 'validation:ajv', {
    valid,
    errorCount: errors.length,
    firstError: errors.length > 0 ? errors[0] : null,
  });

  return { valid, errors };
}
