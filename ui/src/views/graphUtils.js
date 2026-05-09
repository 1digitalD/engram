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

/** Count knowledge graph links pointing to a note (incoming / backlinks). */
export function incomingKnowledgeBacklinkCount(noteId, graphLinks) {
  if (noteId == null || !Array.isArray(graphLinks)) return 0;
  const id = String(noteId);
  let n = 0;
  for (const l of graphLinks) {
    if (l && String(l.dst_id) === id) n += 1;
  }
  return n;
}

/**
 * Activity score for heat map: prefer API `backlink_count`, else derive from `graphLinks`.
 */
export function noteActivityForHeatMap(note, graphLinks) {
  if (!note) return 0;
  const api = Number(note.backlink_count);
  if (Number.isFinite(api) && api >= 0) return Math.floor(api);
  return incomingKnowledgeBacklinkCount(note.id, graphLinks);
}

const HEAT_MAP_GREY = '#9CA3AF';

function hexToRgb(hex) {
  const m = typeof hex === 'string' && /^#([0-9A-Fa-f]{6})$/.exec(hex.trim());
  if (!m) return null;
  const v = parseInt(m[1], 16);
  return { r: (v >> 16) & 255, g: (v >> 8) & 255, b: v & 255 };
}

/**
 * Fill + stroke for heat-mapped note nodes: grey at low activity → accent at high.
 */
export function heatMapNodeColors(activity, maxActivity, accentHex = '#7C6AFF') {
  const max = Math.max(1, Number(maxActivity) || 1);
  const t = Math.min(1, Math.max(0, (Number(activity) || 0) / max));
  const g = hexToRgb(HEAT_MAP_GREY);
  const a = hexToRgb(accentHex) || hexToRgb('#7C6AFF');
  if (!g || !a) return { fill: HEAT_MAP_GREY, stroke: HEAT_MAP_GREY };
  const r = Math.round(g.r + (a.r - g.r) * t);
  const gr = Math.round(g.g + (a.g - g.g) * t);
  const b = Math.round(g.b + (a.b - g.b) * t);
  const fill = `rgb(${r},${gr},${b})`;
  const stroke = `rgb(${Math.max(0, r - 40)},${Math.max(0, gr - 35)},${Math.max(0, b - 20)})`;
  return { fill, stroke };
}

/** Multiplier for base node radius (1 at zero activity, up to maxScale at max activity). */
export function heatMapRadiusScale(activity, maxActivity, minScale = 1, maxScale = 2.35) {
  const max = Math.max(1, Number(maxActivity) || 1);
  const t = Math.min(1, Math.max(0, (Number(activity) || 0) / max));
  return minScale + (maxScale - minScale) * t;
}

/** Max heat value across notes (for normalization); at least 1. */
export function maxNoteHeatActivity(notes, graphLinks) {
  if (!Array.isArray(notes) || notes.length === 0) return 1;
  let m = 0;
  for (const n of notes) {
    const a = noteActivityForHeatMap(n, graphLinks);
    if (a > m) m = a;
  }
  return Math.max(1, m);
}

/**
 * Graph node summary shape: `{ type: string, data: object }`.
 * Returns hull key + fill/stroke color (hex or hsl) for clustered layout.
 *
 * @param {{ type: string, data?: object|null }} graphNode
 * @param {'none'|'project'|'area'|'tag'} mode
 * @param {{ projectsById: Map, areasById: Map, tagsById: Map, defaultProjectHex: string, defaultAreaHex: string }} lookups
 */
/** Canonical graph entity kinds rendered in Graph.jsx */
export const GRAPH_ENTITY_TYPES = ['note', 'daily', 'resource', 'project', 'area', 'person'];

export function noteProjectIds(note) {
  if (!note) return [];
  if (Array.isArray(note.project_ids) && note.project_ids.length)
    return note.project_ids.map((id) => String(id));
  if (note.project_id != null && note.project_id !== '') return [String(note.project_id)];
  return [];
}

/**
 * @param {{ type: string }} graphNode
 * @param {Record<string, boolean>} enabledTypes — false hides that type; missing key defaults to true
 */
export function graphNodeMatchesEnabledTypes(graphNode, enabledTypes) {
  if (!graphNode?.type) return false;
  const v = enabledTypes[graphNode.type];
  return v !== false;
}

/**
 * Location filter: empty project AND empty area selection means no restriction.
 * When either set is non-empty, a node must match the project constraint (if any)
 * AND the area constraint (if any). Persons without area/project never match when a filter is active.
 *
 * @param {{ type: string, data?: object|null }} graphNode
 * @param {Iterable<string|number>} selectedProjectIds
 * @param {Iterable<string|number>} selectedAreaIds
 */
export function graphNodeMatchesLocationFilter(graphNode, selectedProjectIds, selectedAreaIds) {
  const sp = new Set([...selectedProjectIds].map(String));
  const sa = new Set([...selectedAreaIds].map(String));
  const hasP = sp.size > 0;
  const hasA = sa.size > 0;
  if (!hasP && !hasA) return true;

  const type = graphNode.type;
  const d = graphNode.data || {};

  const matchesProject = () => {
    if (!hasP) return true;
    if (type === 'project') return sp.has(String(d.id));
    if (type === 'note' || type === 'daily') return noteProjectIds(d).some((id) => sp.has(id));
    return false;
  };

  const matchesArea = () => {
    if (!hasA) return true;
    if (type === 'area') return sa.has(String(d.id));
    const aid = d.area_id;
    if (aid == null || aid === '') return false;
    return sa.has(String(aid));
  };

  return matchesProject() && matchesArea();
}

/**
 * Ids of nodes adjacent to `centerId` using undirected structural + knowledge edges.
 * `linkRows`: `{ source: string, target: string }[]` (ids, not objects).
 */
export function neighborIdsForGraphLinks(centerId, linkRows) {
  const out = new Set();
  if (!centerId || !Array.isArray(linkRows)) return out;
  for (const row of linkRows) {
    const s = typeof row.source === 'string' ? row.source : row.source?.id;
    const t = typeof row.target === 'string' ? row.target : row.target?.id;
    if (!s || !t) continue;
    if (s === centerId) out.add(t);
    else if (t === centerId) out.add(s);
  }
  return out;
}

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
