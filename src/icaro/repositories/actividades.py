__all__ = ["ActividadesRepositoryDependency", "ActividadesRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ActividadesDocument


class ActividadesRepository(BaseRepository[ActividadesDocument]):
    collection_name = "icaro_actividades"
    model = ActividadesDocument


ActividadesRepositoryDependency = Annotated[ActividadesRepository, Depends()]
