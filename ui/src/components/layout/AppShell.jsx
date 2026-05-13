import React, { useState, useEffect, useMemo } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Inbox, FileText, FolderOpen, Library,
  Map, Layers, Users, CheckSquare, Network, Calendar, Sun,
  Search, Plus, ChevronLeft, ChevronRight, Menu, Keyboard, Loader2, X,
} from 'lucide-react';
import styles from './AppShell.module.css';
import CommandPalette from '../search/CommandPalette';
import NoteEditor from '../notes/NoteEditor';
import KeyboardShortcutsModal from './KeyboardShortcutsModal';
import useStore from '../../stores/useStore';

const NAV_ITEMS = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/today',    icon: Sun,             label: 'Today' },
  { to: '/inbox',    icon: Inbox,           label: 'Inbox' },
  { to: '/notes',    icon: FileText,        label: 'Notes' },
  { to: '/moc',      icon: Layers,          label: 'Maps' },
  { to: '/projects', icon: FolderOpen,      label: 'Projects' },
  { to: '/areas',    icon: Map,             label: 'Areas' },
  { to: '/resources', icon: Library,        label: 'Resources' },
  { to: '/people',   icon: Users,           label: 'People' },
  { to: '/tasks',    icon: CheckSquare,     label: 'Tasks' },
  { to: '/graph',    icon: Network,         label: 'Graph' },
  { to: '/review',   icon: Calendar,        label: 'Review' },
];

const BOTTOM_NAV = [
  { to: '/today', icon: Sun,         label: 'Today' },
  { to: '/inbox', icon: Inbox,       label: 'Inbox' },
  { to: '/notes', icon: FileText,    label: 'Notes' },
  { to: '/tasks', icon: CheckSquare, label: 'Tasks' },
];

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const q = window.matchMedia('(max-width: 768px)');
    const apply = () => setMobile(q.matches);
    apply();
    q.addEventListener('change', apply);
    return () => q.removeEventListener('change', apply);
  }, []);
  return mobile;
}

function isTypingElement(el) {
  if (!el || !(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (el.closest('[contenteditable="true"]')) return true;
  return false;
}

function paletteKbdHint() {
  if (typeof navigator === 'undefined') return '⌘K';
  return /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent) ? '⌘K' : 'Ctrl+K';
}

const CAPTURE_TYPES = [
  { value: 'note', label: 'Note', icon: FileText },
  { value: 'task', label: 'Task', icon: CheckSquare },
  { value: 'resource', label: 'Resource', icon: Library },
  { value: 'person', label: 'Person', icon: Users },
];

function getCaptureRoute(entity, fallbackType = 'note') {
  const type = String(entity?.type || entity?.entity_type || fallbackType).toLowerCase();
  const id = entity?.id;

  switch (type) {
    case 'project':
      return id ? `/projects/${id}` : '/projects';
    case 'area':
      return id ? `/areas/${id}` : '/areas';
    case 'resource':
      return id ? `/resources/${id}` : '/resources';
    case 'person':
      return id ? `/people/${id}` : '/people';
    case 'task':
      return '/tasks';
    case 'note':
    default:
      return id ? `/notes/${id}` : '/notes';
  }
}

function CaptureModal({ onClose, onCreated }) {
  const [content, setContent] = useState('');
  const [entityType, setEntityType] = useState('note');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const textareaRef = React.useRef(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const body = content.trim();
    if (!body || submitting) return;

    setSubmitting(true);
    setError('');

    try {
      const response = await fetch('/api/v2/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: body,
          entity_type: entityType,
          source: 'ui',
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
      }

      const entity = payload.data || payload.entity || payload.note;
      if (!entity?.id) {
        throw new Error('Capture response did not include a created entity');
      }

      onCreated({
        entity,
        aiStatus: payload.ai_status || entity.ai_status || 'processing',
        selectedType: entityType,
      });
    } catch (err) {
      setError(err.message || 'Capture failed');
      setSubmitting(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape' && !submitting) {
      event.preventDefault();
      onClose();
    }
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSubmit(event);
    }
  };

  return (
    <div
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.44)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        zIndex: 60,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="capture-modal-title"
        onMouseDown={(event) => event.stopPropagation()}
        style={{
          width: 'min(100%, 520px)',
          borderRadius: '16px',
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          boxShadow: '0 28px 60px rgba(15, 23, 42, 0.22)',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
          <div>
            <h2 id="capture-modal-title" style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
              Quick capture
            </h2>
            <p style={{ margin: '6px 0 0', color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
              Create from anywhere. AI classifies and links after save.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close capture"
            className={styles.iconBtn}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ marginTop: '18px' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
            {CAPTURE_TYPES.map(({ value, label, icon: Icon }) => {
              const active = value === entityType;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setEntityType(value)}
                  disabled={submitting}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    borderRadius: '999px',
                    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                    background: active ? 'var(--accent-dim)' : 'transparent',
                    color: active ? 'var(--accent)' : 'var(--text-secondary)',
                    padding: '7px 11px',
                    fontSize: '0.82rem',
                    fontWeight: 500,
                  }}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              );
            })}
          </div>

          <textarea
            ref={textareaRef}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Capture a thought, task, person, or reference..."
            rows={7}
            disabled={submitting}
            style={{
              width: '100%',
              resize: 'vertical',
              borderRadius: '12px',
              border: '1px solid var(--border)',
              background: 'var(--surface-2)',
              color: 'var(--text)',
              padding: '14px 15px',
              fontSize: '0.94rem',
              lineHeight: 1.5,
              outline: 'none',
              minHeight: '148px',
            }}
          />

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginTop: '14px' }}>
            <div style={{ minHeight: '20px', fontSize: '0.82rem', color: error ? 'var(--red)' : 'var(--text-secondary)' }}>
              {error ? error : submitting ? 'AI pipeline running: classifying and linking…' : 'Cmd/Ctrl+Enter to create'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting || !content.trim()}
                style={{ minWidth: '112px', justifyContent: 'center' }}
              >
                {submitting ? <Loader2 size={14} className="spin" /> : null}
                {submitting ? 'Processing…' : 'Create'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AppShell({ children }) {
  const { projects, notes, captureOpen, openCapture, closeCapture, addToast } = useStore();
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useIsMobile();

  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [showNoteEditor, setShowNoteEditor] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const kbdPalette = useMemo(() => paletteKbdHint(), []);

  const sidebarCollapsed = isMobile ? false : collapsed;

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const handler = (e) => {
      const target = /** @type {HTMLElement} */ (e.target);
      if (isTypingElement(target)) return;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setShowPalette((p) => !p);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        if (e.shiftKey) {
          setShowNoteEditor(true);
        } else {
          openCapture();
        }
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        setShowShortcuts(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [openCapture]);

  const activeProjects = projects.filter(p => !p.is_archived).slice(0, 8);
  const inboxCount = notes.filter(n => n.bucket === 'INBOX').length;
  const mocNotes = notes
    .filter((n) => String(n.note_type || 'NOTE').toUpperCase() === 'MOC')
    .slice()
    .sort((a, b) => {
      const ta = (a.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim() || 'Untitled';
      const tb = (b.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim() || 'Untitled';
      return ta.localeCompare(tb, undefined, { sensitivity: 'base' });
    })
    .slice(0, 8);

  const closeDrawer = () => setDrawerOpen(false);
  const navEndProps = isMobile ? { onClick: closeDrawer } : {};
  const handleCaptureCreated = ({ entity, aiStatus, selectedType }) => {
    closeCapture();
    addToast({
      type: 'success',
      message: aiStatus === 'done'
        ? 'Capture created'
        : 'Capture created · AI classifying and linking…',
    });
    navigate(getCaptureRoute(entity, selectedType));
  };

  return (
    <div className={`${styles.shell} ${drawerOpen ? styles.drawerOpen : ''}`}>
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          {isMobile && (
            <button
              type="button"
              className={styles.iconBtn}
              aria-label="Open menu"
              onClick={() => setDrawerOpen(true)}
            >
              <Menu size={18} />
            </button>
          )}
          <NavLink
            to="/today"
            className={({ isActive }) =>
              `${styles.todayBtn} ${isActive ? styles.todayBtnActive : ''}`
            }
            title="Today"
          >
            <Sun size={20} strokeWidth={2.25} />
          </NavLink>
          <NavLink to="/" className={styles.topBrand} end>
            Engram
          </NavLink>
        </div>
        <div className={styles.topRight}>
          <button
            type="button"
            className={styles.iconBtn}
            aria-label="Keyboard shortcuts"
            title="Keyboard shortcuts"
            onClick={() => setShowShortcuts(true)}
          >
            <Keyboard size={18} />
          </button>
          <button
            type="button"
            className={styles.topSearch}
            onClick={() => setShowPalette(true)}
          >
            <Search size={15} />
            <span className={styles.topSearchLabel}>Search or run command…</span>
            <kbd className={styles.kbd}>{kbdPalette}</kbd>
          </button>
        </div>
      </header>

      <div className={styles.body}>
        {isMobile && drawerOpen && (
          <button
            type="button"
            className={styles.scrim}
            aria-label="Close menu"
            onClick={closeDrawer}
          />
        )}

        <aside
          className={`${styles.sidebar} ${sidebarCollapsed ? styles.collapsed : ''} ${
            isMobile ? styles.sidebarDrawer : ''
          }`}
        >
          <div className={styles.logo}>
            <NavLink to="/" className={styles.brand} onClick={closeDrawer} end>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="9" stroke="var(--accent)" strokeWidth="1.5"/>
                <circle cx="7" cy="8" r="2" fill="var(--accent)" opacity="0.6"/>
                <circle cx="13" cy="8" r="2" fill="var(--accent)" opacity="0.6"/>
                <circle cx="10" cy="13" r="2" fill="var(--accent)"/>
                <line x1="7" y1="8" x2="10" y2="13" stroke="var(--accent)" strokeWidth="1" opacity="0.4"/>
                <line x1="13" y1="8" x2="10" y2="13" stroke="var(--accent)" strokeWidth="1" opacity="0.4"/>
              </svg>
              {!sidebarCollapsed && <span className={styles.brandName}>Engram</span>}
            </NavLink>
            <button
              type="button"
              className={styles.iconBtn}
              onClick={() => {
                openCapture();
                closeDrawer();
              }}
              title="Quick capture"
              aria-label="Quick capture"
            >
              <Plus size={16} />
            </button>
            {!isMobile && (
              <button
                className={styles.collapseBtn}
                onClick={() => setCollapsed(c => !c)}
                title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
              </button>
            )}
            {isMobile && (
              <button
                className={styles.collapseBtn}
                onClick={closeDrawer}
                title="Close"
                aria-label="Close menu"
              >
                <ChevronLeft size={14} />
              </button>
            )}
          </div>

          <button
            className={styles.captureBtn}
            onClick={() => {
              openCapture();
              closeDrawer();
            }}
            title="Quick capture (⌘N)"
          >
            <Plus size={14} />
            {!sidebarCollapsed && <span>Capture</span>}
          </button>

          <nav className={styles.nav}>
            {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `${styles.navItem} ${isActive ? styles.navActive : ''}`
                }
                title={sidebarCollapsed ? label : undefined}
                {...navEndProps}
              >
                <Icon size={16} />
                {!sidebarCollapsed && <span>{label}</span>}
                {!sidebarCollapsed && label === 'Inbox' && inboxCount > 0 && (
                  <span className={styles.badge}>{inboxCount}</span>
                )}
              </NavLink>
            ))}
          </nav>

          {!sidebarCollapsed && (
            <div className={styles.section}>
              <div className={styles.sectionHeader}>MOCs</div>
              {mocNotes.map((n) => {
                const title =
                  (n.raw_text || '').split('\n')[0].replace(/^#\s*/, '').trim() || 'Untitled';
                return (
                  <NavLink
                    key={n.id}
                    to={`/notes/${n.id}`}
                    className={styles.projectItem}
                    onClick={closeDrawer}
                    title={title}
                  >
                    <Layers size={14} className={styles.mocSidebarIcon} aria-hidden />
                    <span className={styles.projectName}>{title}</span>
                  </NavLink>
                );
              })}
              <NavLink
                to="/moc"
                className={styles.projectItem}
                onClick={closeDrawer}
              >
                <Layers size={14} className={styles.mocSidebarIcon} aria-hidden />
                <span className={styles.projectName} style={{ opacity: mocNotes.length ? 0.85 : 1 }}>
                  {mocNotes.length ? 'View all maps…' : 'Browse maps of content'}
                </span>
              </NavLink>
            </div>
          )}

          {!sidebarCollapsed && activeProjects.length > 0 && (
            <div className={styles.section}>
              <div className={styles.sectionHeader}>Projects</div>
              {activeProjects.map(p => (
                <NavLink
                  key={p.id}
                  to={`/projects/${p.id}`}
                  className={styles.projectItem}
                  onClick={closeDrawer}
                >
                  <span className={styles.projectDot} style={{ background: p.color || 'var(--accent)' }} />
                  <span className={styles.projectName}>{p.name}</span>
                </NavLink>
              ))}
            </div>
          )}

          <button
            className={styles.searchTrigger}
            onClick={() => {
              setShowPalette(true);
              closeDrawer();
            }}
          >
            <Search size={13} />
            {!sidebarCollapsed && <span>Command palette…</span>}
            {!sidebarCollapsed && <kbd className={styles.kbd}>{kbdPalette}</kbd>}
          </button>
        </aside>

        <main className={styles.main}>{children}</main>
      </div>

      {isMobile && (
        <nav className={styles.bottomNav} aria-label="Primary">
          {BOTTOM_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `${styles.bottomNavItem} ${isActive ? styles.bottomNavActive : ''}`
              }
            >
              <Icon size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
          <button
            type="button"
            className={styles.bottomNavItem}
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={20} />
            <span>More</span>
          </button>
        </nav>
      )}

      {showPalette && (
        <CommandPalette onClose={() => setShowPalette(false)} />
      )}
      {captureOpen && (
        <CaptureModal
          onClose={() => closeCapture()}
          onCreated={handleCaptureCreated}
        />
      )}
      {showNoteEditor && (
        <NoteEditor
          onClose={() => setShowNoteEditor(false)}
          onSaved={() => setShowNoteEditor(false)}
        />
      )}
      {showShortcuts && (
        <KeyboardShortcutsModal onClose={() => setShowShortcuts(false)} />
      )}
    </div>
  );
}
