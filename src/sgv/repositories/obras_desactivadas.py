__all__ = [
    "ObrasDesactivadasRepositoryDependency",
    "ObrasDesactivadasRepository",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ObrasDesactivadasDocument


class ObrasDesactivadasRepository(BaseRepository[ObrasDesactivadasDocument]):
    collection_name = "sgv_obras_desactivadas"
    model = ObrasDesactivadasDocument


ObrasDesactivadasRepositoryDependency = Annotated[
    ObrasDesactivadasRepository, Depends()
]
