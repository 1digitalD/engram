const GLYPHS = {
  note: '📝',
  task: '☐',
  project: '▣',
  area: '◫',
  person: '👤',
  resource: '🔗',
  decision: '⚖',
  ai: '✦',
};

export function typeGlyph(type) {
  return GLYPHS[type] || '·';
}

export default function XGlyph({ type, className, label }) {
  const glyph = typeGlyph(type);
  if (label) {
    return (
      <span className={className} aria-hidden="true" title={label}>
        {glyph}
      </span>
    );
  }
  return (
    <span className={className} aria-hidden="true">
      {glyph}
    </span>
  );
}
