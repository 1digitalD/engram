import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Link2, Loader2, X } from 'lucide-react';
import {
  EntityTypeIcon,
  getEntityTitle,
  getEntityRoute,
  resolveEntity,
  getRelationshipDisplayLabel,
} from '../../utils/entity';
import useStore from '../../stores/useStore';

const GROUP_ORDER = ['project', 'area', 'task', 'note', 'resource', 'person'];

function toLink(link, store, entityId) {
  const isOutgoing = link.src_id === entityId;
  const otherId = isOutgoing ? link.dst_id : link.src_id;
  const other = resolveEntity(otherId, store);
  const direction = isOutgoing ? 'outgoing' : 'incoming';
  const otherType = other?.type || '';
  const srcType = link.src_type || otherType;
  const dstType = link.dst_type || otherType;
  const label = getRelationshipDisplayLabel(srcType, dstType, link.link_type, direction);
  return {
    id: link.id,
    entity: other || { id: otherId, title: `Entity ${String(otherId).slice(0, 8)}` },
    linkType: link.link_type,
    label,
    direction,
    source: link.source || 'manual',
    confidence: link.confidence,
  };
}

function groupLinks(links) {
  const groups = {};
  for (const link of links) {
    const type = link.entity?.type || 'note';
    if (!groups[type]) groups[type] = [];
    groups[type].push(link);
  }
  const sorted = [];
  for (const type of GROUP_ORDER) {
    if (groups[type]?.length) sorted.push({ type, links: groups[type] });
  }
  return sorted;
}

export default function LinkedContextPanel({
  entityId,
  linksOut,
  linksIn,
  loading,
  onRemoveLink,
}) {
  const store = useStore();
  const entityStore = { notes: store.notes, tasks: store.tasks, projects: store.projects, areas: store.areas, people: store.people, resources: store.resources };

  const links = useMemo(() => {
    const result = [];
    for (const l of (linksOut || [])) result.push(toLink(l, entityStore, entityId));
    for (const l of (linksIn || [])) result.push(toLink(l, entityStore, entityId));
    const seen = new Set();
    return result.filter(l => {
      if (seen.has(l.entity?.id)) return false;
      seen.add(l.entity?.id);
      return true;
    });
  }, [linksOut, linksIn, entityId, entityStore]);

  const grouped = useMemo(() => groupLinks(links), [links]);

  if (loading) {
    return (
      <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Loader2 size={14} className="spin" /> Loading linked context…
      </div>
    );
  }

  if (!links.length) {
    return (
      <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '12px', fontStyle: 'italic' }}>
        No linked context yet. Links to people, projects, notes, resources will appear here.
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: '4px' }}>
      {grouped.map(({ type, links: typeLinks }) => (
        <div key={type}>
          <div style={{
            fontSize: '10px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--text-muted)',
            padding: '6px 8px 2px',
          }}>
            {type.charAt(0).toUpperCase() + type.slice(1)}s
          </div>
          {typeLinks.map(link => (
            <div
              key={link.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 8px',
                borderRadius: '6px',
                fontSize: '12px',
              }}
            >
              <Link
                to={getEntityRoute(link.entity) || '#'}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: 'var(--text)',
                  textDecoration: 'none',
                  flex: 1,
                  minWidth: 0,
                }}
              >
                <EntityTypeIcon type={link.entity?.type} size={12} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {getEntityTitle(link.entity)}
                </span>
              </Link>
              <span style={{
                fontSize: '10px',
                color: 'var(--text-muted)',
                whiteSpace: 'nowrap',
                fontFamily: 'var(--font-mono, monospace)',
              }}>
                {link.label}
              </span>
              {onRemoveLink && (
                <button
                  type="button"
                  onClick={() => onRemoveLink(link.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '2px',
                    display: 'flex',
                  }}
                  title="Remove link"
                >
                  <X size={10} />
                </button>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
