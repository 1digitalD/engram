# Engram — Specification

> A personal knowledge and task management system. An engram is a physical trace in the brain that stores a memory — knowledge that persists and can be recalled.

## 1. Overview

**Goal:** Build a self-hosted second brain that captures, classifies, stores, and retrieves information via web UI and an AI agent (Hermes).

**Core metaphor:** Your brain has an "inbox" for new information. Some gets processed into projects (active work), areas (ongoing responsibilities), resources (reference), or archives (dormant). Engram automates this classification and makes everything searchable.

**Target users:** Dan (single user, self-hosted on Mac Mini)

---

## 2. Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Hermes    │────▶│  Flask API  │────▶│   SQLite    │
│  (Discord)  │     │   :5000     │     │  engram.db  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌─────────┐   ┌──────────┐
              │ Web UI  │   │ OpenAI   │
              │ :5000   │   │ (GPT-4o) │
              └─────────┘   └──────────┘
```

**Tech stack:**
- Flask (Python 3.11+)
- SQLAlchemy + SQLite (FTS5 for full-text search)
- OpenAI GPT-4o for classification
- Jinja2 templates + vanilla JS (no SPA)
- Pytest for testing

---

## 3. Data Model

### Entities

**Note** (the core entity)
```
id: UUID (primary key)
raw_text: TEXT (the captured content)
bucket: ENUM ('inbox', 'projects', 'areas', 'resources', 'archives')
is_archived: BOOLEAN
created_at: DATETIME
modified_at: DATETIME

# Relationships
project_id: FK (nullable, many-to-one)
area_id: FK (nullable, many-to-one)
tags: M2M through note_tags
person_id: FK (nullable, for people-related notes)
```

**Project**
```
id: UUID
name: TEXT
description: TEXT (nullable)
priority: ENUM ('low', 'medium', 'high', 'urgent')
color: TEXT (hex, nullable)
deadline: DATETIME (nullable)
is_archived: BOOLEAN
created_at: DATETIME
modified_at: DATETIME
```

**Area**
```
id: UUID
name: TEXT
description: TEXT (nullable)
color: TEXT (hex, nullable)
created_at: DATETIME
modified_at: DATETIME
```

**Tag**
```
id: UUID
name: TEXT (unique)
color: TEXT (hex, nullable)
created_at: DATETIME
```

**Person**
```
id: UUID
name: TEXT
email: TEXT (nullable)
discord_id: TEXT (nullable)
notes: TEXT (free-form notes about the person)
last_contacted_at: DATETIME (nullable)
created_at: DATETIME
modified_at: DATETIME
```

**Task**
```
id: UUID
title: TEXT
description: TEXT (nullable)
status: ENUM ('pending', 'in_progress', 'done', 'cancelled')
priority: ENUM ('low', 'medium', 'high', 'urgent')
due_date: DATETIME (nullable)
project_id: FK (nullable)
created_at: DATETIME
modified_at: DATETIME
```

**WeeklySummary**
```
id: UUID
entity_type: ENUM ('project', 'area')
entity_id: UUID
entity_name: TEXT
week_year: INT
week_number: INT
summary_content: TEXT
note_count: INT
created_at: DATETIME
```

### Full-Text Search

SQLite FTS5 virtual table on `notes.raw_text` with triggers for sync.

---

## 4. API Design

Base URL: `http://localhost:5000/api/v1`

### Notes

| Method | Endpoint | Description |
|---|---|---|
| GET | `/notes` | List notes (filter by bucket, project, area, tag) |
| POST | `/notes` | Create note (auto-classify via AI) |
| GET | `/notes/<id>` | Get single note |
| PATCH | `/notes/<id>` | Update note |
| DELETE | `/notes/<id>` | Delete note |
| GET | `/notes/search?q=` | Full-text search |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| GET | `/projects` | List projects |
| POST | `/projects` | Create project |
| GET | `/projects/<id>` | Get project with its notes |
| PATCH | `/projects/<id>` | Update project |
| DELETE | `/projects/<id>` | Delete project |

### Areas

| Method | Endpoint | Description |
|---|---|---|
| GET | `/areas` | List areas |
| POST | `/areas` | Create area |
| GET | `/areas/<id>` | Get area with its notes |
| PATCH | `/areas/<id>` | Update area |
| DELETE | `/areas/<id>` | Delete area |

### Tags

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tags` | List all tags |
| POST | `/tags` | Create tag |
| PATCH | `/tags/<id>` | Update tag |
| DELETE | `/tags/<id>` | Delete tag |

### People

| Method | Endpoint | Description |
|---|---|---|
| GET | `/people` | List people |
| POST | `/people` | Create person |
| GET | `/people/<id>` | Get person |
| PATCH | `/people/<id>` | Update person |
| DELETE | `/people/<id>` | Delete person |

### Tasks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tasks` | List tasks (filter by status, project) |
| POST | `/tasks` | Create task |
| PATCH | `/tasks/<id>` | Update task (including status change) |
| DELETE | `/tasks/<id>` | Delete task |

### Weekly Summaries

| Method | Endpoint | Description |
|---|---|---|
| GET | `/summaries` | List summaries |
| POST | `/summaries/generate` | Trigger AI summary for a project/area |
| GET | `/summaries/<id>` | Get single summary |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Returns status: db, ai, etc. |

---

## 5. Web UI

Pages (Jinja2 templates):

| Route | Page |
|---|---|
| `/` | Dashboard — inbox count, recent notes, active projects |
| `/inbox` | Inbox — unprocessed notes |
| `/notes` | All notes (filterable by bucket) |
| `/notes/<id>` | Note detail |
| `/projects` | Projects list |
| `/projects/<id>` | Project detail + its notes |
| `/areas` | Areas list |
| `/areas/<id>` | Area detail + its notes |
| `/tags` | Tags cloud |
| `/people` | People list |
| `/people/<id>` | Person detail |
| `/tasks` | Task board (Kanban by status) |
| `/search` | Search results |
| `/review` | Weekly review |

---

## 6. AI Classification

### How it works

1. User submits raw text via API or UI
2. Engram sends text + context to OpenAI GPT-4o
3. GPT-4o returns: `{ bucket, suggested_project?, suggested_area?, suggested_tags?, reasoning }`
4. Note is created with AI recommendation
5. User can accept or override the classification

### Prompt template

```
You are an assistant that classifies notes using the PARA method:
- Projects: active work with a deadline or outcome
- Areas: ongoing responsibilities (no end date)
- Resources: reference material worth keeping
- Archives: dormant but worth preserving
- Inbox: needs processing

Classify this note:
---
{raw_text}
---

Respond in JSON:
{
  "bucket": "projects|areas|resources|archives|inbox",
  "suggested_project": "name or null",
  "suggested_area": "name or null",
  "suggested_tags": ["tag1", "tag2"],
  "reasoning": "why this classification"
}
```

---

## 7. Hermes Integration

Hermes (the AI agent) will interact with Engram via the REST API.

**Capabilities:**
- "Add a note about X" → POST /api/v1/notes
- "What notes do I have about X?" → GET /api/v1/notes/search?q=X
- "Show me my inbox" → GET /api/v1/notes?bucket=inbox
- "Create a project for X" → POST /api/v1/projects
- "What's on my task list?" → GET /api/v1/tasks
- "Add a task to project X" → POST /api/v1/tasks

Hermes will be configured to use Engram as a skill/tool.

---

## 8. MVP Scope (MoSCoW)

### Must have
- [ ] Flask app with SQLite database
- [ ] Note CRUD with bucket classification
- [ ] Project and Area entities
- [ ] Tag system (M2M with notes)
- [ ] Full-text search (FTS5)
- [ ] Web UI list views for all entities
- [ ] REST API for all entities
- [ ] OpenAI classification endpoint
- [ ] Basic search UI

### Should have
- [ ] Task management (CRUD, status, priority, due date)
- [ ] People database
- [ ] Weekly summary generation
- [ ] Dashboard with stats

### Could have
- [ ] Semantic/similarity search (embeddings)
- [ ] Mobile-friendly UI
- [ ] Email capture (future)
- [ ] Voice input (future)

### Won't have (MVP)
- [ ] Multi-user / auth (single user)
- [ ] Real-time sync
- [ ] Mobile app
- [ ] Collaboration features

---

## 9. Error Handling

| Scenario | Response |
|---|---|
| DB write fails | 500 + logged, retry once |
| OpenAI timeout | 504 + note saved as inbox (unclassified) |
| OpenAI rate limit | 429 + exponential backoff (1s, 2s, 4s, 8s) |
| Invalid input | 400 + validation errors |
| Not found | 404 + entity type |

All errors logged to `engram.log`.

---

## 10. File Structure

```
engram/
├── app.py                  # Flask app factory
├── config.py               # Configuration
├── models.py               # SQLAlchemy models
├── extensions.py           # Flask extensions (db, etc.)
├── services/
│   ├── __init__.py
│   ├── classifier.py       # OpenAI classification
│   ├── search.py           # FTS5 search
│   └── summarizer.py       # Weekly summaries
├── api/
│   ├── __init__.py
│   ├── notes.py
│   ├── projects.py
│   ├── areas.py
│   ├── tags.py
│   ├── people.py
│   ├── tasks.py
│   └── summaries.py
├── templates/              # Jinja2 HTML
│   ├── base.html
│   ├── index.html          # Dashboard
│   ├── notes/
│   ├── projects/
│   ├── areas/
│   ├── tags/
│   ├── people/
│   ├── tasks/
│   └── review/
├── static/
│   ├── style.css
│   └── app.js
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_api_notes.py
│   ├── test_api_projects.py
│   ├── test_classifier.py
│   └── test_search.py
├── engram.db               # SQLite (gitignored)
├── requirements.txt
├── .env.example
├── SPEC.md
└── README.md
```

---

## 11. Setup Steps

1. `git clone https://github.com/1digitalD/engram`
2. `cd engram`
3. `python3.11 -m venv venv && source venv/bin/activate`
4. `pip install -r requirements.txt`
5. `cp .env.example .env` — add OpenAI API key
6. `flask init-db` — create tables
7. `flask run` — start dev server on :5000

---

## 12. Out of Scope (Future)

- Cloud deployment (HuggingFace Spaces, Railway, etc.)
- Mobile app (SwiftUI or React Native)
- Email ingestion
- Voice-to-text
- Browser extension
- Collaboration
- End-to-end encryption
