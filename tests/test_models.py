from extensions import db
from models import Note, Project, Area, Tag, Person, Task, BucketType, Priority, TaskStatus


def test_create_note(app):
    with app.app_context():
        note = Note(raw_text="This is a test note")
        db.session.add(note)
        db.session.commit()

        assert note.id is not None
        assert note.raw_text == "This is a test note"
        assert note.bucket == BucketType.INBOX
        assert note.is_archived == False
        assert note.created_at is not None


def test_note_to_dict(app):
    with app.app_context():
        note = Note(raw_text="Test note content")
        db.session.add(note)
        db.session.commit()

        d = note.to_dict()
        assert d["raw_text"] == "Test note content"
        assert d["bucket"] == "inbox"
        assert "created_at" in d
        assert "modified_at" in d


def test_create_project(app):
    with app.app_context():
        project = Project(name="Test Project", priority=Priority.HIGH)
        db.session.add(project)
        db.session.commit()

        assert project.id is not None
        assert project.name == "Test Project"
        assert project.priority == Priority.HIGH
        assert project.is_archived == False


def test_project_with_notes(app):
    with app.app_context():
        project = Project(name="My Project")
        db.session.add(project)
        db.session.commit()

        note = Note(raw_text="Note for project", project_id=project.id)
        db.session.add(note)
        db.session.commit()

        # Refresh from DB
        project = db.session.get(Project, project.id)
        assert len(project.notes) == 1
        assert project.notes[0].raw_text == "Note for project"


def test_create_area(app):
    with app.app_context():
        area = Area(name="Health", description="Personal health tracking")
        db.session.add(area)
        db.session.commit()

        assert area.id is not None
        assert area.name == "Health"


def test_create_task(app):
    with app.app_context():
        task = Task(title="Complete the project", priority=Priority.HIGH)
        db.session.add(task)
        db.session.commit()

        assert task.id is not None
        assert task.title == "Complete the project"
        assert task.status == TaskStatus.PENDING


def test_task_status_transition(app):
    with app.app_context():
        task = Task(title="Test task")
        db.session.add(task)
        db.session.commit()

        task.status = TaskStatus.IN_PROGRESS
        db.session.commit()

        task = db.session.get(Task, task.id)
        assert task.status == TaskStatus.IN_PROGRESS


def test_create_person(app):
    with app.app_context():
        person = Person(name="John Doe", email="john@example.com", discord_id="12345")
        db.session.add(person)
        db.session.commit()

        assert person.id is not None
        assert person.name == "John Doe"
        assert person.email == "john@example.com"


def test_note_tag_association(app):
    with app.app_context():
        tag = Tag(name="urgent")
        db.session.add(tag)
        db.session.commit()

        note = Note(raw_text="Urgent note")
        note.tags.append(tag)
        db.session.add(note)
        db.session.commit()

        note = db.session.get(Note, note.id)
        assert len(note.tags) == 1
        assert note.tags[0].name == "urgent"
