"""Engram v4 API blueprint assembly.

Importing the submodules registers their route handlers on the shared
``api_v4_bp`` blueprint defined in ``api``.
"""

from api import api_v4_bp

from . import capture
from . import entities
from . import insights
from . import links
from . import markers
from . import recall
from . import reports
from . import system
from . import today
from . import workboard
