import React from 'react';
import { CheckCircle, X, Loader2 } from 'lucide-react';
import { EntityTypeIcon, getEntityTitle } from '../../utils/entity';

export default function AISuggestionCard({
  suggestion,
  onAccept,
  onDismiss,
  onEdit,
  busy,
  entityStore,
}) {
  const otherEntity = suggestion.other_entity || (entityStore ? resolveEntity(suggestion.other_id, entityStore) : null);

  return (
    <div style={{
      padding: '10px 12px',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      display: 'grid',
      gap: '6px',
      fontSize: '12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {otherEntity && (
          <>
            <EntityTypeIcon type={otherEntity.type} size={12} />
            <span style={{ fontWeight: 600, color: 'var(--text)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {getEntityTitle(otherEntity)}
            </span>
          </>
        )}
        {!otherEntity && (
          <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
            {suggestion.label || 'Unknown entity'}
          </span>
        )}
        <span style={{
          fontSize: '10px',
          fontFamily: 'var(--font-mono, monospace)',
          color: suggestion.confidence >= 0.92 ? 'var(--green)' : suggestion.confidence >= 0.7 ? 'var(--yellow)' : 'var(--text-muted)',
          whiteSpace: 'nowrap',
        }}>
          {Math.round((suggestion.confidence || 0) * 100)}%
        </span>
      </div>
      {suggestion.reason && (
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '11px', lineHeight: 1.4 }}>
          {suggestion.reason}
        </p>
      )}
      <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={() => onAccept?.(suggestion)}
          disabled={busy}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 8px',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            background: 'var(--surface2)',
            color: 'var(--green)',
            fontSize: '11px',
            fontWeight: 600,
            cursor: busy ? 'default' : 'pointer',
            opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? <Loader2 size={11} className="spin" /> : <CheckCircle size={11} />}
          Accept
        </button>
        {onDismiss && (
          <button
            type="button"
            onClick={() => onDismiss(suggestion)}
            disabled={busy}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'transparent',
              color: 'var(--text-muted)',
              fontSize: '11px',
              cursor: busy ? 'default' : 'pointer',
              opacity: busy ? 0.6 : 1,
            }}
          >
            <X size={11} />
            Dismiss
          </button>
        )}
        {onEdit && (
          <button
            type="button"
            onClick={() => onEdit(suggestion)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'transparent',
              color: 'var(--accent)',
              fontSize: '11px',
              cursor: 'pointer',
            }}
          >
            Edit
          </button>
        )}
      </div>
    </div>
  );
}

function resolveEntity(id, store) {
  if (!id || !store) return null;
  for (const key of ['notes', 'tasks', 'projects', 'areas', 'people', 'resources']) {
    const entity = store[key]?.find(item => item.id === id);
    if (entity) return entity;
  }
  return null;
}
