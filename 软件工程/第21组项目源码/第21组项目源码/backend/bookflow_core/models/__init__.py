from __future__ import annotations

"""ORM model exports backed by the explicit BookFlow database mapping.

The application imports models from this package.  The physical schema is now
defined in ``bookflow_core.db.models`` using SQLAlchemy Declarative models; no
runtime automap reflection is used here.
"""

from bookflow_core.db.models import *  # noqa: F401,F403

