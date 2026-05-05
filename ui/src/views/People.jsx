import React, { useState } from 'react';
import { Plus, Mail, FileText } from 'lucide-react';
import Modal from '../components/ui/Modal';
import useStore from '../stores/useStore';
import EmptyState from '../components/ui/EmptyState';
import styles from './People.module.css';

export default function People() {
  const { people, notes, createPerson } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [noteText, setNoteText] = useState('');

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    await createPerson({ name: name.trim(), email: email.trim() || undefined, notes: noteText.trim() || undefined });
    setName(''); setEmail(''); setNoteText(''); setShowModal(false);
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
              <div key={p.id} className={styles.card}>
                <div className={styles.avatar}>{p.name.charAt(0).toUpperCase()}</div>
                <div className={styles.info}>
                  <span className={styles.name}>{p.name}</span>
                  {p.email && (
                    <span className={styles.email}>
                      <Mail size={11} /> {p.email}
                    </span>
                  )}
                  {p.notes && <p className={styles.desc}>{p.notes}</p>}
                  <span className={styles.meta}>{personNotes.length} notes</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <Modal isOpen onClose={() => setShowModal(false)} title="Add Person" footer={
          <><button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim()}>Add</button></>
        }>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div><label className={styles.label}>Name</label><input value={name} onChange={e => setName(e.target.value)} placeholder="Full name" autoFocus /></div>
            <div><label className={styles.label}>Email</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" /></div>
            <div><label className={styles.label}>Notes</label><textarea value={noteText} onChange={e => setNoteText(e.target.value)} rows={3} placeholder="Context about this person..." /></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
