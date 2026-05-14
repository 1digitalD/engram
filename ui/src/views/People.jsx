import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Pencil, Trash2, Loader2, Sparkles } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import DeleteConfirmModal from '../components/DeleteConfirmModal';
import styles from './People.module.css';

function getInitials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
  if (parts.length === 0) return '?';
  return parts.map((part) => part[0].toUpperCase()).join('');
}

function getProp(person, key) {
  return (person.properties && person.properties[key]) || person[key] || '';
}

export default function People() {
  const navigate = useNavigate();
  const { people, notes, createPerson, updatePerson, deletePerson, getDeletePreview, setActivePerson, loading } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editingPerson, setEditingPerson] = useState(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [noteText, setNoteText] = useState('');
  const [lastContactedAt, setLastContactedAt] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePreview, setDeletePreview] = useState(null);
  const [pendingDeletePerson, setPendingDeletePerson] = useState(null);

  const filteredPeople = useMemo(() => {
    if (!searchQuery.trim()) return people;
    const q = searchQuery.toLowerCase();
    return people.filter((p) => {
      const n = (p.title || '').toLowerCase();
      const e = (getProp(p, 'email') || '').toLowerCase();
      const r = (getProp(p, 'role') || '').toLowerCase();
      return n.includes(q) || e.includes(q) || r.includes(q);
    });
  }, [people, searchQuery]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createPerson({
      title: name.trim(),
      email: email.trim() || undefined,
      role: role.trim() || undefined,
      notes: noteText.trim() || undefined,
      last_contacted_at: lastContactedAt || undefined,
    });
    resetForm();
    setShowModal(false);
  };

  const resetForm = () => {
    setName('');
    setEmail('');
    setRole('');
    setNoteText('');
    setLastContactedAt('');
  };

  const openEdit = (person) => {
    setEditingPerson(person);
    setName(person.title || '');
    setEmail(getProp(person, 'email'));
    setRole(getProp(person, 'role'));
    setNoteText(getProp(person, 'notes_text') || getProp(person, 'notes') || '');
    setLastContactedAt(getProp(person, 'last_contacted_at') ? getProp(person, 'last_contacted_at').slice(0, 10) : '');
  };

  const closeEdit = () => {
    setEditingPerson(null);
    resetForm();
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editingPerson || !name.trim()) return;
    await updatePerson(editingPerson.id, {
      title: name.trim(),
      email: email.trim() || null,
      role: role.trim() || null,
      notes: noteText.trim() || null,
      last_contacted_at: lastContactedAt || null,
    });
    closeEdit();
  };

  const handleDeleteClick = async (person) => {
    try {
      const preview = await getDeletePreview(person.id);
      setDeletePreview(preview);
      setPendingDeletePerson(person);
      setShowDeleteModal(true);
    } catch (e) {
      useStore.getState().addToast({ type: 'error', message: e.message || 'Failed to load delete preview' });
    }
  };

  const handleDeleteConfirm = async (cascadeIds) => {
    if (!pendingDeletePerson) return;
    await deletePerson(pendingDeletePerson.id, cascadeIds);
    setShowDeleteModal(false);
    setDeletePreview(null);
    setPendingDeletePerson(null);
  };

  const handleOpenPerson = (person) => {
    setActivePerson(person);
    navigate(`/people/${person.id}`);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1>People</h1>
          <p className={styles.count}>{people.length} contacts</p>
        </div>
        <button className={styles.addBtn} onClick={() => setShowModal(true)}>
          <Plus size={12} /> Add Person
        </button>
      </div>

      <div className={styles.searchBar}>
        <Search size={14} className={styles.searchIcon} />
        <input
          type="text"
          placeholder="Search by name, email, or role..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={styles.searchInput}
        />
      </div>

      {loading && people.length === 0 ? (
        <Loader2 size={20} className="spin" style={{ display: 'block', margin: '40px auto', color: 'var(--text-muted)' }} />
      ) : people.length === 0 ? (
        <EmptyState
          type="notes"
          title="No people yet"
          message="Add the people you work with — teammates, partners, clients — so you can link notes to them."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Add person</button>}
        />
      ) : filteredPeople.length === 0 ? (
        <div className={styles.emptySearch}>
          <p>No matches for &ldquo;{searchQuery}&rdquo;</p>
        </div>
      ) : (
        <div className={styles.grid}>
          {filteredPeople.map(p => {
            const personNotes = notes.filter(n => n.person_id === p.id);
            const initials = getInitials(p.title || '');
            const personRole = getProp(p, 'role');
            const personEmail = getProp(p, 'email');

            return (
              <div
                key={p.id}
                className={styles.card}
                role="button"
                tabIndex={0}
                onClick={() => handleOpenPerson(p)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleOpenPerson(p);
                  }
                }}
              >
                <div className={styles.avatar}>{initials}</div>
                <div className={styles.info}>
                  <span className={styles.name}>{p.title}</span>
                  {personRole && <span className={styles.role}>{personRole}</span>}
                  {!personRole && personEmail && (
                    <span className={styles.role}>{personEmail}</span>
                  )}
                  {p.ai_status === 'processing' && (
                    <span className={styles.aiProcessing}><Loader2 size={10} className="spin" /></span>
                  )}
                  {p.ai_status === 'done' && p._ai_meta?.bucket && (
                    <span className={styles.aiClassification}>
                      <Sparkles size={10} />
                      {p._ai_meta.bucket}
                    </span>
                  )}
                  <div className={styles.cardActions}>
                    <button
                      className={styles.iconBtn}
                      onClick={(e) => { e.stopPropagation(); openEdit(p); }}
                      title="Edit person"
                    >
                      <Pencil size={12} />
                    </button>
                    <button
                      className={`${styles.iconBtn} ${styles.dangerBtn}`}
                      onClick={(e) => { e.stopPropagation(); handleDeleteClick(p); }}
                      title="Delete person"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
                {personNotes.length > 0 && (
                  <span className={styles.noteCount}>{personNotes.length}</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <Modal isOpen onClose={() => { resetForm(); setShowModal(false); }} title="Add Person" footer={
          <><button className="btn btn-ghost" onClick={() => { resetForm(); setShowModal(false); }}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim()}>Add</button></>
        }>
          <div className={styles.formFields}>
            <div><label className={styles.label}>Name</label><input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" autoFocus /></div>
            <div><label className={styles.label}>Role</label><input value={role} onChange={e => setRole(e.target.value)} placeholder="e.g. Engineering Manager" /></div>
            <div><label className={styles.label}>Email</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" /></div>
            <div><label className={styles.label}>Notes</label><textarea value={noteText} onChange={e => setNoteText(e.target.value)} rows={3} placeholder="Context about this person..." /></div>
            <div><label className={styles.label}>Last Contacted</label><input type="date" value={lastContactedAt} onChange={e => setLastContactedAt(e.target.value)} /></div>
          </div>
        </Modal>
      )}

      {editingPerson && (
        <Modal isOpen onClose={closeEdit} title="Edit Person" footer={
          <><button className="btn btn-ghost" onClick={closeEdit}>Cancel</button>
          <button className="btn btn-primary" onClick={handleUpdate} disabled={!name.trim()}>Save</button></>
        }>
          <div className={styles.formFields}>
            <div><label className={styles.label}>Name</label><input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" autoFocus /></div>
            <div><label className={styles.label}>Role</label><input value={role} onChange={e => setRole(e.target.value)} placeholder="e.g. Engineering Manager" /></div>
            <div><label className={styles.label}>Email</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" /></div>
            <div><label className={styles.label}>Notes</label><textarea value={noteText} onChange={e => setNoteText(e.target.value)} rows={3} placeholder="Context about this person..." /></div>
            <div><label className={styles.label}>Last Contacted</label><input type="date" value={lastContactedAt} onChange={e => setLastContactedAt(e.target.value)} /></div>
          </div>
        </Modal>
      )}

      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => { setShowDeleteModal(false); setDeletePreview(null); setPendingDeletePerson(null); }}
        onConfirm={handleDeleteConfirm}
        entityTitle={pendingDeletePerson?.title || 'Person'}
        entityType="person"
        preview={deletePreview}
      />
    </div>
  );
}
