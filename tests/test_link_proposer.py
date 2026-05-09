"""Tests for services/link_proposer.py (no OpenAI / sqlite-vec required)."""

from extensions import db
from models import Area, BucketType, Link, Note, Tag


def test_propose_links_shared_tags_and_lexical_overlap(app):
    with app.app_context():
        from services.link_proposer import propose_links

        tag = Tag(name="shared-topic")
        note_a = Note(
            raw_text="quarterly planning themes and roadmap draft for shared-topic",
            bucket=BucketType.INBOX,
        )
        note_b = Note(
            raw_text="follow up on quarterly planning themes for shared-topic next week",
            bucket=BucketType.INBOX,
        )
        note_a.tags.append(tag)
        note_b.tags.append(tag)
        db.session.add_all([tag, note_a, note_b])
        db.session.commit()

        proposals = propose_links([note_a.id, note_b.id], min_confidence=0.35)
        assert len(proposals) >= 1
        p0 = proposals[0]
        assert {p0["from_note_id"], p0["to_note_id"]} == {note_a.id, note_b.id}
        assert "confidence" in p0 and 0 < p0["confidence"] <= 1
        assert "reason" in p0 and p0["reason"]
        assert "shared" in p0["reason"].lower() or "semantic" in p0["reason"].lower() or "lexical" in p0[
            "reason"
        ].lower()


def test_propose_links_skips_existing_link(app):
    with app.app_context():
        from services.link_proposer import propose_links

        tag = Tag(name="x")
        a = Note(raw_text="one two three four five six", bucket=BucketType.INBOX)
        b = Note(raw_text="one two three four five seven", bucket=BucketType.INBOX)
        a.tags.append(tag)
        b.tags.append(tag)
        db.session.add_all([tag, a, b])
        db.session.flush()
        db.session.add(
            Link(
                src_id=a.id,
                dst_id=b.id,
                link_type="related",
                weight=1.0,
                source="manual",
            )
        )
        db.session.commit()

        assert propose_links([a.id, b.id]) == []


def test_propose_links_same_area_and_recent(app):
    with app.app_context():
        from services.link_proposer import propose_links

        area = Area(name="Work")
        n1 = Note(raw_text="status update about vendor integration milestones", bucket=BucketType.INBOX, area=area)
        n2 = Note(raw_text="vendor integration checklist and risks discussed", bucket=BucketType.INBOX, area=area)
        db.session.add_all([area, n1, n2])
        db.session.commit()

        proposals = propose_links([n1.id, n2.id], min_confidence=0.32)
        assert proposals
        assert any("area" in p["reason"].lower() for p in proposals)


def test_propose_links_empty_pool(app):
    with app.app_context():
        from services.link_proposer import propose_links

        assert propose_links([]) == []
        n = Note(raw_text="solo", bucket=BucketType.INBOX)
        db.session.add(n)
        db.session.commit()
        assert propose_links([n.id]) == []
