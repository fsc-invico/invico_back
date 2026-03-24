__all__ = ["PartidasRepositoryDependency", "PartidasRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import PartidasDocument


class PartidasRepository(BaseRepository[PartidasDocument]):
    collection_name = "icaro_partidas"
    model = PartidasDocument


PartidasRepositoryDependency = Annotated[PartidasRepository, Depends()]
