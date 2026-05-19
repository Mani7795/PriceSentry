"""DEPRECATED — moved to app.api.deps + per-domain services.

Kept as a shim so the old Phase 1 imports don't break. Delete after Phase 2.2.
"""
from app.api.deps import get_current_user, require_admin  # noqa: F401
from app.db.session import get_db  # noqa: F401
