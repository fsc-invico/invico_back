__all__ = ["Rpa03gRepositoryDependency", "Rpa03gRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import GtoRpa03gDocument


class Rpa03gRepository(BaseRepository[GtoRpa03gDocument]):
    collection_name = "siif_gto_rpa03g"
    model = GtoRpa03gDocument


Rpa03gRepositoryDependency = Annotated[Rpa03gRepository, Depends()]
