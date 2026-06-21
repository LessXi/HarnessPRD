import type { ValidationResult } from '@/utils/validation';

interface Props {
  formData: Record<string, any>;
  errors: ValidationResult['errors'];
  onClose: () => void;
}

/** TEMP stub — full impl in Task 12 */
export default function JsonPreviewModal({ formData, errors, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">JSON 预览</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <pre className="text-xs bg-gray-50 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap break-all">
          {JSON.stringify({ formData, errors }, null, 2)}
        </pre>
      </div>
    </div>
  );
}
