__all__ = ["Rcg01UejpRepositoryDependency", "Rcg01UejpRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rcg01UejpDocument


class Rcg01UejpRepository(BaseRepository[Rcg01UejpDocument]):
    collection_name = "siif_rcg01_uejp"
    model = Rcg01UejpDocument


Rcg01UejpRepositoryDependency = Annotated[Rcg01UejpRepository, Depends()]
