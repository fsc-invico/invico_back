__all__ = ["ProveedoresRepositoryDependency", "ProveedoresRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ProveedoresDocument


class ProveedoresRepository(BaseRepository[ProveedoresDocument]):
    collection_name = "icaro_proveedores"
    model = ProveedoresDocument


ProveedoresRepositoryDependency = Annotated[ProveedoresRepository, Depends()]
