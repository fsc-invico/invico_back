__all__ = ["Rpa03gRepositoryDependency", "Rpa03gRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rpa03gDocument


class Rpa03gRepository(BaseRepository[Rpa03gDocument]):
    collection_name = "siif_rpa03g"
    model = Rpa03gDocument


Rpa03gRepositoryDependency = Annotated[Rpa03gRepository, Depends()]
