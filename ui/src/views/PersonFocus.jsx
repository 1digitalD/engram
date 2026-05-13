import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, CheckSquare, FileText, FolderOpen, Sparkles, Tag, UserPlus } from 'lucide-react';
import useStore from '../stores/useStore';
import ConnectionsPanel from '../components/ConnectionsPanel/ConnectionsPanel';
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
  const { people, notes, tasks, projects, setActivePerson } = useStore();
  const [tab, setTab] = useState('notes');

  const person = people.find((entry) => entry.id === id);

  useEffect(() => {
    setActivePerson(person || null);
    return () => setActivePerson(null);
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
    ...linkedProjects.slice(0, 2).map((project) => ({ id: project.id, label: project.name, route: `/projects/${project.id}` })),
    ...personNotes.slice(0, 2).map((note) => ({
      id: note.id,
      label: firstLine(note.raw_text) || 'Untitled note',
      route: `/notes/${note.id}`,
    })),
  ];

  if (!person) {
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
        <span className={projectStyles.breadcrumbCurrent}>{person.name}</span>
      </nav>

      <button type="button" className={projectStyles.backBtn} onClick={() => navigate('/people')}>
        <ArrowLeft size={14} /> All People
      </button>

      <div style={shellStyle}>
        <div style={mainPanelStyle}>
          <header style={headerStyle}>
            <div style={personMetaStyle}>
              <div style={avatarStyle}>{getInitials(person.name)}</div>
              <div style={headerCopyStyle}>
                <h1 style={nameStyle}>{person.name}</h1>
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
              {personNotes.length === 0 ? (
                <p className={projectStyles.empty}>No notes linked to this person yet.</p>
              ) : (
                <div style={itemListStyle}>
                  {personNotes.map((note) => (
                    <div key={note.id} style={itemRowStyle}>
                      <div style={itemCopyStyle}>
                        <Link to={`/notes/${note.id}`} style={itemTitleStyle}>
                          {firstLine(note.raw_text) || 'Untitled note'}
                        </Link>
                        <span style={itemMetaStyle}>
                          {note.project_id ? 'Linked to project note' : 'Standalone note'}
                        </span>
                      </div>
                      <span style={badgeStyle}>
                        <FileText size={12} /> Note
                      </span>
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
                          {task.project_id ? ` · ${projects.find((project) => project.id === task.project_id)?.name || 'Project task'}` : ''}
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
                          {project.name}
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
              <ConnectionsPanel entityId={id} />
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
    </div>
  );
}
