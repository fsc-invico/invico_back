__all__ = ["CargaRepositoryDependency", "CargaRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import CargaDocument


class CargaRepository(BaseRepository[CargaDocument]):
    collection_name = "icaro_carga"
    model = CargaDocument


CargaRepositoryDependency = Annotated[CargaRepository, Depends()]
