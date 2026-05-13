import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Mail, Pencil, Trash2 } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './People.module.css';

export default function People() {
  const navigate = useNavigate();
  const { people, notes, createPerson, updatePerson, deletePerson, setActivePerson } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editingPerson, setEditingPerson] = useState(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [noteText, setNoteText] = useState('');
  const [lastContactedAt, setLastContactedAt] = useState('');

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createPerson({
      name: name.trim(),
      email: email.trim() || undefined,
      notes: noteText.trim() || undefined,
      last_contacted_at: lastContactedAt || undefined,
    });
    resetForm();
    setShowModal(false);
  };

  const resetForm = () => {
    setName('');
    setEmail('');
    setNoteText('');
    setLastContactedAt('');
  };

  const openEdit = (person) => {
    setEditingPerson(person);
    setName(person.name || '');
    setEmail(person.email || '');
    setNoteText(person.notes || '');
    setLastContactedAt(person.last_contacted_at ? person.last_contacted_at.slice(0, 10) : '');
  };

  const closeEdit = () => {
    setEditingPerson(null);
    resetForm();
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editingPerson || !name.trim()) return;
    await updatePerson(editingPerson.id, {
      name: name.trim(),
      email: email.trim() || null,
      notes: noteText.trim() || null,
      last_contacted_at: lastContactedAt || null,
    });
    closeEdit();
  };

  const handleDelete = async (person) => {
    if (!window.confirm(`Delete person "${person.name}"? This cannot be undone.`)) return;
    await deletePerson(person.id);
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
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={15} /> Add Person
        </button>
      </div>

      {people.length === 0 ? (
        <EmptyState
          type="notes"
          title="No people yet"
          message="Add the people you work with — teammates, partners, clients — so you can link notes to them."
          action={<button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={14} /> Add person</button>}
        />
      ) : (
        <div className={styles.grid}>
          {people.map(p => {
            const personNotes = notes.filter(n => n.person_id === p.id);
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
                style={{ cursor: 'pointer' }}
              >
                <div className={styles.avatar}>{p.name.charAt(0).toUpperCase()}</div>
                <div className={styles.info}>
                  <span className={styles.name}>{p.name}</span>
                  {p.email && (
                    <span className={styles.email}>
                      <Mail size={11} /> {p.email}
                    </span>
                  )}
                  {p.notes && <p className={styles.desc}>{p.notes}</p>}
                  {p.last_contacted_at && (
                    <span className={styles.meta}>Last contacted {new Date(p.last_contacted_at).toLocaleDateString()}</span>
                  )}
                  <span className={styles.meta}>{personNotes.length} notes</span>
                  <div className={styles.cardActions}>
                    <button
                      className={styles.iconBtn}
                      onClick={(e) => { e.stopPropagation(); openEdit(p); }}
                      title="Edit person"
                    >
                      <Pencil size={13} /> Edit
                    </button>
                    <button
                      className={`${styles.iconBtn} ${styles.dangerBtn}`}
                      onClick={(e) => { e.stopPropagation(); handleDelete(p); }}
                      title="Delete person"
                    >
                      <Trash2 size={13} /> Delete
                    </button>
                  </div>
                </div>
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div><label className={styles.label}>Name</label><input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" autoFocus /></div>
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div><label className={styles.label}>Name</label><input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" autoFocus /></div>
            <div><label className={styles.label}>Email</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" /></div>
            <div><label className={styles.label}>Notes</label><textarea value={noteText} onChange={e => setNoteText(e.target.value)} rows={3} placeholder="Context about this person..." /></div>
            <div><label className={styles.label}>Last Contacted</label><input type="date" value={lastContactedAt} onChange={e => setLastContactedAt(e.target.value)} /></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
