from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

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
    search,
)
