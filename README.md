# Engram

Personal knowledge management with PARA methodology and AI-powered recall.

> An engram is a physical trace in the brain that stores a memory.

## Setup

```bash
git clone https://github.com/1digitalD/engram
cd engram
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env
flask init-db
flask run
```

Open http://localhost:5000

## Features

- **Capture** notes and auto-classify into PARA buckets via OpenAI
- **Search** full-text search across all notes
- **Projects, Areas, People, Tags** management
- **Tasks** with status, priority, and due dates
- **Weekly Review** AI-generated summaries
- **REST API** at `/api/v1/*`

## Tech Stack

- Flask + SQLAlchemy + SQLite
- OpenAI GPT-4o for classification
- Jinja2 templates + vanilla JS

## Status

MVP scaffolding complete. See [SPEC.md](SPEC.md) for full specification.
