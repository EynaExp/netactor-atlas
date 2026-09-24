"""Async key/value helpers for settings persisted in the database.

NetActor's app settings (LLM provider) historically lived in an in-memory dict
that resets on restart.  Anything that must survive a restart (the ATLAS API
key, the optional NVD API key) goes through these helpers instead, backed by
the ``settings`` table.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.models.models import Setting


async def get_setting(key: str, session: Optional[AsyncSession] = None) -> Optional[str]:
    """Return the stored value for ``key``, or None."""
    if session is not None:
        row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        return row.value if row else None
    async with async_session() as s:
        row = (await s.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        return row.value if row else None


async def set_setting(key: str, value: str, session: Optional[AsyncSession] = None) -> None:
    """Create or update ``key``."""
    async with async_session() as s:
        row = (await s.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if row:
            row.value = value
        else:
            s.add(Setting(key=key, value=value))
        await s.commit()


async def delete_setting(key: str, session: Optional[AsyncSession] = None) -> bool:
    """Delete ``key``; returns True when a row was removed."""
    async with async_session() as s:
        row = (await s.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if not row:
            return False
        await s.delete(row)
        await s.commit()
        return True
