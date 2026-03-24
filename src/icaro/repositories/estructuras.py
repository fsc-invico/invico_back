__all__ = ["EstructurasRepositoryDependency", "EstructurasRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import EstructurasDocument


class EstructurasRepository(BaseRepository[EstructurasDocument]):
    collection_name = "icaro_estructuras"
    model = EstructurasDocument


EstructurasRepositoryDependency = Annotated[EstructurasRepository, Depends()]
