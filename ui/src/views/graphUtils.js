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

const HEX_COLOR = /^#([0-9A-Fa-f]{6})$/;

export function coerceHexColor(value, fallback) {
  return typeof value === 'string' && HEX_COLOR.test(value.trim()) ? value.trim() : fallback;
}

/** HSL-ish hash fallback when entity has no color */
export function colorFromKey(key, fallbackHue = 252) {
  if (!key) return `hsl(${fallbackHue} 52% 58%)`;
  let h = 0;
  for (let i = 0; i < key.length; i += 1) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsl(${hue} 42% 52%)`;
}

/** Monotone-chain convex hull; returns vertices in CCW order (open ring, no duplicate first point). */
export function convexHullMonotone(xy) {
  const pts = xy.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (pts.length <= 1) return pts.slice();
  const sorted = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0)
      lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = sorted.length - 1; i >= 0; i -= 1) {
    const p = sorted[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0)
      upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

export function radialExpandPolygon(ring, padding) {
  const pad = typeof padding === 'number' && Number.isFinite(padding) ? Math.max(0, padding) : 0;
  if (ring.length === 0) return [];
  if (pad === 0) return ring.map(([x, y]) => [x, y]);
  let cx = 0;
  let cy = 0;
  for (const [x, y] of ring) {
    cx += x;
    cy += y;
  }
  cx /= ring.length;
  cy /= ring.length;
  return ring.map(([x, y]) => {
    const dx = x - cx;
    const dy = y - cy;
    const len = Math.hypot(dx, dy) || 1;
    const f = (len + pad) / len;
    return [cx + dx * f, cy + dy * f];
  });
}

/** SVG path for a softly padded hull around XY positions (canvas coordinates). */
export function hullPathFromXY(points, padding = 38) {
  const valid = points.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
  if (valid.length === 0) return '';
  if (valid.length === 1) {
    const [x, y] = valid[0];
    const s = padding * 0.85;
    return `M ${x - s} ${y - s} L ${x + s} ${y - s} L ${x + s} ${y + s} L ${x - s} ${y + s} Z`;
  }
  if (valid.length === 2) {
    const [ax, ay] = valid[0];
    const [bx, by] = valid[1];
    const dx = bx - ax;
    const dy = by - ay;
    const len = Math.hypot(dx, dy) || 1;
    const ux = (-dy / len) * (padding * 0.65);
    const uy = (dx / len) * (padding * 0.65);
    return `M ${ax + ux} ${ay + uy} L ${bx + ux} ${by + uy} L ${bx - ux} ${by - uy} L ${ax - ux} ${ay - uy} Z`;
  }
  let ring = convexHullMonotone(valid);
  if (ring.length < 3) return '';
  ring = radialExpandPolygon(ring, padding * 0.55);
  if (ring.length < 3) return '';
  const [fx, fy] = ring[0];
  return `M ${fx} ${fy} ${ring.slice(1).map(([x, y]) => `L ${x} ${y}`).join(' ')} Z`;
}

/** Toggle values for Graph cluster hull + weak force grouping */
export const GRAPH_CLUSTER_MODES = ['none', 'project', 'area', 'tag'];

/**
 * Graph node summary shape: `{ type: string, data: object }`.
 * Returns hull key + fill/stroke color (hex or hsl) for clustered layout.
 *
 * @param {{ type: string, data?: object|null }} graphNode
 * @param {'none'|'project'|'area'|'tag'} mode
 * @param {{ projectsById: Map, areasById: Map, tagsById: Map, defaultProjectHex: string, defaultAreaHex: string }} lookups
 */
export function clusterAppearanceForGraphNode(graphNode, mode, lookups) {
  if (!graphNode || mode === 'none') return { key: null, color: null };

  const d = graphNode.data || {};
  const { projectsById, areasById, tagsById, defaultProjectHex, defaultAreaHex } = lookups;

  if (mode === 'project') {
    if (graphNode.type === 'project') {
      const id = d.id;
      if (!id) return { key: null, color: null };
      const color = coerceHexColor(d.color, colorFromKey(`project:${id}`));
      return { key: `project:${id}`, color };
    }
    if (graphNode.type === 'note' || graphNode.type === 'daily') {
      const pid = d.project_id || (Array.isArray(d.project_ids) && d.project_ids.length ? d.project_ids[0] : null);
      if (!pid) return { key: null, color: null };
      const p = projectsById.get(pid);
      const color = coerceHexColor(p?.color, defaultProjectHex);
      return { key: `project:${pid}`, color };
    }
    return { key: null, color: null };
  }

  if (mode === 'area') {
    if (graphNode.type === 'area') {
      const id = d.id;
      if (!id) return { key: null, color: null };
      const color = coerceHexColor(d.color, colorFromKey(`area:${id}`));
      return { key: `area:${id}`, color };
    }
    let areaId = null;
    if (graphNode.type === 'note' || graphNode.type === 'daily') areaId = d.area_id;
    else if (graphNode.type === 'project' || graphNode.type === 'resource') areaId = d.area_id;
    if (!areaId) return { key: null, color: null };
    const a = areasById.get(areaId);
    const color = coerceHexColor(a?.color, defaultAreaHex);
    return { key: `area:${areaId}`, color };
  }

  if (mode === 'tag') {
    let ids = [];
    if (Array.isArray(d.tag_ids) && d.tag_ids.length) ids = [...d.tag_ids];
    else if (Array.isArray(d.tags) && d.tags.length)
      ids = d.tags.map((t) => t.id).filter(Boolean);
    ids.sort((a, b) => String(a).localeCompare(String(b)));
    const tid = ids[0];
    if (!tid) return { key: null, color: null };
    const tag = tagsById.get(tid);
    const color = coerceHexColor(tag?.color, colorFromKey(`tag:${tid}`));
    return { key: `tag:${tid}`, color };
  }

  return { key: null, color: null };
}
