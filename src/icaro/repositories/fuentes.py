__all__ = ["FuentesRepositoryDependency", "FuentesRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import FuentesDocument


class FuentesRepository(BaseRepository[FuentesDocument]):
    collection_name = "icaro_fuentes"
    model = FuentesDocument


FuentesRepositoryDependency = Annotated[FuentesRepository, Depends()]
