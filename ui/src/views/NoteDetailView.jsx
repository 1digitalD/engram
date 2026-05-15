import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Edit2, Loader2, Trash2, Tag, User, FolderOpen, Map,
  Link2, CheckCircle, X, Sparkles, Diamond, Calendar,
  FileText,
} from 'lucide-react';
import useStore from '../stores/useStore';
import { linksAPI, relationshipsAPI } from '../api/engram';
import { BucketBadge, TagBadge } from '../components/ui/Badge';
import TipTapEditor, { renderStoredContent } from '../components/Editor/TipTapEditor';
import {
  EntityTypeIcon,
  getEntityRoute,
  getEntityTitle,
  resolveEntity,
} from '../utils/entity';
import LinkedContextPanel from '../components/LinkedContextPanel/LinkedContextPanel';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './NoteDetailView.module.css';

function notePreviewLine(n) {
  if (!n) return '';
  const line = (n.content || n.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim();
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

const STRUCTURED_META_KEYS = ['due', 'priority', 'status', 'linked', 'source'];

function extractStructuredMetadata(rawText) {
  const text = String(rawText || '');
  const lines = text.split('\n');
  const metadata = [];
  let idx = 0;

  while (idx < lines.length && !lines[idx].trim()) idx += 1;

  // Optional first line title (e.g., "Task: ...") before metadata block.
  // If followed by at least one known metadata row, skip it from body render.
  const startIdx = idx;
  if (idx + 1 < lines.length) {
    const next = lines[idx + 1].trim();
    const nextMatch = next.match(/^([A-Za-z][A-Za-z _-]*):\s*(.+)$/);
    if (nextMatch && STRUCTURED_META_KEYS.includes(nextMatch[1].trim().toLowerCase())) {
      idx += 1;
    }
  }

  for (; idx < lines.length; idx += 1) {
    const line = lines[idx].trim();
    if (!line) {
      idx += 1;
      break;
    }
    const match = line.match(/^([A-Za-z][A-Za-z _-]*):\s*(.+)$/);
    if (!match) break;
    const key = match[1].trim();
    const value = match[2].trim();
    if (!STRUCTURED_META_KEYS.includes(key.toLowerCase())) break;
    metadata.push({ key, value });
  }

  if (metadata.length === 0) {
    return { metadata: [], body: text };
  }

  return {
    metadata,
    body: lines.slice(idx).join('\n').trimStart(),
    // Used only to avoid duplicate title/meta blocks in the rendered article.
    _strippedFrom: startIdx,
  };
}



const ENTITY_GROUPS = [
  { key: 'notes', label: 'Notes', type: 'note' },
  { key: 'tasks', label: 'Tasks', type: 'task' },
  { key: 'projects', label: 'Projects', type: 'project' },
  { key: 'areas', label: 'Areas', type: 'area' },
  { key: 'people', label: 'People', type: 'person' },
  { key: 'resources', label: 'Resources', type: 'resource' },
];

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
    addToast,
    startAiStatusPoll,
    stopAiStatusPoll,
    loading,
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
  const [extractedData, setExtractedData] = useState(null);
  const [extractedLoading, setExtractedLoading] = useState(false);

  const note = notes.find(n => n.id === id);

  const [classifying, setClassifying] = useState(false);
  const [followUpBusy, setFollowUpBusy] = useState(false);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [projectPick, setProjectPick] = useState('');
  const [areaPick, setAreaPick] = useState('');
  const [personPick, setPersonPick] = useState('');
  const [assocBusy, setAssocBusy] = useState(false);

  const loadLinks = useCallback(async () => {
    if (!note?.id) return;
    setLinksLoading(true);
    try {
      const res = await relationshipsAPI.list(note.id);
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

  const loadExtracted = useCallback(async () => {
    if (!note?.id) return;
    setExtractedLoading(true);
    try {
      const res = await fetchJson(`/api/v2/entities/${encodeURIComponent(note.id)}/extracted`);
      setExtractedData(res.data || { derived: [], linked_existing: [], suggestions: [] });
    } catch (e) {
      setExtractedData({ derived: [], linked_existing: [], suggestions: [] });
    } finally {
      setExtractedLoading(false);
    }
  }, [note?.id, addToast]);

  useEffect(() => {
    loadLinks();
  }, [loadLinks]);

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  useEffect(() => {
    loadExtracted();
  }, [loadExtracted]);

  useEffect(() => {
    if ((note?.ai_status === 'processing' || note?.ai_status === 'pending') && note?.id) {
      startAiStatusPoll(note.id, 'note');
    }
    return () => {
      if (note?.id) stopAiStatusPoll(note.id);
    };
  }, [note?.id, note?.ai_status, startAiStatusPoll, stopAiStatusPoll]);

  useEffect(() => {
    if (note?.id && note?.ai_status === 'done') {
      loadExtracted();
      loadProposals();
      loadLinks();
    }
  }, [note?.id, note?.ai_status, loadExtracted, loadProposals, loadLinks]);

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
      <span className={styles.entityLinkContent}>
        <EntityTypeIcon type={entity?.type} size={12} />
        <span>{label}</span>
      </span>
    );

    if (!route) {
      return content;
    }

    return <Link to={route}>{content}</Link>;
  };

  const linkCandidates = useMemo(() => {
    const allEntities = [
      ...notes.map(e => ({ ...e, _type: 'note', _label: notePreviewLine(e) })),
      ...tasks.map(e => ({ ...e, _type: 'task', _label: e.title })),
      ...projects.map(e => ({ ...e, _type: 'project', _label: e.title })),
      ...areas.map(e => ({ ...e, _type: 'area', _label: e.title })),
      ...people.map(e => ({ ...e, _type: 'person', _label: e.title })),
      ...resources.map(e => ({ ...e, _type: 'resource', _label: e.title })),
    ];
    const q = linkQuery.trim().toLowerCase();
    return allEntities
      .filter(e => e.id !== note?.id)
      .filter(e => !q || e._label.toLowerCase().includes(q))
      .slice(0, 80);
  }, [notes, tasks, projects, areas, people, resources, linkQuery, note?.id]);

  const linkCandidatesGrouped = useMemo(() => {
    const groups = {};
    for (const e of linkCandidates) {
      const t = e._type;
      if (!groups[t]) groups[t] = [];
      groups[t].push(e);
    }
    return groups;
  }, [linkCandidates]);

  if (!note) {
    if (loading) {
      return (
        <div className={styles.page}>
          <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
        </div>
      );
    }
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
    try {
      const ids = noteProjectIds.filter(id => id !== projectId);
      await updateNote(note.id, { project_ids: ids });
    } catch (error) {
      addToast({ type: 'error', message: error.message || 'Could not remove project' });
    }
  };

  const handleRemoveAreaFromNote = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await updateNote(note.id, { area_id: null });
    } catch (error) {
      addToast({ type: 'error', message: error.message || 'Could not remove area' });
    }
  };

  const handleRemovePersonFromNote = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await updateNote(note.id, { person_id: null });
    } catch (error) {
      addToast({ type: 'error', message: error.message || 'Could not remove person' });
    }
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
      startAiStatusPoll(note.id, 'note');
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

  const tagNames = note.tag_names || [];
  const structuredMeta = extractStructuredMetadata(note.raw_text || '');
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

  const availableProjectCandidates = projects.filter((p) => !noteProjectIds.includes(p.id));
  const availableAreaCandidates = areas.filter((a) => a.id !== note.area_id);
  const availablePersonCandidates = people.filter((p) => p.id !== note.person_id);

  const handleAddProjectToNote = async () => {
    if (!projectPick || assocBusy) return;
    setAssocBusy(true);
    try {
      await updateNote(note.id, { project_ids: [...noteProjectIds, projectPick] });
      setProjectPick('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not add project' });
    } finally {
      setAssocBusy(false);
    }
  };

  const handleSetAreaForNote = async () => {
    if (!areaPick || assocBusy) return;
    setAssocBusy(true);
    try {
      await updateNote(note.id, { area_id: areaPick });
      setAreaPick('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not set area' });
    } finally {
      setAssocBusy(false);
    }
  };

  const handleSetPersonForNote = async () => {
    if (!personPick || assocBusy) return;
    setAssocBusy(true);
    try {
      await updateNote(note.id, { person_id: personPick });
      setPersonPick('');
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not set person' });
    } finally {
      setAssocBusy(false);
    }
  };

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

      <div className={styles.shell}>
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
            {structuredMeta.metadata.length > 0 && (
              <section className={styles.inlineMetaSection} aria-label="Note metadata">
                {structuredMeta.metadata.map((entry) => (
                  <div key={entry.key} className={styles.inlineMetaItem}>
                    <span className={styles.inlineMetaKey}>{entry.key}</span>
                    <span className={styles.inlineMetaValue}>{entry.value}</span>
                  </div>
                ))}
              </section>
            )}
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
              <div dangerouslySetInnerHTML={{ __html: renderStoredContent(structuredMeta.body || '') }} />
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
              <span className={styles.aiLabel}>AI</span>
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
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Type</span>
                <span className={styles.metaItem}>
                  <Diamond size={12} /> Note
                  {isMoc && <span className={styles.mocInline}>MOC</span>}
                </span>
              </div>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Status</span>
                <span className={styles.metaItem}>
                  <BucketBadge bucket={note.bucket || 'INBOX'} />
                </span>
              </div>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Created</span>
                <span className={styles.metaItem}>{formatDateTime(note.created_at)}</span>
              </div>
              <div className={styles.metaRow}>
                <span className={styles.metaLabel}>Modified</span>
                <span className={styles.metaItem}>{formatDateTime(note.updated_at || note.created_at)}</span>
              </div>
              {note.follow_up_at && (
                <div className={styles.metaRow}>
                  <span className={styles.metaLabel}>Follow-up</span>
                  <span style={{ color: 'var(--yellow)' }} className={styles.metaItem}>
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
                <Link2 size={14} /> Linked Context
              </h2>

              <div className={styles.assocBlock}>
                <span className={styles.metaLabel}>Primary associations</span>

                <div className={styles.assocChips}>
                  {linkedProjects.map((p) => (
                    <span key={p.id} className={styles.projectChipLinkWrap}>
                      <Link to={`/projects/${p.id}`} className={styles.entityChip}>
                        <FolderOpen size={11} />
                        {p.title}
                      </Link>
                      <button type="button" className={styles.projectChipRemove} onClick={(e) => handleRemoveProjectFromNote(p.id, e)}>
                        <X size={11} />
                      </button>
                    </span>
                  ))}
                  {area ? (
                    <span className={styles.projectChipLinkWrap}>
                      <Link to={`/areas/${area.id}`} className={styles.entityChip}><Map size={11} />{area.title}</Link>
                      <button type="button" className={styles.projectChipRemove} onClick={handleRemoveAreaFromNote}><X size={11} /></button>
                    </span>
                  ) : null}
                  {person ? (
                    <span className={styles.projectChipLinkWrap}>
                      <Link to={`/people/${person.id}`} className={styles.entityChip}><User size={11} />{person.title}</Link>
                      <button type="button" className={styles.projectChipRemove} onClick={handleRemovePersonFromNote}><X size={11} /></button>
                    </span>
                  ) : null}
                  {linkedProjects.length === 0 && !area && !person && (
                    <span className={styles.chipEmpty}>No primary associations yet</span>
                  )}
                </div>

                <div className={styles.assocAddRow}>
                  <select className={styles.linkSelect} value={projectPick} onChange={(e) => setProjectPick(e.target.value)}>
                    <option value="">Add project…</option>
                    {availableProjectCandidates.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                  </select>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleAddProjectToNote} disabled={!projectPick || assocBusy}>
                    Add
                  </button>
                </div>
                <div className={styles.assocAddRow}>
                  <select className={styles.linkSelect} value={areaPick} onChange={(e) => setAreaPick(e.target.value)}>
                    <option value="">Set area…</option>
                    {availableAreaCandidates.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
                  </select>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleSetAreaForNote} disabled={!areaPick || assocBusy}>
                    Set
                  </button>
                </div>
                <div className={styles.assocAddRow}>
                  <select className={styles.linkSelect} value={personPick} onChange={(e) => setPersonPick(e.target.value)}>
                    <option value="">Set person…</option>
                    {availablePersonCandidates.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                  </select>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleSetPersonForNote} disabled={!personPick || assocBusy}>
                    Set
                  </button>
                </div>
              </div>

              {/* AI Suggestions */}
              {proposals.length > 0 && (
                <div className={styles.proposedSection}>
                  <span className={styles.linkHeading}>
                    <Sparkles size={12} aria-hidden />
                    Suggested Links
                  </span>
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
                </div>
              )}

              {/* Linked Context Panel */}
              <LinkedContextPanel
                entityId={note.id}
                linksOut={linksOut}
                linksIn={linksIn}
                loading={linksLoading}
              />

              <div className={styles.linkAdd}>
                <input
                  type="search"
                  className={styles.linkFilter}
                  placeholder="Filter entities…"
                  value={linkQuery}
                  onChange={e => setLinkQuery(e.target.value)}
                />
                <select
                  className={styles.linkSelect}
                  value={linkPick}
                  onChange={e => setLinkPick(e.target.value)}
                >
                  <option value="">Link to entity…</option>
                  {ENTITY_GROUPS.map(group => {
                    const items = linkCandidatesGrouped[group.type];
                    if (!items?.length) return null;
                    return (
                      <optgroup key={group.type} label={group.label}>
                        {items.map(e => (
                          <option key={e.id} value={e.id}>{e._label}</option>
                        ))}
                      </optgroup>
                    );
                  })}
                  {!linkQuery && Object.keys(linkCandidatesGrouped).length === 0 && (
                    <option value="" disabled>Type to search</option>
                  )}
                  {linkQuery && Object.keys(linkCandidatesGrouped).length === 0 && (
                    <option value="" disabled>No matches</option>
                  )}
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
            </section>

            {/* Extracted from this note */}
            <section className={styles.panel}>
              <h2 className={styles.panelTitle}>
                <Sparkles size={14} /> Extracted from this note
              </h2>
              {extractedLoading ? (
                <p className={styles.panelMuted}>
                  <Loader2 size={14} className="spin" aria-hidden /> Loading…
                </p>
              ) : (
                <>
                  {/* Derived entities (created from this note) */}
                  {extractedData?.derived?.length > 0 && (
                    <div className={styles.extractedGroup}>
                      <span className={styles.linkHeading}>Created</span>
                      <ul className={styles.extractedList}>
                        {extractedData.derived.map(e => (
                          <li key={e.id} className={styles.extractedItem}>
                            {renderEntityLink(e.id, getEntityTitle(e) || e.title, e)}
                            <span className={styles.entityTypeTag}>{e.type}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Linked existing projects/areas */}
                  {extractedData?.linked_existing?.length > 0 && (
                    <div className={styles.extractedGroup}>
                      <span className={styles.linkHeading}>Linked existing</span>
                      <ul className={styles.extractedList}>
                        {extractedData.linked_existing.map(e => (
                          <li key={e.id} className={styles.extractedItem}>
                            {renderEntityLink(e.id, getEntityTitle(e) || e.title, e)}
                            <span className={styles.entityTypeTag}>{e.type}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Pending AI suggestions */}
                  {extractedData?.suggestions?.length > 0 && (
                    <div className={styles.extractedGroup}>
                      <span className={styles.linkHeading}>Suggestions</span>
                      <ul className={styles.extractedList}>
                        {extractedData.suggestions.map(s => (
                          <li key={s.id} className={styles.extractedItem}>
                            <span className={styles.suggestionOp}>{s.suggestion_type}</span>
                            <span className={styles.suggestionConf}>
                              {Math.round((s.confidence || 0) * 100)}%
                            </span>
                            {s.reason && <span className={styles.proposalReason}>{s.reason}</span>}
                            <div className={styles.suggestionActions}>
                              <button
                                type="button"
                                className="btn btn-primary btn-xs"
                                onClick={async () => {
                                  setProposalActionId(s.id);
                                  try {
                                    await suggestionsAPI.accept(s.id);
                                    loadExtracted();
                                  } catch (e) {
                                    addToast({ type: 'error', message: 'Failed to accept suggestion' });
                                  } finally {
                                    setProposalActionId(null);
                                  }
                                }}
                                disabled={proposalActionId === s.id}
                              >
                                Accept
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-xs"
                                onClick={async () => {
                                  setProposalActionId(s.id);
                                  try {
                                    await suggestionsAPI.dismiss(s.id);
                                    loadExtracted();
                                  } catch (e) {
                                    addToast({ type: 'error', message: 'Failed to dismiss suggestion' });
                                  } finally {
                                    setProposalActionId(null);
                                  }
                                }}
                                disabled={proposalActionId === s.id}
                              >
                                Dismiss
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {((!extractedData?.derived?.length) && (!extractedData?.linked_existing?.length) && (!extractedData?.suggestions?.length)) && (
                    <p className={styles.panelMuted}>Nothing extracted yet. Classify this note to extract entities.</p>
                  )}
                </>
              )}
            </section>
          </div>
        </div>

        {/* AI Sidebar */}
        <aside className={styles.sidebar}>
          {/* Tags */}
          <section className={styles.sidebarCard}>
            <h2 className={styles.sidebarTitle}>
              <Tag size={13} /> Tags
            </h2>
            {tagNames.length > 0 ? (
              <div className={styles.tagChipList}>
                {tagNames.map(tag => (
                  <span key={tag} className={styles.chip}>{tag}</span>
                ))}
              </div>
            ) : (
              <p className={styles.chipEmpty}>No tags yet.</p>
            )}
          </section>

          {/* Quick actions */}
          <section className={styles.sidebarCard}>
            <h2 className={styles.sidebarTitle}>
              <Sparkles size={13} /> Quick actions
            </h2>
            <button
              type="button"
              className={styles.actionButton}
              onClick={handleClassify}
              disabled={classifying}
            >
              {classifying ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
              Re-classify
            </button>
            <button
              type="button"
              className={styles.actionButton}
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
              className={styles.actionButton}
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
