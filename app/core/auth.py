from __future__ import annotations

from uuid import UUID


async def get_current_user_id() -> UUID:
    """
    Dependency that returns the authenticated user's UUID.

    NOTE: This should be implemented using the project's JWT/session auth.
    """
    raise NotImplementedError("Auth wiring not yet configured")

