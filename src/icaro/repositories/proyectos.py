__all__ = ["ProyectosRepositoryDependency", "ProyectosRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ProyectosDocument


class ProyectosRepository(BaseRepository[ProyectosDocument]):
    collection_name = "icaro_proyectos"
    model = ProyectosDocument


ProyectosRepositoryDependency = Annotated[ProyectosRepository, Depends()]
