/**
 * 文档复杂度评估
 * 根据文档内容计算复杂度等级和分数
 */
export function assessComplexity(content: string): { level: string; score: number } {
  if (!content) return { level: "无", score: 0 };

  const lines = content.split('\n');
  const paragraphs = lines.filter(line => line.trim().length > 0);
  const headings = lines.filter(line => /^#{1,6}\s/.test(line));
  const avgParagraphLength = paragraphs.length > 0 ? content.length / paragraphs.length : 0;

  // 计算复杂度分数（0-100）
  let score = 0;

  // 段落数量（权重：30%）
  score += Math.min(paragraphs.length / 10, 1) * 30;

  // 标题数量（权重：20%）
  score += Math.min(headings.length / 5, 1) * 20;

  // 平均段落长度（权重：25%）
  score += Math.min(avgParagraphLength / 200, 1) * 25;

  // 总字数（权重：25%）
  score += Math.min(content.length / 1000, 1) * 25;

  // 确定复杂度等级
  let level: string;
  if (score < 30) level = "简单";
  else if (score < 60) level = "中等";
  else if (score < 80) level = "复杂";
  else level = "非常复杂";

  return { level, score: Math.round(score) };
}
