__all__ = ["RetencionesRepositoryDependency", "RetencionesRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import RetencionesDocument


class RetencionesRepository(BaseRepository[RetencionesDocument]):
    collection_name = "icaro_retenciones"
    model = RetencionesDocument


RetencionesRepositoryDependency = Annotated[RetencionesRepository, Depends()]
