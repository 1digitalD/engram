import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, CheckSquare, FileText, FolderOpen, Sparkles, Tag, UserPlus, Plus, X, Loader2, CheckCircle } from 'lucide-react';
import useStore from '../stores/useStore';
import ConnectionsPanel from '../components/ConnectionsPanel/ConnectionsPanel';
import LinkToEntity from '../components/LinkToEntity/LinkToEntity';
import NoteEditor from '../components/notes/NoteEditor';
import { getEntityTitle } from '../components/ConnectionsPanel/ConnectionsPanel';
import projectStyles from './ProjectFocus.module.css';

function getInitials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
  if (parts.length === 0) return '?';
  return parts.map((part) => part.charAt(0).toUpperCase()).join('');
}

function firstLine(text) {
  return (text || '').split('\n')[0].trim();
}

function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString();
}

const shellStyle = {
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1fr) 224px',
  gap: '24px',
  alignItems: 'start',
};

const mainPanelStyle = {
  minWidth: 0,
};

const headerStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '16px',
  paddingBottom: '18px',
  marginBottom: '20px',
  borderBottom: '1px solid var(--border)',
};

const personMetaStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  minWidth: 0,
};

const avatarStyle = {
  width: '32px',
  height: '32px',
  borderRadius: '999px',
  background: 'var(--accent-dim)',
  color: 'var(--accent)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.04em',
  flexShrink: 0,
};

const headerCopyStyle = {
  minWidth: 0,
};

const nameStyle = {
  fontSize: '22px',
  lineHeight: 1.1,
  margin: 0,
};

const roleStyle = {
  margin: '4px 0 0',
  color: 'var(--text-secondary)',
  fontSize: '12.5px',
};

const statStyle = {
  fontSize: '11px',
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
};

const tabBodyStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const itemListStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
};

const itemRowStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '12px',
  padding: '12px 14px',
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
};

const itemCopyStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '4px',
  minWidth: 0,
};

const itemTitleStyle = {
  color: 'var(--text-primary)',
  textDecoration: 'none',
  fontSize: '13px',
  fontWeight: 600,
};

const itemMetaStyle = {
  color: 'var(--text-muted)',
  fontSize: '11px',
};

const badgeStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '5px 9px',
  borderRadius: '999px',
  border: '1px solid var(--border)',
  background: 'var(--bg-elevated)',
  color: 'var(--text-secondary)',
  fontSize: '11px',
  whiteSpace: 'nowrap',
};

const sidebarStyle = {
  width: '224px',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

const sidebarCardStyle = {
  background: 'var(--bg-surface)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
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
  color: 'var(--text-primary)',
  margin: 0,
};

const chipsStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '8px',
};

const chipStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '4px 8px',
  borderRadius: '999px',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  color: 'var(--text-secondary)',
  fontSize: '11px',
};

const sidebarLinkStyle = {
  color: 'var(--text-secondary)',
  textDecoration: 'none',
  fontSize: '12px',
  lineHeight: 1.4,
};

const actionButtonStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  width: '100%',
  padding: '9px 10px',
  borderRadius: '10px',
  border: '1px solid var(--border)',
  background: 'var(--bg-elevated)',
  color: 'var(--text-primary)',
  fontSize: '12px',
  textAlign: 'left',
  cursor: 'pointer',
};

export default function PersonFocus() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { people, notes, tasks, projects, setActivePerson, createNote, updateNote, addToast, loading } = useStore();
  const [tab, setTab] = useState('notes');

  // Add-note modal state
  const [showAddNoteModal, setShowAddNoteModal] = useState(false);
  const [noteSearchQuery, setNoteSearchQuery] = useState('');
  const [notePick, setNotePick] = useState('');
  const [noteLinkBusy, setNoteLinkBusy] = useState(false);

  // Connections tab refresh
  const [connRefreshKey, setConnRefreshKey] = useState(0);

  // Inline new-note creation
  const [showNewNoteEditor, setShowNewNoteEditor] = useState(false);

  const person = people.find((entry) => entry.id === id);

  const personIdRef = useRef(null);
  useEffect(() => {
    personIdRef.current = person?.id || null;
    setActivePerson(person || null);
    return () => {
      if (personIdRef.current === person?.id) {
        setActivePerson(null);
      }
    };
  }, [person, setActivePerson]);

  const personNotes = useMemo(
    () => notes.filter((note) => note.person_id === id),
    [id, notes],
  );

  const personNoteIds = useMemo(
    () => new Set(personNotes.map((note) => note.id)),
    [personNotes],
  );

  const linkedProjectIds = useMemo(() => {
    const ids = new Set();
    personNotes.forEach((note) => {
      if (note.project_id) ids.add(note.project_id);
      (note.project_ids || []).forEach((projectId) => ids.add(projectId));
    });
    return ids;
  }, [personNotes]);

  const linkedProjects = useMemo(
    () => projects.filter((project) => linkedProjectIds.has(project.id)),
    [linkedProjectIds, projects],
  );

  const linkedTasks = useMemo(() => {
    const seen = new Set();
    return tasks.filter((task) => {
      const isLinked = personNoteIds.has(task.note_id) || linkedProjectIds.has(task.project_id);
      if (!isLinked || seen.has(task.id)) return false;
      seen.add(task.id);
      return true;
    });
  }, [linkedProjectIds, personNoteIds, tasks]);

  const role = person?.role || person?.properties?.role || person?.email || 'No role set';
  const tagNames = person?.tag_names || [];
  const suggestedLinks = [
    ...linkedProjects.slice(0, 2).map((project) => ({ id: project.id, label: project.title, route: `/projects/${project.id}` })),
    ...personNotes.slice(0, 2).map((note) => ({
      id: note.id,
      label: firstLine(note.raw_text) || 'Untitled note',
      route: `/notes/${note.id}`,
    })),
  ];

  // Note candidates: notes not already linked to this person
  const alreadyLinkedNoteIds = new Set(personNotes.map((n) => n.id));
  const noteCandidates = notes
    .filter((n) => !alreadyLinkedNoteIds.has(n.id))
    .filter((n) => (n.title || firstLine(n.raw_text)).toLowerCase().includes(noteSearchQuery.trim().toLowerCase()))
    .slice(0, 80);

  // ── Add existing note to this person ──
  async function handleAddNoteLink() {
    if (!notePick || noteLinkBusy) return;
    setNoteLinkBusy(true);
    try {
      await updateNote(notePick, { person_id: id });
      setNotePick('');
      setNoteSearchQuery('');
      setShowAddNoteModal(false);
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not link note' });
    } finally {
      setNoteLinkBusy(false);
    }
  }

  // ── Remove note from this person ──
  async function handleRemoveNoteFromPerson(noteId) {
    try {
      await updateNote(noteId, { person_id: null });
    } catch (e) {
      addToast({ type: 'error', message: e.message || 'Could not unlink note' });
    }
  }

  if (!person) {
    if (loading) {
      return (
        <div className={projectStyles.page}>
          <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
        </div>
      );
    }
    return (
      <div className={projectStyles.page}>
        <p className={projectStyles.empty}>Person not found.</p>
        <button type="button" className={projectStyles.backBtn} onClick={() => navigate('/people')}>
          <ArrowLeft size={14} /> All People
        </button>
      </div>
    );
  }

  return (
    <div className={projectStyles.page}>
      <nav className={projectStyles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/people">People</Link>
        <span className={projectStyles.breadcrumbSep}>/</span>
        <span className={projectStyles.breadcrumbCurrent}>{person.title}</span>
      </nav>

      <button type="button" className={projectStyles.backBtn} onClick={() => navigate('/people')}>
        <ArrowLeft size={14} /> All People
      </button>

      <div style={shellStyle}>
        <div style={mainPanelStyle}>
          <header style={headerStyle}>
            <div style={personMetaStyle}>
              <div style={avatarStyle}>{getInitials(person.title)}</div>
              <div style={headerCopyStyle}>
                <h1 style={nameStyle}>{person.title}</h1>
                <p style={roleStyle}>{role}</p>
              </div>
            </div>
            <span style={statStyle}>{personNotes.length} notes linked</span>
          </header>

          <div className={projectStyles.tabs}>
            {[
              { key: 'notes', label: `Notes (${personNotes.length})` },
              { key: 'tasks', label: `Tasks (${linkedTasks.length})` },
              { key: 'projects', label: `Projects (${linkedProjects.length})` },
              { key: 'connections', label: 'Connections' },
            ].map((entry) => (
              <button
                key={entry.key}
                type="button"
                className={`${projectStyles.tab} ${tab === entry.key ? projectStyles.tabActive : ''}`}
                onClick={() => setTab(entry.key)}
              >
                {entry.label}
              </button>
            ))}
          </div>

          {tab === 'notes' && (
            <div className={projectStyles.content} style={tabBodyStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {personNotes.length} linked notes
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-secondary btn-sm" type="button" onClick={() => setShowAddNoteModal(true)}>
                    <Plus size={13} /> Add Note
                  </button>
                  <button className="btn btn-primary btn-sm" type="button" onClick={() => setShowNewNoteEditor(true)}>
                    <Plus size={13} /> New Note
                  </button>
                </div>
              </div>

              {/* Add existing note modal */}
              {showAddNoteModal && (
                <div style={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '14px',
                  padding: '14px',
                  display: 'grid',
                  gap: '10px',
                  marginBottom: '12px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Link existing note</span>
                    <button
                      type="button"
                      onClick={() => { setShowAddNoteModal(false); setNotePick(''); setNoteSearchQuery(''); }}
                      style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <input
                    type="search"
                    placeholder="Filter notes…"
                    value={noteSearchQuery}
                    onChange={(e) => setNoteSearchQuery(e.target.value)}
                    style={{
                      padding: '8px 10px',
                      fontSize: '12px',
                      background: 'var(--surface2)',
                      border: '1px solid var(--border-faint)',
                      borderRadius: '6px',
                      color: 'var(--text)',
                      outline: 'none',
                    }}
                  />
                  <select
                    value={notePick}
                    onChange={(e) => setNotePick(e.target.value)}
                    style={{
                      padding: '8px 10px',
                      fontSize: '12px',
                      background: 'var(--surface2)',
                      border: '1px solid var(--border-faint)',
                      borderRadius: '6px',
                      color: 'var(--text)',
                      cursor: 'pointer',
                    }}
                  >
                    <option value="">Select a note…</option>
                    {noteCandidates.map((n) => (
                      <option key={n.id} value={n.id}>{n.title || firstLine(n.raw_text)}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleAddNoteLink}
                    disabled={!notePick || noteLinkBusy}
                    style={{ alignSelf: 'end' }}
                  >
                    {noteLinkBusy ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
                    Add link
                  </button>
                </div>
              )}

              {personNotes.length === 0 ? (
                <p className={projectStyles.empty}>No notes linked to this person yet.</p>
              ) : (
                <div style={itemListStyle}>
                  {personNotes.map((note) => (
                    <div key={note.id} style={{ ...itemRowStyle, position: 'relative' }}>
                      <div style={itemCopyStyle}>
                        <Link to={`/notes/${note.id}`} style={itemTitleStyle}>
                          {firstLine(note.raw_text) || 'Untitled note'}
                        </Link>
                        <span style={itemMetaStyle}>
                          {note.project_id ? 'Linked to project note' : 'Standalone note'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={badgeStyle}>
                          <FileText size={12} /> Note
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveNoteFromPerson(note.id)}
                          style={{
                            background: 'none',
                            border: '1px solid var(--border-faint)',
                            borderRadius: '6px',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: '4px 6px',
                            display: 'flex',
                            alignItems: 'center',
                            fontSize: '10px',
                          }}
                          title="Remove note from person"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'tasks' && (
            <div className={projectStyles.content} style={tabBodyStyle}>
              {linkedTasks.length === 0 ? (
                <p className={projectStyles.empty}>No tasks linked through this person’s notes or projects.</p>
              ) : (
                <div style={itemListStyle}>
                  {linkedTasks.map((task) => (
                    <div key={task.id} style={itemRowStyle}>
                      <div style={itemCopyStyle}>
                        <span style={{ ...itemTitleStyle, cursor: 'default' }}>{task.title || getEntityTitle(task)}</span>
                        <span style={itemMetaStyle}>
                          {task.status || 'pending'}
                          {task.project_id ? ` · ${projects.find((project) => project.id === task.project_id)?.title || 'Project task'}` : ''}
                        </span>
                      </div>
                      <span style={badgeStyle}>
                        <CheckSquare size={12} /> Task
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'projects' && (
            <div className={projectStyles.content} style={tabBodyStyle}>
              {linkedProjects.length === 0 ? (
                <p className={projectStyles.empty}>No projects linked to this person yet.</p>
              ) : (
                <div style={itemListStyle}>
                  {linkedProjects.map((project) => (
                    <div key={project.id} style={itemRowStyle}>
                      <div style={itemCopyStyle}>
                        <Link to={`/projects/${project.id}`} style={itemTitleStyle}>
                          {project.title}
                        </Link>
                        <span style={itemMetaStyle}>
                          {project.status || 'active'}
                        </span>
                      </div>
                      <span style={badgeStyle}>
                        <FolderOpen size={12} /> Project
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'connections' && (
            <div className={projectStyles.content}>
              <LinkToEntity entityId={id} entityType="person" onLinkCreated={() => setConnRefreshKey(k => k + 1)} />
              <ConnectionsPanel entityId={id} refreshKey={connRefreshKey} />
            </div>
          )}
        </div>

        <aside style={sidebarStyle}>
          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <Tag size={13} /> Tags
            </h2>
            {tagNames.length > 0 ? (
              <div style={chipsStyle}>
                {tagNames.map((tag) => (
                  <span key={tag} style={chipStyle}>{tag}</span>
                ))}
              </div>
            ) : (
              <p style={itemMetaStyle}>No tags yet.</p>
            )}
          </section>

          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <Sparkles size={13} /> Suggested links
            </h2>
            {suggestedLinks.length > 0 ? (
              suggestedLinks.map((entry) => (
                <Link key={entry.id} to={entry.route} style={sidebarLinkStyle}>
                  {entry.label}
                </Link>
              ))
            ) : (
              <p style={itemMetaStyle}>No suggested links yet.</p>
            )}
          </section>

          <section style={sidebarCardStyle}>
            <h2 style={sidebarTitleStyle}>
              <UserPlus size={13} /> Quick actions
            </h2>
            <button
              type="button"
              style={actionButtonStyle}
              onClick={() => {
                const nextRoute = linkedProjects[0] ? `/projects/${linkedProjects[0].id}` : '/notes';
                navigate(nextRoute);
              }}
            >
              <FolderOpen size={13} /> Open related project
            </button>
            <button
              type="button"
              style={actionButtonStyle}
              onClick={() => {
                const nextRoute = personNotes[0] ? `/notes/${personNotes[0].id}` : '/notes';
                navigate(nextRoute);
              }}
            >
              <FileText size={13} /> Jump to latest note
            </button>
          </section>
        </aside>
      </div>

      {showNewNoteEditor && (
        <NoteEditor
          initialData={{ person_id: id, bucket: 'PEOPLE' }}
          onClose={() => setShowNewNoteEditor(false)}
          onSaved={() => setShowNewNoteEditor(false)}
        />
      )}
    </div>
  );
}
