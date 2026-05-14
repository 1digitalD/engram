import React from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, Sparkles, AlertCircle, Undo2, ExternalLink } from 'lucide-react';
import { EntityTypeIcon, getEntityTitle, getEntityRoute } from '../../utils/entity';

export default function PostCaptureSummary({
  open,
  onClose,
  sourceNote,
  appliedChanges,
  suggestions,
  onUndo,
  onReview,
}) {
  if (!open) return null;

  const changes = appliedChanges || [];
  const suggested = suggestions || [];

  return (
    <div style={{
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      width: '380px',
      maxHeight: '70vh',
      overflowY: 'auto',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      boxShadow: '0 12px 40px rgba(0,0,0,0.35)',
      zIndex: 1000,
      display: 'grid',
      gap: '8px',
      padding: '16px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600 }}>
          <CheckCircle size={16} style={{ color: 'var(--green)' }} />
          Captured successfully
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px', fontSize: '16px', lineHeight: 1 }}
        >
          &times;
        </button>
      </div>

      {sourceNote && (
        <Link
          to={getEntityRoute(sourceNote) || '#'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            color: 'var(--accent)',
            textDecoration: 'none',
            fontSize: '12px',
            padding: '6px 8px',
            background: 'var(--surface2)',
            borderRadius: '6px',
          }}
        >
          <ExternalLink size={12} />
          View source note
        </Link>
      )}

      {/* Applied changes */}
      {changes.length > 0 && (
        <div>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
            Applied
          </div>
          <div style={{ display: 'grid', gap: '4px' }}>
            {changes.map((change, i) => (
              <ChangeRow key={i} change={change} />
            ))}
          </div>
        </div>
      )}

      {/* Suggestions */}
      {suggested.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: 600, color: 'var(--yellow)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px' }}>
            <Sparkles size={12} />
            Needs review
          </div>
          <div style={{ display: 'grid', gap: '4px' }}>
            {suggested.map((s, i) => (
              <ChangeRow key={i} change={s} isSuggestion />
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
        {onUndo && (
          <button
            type="button"
            onClick={onUndo}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'var(--surface2)',
              color: 'var(--text)',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <Undo2 size={12} />
            Undo
          </button>
        )}
        {onReview && suggested.length > 0 && (
          <button
            type="button"
            onClick={onReview}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border)',
              background: 'var(--accent-dim)',
              color: 'var(--accent)',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <AlertCircle size={12} />
            Review
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '6px 12px',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            background: 'transparent',
            color: 'var(--text-muted)',
            fontSize: '11px',
            cursor: 'pointer',
            marginLeft: 'auto',
          }}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

function ChangeRow({ change, isSuggestion }) {
  const label = change.label || change.operation || change.action || '';
  const entityName = change.title || change.name || '';
  const iconType = change.type || '';

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '4px 6px',
      borderRadius: '4px',
      fontSize: '11px',
      color: isSuggestion ? 'var(--yellow)' : 'var(--text)',
    }}>
      <EntityTypeIcon type={iconType} size={11} />
      <span style={{ fontWeight: 500, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {label}: {entityName}
      </span>
      {change.confidence && (
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono, monospace)', whiteSpace: 'nowrap' }}>
          {Math.round(change.confidence * 100)}%
        </span>
      )}
    </div>
  );
}
