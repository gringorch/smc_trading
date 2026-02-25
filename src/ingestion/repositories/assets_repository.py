"""Assets repository."""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from db.models.assets import Asset


class AssetsRepository:
    """Read access to configured assets."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self, asset_id: int | None = None) -> list[Asset]:
        stmt: Select[tuple[Asset]] = select(Asset).where(Asset.is_active.is_(True))
        if asset_id is not None:
            stmt = stmt.where(Asset.id == asset_id)
        return list(self._session.scalars(stmt).all())
