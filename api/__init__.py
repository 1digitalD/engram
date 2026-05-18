from flask import Blueprint

api_v4_bp = Blueprint("api_v4", __name__, url_prefix="/api/v4")

from . import v4_entities
