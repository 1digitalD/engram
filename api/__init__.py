from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
api_v2_bp = Blueprint("api_v2", __name__, url_prefix="/api/v2")

from . import (
    moc,
    metrics,
    review,
    notes,
    projects,
    areas,
    tags,
    people,
    tasks,
    summaries,
    summarize,
    jobs,
    ingest,
    links,
    proposals,
    batch,
    daily,
    resources,
    ai_selection,
    feedback,
    search,
)
