"""Tests for services/link_proposer.py — v2 Entity model.

No OpenAI / pgvector required — tests lexical, entity-signal, and temporal logic.
"""

from extensions import db
from models import Entity, EntityLink, EntityTag, Tag


def _make_note(title, content, lifecycle="active", properties=None):
    """Helper to create a note Entity."""
    return Entity(
        type="note",
        title=title,
        content=content,
        lifecycle=lifecycle,
        properties=properties or {},
    )


def _add(entity):
    """Add and flush a single entity (avoids batch-insert RETURNING issues)."""
    db.session.add(entity)
    db.session.flush()
    return entity


def test_propose_links_shared_tags_and_lexical_overlap(app):
    """Two notes sharing a tag with overlapping content should produce a proposal."""
    with app.app_context():
        from services.link_proposer import propose_links

        tag = _add(Tag(name="shared-topic"))
        note_a = _add(_make_note("A", "quarterly planning themes and roadmap draft for shared-topic"))
        note_b = _add(_make_note("B", "follow up on quarterly planning themes for shared-topic next week"))

        db.session.add_all([
            EntityTag(entity_id=note_a.id, tag_id=tag.id),
            EntityTag(entity_id=note_b.id, tag_id=tag.id),
        ])
        db.session.commit()

        proposals = propose_links([note_a.id, note_b.id], min_confidence=0.35)
        assert len(proposals) >= 1
        p0 = proposals[0]
        assert {p0["from_note_id"], p0["to_note_id"]} == {str(note_a.id), str(note_b.id)}
        assert "confidence" in p0 and 0 < p0["confidence"] <= 1
        assert "reason" in p0 and p0["reason"]
        assert "shared" in p0["reason"].lower() or "semantic" in p0["reason"].lower() or "lexical" in p0[
            "reason"
        ].lower()


def test_propose_links_skips_existing_link(app):
    """Notes already linked via EntityLink should not be proposed again."""
    with app.app_context():
        from services.link_proposer import propose_links

        tag = _add(Tag(name="x"))
        a = _add(_make_note("A", "one two three four five six"))
        b = _add(_make_note("B", "one two three four five seven"))

        db.session.add_all([
            EntityTag(entity_id=a.id, tag_id=tag.id),
            EntityTag(entity_id=b.id, tag_id=tag.id),
            EntityLink(src_id=a.id, dst_id=b.id, link_type="related", source="manual"),
        ])
        db.session.commit()

        assert propose_links([a.id, b.id]) == []


def test_propose_links_same_area_and_recent(app):
    """Notes linked to the same area entity should get an area boost."""
    with app.app_context():
        from services.link_proposer import propose_links

        area = _add(Entity(type="area", title="Work", lifecycle="active"))
        n1 = _add(_make_note("N1", "status update about vendor integration milestones"))
        n2 = _add(_make_note("N2", "vendor integration checklist and risks discussed"))

        db.session.add_all([
            EntityLink(src_id=n1.id, dst_id=area.id, link_type="related", source="manual"),
            EntityLink(src_id=n2.id, dst_id=area.id, link_type="related", source="manual"),
        ])
        db.session.commit()

        proposals = propose_links([n1.id, n2.id], min_confidence=0.32)
        assert proposals
        assert any("area" in p["reason"].lower() for p in proposals)


def test_propose_links_empty_pool(app):
    """Empty or single-entity pools return no proposals."""
    with app.app_context():
        from services.link_proposer import propose_links

        assert propose_links([]) == []
        n = _add(_make_note("solo", "solo note content"))
        db.session.commit()
        assert propose_links([n.id]) == []


def test_propose_links_excludes_archived(app):
    """Archived notes (lifecycle='archived') should be excluded from the pool."""
    with app.app_context():
        from services.link_proposer import propose_links

        tag = _add(Tag(name="topic"))
        active = _add(_make_note("Active", "quarterly planning themes roadmap"))
        archived = _add(_make_note("Archived", "quarterly planning themes roadmap", lifecycle="archived"))

        db.session.add_all([
            EntityTag(entity_id=active.id, tag_id=tag.id),
            EntityTag(entity_id=archived.id, tag_id=tag.id),
        ])
        db.session.commit()

        # Passing both IDs — archived should be filtered out, leaving only 1 => no pairs
        proposals = propose_links([active.id, archived.id])
        assert proposals == []


def test_propose_links_shared_project(app):
    """Notes linked to the same project entity should get a project boost."""
    with app.app_context():
        from services.link_proposer import propose_links

        project = _add(Entity(type="project", title="Alpha", lifecycle="active"))
        n1 = _add(_make_note("N1", "sprint planning notes for alpha release"))
        n2 = _add(_make_note("N2", "alpha release retrospective and lessons"))

        db.session.add_all([
            EntityLink(src_id=n1.id, dst_id=project.id, link_type="related", source="manual"),
            EntityLink(src_id=n2.id, dst_id=project.id, link_type="related", source="manual"),
        ])
        db.session.commit()

        proposals = propose_links([n1.id, n2.id], min_confidence=0.30)
        assert proposals
        assert any("project" in p["reason"].lower() for p in proposals)


def test_propose_links_bulk_tag_loading(app):
    """Verify bulk tag loading works with many notes and tags (no N+1)."""
    with app.app_context():
        from services.link_proposer import propose_links

        tags = [_add(Tag(name=f"tag-{i}")) for i in range(5)]
        # Notes with overlapping content so lexical similarity kicks in
        notes = [
            _add(_make_note(f"N{i}", f"shared content about topic-{i} and topic-{(i+1) % 5}"))
            for i in range(6)
        ]

        # Each note gets 2 tags; adjacent notes share one tag
        entity_tags = []
        for i, note in enumerate(notes):
            entity_tags.append(EntityTag(entity_id=note.id, tag_id=tags[i % 5].id))
            entity_tags.append(EntityTag(entity_id=note.id, tag_id=tags[(i + 1) % 5].id))
        db.session.add_all(entity_tags)
        db.session.commit()

        ids = [n.id for n in notes]
        proposals = propose_links(ids, min_confidence=0.30)
        # Adjacent notes share tags and have overlapping content
        assert len(proposals) > 0
