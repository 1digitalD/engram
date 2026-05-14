import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Edit2, Loader2, Trash2, Tag, User, FolderOpen, Map,
  Link2, CheckCircle, Circle, X, Sparkles, Diamond, Calendar,
  FileText,
} from 'lucide-react';
import useStore from '../stores/useStore';
import { linksAPI } from '../api/engram';
import { BucketBadge, TagBadge } from '../components/ui/Badge';
import TipTapEditor, { renderStoredContent } from '../components/Editor/TipTapEditor';
import {
  EntityTypeIcon,
  getEntityRoute,
  getEntityTitle,
  resolveEntity,
} from '../components/ConnectionsPanel/ConnectionsPanel';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './NoteDetailView.module.css';

function notePreviewLine(n) {
  if (!n) return '';
  const line = (n.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim();
  return (line || 'Untitled').slice(0, 72);
}

function noteIsMoc(n) {
  return String(n?.note_type || 'NOTE').toUpperCase() === 'MOC';
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.message || `HTTP ${res.status}`);
  }

  return res.json();
}

function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const shellStyle = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) 224px',
  gap: '24px',
  alignItems: 'start',
};

const sidebarStyle = {
  width: '224px',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const sidebarCardStyle = {
  background: 'var(--surface)',
  border: '1px solid var(--border-faint)',
  borderRadius: 'var(--radius-md)',
  padding: '14px',
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
};

const sidebarTitleStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12px',
  fontWeight: 600,
  color: 'var(--text)',
  margin: 0,
};

const actionButtonStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  width: '100%',
  padding: '9px 10px',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-faint)',
  background: 'var(--surface)',
  color: 'var(--text)',
  fontSize: '12px',
  textAlign: 'left',
  cursor: 'pointer',
};

const metaRowStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
};

const metaItemStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '12px',
  color: 'var(--text-secondary)',
};

const metaLabelStyle = {
  fontSize: '11px',
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  minWidth: '72px',
};

const chipStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '4px 8px',
  borderRadius: 'var(--radius-full)',
  background: 'var(--surface2)',
  border: '1px solid var(--border-faint)',
  color: 'var(--text-secondary)',
  fontSize: '11px',
};

export default function NoteDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    notes,
    projects,
    areas,
    people,
    tasks,
    resources,
    updateNote,
    deleteNote,
    getDeletePreview,
    createTask,
    updateTask,
    addToast,
    startAiStatusPoll,
  } = useStore();
  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState('');
  const [saving, setSaving] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);

  const [linksOut, setLinksOut] = useState([]);
  const [linksIn, setLinksIn] = useState([]);
  const [linksLoading, setLinksLoading] = useState(false);
  const [linkQuery, setLinkQuery] = useState('');
  const [linkPick, setLinkPick] = useState('');
  const [linkBusy, setLinkBusy] = useState(false);

  const [proposals, setProposals] = useState([]);
  const [proposalsLoading, setProposalsLoading] = useState(false);
  const [proposalActionId, setProposalActionId] = useState(null);
  const [linkedTasksKey, setLinkedTasksKey] = useState(0);

  const note = notes.find(n => n.id === id);

  const linkedTasks = useMemo(() => {
    return note ? tasks.filter(t => t.note_id === note.id) : [];
  }, [tasks, note, linkedTasksKey]);
  const [classifying, setClassifying] = useState(false);
  const [followUpBusy, setFollowUpBusy] = useState(false);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);

  const loadLinks = useCallback(async () => {
    if (!note?.id) return;
    setLinksLoading(true);
    try {
      const res = await linksAPI.forNote(note.id);
      setLinksOut(res.outgoing || []);
      setLinksIn(res.incoming || []);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to load links' });
      setLinksOut([]);
      setLinksIn([]);
    } finally {
      setLinksLoading(false);
    }
  }, [note?.id, addToast]);

  const loadProposals = useCallback(async () => {
    if (!note?.id) return;
    setProposalsLoading(true);
    try {
      const res = await fetchJson(`/api/v2/proposals?entity_id=${encodeURIComponent(note.id)}&limit=100`);
      setProposals(res.data || []);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to load link proposals' });
      setProposals([]);
    } finally {
      setProposalsLoading(false);
    }
  }, [note?.id, addToast]);

  useEffect(() => {
    loadLinks();
  }, [loadLinks]);

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  useEffect(() => {
    if (note?.ai_status === 'processing' && note?.id) {
      startAiStatusPoll(note.id, 'note');
    }
  }, [note?.id, note?.ai_status, startAiStatusPoll]);

  useEffect(() => {
    if (!isEditing) setDraftText(note?.raw_text || '');
  }, [note?.id, note?.raw_text, isEditing]);

  const entityStore = { notes, tasks, projects, areas, people, resources };
  const getResolvedEntity = (entityId) => resolveEntity(entityId, entityStore);
  const renderEntityLink = (entityId, fallbackLabel, fallbackEntity = null) => {
    const entity = getResolvedEntity(entityId) || fallbackEntity;
    const route = getEntityRoute(entity);
    const label = entity ? getEntityTitle(entity) : fallbackLabel;

    const content = (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
        <EntityTypeIcon type={entity?.type} size={12} />
        <span>{label}</span>
      </span>
    );

    if (!route) {
      return content;
    }

    return <Link to={route}>{content}</Link>;
  };

  const linkCandidates = notes
    .filter(n => n.id !== note?.id)
    .filter(n => notePreviewLine(n).toLowerCase().includes(linkQuery.trim().toLowerCase()))
    .slice(0, 80);

  if (!note) {
    return (
      <div className={styles.page}>
        <p className={styles.notFound}>Note not found.</p>
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>
          <ArrowLeft size={14} /> Go back
        </button>
      </div>
    );
  }

  const noteProjectIds = note.project_ids?.length
    ? note.project_ids
    : (note.project_id ? [note.project_id] : []);
  const linkedProjects = noteProjectIds
    .map(pid => projects.find(p => p.id === pid))
    .filter(Boolean);
  const area = note.area_id ? areas.find(a => a.id === note.area_id) : null;
  const person = note.person_id ? people.find(p => p.id === note.person_id) : null;

  const isMoc = noteIsMoc(note);

  const handleRemoveProjectFromNote = async (projectId, e) => {
    e.preventDefault();
    e.stopPropagation();
    const ids = noteProjectIds.filter(id => id !== projectId);
    await updateNote(note.id, { project_ids: ids });
  };

  const handleRemoveAreaFromNote = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await updateNote(note.id, { area_id: null });
  };

  const handleRemovePersonFromNote = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    await updateNote(note.id, { person_id: null });
  };

  const startEditing = () => {
    setDraftText(note.raw_text || '');
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setDraftText(note.raw_text || '');
    setIsEditing(false);
  };

  const handleDeleteClick = async () => {
    try {
      const preview = await getDeletePreview(note.id);
      setDeletePreview(preview);
      setShowDeleteModal(true);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Failed to load delete preview' });
    }
  };

  const handleDeleteConfirm = async (cascadeIds) => {
    await deleteNote(note.id, cascadeIds);
    setShowDeleteModal(false);
    setDeletePreview(null);
    navigate('/notes');
  };

  const handleClassify = async () => {
    if (classifying) return;
    setClassifying(true);
    try {
      await updateNote(note.id, { classify: true });
      addToast({ type: 'success', message: 'AI re-classified this note' });
    } catch (e) {
      addToast({ type: 'error', message: 'Classification failed' });
    } finally {
      setClassifying(false);
    }
  };

  const handleFollowUpChange = async (e) => {
    const value = e.target.value;
    setFollowUpBusy(true);
    try {
      await updateNote(note.id, { follow_up_at: value || null }, { silent: true });
    } catch (e) {
      addToast({ type: 'error', message: 'Failed to update follow-up date' });
    } finally {
      setFollowUpBusy(false);
    }
  };

  const handleFollowUpClear = async () => {
    setFollowUpBusy(true);
    try {
      await updateNote(note.id, { follow_up_at: null }, { silent: true });
    } catch (e) {
      addToast({ type: 'error', message: 'Failed to clear follow-up date' });
    } finally {
      setFollowUpBusy(false);
    }
  };

  const handleLifecycleChange = async (e) => {
    const newBucket = e.target.value;
    setLifecycleBusy(true);
    try {
      await updateNote(note.id, { bucket: newBucket }, { silent: true });
      addToast({ type: 'success', message: `Note moved to ${newBucket}` });
    } catch (e) {
      addToast({ type: 'error', message: 'Failed to update lifecycle' });
    } finally {
      setLifecycleBusy(false);
    }
  };

  const handleAddLink = async () => {
    if (!linkPick || linkBusy) return;
    setLinkBusy(true);
    try {
      await linksAPI.create({ src_id: note.id, dst_id: linkPick, link_type: 'related' });
      addToast({ type: 'success', message: 'Link added' });
      setLinkPick('');
      setLinkQuery('');
      await loadLinks();
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not add link' });
    } finally {
      setLinkBusy(false);
    }
  };

  const handleAcceptProposal = async (proposal) => {
    if (proposalActionId) return;
    setProposalActionId(proposal.id);
    try {
      await fetchJson('/api/v2/links', {
        method: 'POST',
        body: JSON.stringify({
          src_id: proposal.src_id,
          dst_id: proposal.dst_id,
          link_type: proposal.link_type || 'related',
        }),
      });
      setProposals((current) => current.filter((entry) => entry.id !== proposal.id));
      addToast({ type: 'success', message: 'Link accepted' });
      await loadLinks();
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not accept proposal' });
    } finally {
      setProposalActionId(null);
    }
  };

  const handleDismissProposal = async (proposalId) => {
    if (proposalActionId) return;
    setProposalActionId(proposalId);
    try {
      setProposals((current) => current.filter((entry) => entry.id !== proposalId));
      addToast({ type: 'success', message: 'Suggestion dismissed' });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not dismiss proposal' });
    } finally {
      setProposalActionId(null);
    }
  };

  const toggleLinkedTask = async (t) => {
    const next = t.status === 'DONE' ? 'PENDING' : 'DONE';
    await updateTask(t.id, { status: next });
  };

  const handleAddNoteTask = async (e) => {
    e.preventDefault();
    const title = newTaskTitle.trim();
    if (!title) return;
    await createTask({ title, note_id: note.id });
    setNewTaskTitle('');
    setLinkedTasksKey(k => k + 1);
  };

  const tagNames = note.tag_names || [];
  const suggestedLinks = [
    ...linkedProjects.slice(0, 2).map(p => ({ id: p.id, label: p.title, route: `/projects/${p.id}` })),
    ...linksOut.slice(0, 2).map(l => {
      const target = getResolvedEntity(l.dst_id);
      return {
        id: l.dst_id,
        label: target ? getEntityTitle(target) : `Entity ${String(l.dst_id).slice(0, 8)}`,
        route: target ? getEntityRoute(target) : null,
      };
    }).filter(Boolean),
  ];

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/notes">Notes</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{notePreviewLine(note)}</span>
      </nav>

      <button type="button" className={styles.backBtn} onClick={() => navigate(-1)}>
        <ArrowLeft size={14} /> Back
      </button>

      <div style={shellStyle}>
        {/* Main content */}
        <div className={styles.mainContent}>
          {/* Header */}
          <header className={styles.header}>
            <div className={styles.headerTop}>
              <div className={styles.headerIcon}>
                <Diamond size={22} strokeWidth={1.5} />
              </div>
              <h1 className={styles.title}>{notePreviewLine(note)}</h1>
            </div>
            <div className={styles.metaRow}>
              <span className={styles.entityTypeLabel}>Note</span>
              {isMoc && (
                <span className={styles.mocBadge} data-testid="moc-badge">
                  <Map size={12} aria-hidden /> MOC
                </span>
              )}
              <div className={styles.metaActions}>
                {!isEditing && (
                  <button className="btn btn-ghost btn-sm" onClick={startEditing}>
                    <Edit2 size={13} /> Edit
                  </button>
                )}
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={handleClassify}
                  disabled={classifying}
                  title="Re-run AI classification on this note"
                >
                  {classifying ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
                  Classify
                </button>
                <button className="btn btn-ghost btn-sm" onClick={handleDeleteClick}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          </header>

          {/* MOC TOC */}
          {isMoc && (
            <nav className={styles.mocToc} data-testid="moc-toc" aria-label="Table of contents">
              <h3 className={styles.mocTocHeading}>Contents</h3>
              {linksLoading ? (
                <p className={styles.panelMuted}>
                  <Loader2 size={14} className="spin" aria-hidden /> Building outline…
                </p>
              ) : linksOut.length === 0 ? (
                <p className={styles.panelMuted}>
                  No outgoing links yet. Link notes here to populate this table of contents.
                </p>
              ) : (
                <ol className={styles.mocTocList}>
                  {linksOut.map((l) => {
                    const target = getResolvedEntity(l.dst_id);
                    const label = target ? getEntityTitle(target) : `Entity ${String(l.dst_id).slice(0, 8)}…`;
                    return (
                      <li key={l.id}>
                        {renderEntityLink(l.dst_id, label)}
                      </li>
                    );
                  })}
                </ol>
              )}
            </nav>
          )}

          {/* Note body / Editor */}
          {isEditing ? (
            <div className={styles.inlineEditor}>
              <TipTapEditor
                initialContent={note.raw_text || ''}
                noteId={note.id}
                placeholder="Edit note..."
                onSave={async ({ html }) => {
                  if (!html.trim() || saving) return;
                  setSaving(true);
                  try {
                    await updateNote(note.id, { content: html });
                    setIsEditing(false);
                  } finally {
                    setSaving(false);
                  }
                }}
              />
              <div className={styles.inlineActions}>
                <span className={styles.shortcutHint}>Use the editor toolbar to save</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={cancelEditing} disabled={saving}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <article
              className={styles.body}
              onClick={(e) => {
                if (e.target instanceof Element && e.target.closest('a')) return;
                startEditing();
              }}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  startEditing();
                }
              }}
              role="button"
              tabIndex={0}
              aria-label="Edit note text"
            >
              <span className={styles.editHint}>Click to edit</span>
              <div dangerouslySetInnerHTML={{ __html: renderStoredContent(note.raw_text || '') }} />
            </article>
          )}

          {/* Tags */}
          {tagNames.length > 0 && (
            <div className={styles.tags}>
              <Tag size={13} className={styles.tagIcon} />
              {tagNames.map(t => <TagBadge key={t} tag={t} />)}
            </div>
          )}

          {/* AI info */}
          {note._ai_meta && (
            <div className={styles.aiInfo}>
              <span className={styles.aiLabel}>AI classified as</span>
              <BucketBadge bucket={note._ai_meta.bucket?.toUpperCase()} />
              <span className={styles.aiConf}>
                {Math.round((note._ai_meta.confidence || 0) * 100)}% confidence
              </span>
              {note._ai_meta.reasoning && (
                <p className={styles.aiReason}>{note._ai_meta.reasoning}</p>
              )}
            </div>
          )}

          {/* Metadata section */}
          <section className={styles.metadataSection}>
            <h2 className={styles.sectionTitle}>
              <FileText size={14} /> Metadata
            </h2>
            <div className={styles.metadataGrid}>
              <div style={metaRowStyle}>
                <span style={metaLabelStyle}>Type</span>
                <span style={metaItemStyle}>
                  <Diamond size={12} /> Note
                  {isMoc && <span className={styles.mocInline}>MOC</span>}
                </span>
              </div>
              <div style={metaRowStyle}>
                <span style={metaLabelStyle}>Status</span>
                <span style={metaItemStyle}>
                  <BucketBadge bucket={note.bucket || 'INBOX'} />
                </span>
              </div>
              <div style={metaRowStyle}>
                <span style={metaLabelStyle}>Created</span>
                <span style={metaItemStyle}>{formatDateTime(note.created_at)}</span>
              </div>
              <div style={metaRowStyle}>
                <span style={metaLabelStyle}>Modified</span>
                <span style={metaItemStyle}>{formatDateTime(note.updated_at || note.created_at)}</span>
              </div>
              {note.follow_up_at && (
                <div style={metaRowStyle}>
                  <span style={metaLabelStyle}>Follow-up</span>
                  <span style={{ ...metaItemStyle, color: 'var(--yellow)' }}>
                    <Calendar size={12} /> {formatDate(note.follow_up_at)}
                  </span>
                </div>
              )}
            </div>
          </section>

          {/* Panels */}
          <div className={styles.panels}>
            <section className={styles.panel}>
              <h2 className={styles.panelTitle}>
                <Link2 size={14} /> Links &amp; backlinks
              </h2>
              <div className={styles.proposedSection}>
                <span className={styles.linkHeading}>
                  <Sparkles size={12} aria-hidden />
                  Suggested Links
                </span>
                {proposalsLoading ? (
                  <p className={styles.panelMuted}>
                    <Loader2 size={14} className="spin" /> Loading suggestions…
                  </p>
                ) : proposals.length === 0 ? (
                  <p className={styles.panelMuted}>No pending suggestions for this note.</p>
                ) : (
                  <ul className={styles.proposalList}>
                    {proposals.map((p) => {
                      const otherId = p.other_entity?.id || (p.src_id === note.id ? p.dst_id : p.src_id);
                      const other = p.other_entity || getResolvedEntity(otherId);
                      const busy = proposalActionId === p.id;
                      return (
                        <li key={p.id} className={styles.proposalRow}>
                          <div className={styles.proposalMain}>
                            {renderEntityLink(
                              otherId,
                              other ? getEntityTitle(other) : `Entity ${String(otherId).slice(0, 8)}…`,
                              other,
                            )}
                            <span className={styles.proposalConf}>
                              {Math.round((p.confidence ?? 0) * 100)}% confidence
                            </span>
                            {p.reason ? (
                              <p className={styles.proposalReason}>{p.reason}</p>
                            ) : null}
                          </div>
                          <div className={styles.proposalActions}>
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              onClick={() => handleAcceptProposal(p)}
                              disabled={busy}
                              title="Accept and create link"
                            >
                              {busy ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
                              Accept
                            </button>
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => handleDismissProposal(p.id)}
                              disabled={busy}
                              title="Dismiss suggestion"
                            >
                              Dismiss
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              {linksLoading ? (
                <p className={styles.panelMuted}>
                  <Loader2 size={14} className="spin" /> Loading confirmed links…
                </p>
              ) : (
                <>
                  <div className={styles.linkSection}>
                    <span className={styles.linkHeading}>From this note</span>
                    {linksOut.length === 0 ? (
                      <p className={styles.panelMuted}>No outgoing links.</p>
                    ) : (
                      <ul className={styles.linkList}>
                        {linksOut.map(l => {
                          const other = getResolvedEntity(l.dst_id);
                          return (
                            <li key={l.id}>
                              {renderEntityLink(l.dst_id, other ? getEntityTitle(other) : `Entity ${l.dst_id.slice(0, 8)}…`)}
                              <span className={styles.linkMeta}>{l.link_type}</span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                  <div className={styles.linkSection}>
                    <span className={styles.linkHeading}>Backlinks</span>
                    {linksIn.length === 0 ? (
                      <p className={styles.panelMuted}>No notes link here yet.</p>
                    ) : (
                      <ul className={styles.linkList}>
                        {linksIn.map(l => {
                          const other = getResolvedEntity(l.src_id);
                          return (
                            <li key={l.id}>
                              {renderEntityLink(l.src_id, other ? getEntityTitle(other) : `Entity ${l.src_id.slice(0, 8)}…`)}
                              <span className={styles.linkMeta}>{l.link_type}</span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                  <div className={styles.linkAdd}>
                    <input
                      type="search"
                      className={styles.linkFilter}
                      placeholder="Filter notes…"
                      value={linkQuery}
                      onChange={e => setLinkQuery(e.target.value)}
                    />
                    <select
                      className={styles.linkSelect}
                      value={linkPick}
                      onChange={e => setLinkPick(e.target.value)}
                    >
                      <option value="">Link to note…</option>
                      {linkCandidates.map(n => (
                        <option key={n.id} value={n.id}>{notePreviewLine(n)}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={handleAddLink}
                      disabled={!linkPick || linkBusy}
                    >
                      {linkBusy ? <Loader2 size={13} className="spin" /> : 'Add link'}
                    </button>
                  </div>
                </>
              )}
            </section>

            <section className={styles.panel}>
              <h2 className={styles.panelTitle}>Tasks on this note</h2>
              {linkedTasks.length === 0 ? (
                <p className={styles.panelMuted}>No tasks linked yet.</p>
              ) : (
                <ul className={styles.taskRows}>
                  {linkedTasks.map(t => (
                    <li key={t.id} className={styles.taskRow}>
                      <button
                        type="button"
                        className={styles.taskCheck}
                        onClick={() => toggleLinkedTask(t)}
                        aria-label={t.status === 'DONE' ? 'Mark pending' : 'Mark done'}
                      >
                        {t.status === 'DONE' ? <CheckCircle size={16} /> : <Circle size={16} />}
                      </button>
                      <span className={t.status === 'DONE' ? styles.taskTitleDone : styles.taskTitle}>{t.title}</span>
                    </li>
                  ))}
                </ul>
              )}
              <form className={styles.taskAdd} onSubmit={handleAddNoteTask}>
                <input
                  className={styles.taskInput}
                  placeholder="New task…"
                  value={newTaskTitle}
                  onChange={e => setNewTaskTitle(e.target.value)}
                />
                <button type="submit" className="btn btn-primary btn-sm" disabled={!newTaskTitle.trim()}>
                  Add
                </button>
              </form>
            </section>
          </div>
        </div>

        {/* AI Sidebar */}
        <aside style={sidebarStyle}>
          {/* Tags */}
          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <Tag size={13} /> Tags
            </h2>
            {tagNames.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {tagNames.map(tag => (
                  <span key={tag} style={chipStyle}>{tag}</span>
                ))}
              </div>
            ) : (
              <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)' }}>No tags yet.</p>
            )}
          </section>

          {/* Quick actions */}
          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <Sparkles size={13} /> Quick actions
            </h2>
            <button
              type="button"
              style={actionButtonStyle}
              onClick={handleClassify}
              disabled={classifying}
            >
              {classifying ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
              Re-classify
            </button>
            <button
              type="button"
              style={actionButtonStyle}
              onClick={() => {
                if (linkedProjects.length > 0) {
                  navigate(`/projects/${linkedProjects[0].id}`);
                } else if (area) {
                  navigate(`/areas/${area.id}`);
                } else {
                  navigate('/notes');
                }
              }}
            >
              <FolderOpen size={13} /> Open related project
            </button>
            <button
              type="button"
              style={actionButtonStyle}
              onClick={() => navigate('/notes')}
            >
              <FileText size={13} /> All notes
            </button>
          </section>
        </aside>
      </div>

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); }}
        onConfirm={handleDeleteConfirm}
        entityTitle={notePreviewLine(note)}
        entityType="note"
        preview={deletePreview}
      />
    </div>
  );
}
