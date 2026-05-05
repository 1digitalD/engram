from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

from . import notes, projects, areas, tags, people, tasks, summaries, ingest, links, batch
