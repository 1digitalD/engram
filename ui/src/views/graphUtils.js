/** Pure helpers for Graph visualization — testable without D3. */

export const DAILY_HEADING_PREFIX = '# Daily — ';

export function isDailyNote(note) {
  if (!note?.raw_text) return false;
  const b = typeof note.bucket === 'string' ? note.bucket.toUpperCase() : note.bucket;
  return b === 'INBOX' && note.raw_text.startsWith(DAILY_HEADING_PREFIX);
}

/** Knowledge / note–note link line colors by link_type */
export const KNOWLEDGE_LINK_COLORS = {
  related: '#9333EA',
  child_of: '#2563EB',
  depends_on: '#EA580C',
  mentions: '#6B7280',
  see_also: '#9CA3AF',
};

export const STRUCTURAL_LINK_COLOR = '#3F3F46';

export function knowledgeLinkStrokeColor(linkType) {
  if (!linkType) return KNOWLEDGE_LINK_COLORS.mentions;
  return KNOWLEDGE_LINK_COLORS[linkType] || KNOWLEDGE_LINK_COLORS.mentions;
}

/**
 * Stroke width (px) for knowledge links; scales with semantic weight.
 * Embedding similarities are typically 0–1; manual links often use 1.0.
 */
export function strokeWidthForKnowledgeWeight(weight) {
  const w = typeof weight === 'number' && Number.isFinite(weight) ? weight : 1;
  const clamped = Math.min(3, Math.max(0.15, w));
  return 0.55 + 3.2 * (clamped / 3);
}
