import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Edit2, Loader2, Trash2, Tag, User, FolderOpen, Map,
  Link2, CheckCircle, Circle, X, Sparkles,
} from 'lucide-react';
import useStore from '../stores/useStore';
import { linksAPI, proposalsAPI } from '../api/engram';
import { BucketBadge, TagBadge } from '../components/ui/Badge';
import TipTapEditor, { renderStoredContent } from '../components/Editor/TipTapEditor';
import ConnectionsPanel from '../components/ConnectionsPanel/ConnectionsPanel';
import styles from './NoteDetailView.module.css';

function notePreviewLine(n) {
  if (!n) return '';
  const line = (n.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim();
  return (line || 'Untitled').slice(0, 72);
}

function noteIsMoc(n) {
  return String(n?.note_type || 'NOTE').toUpperCase() === 'MOC';
}

export default function NoteDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    notes,
    projects,
    areas,
    people,
    tasks,
    updateNote,
    deleteNote,
    createTask,
    updateTask,
    addToast,
  } = useStore();
  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState('');
  const [saving, setSaving] = useState(false);

  const [linksOut, setLinksOut] = useState([]);
  const [linksIn, setLinksIn] = useState([]);
  const [linksLoading, setLinksLoading] = useState(false);
  const [linkQuery, setLinkQuery] = useState('');
  const [linkPick, setLinkPick] = useState('');
  const [linkBusy, setLinkBusy] = useState(false);

  const [proposals, setProposals] = useState([]);
  const [proposalsLoading, setProposalsLoading] = useState(false);
  const [proposalActionId, setProposalActionId] = useState(null);

  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [classifying, setClassifying] = useState(false);

  const note = notes.find(n => n.id === id);

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
      const res = await proposalsAPI.list({ status: 'pending', note_id: note.id, limit: 100 });
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
    if (!isEditing) setDraftText(note?.raw_text || '');
  }, [note?.id, note?.raw_text, isEditing]);

  const resolveNote = (nid) => notes.find(n => n.id === nid);

  const linkedTasks = note ? tasks.filter(t => t.note_id === note.id) : [];

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

  const saveInlineEdit = async () => {
    if (!draftText.trim() || saving) return;
    setSaving(true);
    try {
      await updateNote(note.id, { raw_text: draftText });
      setIsEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleEditKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelEditing();
      return;
    }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      saveInlineEdit();
    }
  };

  const handleBodyClick = (e) => {
    if (e.target instanceof Element && e.target.closest('a')) return;
    startEditing();
  };

  const handleDelete = async () => {
    if (!confirm('Delete this note?')) return;
    await deleteNote(note.id);
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

  const handleAcceptProposal = async (proposalId) => {
    if (proposalActionId) return;
    setProposalActionId(proposalId);
    try {
      await proposalsAPI.accept(proposalId);
      addToast({ type: 'success', message: 'Link accepted' });
      await Promise.all([loadLinks(), loadProposals()]);
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
      await proposalsAPI.dismiss(proposalId);
      addToast({ type: 'success', message: 'Suggestion dismissed' });
      await loadProposals();
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
  };

  return (
    <div className={styles.page}>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/notes">Notes</Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{notePreviewLine(note)}</span>
      </nav>

      {/* Back */}
      <button type="button" className={styles.backBtn} onClick={() => navigate(-1)}>
        <ArrowLeft size={14} /> Back
      </button>

      <div className={styles.content}>
        {/* Meta bar */}
        <div className={styles.metaBar}>
          <BucketBadge bucket={note.bucket} />
          {isMoc ? (
            <span className={styles.mocBadge} data-testid="moc-badge">
              <Map size={12} aria-hidden /> MOC
            </span>
          ) : null}
          <span className={styles.date}>
            {new Date(note.created_at).toLocaleDateString('en-US', {
              weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
            })}
          </span>
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
            <button className="btn btn-ghost btn-sm" onClick={handleDelete}>
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        {isMoc ? (
          <header className={styles.mocHeader} data-testid="moc-header">
            <div className={styles.mocHeaderInner}>
              <Map size={28} className={styles.mocHeaderIcon} aria-hidden />
              <div className={styles.mocHeaderText}>
                <p className={styles.mocHeaderEyebrow}>Map of contents</p>
                <h2 className={styles.mocHeaderTitle}>{notePreviewLine(note)}</h2>
                <p className={styles.mocHeaderBlurb}>
                  Outline built from outgoing links. Add or reorder links in the panel below.
                </p>
              </div>
            </div>
          </header>
        ) : null}

        {isMoc ? (
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
                  const target = resolveNote(l.dst_id);
                  const label = notePreviewLine(target) || `Note ${String(l.dst_id).slice(0, 8)}…`;
                  return (
                    <li key={l.id}>
                      <Link to={`/notes/${l.dst_id}`}>{label}</Link>
                    </li>
                  );
                })}
              </ol>
            )}
          </nav>
        ) : null}

        {/* Linked entities */}
        {(linkedProjects.length > 0 || area || person) && (
          <div className={styles.linkedEntities}>
            {linkedProjects.map(p => (
              <span key={p.id} className={styles.projectChipLinkWrap}>
                <Link to={`/projects/${p.id}`} className={styles.entityChip}>
                  <FolderOpen size={12} /> {p.name}
                </Link>
                <button
                  type="button"
                  className={styles.projectChipRemove}
                  aria-label={`Remove ${p.name} from this note`}
                  onClick={e => handleRemoveProjectFromNote(p.id, e)}
                >
                  <X size={12} strokeWidth={2.5} />
                </button>
              </span>
            ))}
            {area && (
              <span className={styles.projectChipLinkWrap}>
                <Link to={`/areas/${area.id}`} className={styles.entityChip}>
                  <Map size={12} /> {area.name}
                </Link>
                <button
                  type="button"
                  className={styles.projectChipRemove}
                  aria-label={`Remove ${area.name} from this note`}
                  onClick={handleRemoveAreaFromNote}
                >
                  <X size={12} strokeWidth={2.5} />
                </button>
              </span>
            )}
            {person && (
              <span className={styles.projectChipLinkWrap}>
                <Link to={`/people/${person.id}`} className={styles.entityChip}>
                  <User size={12} /> {person.name}
                </Link>
                <button
                  type="button"
                  className={styles.projectChipRemove}
                  aria-label={`Remove ${person.name} from this note`}
                  onClick={handleRemovePersonFromNote}
                >
                  <X size={12} strokeWidth={2.5} />
                </button>
              </span>
            )}
          </div>
        )}

        {/* Note body */}
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
            onClick={handleBodyClick}
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
        {note.tag_names?.length > 0 && (
          <div className={styles.tags}>
            <Tag size={13} className={styles.tagIcon} />
            {note.tag_names.map(t => <TagBadge key={t} tag={t} />)}
          </div>
        )}

        {/* AI info */}
        {note.ai_meta && (
          <div className={styles.aiInfo}>
            <span className={styles.aiLabel}>AI classified as</span>
            <BucketBadge bucket={note.ai_meta.bucket?.toUpperCase()} />
            <span className={styles.aiConf}>
              {Math.round((note.ai_meta.confidence || 0) * 100)}% confidence
            </span>
            {note.ai_meta.reasoning && (
              <p className={styles.aiReason}>{note.ai_meta.reasoning}</p>
            )}
          </div>
        )}

        <div className={styles.panels}>
          <ConnectionsPanel entityId={note.id} refreshKey={linksOut.length + linksIn.length} />

          <section className={styles.panel}>
            <h2 className={styles.panelTitle}>
              <Link2 size={14} /> Links &amp; backlinks
            </h2>
            <div className={styles.proposedSection}>
              <span className={styles.linkHeading}>
                <Sparkles size={12} aria-hidden />
                Suggested links
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
                    const otherId = p.src_id === note.id ? p.dst_id : p.src_id;
                    const other = resolveNote(otherId);
                    const busy = proposalActionId === p.id;
                    return (
                      <li key={p.id} className={styles.proposalRow}>
                        <div className={styles.proposalMain}>
                          <Link to={`/notes/${otherId}`}>
                            {notePreviewLine(other) || `Note ${String(otherId).slice(0, 8)}…`}
                          </Link>
                          <span className={styles.proposalConf}>
                            {Math.round((p.confidence ?? 0) * 100)}% match
                          </span>
                          {p.reason ? (
                            <p className={styles.proposalReason}>{p.reason}</p>
                          ) : null}
                        </div>
                        <div className={styles.proposalActions}>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => handleAcceptProposal(p.id)}
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
                        const other = resolveNote(l.dst_id);
                        return (
                          <li key={l.id}>
                            <Link to={`/notes/${l.dst_id}`}>{notePreviewLine(other) || `Note ${l.dst_id.slice(0, 8)}…`}</Link>
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
                        const other = resolveNote(l.src_id);
                        return (
                          <li key={l.id}>
                            <Link to={`/notes/${l.src_id}`}>{notePreviewLine(other) || `Note ${l.src_id.slice(0, 8)}…`}</Link>
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
    </div>
  );
}
