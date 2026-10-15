__all__ = [
    "ObrasRecuperadasRepositoryDependency",
    "ObrasRecuperadasRepository",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ObrasRecuperadasDocument


class ObrasRecuperadasRepository(BaseRepository[ObrasRecuperadasDocument]):
    collection_name = "sgv_obras_recuperadas"
    model = ObrasRecuperadasDocument


ObrasRecuperadasRepositoryDependency = Annotated[ObrasRecuperadasRepository, Depends()]
