from flask import Blueprint

api_v4_bp = Blueprint("api_v4", __name__, url_prefix="/api/v4")

from .v4 import capture  # noqa: F401
from .v4 import entities  # noqa: F401
from .v4 import insights  # noqa: F401
from .v4 import links  # noqa: F401
from .v4 import markers  # noqa: F401
from .v4 import recall  # noqa: F401
from .v4 import reports  # noqa: F401
from .v4 import system  # noqa: F401
from .v4 import today  # noqa: F401
from .v4 import workboard  # noqa: F401
