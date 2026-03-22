__all__ = ["Rfondo07tpRepositoryDependency", "Rfondo07tpRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rfondo07tpDocument


class Rfondo07tpRepository(BaseRepository[Rfondo07tpDocument]):
    collection_name = "siif_rfondo07tp"
    model = Rfondo07tpDocument


Rfondo07tpRepositoryDependency = Annotated[Rfondo07tpRepository, Depends()]
